"""The special-event sheet parser (Plan 17 Task 1)."""

from datetime import date

import pytest

from sunday_clays.ingest import parse_upload
from sunday_clays.ingest.special import (
    BAD_TARGETS,
    LABEL_TOO_LONG,
    MISSING_DATE,
    MISSING_LABEL,
    NO_ROWS,
    NO_STATIONS,
    TOO_MANY_STATIONS,
    parse_special,
)
from sunday_clays.ingest.types import FileKind, ParseError, Severity, SpecialParse
from sunday_clays.ingest.workbook import detect_kind

from .builders import loaded_workbook, workbook_bytes
from .builders_scores import SUNDAY, scores_sheets
from .builders_special import DEVLIN, HADLEY, LABEL, SPECIAL_SUNDAY, special_sheet

SHEET = "Special Event"


def parse(rows: list[list[object]]) -> SpecialParse:
    return parse_special(loaded_workbook({SHEET: rows}))


def test_parses_the_label_date_layout_and_rows() -> None:
    parsed = parse(special_sheet())

    assert parsed.label == LABEL
    assert parsed.event_date == SPECIAL_SUNDAY
    assert [e.label for e in parsed.layout] == [str(n) for n in range(1, 11)]
    assert [e.station_no for e in parsed.layout] == list(range(1, 11))
    assert {e.target_count for e in parsed.layout} == {6}
    assert parsed.target_total == 60
    assert [(r.row_number, r.raw_name, r.total) for r in parsed.rows] == [
        (5, "Hadley, Ike", 55),
        (6, "Devlin, Sid", 48),
    ]
    assert parsed.rows[0].hits[:2] == (("1", 6), ("2", 5))
    assert parsed.findings == ()
    assert parsed.kind is FileKind.SPECIAL


def test_detects_the_special_sheet_ignoring_case_and_spacing() -> None:
    assert detect_kind(loaded_workbook({" special   EVENT": special_sheet()})) is FileKind.SPECIAL


def test_a_scores_sheet_still_wins_over_a_special_sheet() -> None:
    both = loaded_workbook({**scores_sheets(), SHEET: special_sheet()})
    assert detect_kind(both) is FileKind.SCORES


def test_lettered_stations_keep_their_label_and_sort_number() -> None:
    rows = special_sheet(
        [["Hadley, Ike", 5, 6, 4, 3]], stations=(1, 2, "7a", 8), targets=(6, 6, 6, 6)
    )
    parsed = parse(rows)

    assert [(e.label, e.station_no) for e in parsed.layout] == [
        ("1", 1),
        ("2", 2),
        ("7A", 7),
        ("8", 8),
    ]
    assert parsed.target_total == 24
    assert parsed.rows[0].hits[2] == ("7A", 4)


def test_a_wrong_total_is_reported_and_the_station_sum_is_used() -> None:
    parsed = parse(special_sheet([[*HADLEY, 50], DEVLIN]))

    assert [r.total for r in parsed.rows] == [55, 48]
    (finding,) = parsed.findings
    assert (finding.code, finding.severity, finding.row, finding.name) == (
        "special_total_mismatch",
        Severity.WARNING,
        5,
        "Hadley, Ike",
    )
    assert finding.message == "The total column says 50 but the stations add up to 55; 55 is used"
    assert (finding.sheet, finding.event_date) == (SHEET, SPECIAL_SUNDAY)


def test_a_blank_total_or_no_total_column_is_not_reported() -> None:
    assert parse(special_sheet([[*HADLEY, None]])).findings == ()
    no_total = parse(special_sheet([HADLEY], total=False))
    assert no_total.findings == ()
    assert no_total.rows[0].total == 55


@pytest.mark.parametrize(
    ("value", "shown"),
    [(7, "7"), (-1, "-1"), (None, "nothing"), ("x", "x"), (4.5, "4.5")],
)
def test_a_hit_that_is_not_a_count_up_to_the_targets_drops_the_row(
    value: object, shown: str
) -> None:
    bad = ["Devlin, Sid", 5, 5, value, 5, 5, 4, 5, 5, 5, 5, 48]
    parsed = parse(special_sheet([HADLEY, bad]))

    assert [r.raw_name for r in parsed.rows] == ["Hadley, Ike"]
    (finding,) = parsed.findings
    assert (finding.code, finding.severity, finding.row, finding.name) == (
        "special_hits_invalid",
        Severity.ERROR,
        6,
        "Devlin, Sid",
    )
    assert finding.message == (
        f"Station 3 has {shown}, not a hit count from 0 to 6; the row is left out"
    )


