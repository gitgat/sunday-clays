from datetime import date

import pytest

from parse import Course, Presentation, ResultRow, parse_course, parse_date, parse_results
from tests.fixtures import TYPED


def test_date_from_typed_header():
    assert parse_date(TYPED) == date(2026, 5, 31)


@pytest.mark.parametrize("text", ["no header here", "Sunday, Smarch 31, 2026"])
def test_date_missing_or_invalid(text):
    assert parse_date(text) is None


def test_results_rows_notes_gauge_and_ties():
    rows = parse_results(TYPED)
    assert [r.name for r in rows] == [
        "Testerson, Ann",
        "Fakeman, Bo",
        "Mockley, Cy",
        "Benedetto, Di",
        "Dummy, Ed",
        "O'Sample, Flo",
        "Van Der Test, Gus",
    ]
    assert rows[0] == ResultRow("Testerson, Ann", 22)
    assert rows[2] == ResultRow("Mockley, Cy", 20, None, "28 Gauge")
    assert rows[3].note == "PB"
    assert rows[4].note == "G"
    assert rows[5] == ResultRow("O'Sample, Flo", 15, "N", "20 Gauge")
    assert rows[6].note == "NG"
    assert [r.hits for r in rows] == [22, 21, 20, 20, 18, 15, 10]


def test_results_table_stops_at_average_score():
    assert "Zed, Not Aresult" not in [r.name for r in parse_results(TYPED)]


def test_results_without_table_header_scan_whole_text():
    assert parse_results("   Solo, Jo    30    1\n") == (ResultRow("Solo, Jo", 30),)


def test_course_stations_and_presentations():
    course = parse_course(TYPED)
    assert course.stations == ((2, 7), (4, 7), (7, 8))
    assert course.presentations["2"] == (
        Presentation(1, "SINGLE", "A", 1),
        Presentation(1, "SINGLE", "B", 1),
        Presentation(1, "REPORT PAIR", "D-A", 2),
        Presentation(1, "REPORT PAIR", "A-B", 2),
        Presentation(1, "TRUE PAIR", "B-A", 1),
    )
    assert course.presentations["4"][1] == Presentation(3, "REPORT PAIR", "B-C", 6)


def test_course_missing():
    assert parse_course("nothing") == Course(stations=())


VARIANT = """
                          COURSE DESIGN SHEET                      Designer Initials
                                Sunday, August 9, 2026

                Stn. Tgts Rep. Presentation              Traps
                 3    6     1   Single                    A
                            1   Report Pair              A-C      Station Target Count
                                                                          6
                 7A   8     4   Report Pair    B-C     Std-Std    2
                 5    7     3   SINGLE          A        1
                            SINGLE          C        1
                            REPORT PAIR    A-C       2
"""


def test_course_variants_design_sheet_lettered_station_optional_columns():
    course = parse_course(VARIANT)
    assert course.stations == ((3, 6), ("7A", 8), (5, 7))
    assert course.presentations["3"] == (
        Presentation(1, "SINGLE", "A", None),
        Presentation(1, "REPORT PAIR", "A-C", None),
    )
    assert course.presentations["7A"] == (Presentation(4, "REPORT PAIR", "B-C", 2),)
    assert course.presentations["5"][1:] == (
        Presentation(None, "SINGLE", "C", 1),
        Presentation(None, "REPORT PAIR", "A-C", 2),
    )
