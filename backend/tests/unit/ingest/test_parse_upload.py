import io
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import date

import openpyxl
import pytest

from sunday_clays.ingest import parse_upload
from sunday_clays.ingest.names import identity_key, name_key, similar_name_keys
from sunday_clays.ingest.types import (
    FileKind,
    ParseError,
    ScoresParse,
    Severity,
    StationsParse,
)

from .builders import SheetRows, workbook_bytes
from .builders_scores import NEXT_SUNDAY, SUNDAY, scores_sheets
from .builders_stations import DEVLIN, HADLEY, station_sheet

MONDAY = date(2026, 9, 14)
ROW = ["Hadley, Ike", 34, SUNDAY, "Member", None]
POSSIBLE_DUPLICATES = {
    ("beatrice@2025-02-23", "mortlock beatrice"),
    ("bergstrom desmond", "desmond@2025-02-23"),
    ("burkhalter elias", "elias@2025-02-23"),
    ("burkhalter june", "june@2025-02-23"),
    ("cadogan desmond", "desmond@2025-02-23"),
    ("casterline desmond", "desmond@2025-02-23"),
    ("desmond@2025-02-23", "hagerty desmond"),
    ("desmond@2025-02-23", "hargrove desmond"),
    ("fairbanks sterling", "farbanks sterling"),
    ("fitzhugh thurman", "thurman@2025-02-23"),
    ("fitzhugh weston", "weston@2025-02-23"),
    ("grover@2025-02-23", "hickox grover"),
    ("hagerty judith", "judith@2025-02-23"),
    ("hammond bennett", "hamond bennett"),
    ("kinnear landon", "landon@2025-02-23"),
    ("kinnear zelda", "zelda@2025-02-23"),
    ("ledford roland", "ledford rolland"),
    ("lennox stan", "lennox stanley"),
    ("lindenmeb darrel", "lindenmeyer darrell"),
    ("lindenmeb yancy", "lindenmeyer yancy"),
    ("mccready tate", "tate@2025-02-23"),
    ("pierpont tate", "tate@2025-02-23"),
    ("preutt clay", "pruett clay"),
    ("raymond@2025-02-23", "ridgway raymond"),
    ("tarleton wendell", "tarleton wendell w"),
}


@pytest.fixture(scope="module")
def scores_upload(scores_file_bytes: bytes) -> ScoresParse:
    parsed = parse_upload(scores_file_bytes)
    assert isinstance(parsed, ScoresParse)
    return parsed


def test_scores_fixture_through_parse_upload(scores_upload: ScoresParse) -> None:
    codes = [f.code for f in scores_upload.findings]

    assert scores_upload.kind is FileKind.SCORES
    assert len(scores_upload.score_rows) == 7480
    assert len(scores_upload.attendance_rows) == 360
    assert Counter(codes) == {
        "first_name_only": 17,
        "gauge_class_corrected": 1,
        "non_sunday_date": 2,
        "duplicate_identical_rows": 5,
        "attendance_without_scores": 49,
        "head_count_mismatch": 29,
    }
    # parser findings first, then the validate_scores findings
    assert set(codes[:18]) == {"first_name_only", "gauge_class_corrected"}


def test_stations_fixture_through_parse_upload(stations_file_bytes: bytes) -> None:
    parsed = parse_upload(stations_file_bytes)

    assert isinstance(parsed, StationsParse)
    assert [sheet.event_date for sheet in parsed.sheets] == [
        date(2026, 9, 6),
        date(2026, 9, 13),
    ]
    assert parsed.findings == ()


def test_fixture_possible_duplicates_exact(scores_upload: ScoresParse) -> None:
    dates: dict[str, set[date]] = defaultdict(set)
    for row in scores_upload.score_rows:
        dates[identity_key(name_key(row.raw_name), row.event_date)].add(row.event_date)

    pairs = {
        tuple(sorted((key, other)))
        for key, key_dates in dates.items()
        for other in similar_name_keys(key, key_dates, dates)
    }

    assert pairs == POSSIBLE_DUPLICATES
    assert ("stroud jasper", "skelton jasper") not in pairs
    assert ("pinnock dudley", "pinnock jed") not in pairs