def test_hits_without_a_name_are_reported_and_blank_rows_are_skipped() -> None:
    parsed = parse(special_sheet([HADLEY, [], [None, 5, 5], DEVLIN]))

    assert [r.raw_name for r in parsed.rows] == ["Hadley, Ike", "Devlin, Sid"]
    (finding,) = parsed.findings
    assert (finding.code, finding.severity, finding.row) == (
        "special_row_without_name",
        Severity.WARNING,
        7,
    )
    assert finding.message == "This row has hits but no name; it is left out"


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (special_sheet(label=None), MISSING_LABEL),
        (special_sheet(label="   "), MISSING_LABEL),
        (special_sheet(label="x" * 61), LABEL_TOO_LONG),
        (special_sheet(event_date=None), MISSING_DATE),
        (special_sheet(event_date="soon"), MISSING_DATE),
        (special_sheet(stations=(), targets=()), NO_STATIONS),
        (
            special_sheet([HADLEY], stations=("Stn", 2), targets=(6, 6)),
            "Row 3 has 'Stn' where a station number belongs",
        ),
        (
            special_sheet([HADLEY], stations=(1, 1), targets=(6, 6)),
            "Station 1 appears twice in row 3",
        ),
        (special_sheet([HADLEY], stations=(1, 2), targets=(6, 0)), BAD_TARGETS),
        (special_sheet([HADLEY], stations=(1, 2), targets=(6, None)), BAD_TARGETS),
        (special_sheet(stations=tuple(range(1, 32)), targets=(6,) * 31), TOO_MANY_STATIONS),
        (special_sheet([]), NO_ROWS),
    ],
    ids=[
        "no-label",
        "blank-label",
        "long-label",
        "no-date",
        "text-date",
        "no-stations",
        "not-a-station",
        "repeated-station",
        "zero-targets",
        "blank-targets",
        "31-stations",
        "no-rows",
    ],
)
def test_an_unusable_sheet_raises_a_plain_message(rows: list[list[object]], message: str) -> None:
    with pytest.raises(ParseError) as excinfo:
        parse(rows)
    assert str(excinfo.value) == message


def test_a_label_of_sixty_characters_and_thirty_stations_are_fine() -> None:
    thirty = tuple(range(1, 31))
    rows = special_sheet(
        [["Hadley, Ike", *([5] * 30)]], label="x" * 60, stations=thirty, targets=(6,) * 30
    )
    parsed = parse(rows)
    assert len(parsed.label) == 60
    assert len(parsed.layout) == 30
    assert parsed.rows[0].total == 150


def test_when_every_row_is_unreadable_the_message_names_the_first_problem() -> None:
    bad = ["Devlin, Sid", 9, 5, 4, 5, 5, 4, 5, 5, 5, 5]
    with pytest.raises(ParseError) as excinfo:
        parse(special_sheet([bad]))
    assert str(excinfo.value) == (
        f"{NO_ROWS}: Station 1 has 9, not a hit count from 0 to 6; the row is left out (row 5)"
    )


def test_a_missing_sheet_is_a_parse_error() -> None:
    with pytest.raises(ParseError, match='no "Special Event" sheet'):
        parse_special(loaded_workbook({"Other": [["x"]]}))


def test_parse_upload_dispatches_and_validates_a_special_workbook() -> None:
    monday = date(2026, 9, 21)
    parsed = parse_upload(
        workbook_bytes({SHEET: special_sheet([HADLEY, HADLEY], event_date=monday)})
    )

    assert isinstance(parsed, SpecialParse)
    assert [(f.code, f.severity, f.row) for f in parsed.findings] == [
        ("non_sunday_date", Severity.WARNING, None),
        ("name_repeated_in_sheet", Severity.WARNING, 5),
    ]
    assert parsed.findings[0].message == "2026-09-21 is a Monday, not a Sunday"
    assert parsed.findings[0].sheet == SHEET
    assert parsed.findings[1].message == "This name is on 2 rows of the sheet"
    assert len(parsed.rows) == 2  # kept: warnings never drop a row


def test_a_sunday_special_sheet_validates_clean() -> None:
    parsed = parse_upload(workbook_bytes({SHEET: special_sheet(event_date=SUNDAY)}))
    assert isinstance(parsed, SpecialParse)
    assert parsed.findings == ()
