from collections import Counter
from datetime import date

import pytest

from sunday_clays.ingest.scores import parse_scores
from sunday_clays.ingest.stations import parse_stations
from sunday_clays.ingest.types import (
    AttendanceRow,
    ScoreRow,
    ScoresParse,
    Severity,
    StationHitsRow,
    StationLayoutEntry,
    StationSheet,
    StationsParse,
)
from sunday_clays.ingest.validate import validate_scores, validate_stations
from sunday_clays.ingest.workbook import LoadedWorkbook

SUNDAY = date(2026, 9, 13)
MONDAY = date(2026, 9, 14)
FRIDAY = date(2026, 9, 18)
LAYOUT_50 = tuple(
    StationLayoutEntry(no, target)
    for no, target in zip(range(4, 11), (7, 7, 7, 7, 7, 7, 8), strict=True)
)


def _row(
    row_number: int,
    name: str,
    score: int,
    event_date: date = SUNDAY,
    status: str | None = "member",
) -> ScoreRow:
    return ScoreRow(row_number, name, score, event_date, status, None)


def _scores(rows: list[ScoreRow], attendance: list[AttendanceRow] | None = None) -> ScoresParse:
    return ScoresParse(tuple(rows), tuple(attendance or ()), ())


def _sheet(
    event_date: date = SUNDAY,
    names: tuple[str, ...] = ("Hadley, Ike",),
    layout: tuple[StationLayoutEntry, ...] = LAYOUT_50,
) -> StationSheet:
    rows = tuple(
        StationHitsRow(10 + i, name, tuple((e.station_no, 5) for e in layout))
        for i, name in enumerate(names)
    )
    title = f"{event_date.month} {event_date.day} {event_date:%y}"
    return StationSheet(title, event_date, layout, rows)


def test_non_sunday_dates_warn_once_per_date() -> None:
    parse = _scores(
        [_row(2, "Hadley, Ike", 34, MONDAY), _row(3, "Devlin, Sid", 25, MONDAY)],
        [AttendanceRow(2, MONDAY, 2), AttendanceRow(3, FRIDAY, 9)],
    )

    findings = [f for f in validate_scores(parse) if f.code == "non_sunday_date"]

    assert [(f.event_date, f.severity) for f in findings] == [
        (MONDAY, Severity.WARNING),
        (FRIDAY, Severity.WARNING),
    ]
    assert findings[0].message == "2026-09-14 is a Monday, not a Sunday"


def test_three_rounds_for_one_shooter_key_in_a_day_warn() -> None:
    parse = _scores(
        [
            _row(2, "Hadley, Ike", 34),
            _row(3, "Hadley Ike", 30),
            _row(4, "HADLEY, IKE", 28),
            _row(5, "Devlin, Sid", 25),
            _row(6, "Devlin, Sid", 24),
        ]
    )

    findings = validate_scores(parse)

    assert [(f.code, f.severity, f.row, f.name) for f in findings] == [
        ("three_plus_rounds", Severity.WARNING, 2, "Hadley, Ike")
    ]


def test_identical_rows_are_reported_as_info() -> None:
    parse = _scores(
        [
            _row(2, "Nickerson, Neal", 40),
            _row(3, "Nickerson, Neal", 40),
            _row(4, "Devlin, Sid", 25),
            _row(5, "Devlin, Sid", 25, status="guest"),
        ]
    )

    findings = validate_scores(parse)

    assert [(f.code, f.severity, f.row) for f in findings] == [
        ("duplicate_identical_rows", Severity.INFO, 2)
    ]
    assert findings[0].message == "Rows 2, 3 are identical; each is kept as a round"


def test_attendance_is_compared_with_score_rows() -> None:
    sept_20 = date(2026, 9, 20)
    parse = _scores(
        [
            _row(2, "Hadley, Ike", 34),
            _row(3, "Devlin, Sid", 25),
            _row(4, "Nordquist, Sherman", 42, sept_20),
        ],
        [
            AttendanceRow(2, date(2026, 9, 6), 24),
            AttendanceRow(3, SUNDAY, 2),
            AttendanceRow(4, sept_20, 3),
        ],
    )

    findings = validate_scores(parse)

    assert [(f.code, f.severity, f.sheet, f.row) for f in findings] == [
        ("attendance_without_scores", Severity.INFO, "Attendance History", 2),
        ("head_count_mismatch", Severity.INFO, "Attendance History", 4),
    ]
    assert findings[1].message == "Head count 3 but 1 score row"