def test_attendance_date_formulas_evaluated_through_parse_upload(
    scores_file_bytes: bytes, scores_upload: ScoresParse
) -> None:
    workbook = openpyxl.load_workbook(io.BytesIO(scores_file_bytes))
    buffer = io.BytesIO()
    workbook.save(buffer)

    stripped = parse_upload(buffer.getvalue())

    assert isinstance(stripped, ScoresParse)
    assert [r.event_date for r in stripped.attendance_rows] == [
        r.event_date for r in scores_upload.attendance_rows
    ]
    assert Counter(f.code for f in stripped.findings)["date_formula_evaluated"] == 35


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (
            b"PK\x03\x04 not really a zip",
            "This file could not be read as an Excel workbook",
        ),
        (
            workbook_bytes({"Name List (2)": [["Name"], ["Hadley, Ike"]]}),
            "This doesn't look like a Sunday Clays scores or station workbook",
        ),
        (
            workbook_bytes({"ALL SCORE DETAIL": [["Name"]]}),
            "The 'ALL SCORE DETAIL' sheet has no header row with the columns "
            "Name, Score Shot, Event, Status, Class",
        ),
    ],
    ids=["not-a-zip", "unrelated-workbook", "scores-without-header"],
)
def test_unusable_upload_raises_parse_error(data: bytes, message: str) -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_upload(data)

    assert str(excinfo.value) == message


def test_unexpected_failure_is_wrapped_without_its_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: object) -> ScoresParse:
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("sunday_clays.ingest.parse_scores", explode)

    with pytest.raises(ParseError) as excinfo:
        parse_upload(workbook_bytes(scores_sheets([ROW])))

    assert str(excinfo.value) == "This workbook could not be processed"
    assert isinstance(excinfo.value.__cause__, RuntimeError)


