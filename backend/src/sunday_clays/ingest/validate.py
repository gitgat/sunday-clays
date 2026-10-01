"""Cross-row checks over an already-filtered parse (Contract C3).

These functions only return findings; they never remove data (anything that
drops a row or a sheet happens in the parsers).
"""

from collections import Counter, defaultdict
from collections.abc import Callable, Hashable
from datetime import date

from sunday_clays.ingest.names import clean_display_name, name_key
from sunday_clays.ingest.scores import ATTENDANCE_SHEET
from sunday_clays.ingest.types import (
    AttendanceRow,
    Finding,
    ScoreRow,
    ScoresParse,
    Severity,
    SpecialParse,
    StationSheet,
    StationsParse,
)
from sunday_clays.ingest.workbook import SCORES_SHEET, SPECIAL_SHEET

LAYOUT_TOTAL = 50
_SUNDAY = 6  # date.weekday() of a Sunday


def validate_scores(p: ScoresParse) -> tuple[Finding, ...]:
    rows_per_date = Counter(row.event_date for row in p.score_rows)
    all_dates = set(rows_per_date) | {row.event_date for row in p.attendance_rows}
    return (
        *[_non_sunday(day) for day in sorted(all_dates) if day.weekday() != _SUNDAY],
        *[
            _group_finding(
                "three_plus_rounds",
                Severity.WARNING,
                f"{len(group)} rounds on one day for this shooter",
                group,
            )
            for group in _groups(p.score_rows, _shooter_day)
            if len(group) >= 3
        ],
        *[
            _group_finding(
                "duplicate_identical_rows",
                Severity.INFO,
                "Rows "
                + ", ".join(str(row.row_number) for row in group)
                + " are identical; each is kept as a round",
                group,
            )
            for group in _groups(p.score_rows, _identical)
            if len(group) >= 2
        ],
        *_attendance_findings(p.attendance_rows, rows_per_date),
    )


def validate_stations(p: StationsParse) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for sheet in p.sheets:
        findings.extend(_sheet_findings(sheet))
    return tuple(findings)


def _sheet_findings(sheet: StationSheet) -> list[Finding]:
    title = sheet.sheet_name
    findings: list[Finding] = []
    if sheet.event_date.weekday() != _SUNDAY:
        findings.append(_non_sunday(sheet.event_date, sheet=title))
    total = sum(entry.target_count for entry in sheet.layout)
    if total != LAYOUT_TOTAL:
        findings.append(
            Finding(
                "layout_total_not_50",
                Severity.WARNING,
                f"Target counts add up to {total}, not {LAYOUT_TOTAL}",
                sheet=title,
                event_date=sheet.event_date,
            )
        )
    repeats = Counter(name_key(row.raw_name) for row in sheet.rows)
    for row in sheet.rows:
        count = repeats.pop(name_key(row.raw_name), 0)
        if count >= 2:
            findings.append(
                Finding(
                    "name_repeated_in_sheet",
                    Severity.WARNING,
                    f"This name is on {count} rows of the sheet",
                    sheet=title,
                    row=row.row_number,
                    event_date=sheet.event_date,
                    name=clean_display_name(row.raw_name),
                )
            )
    return findings


def _attendance_findings(
    rows: tuple[AttendanceRow, ...], rows_per_date: Counter[date]
) -> list[Finding]:
    findings: list[Finding] = []
    for row in rows:
        scored = rows_per_date[row.event_date]
        if scored == 0 and row.head_count > 0:
            message = f"Head count {row.head_count} but no scores for this date"
            findings.append(_attendance_finding("attendance_without_scores", message, row))
        elif scored != row.head_count:
            rows_text = "1 score row" if scored == 1 else f"{scored} score rows"
            message = f"Head count {row.head_count} but {rows_text}"
            findings.append(_attendance_finding("head_count_mismatch", message, row))
    return findings


def _attendance_finding(code: str, message: str, row: AttendanceRow) -> Finding:
    return Finding(
        code,
        Severity.INFO,
        message,
        sheet=ATTENDANCE_SHEET,
        row=row.row_number,
        event_date=row.event_date,
    )


def _non_sunday(event_date: date, sheet: str | None = None) -> Finding:
    return Finding(
        "non_sunday_date",
        Severity.WARNING,
        f"{event_date.isoformat()} is a {event_date:%A}, not a Sunday",
        sheet=sheet,
        event_date=event_date,
    )


def _shooter_day(row: ScoreRow) -> Hashable:
    return (row.event_date, name_key(row.raw_name))


def _identical(row: ScoreRow) -> Hashable:
    return (
        row.event_date,
        name_key(row.raw_name),
        row.score,
        row.status,
        row.gauge_class,
    )


def _groups(
    rows: tuple[ScoreRow, ...], key: Callable[[ScoreRow], Hashable]
) -> list[list[ScoreRow]]:
    groups: dict[Hashable, list[ScoreRow]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return list(groups.values())


def _group_finding(code: str, severity: Severity, message: str, group: list[ScoreRow]) -> Finding:
    first = group[0]
    return Finding(
        code,
        severity,
        message,
        sheet=SCORES_SHEET,
        row=first.row_number,
        event_date=first.event_date,
        name=clean_display_name(first.raw_name),
    )


def validate_special(p: SpecialParse) -> tuple[Finding, ...]:
    """A special sheet's date and repeated names, as the station checks report them."""
    findings: list[Finding] = []
    if p.event_date.weekday() != _SUNDAY:
        findings.append(_non_sunday(p.event_date, sheet=SPECIAL_SHEET))
    repeats = Counter(name_key(row.raw_name) for row in p.rows)
    for row in p.rows:
        count = repeats.pop(name_key(row.raw_name), 0)
        if count >= 2:
            findings.append(
                Finding(
                    "name_repeated_in_sheet",
                    Severity.WARNING,
                    f"This name is on {count} rows of the sheet",
                    sheet=SPECIAL_SHEET,
                    row=row.row_number,
                    event_date=p.event_date,
                    name=clean_display_name(row.raw_name),
                )
            )
    return tuple(findings)