def test_zero_head_count_without_scores_is_consistent() -> None:
    parse = _scores(
        [],
        [AttendanceRow(2, date(2026, 9, 6), 0), AttendanceRow(3, SUNDAY, 1)],
    )

    findings = validate_scores(parse)

    assert [(f.code, f.row) for f in findings] == [("attendance_without_scores", 3)]


def test_validate_scores_orders_findings_by_group_then_attendance_row() -> None:
    # Sheet order is deliberately the reverse of the finding order (D15).
    parse = _scores(
        [
            _row(2, "Devlin, Sid", 25),
            _row(3, "Devlin, Sid", 25),
            _row(4, "Hadley, Ike", 34),
            _row(5, "Hadley, Ike", 30),
            _row(6, "Hadley, Ike", 28),
            _row(7, "Nordquist, Sherman", 42, MONDAY),
        ],
        [
            AttendanceRow(2, date(2026, 9, 6), 24),
            AttendanceRow(3, SUNDAY, 9),
            AttendanceRow(4, date(2026, 9, 20), 12),
        ],
    )

    findings = validate_scores(parse)

    assert [(f.code, f.row) for f in findings] == [
        ("non_sunday_date", None),
        ("three_plus_rounds", 4),
        ("duplicate_identical_rows", 2),
        ("attendance_without_scores", 2),
        ("head_count_mismatch", 3),
        ("attendance_without_scores", 4),
    ]
    assert findings[4].message == "Head count 9 but 5 score rows"


def test_validate_stations_orders_one_sheets_findings() -> None:
    layout_49 = (*LAYOUT_50[:-1], StationLayoutEntry(10, 7))
    sheet = _sheet(MONDAY, names=("Hadley, Ike", "hadley ike"), layout=layout_49)

    findings = validate_stations(StationsParse((sheet,), ()))

    assert [(f.code, f.sheet) for f in findings] == [
        ("non_sunday_date", "9 14 26"),
        ("layout_total_not_50", "9 14 26"),
        ("name_repeated_in_sheet", "9 14 26"),
    ]


def test_station_sheet_checks() -> None:
    layout_49 = (*LAYOUT_50[:-1], StationLayoutEntry(10, 7))
    parse = StationsParse(
        (
            _sheet(MONDAY),
            _sheet(SUNDAY, layout=layout_49),
            _sheet(date(2026, 9, 20), names=("Hadley, Ike", "Devlin, Sid", "hadley ike")),
        ),
        (),
    )

    findings = validate_stations(parse)

    assert [(f.code, f.severity, f.event_date, f.row) for f in findings] == [
        ("non_sunday_date", Severity.WARNING, MONDAY, None),
        ("layout_total_not_50", Severity.WARNING, SUNDAY, None),
        ("name_repeated_in_sheet", Severity.WARNING, date(2026, 9, 20), 10),
    ]
    assert findings[1].message == "Target counts add up to 49, not 50"
    assert findings[2].message == "This name is on 2 rows of the sheet"


@pytest.fixture(scope="module")
def fixture_scores(scores_lw: LoadedWorkbook) -> ScoresParse:
    return parse_scores(scores_lw)


def test_fixture_validate_scores_findings(fixture_scores: ScoresParse) -> None:
    findings = validate_scores(fixture_scores)
    by_code = Counter(f.code for f in findings)
    mismatch_dates = {f.event_date for f in findings if f.code == "head_count_mismatch"}

    assert by_code == {
        "non_sunday_date": 2,
        "duplicate_identical_rows": 5,
        "attendance_without_scores": 49,
        "head_count_mismatch": 29,
    }
    assert {f.event_date for f in findings if f.code == "non_sunday_date"} == {
        date(2019, 1, 14),
        date(2019, 2, 1),
    }
    assert date(2022, 3, 6) in mismatch_dates
    assert date(2026, 8, 30) not in mismatch_dates


def test_fixture_validate_stations_findings(stations_lw: LoadedWorkbook) -> None:
    assert validate_stations(parse_stations(stations_lw)) == ()