FINDING_CASES: list[tuple[str, Severity, Mapping[str, SheetRows]]] = [
    # parse_scores
    (
        "formula_without_cached_value",
        Severity.ERROR,
        scores_sheets(attendance_rows=[["=TODAY()", 20]]),
    ),
    (
        # an uncached formula in Status or Class keeps the row (field left blank)
        "formula_without_cached_value",
        Severity.WARNING,
        scores_sheets([["Hadley, Ike", 34, SUNDAY, '="Member"', None]]),
    ),
    (
        "date_formula_evaluated",
        Severity.INFO,
        scores_sheets(attendance_rows=[[SUNDAY, 20], ["=A2+7", 21]]),
    ),
    (
        "score_missing",
        Severity.ERROR,
        scores_sheets([["Hadley, Ike", None, SUNDAY, "Member", None]]),
    ),
    (
        "score_out_of_range",
        Severity.ERROR,
        scores_sheets([["Hadley, Ike", 51, SUNDAY, "Member", None]]),
    ),
    (
        "unparseable_date",
        Severity.ERROR,
        scores_sheets([["Hadley, Ike", 34, "Sept 13", "Member", None]]),
    ),
    (
        "name_missing",
        Severity.ERROR,
        scores_sheets([[None, 34, SUNDAY, "Member", None]]),
    ),
    (
        "unknown_status",
        Severity.WARNING,
        scores_sheets([["Hadley, Ike", 34, SUNDAY, "Visitor", None]]),
    ),
    (
        "gauge_class_corrected",
        Severity.WARNING,
        scores_sheets([["Hadley, Ike", 34, SUNDAY, "Member", "29 Gauge"]]),
    ),
    (
        "unknown_gauge_class",
        Severity.WARNING,
        scores_sheets([["Hadley, Ike", 34, SUNDAY, "Member", "16 Gauge"]]),
    ),
    (
        "first_name_only",
        Severity.INFO,
        scores_sheets([["Desmond", 30, SUNDAY, "Guest", None]]),
    ),
    (
        "head_count_invalid",
        Severity.ERROR,
        scores_sheets(attendance_rows=[[SUNDAY, "lots"]]),
    ),
    # validate_scores
    (
        "non_sunday_date",
        Severity.WARNING,
        scores_sheets([["Hadley, Ike", 34, MONDAY, "Member", None]]),
    ),
    (
        "three_plus_rounds",
        Severity.WARNING,
        scores_sheets(
            [
                ROW,
                ["Hadley, Ike", 30, SUNDAY, "Member", None],
                ["Hadley, Ike", 28, SUNDAY, "Member", None],
            ]
        ),
    ),
    ("duplicate_identical_rows", Severity.INFO, scores_sheets([ROW, ROW])),
    (
        "attendance_without_scores",
        Severity.INFO,
        scores_sheets([ROW], [[SUNDAY, 1], [NEXT_SUNDAY, 20]]),
    ),
    ("head_count_mismatch", Severity.INFO, scores_sheets([ROW], [[SUNDAY, 5]])),
    # parse_stations
    (
        "sheet_name_date_mismatch",
        Severity.WARNING,
        {"9 20 26": station_sheet(SUNDAY, [HADLEY])},
    ),
    (
        "sheet_date_from_name",
        Severity.WARNING,
        {"9 13 26": station_sheet("no date", [HADLEY])},
    ),
    ("sheet_date_missing", Severity.ERROR, {"Week 3": station_sheet(None, [HADLEY])}),
    (
        "station_layout_missing",
        Severity.ERROR,
        {"9 13 26": [["Event Date"], [SUNDAY], ["Name"], HADLEY]},
    ),
    (
        "station_row_missing_name",
        Severity.WARNING,
        {"9 13 26": station_sheet(SUNDAY, [HADLEY, [None, 3, 4, 6, 5, 7, 4, 7]])},
    ),
    (
        "station_row_blank",
        Severity.INFO,
        {"9 13 26": station_sheet(SUNDAY, [HADLEY, ["Devlin, Sid"]])},
    ),
    (
        "hits_missing",
        Severity.ERROR,
        {"9 13 26": station_sheet(SUNDAY, [HADLEY, ["Devlin, Sid", 2, 4]])},
    ),
    (
        "hits_out_of_range",
        Severity.ERROR,
        {"9 13 26": station_sheet(SUNDAY, [HADLEY, ["Devlin, Sid", 9, 4, 6, 5, 2, 0, 6]])},
    ),
    ("empty_station_sheet", Severity.WARNING, {"9 13 26": station_sheet(SUNDAY)}),
    (
        "duplicate_sheet_date",
        Severity.ERROR,
        {
            "Sheet1": station_sheet(SUNDAY, [HADLEY]),
            "Sheet2": station_sheet(SUNDAY, [DEVLIN]),
        },
    ),
    (
        "first_name_only",
        Severity.INFO,
        {"9 13 26": station_sheet(SUNDAY, [["Desmond", 3, 4, 6, 5, 7, 4, 7]])},
    ),
    # validate_stations
    ("non_sunday_date", Severity.WARNING, {"9 14 26": station_sheet(MONDAY, [HADLEY])}),
    (
        "layout_total_not_50",
        Severity.WARNING,
        {"9 13 26": station_sheet(SUNDAY, [HADLEY], targets=(7, 7, 7, 7, 7, 7, 7))},
    ),
    (
        "name_repeated_in_sheet",
        Severity.WARNING,
        {"9 13 26": station_sheet(SUNDAY, [HADLEY, HADLEY])},
    ),
]


@pytest.mark.parametrize(
    ("code", "severity", "sheets"),
    FINDING_CASES,
    ids=[
        # the severity is in the id because one code can have two severities
        f"{code}-{severity}-{'stations' if 'ALL SCORE DETAIL' not in sheets else 'scores'}"
        for code, severity, sheets in FINDING_CASES
    ],
)
def test_every_finding_code_reaches_parse_upload(
    code: str, severity: Severity, sheets: Mapping[str, SheetRows]
) -> None:
    parsed = parse_upload(workbook_bytes(sheets))

    assert (code, severity) in {(f.code, f.severity) for f in parsed.findings}
