from datetime import date, datetime

import pytest
from openpyxl import Workbook

import scores


def workbook(tmp_path, rows, *, title="ALL SCORE DETAIL", header=("Name", "Score Shot", "Event"), lead=2):
    book = Workbook()
    sheet = book.active
    sheet.title = title
    for _ in range(lead):
        sheet.append(["junk"])
    sheet.append(list(header))
    for row in rows:
        sheet.append(row)
    path = tmp_path / "scores.xlsx"
    book.save(path)
    return path


def test_rows_are_grouped_by_sunday_with_workbook_names_verbatim(tmp_path):
    path = workbook(
        tmp_path,
        [
            ["Testerson, Ann", 22, datetime(2026, 5, 31)],
            ["Fakeman, Bo", 21.0, datetime(2026, 5, 31)],
            ["Testerson, Ann", "18", date(2026, 6, 7)],
            ["Testerson, Ann", 25, datetime(2026, 5, 31)],  # a second round the same Sunday
        ],
    )
    found = scores.load_officials(path)
    assert sorted(found) == ["2026-05-31", "2026-06-07"]
    assert found["2026-05-31"] == [
        {"name": "Testerson, Ann", "hits": 22, "note": None, "gauge": None},
        {"name": "Fakeman, Bo", "hits": 21, "note": None, "gauge": None},
        {"name": "Testerson, Ann", "hits": 25, "note": None, "gauge": None},
    ]
    assert found["2026-06-07"][0]["hits"] == 18


def test_header_labels_match_ignoring_case_spacing_and_column_order(tmp_path):
    path = workbook(
        tmp_path,
        [[datetime(2026, 5, 31), "Testerson, Ann", 22, "x"]],
        title="all score  detail",
        header=("event", " NAME ", "score shot", "Status"),
    )
    assert scores.load_officials(path)["2026-05-31"][0]["name"] == "Testerson, Ann"


def test_rows_that_are_not_scores_are_left_out(tmp_path):
    path = workbook(
        tmp_path,
        [
            [None, 20, datetime(2026, 5, 31)],  # no name
            ["Ann", None, datetime(2026, 5, 31)],  # no score
            ["Bo", 51, datetime(2026, 5, 31)],  # more than 50
            ["Cy", -1, datetime(2026, 5, 31)],
            ["Di", True, datetime(2026, 5, 31)],
            ["Ed", "abc", datetime(2026, 5, 31)],
            ["Flo", 20.5, datetime(2026, 5, 31)],
            ["Gus", 20, "not a date"],
            ["Hal", 20, None],
            [None, None, None],
            ["  Ivy, Jo ", 19, datetime(2026, 5, 31)],
        ],
    )
    assert scores.load_officials(path) == {"2026-05-31": [{"name": "Ivy, Jo", "hits": 19, "note": None, "gauge": None}]}


def test_a_workbook_without_the_scores_sheet_or_header_is_an_error(tmp_path):
    with pytest.raises(scores.ScoresError, match="no 'ALL SCORE DETAIL' sheet"):
        scores.load_officials(workbook(tmp_path, [], title="Other"))
    with pytest.raises(scores.ScoresError, match="no header row"):
        scores.load_officials(workbook(tmp_path, [], header=("Name", "Score Shot")))
    with pytest.raises(scores.ScoresError, match="cannot read"):
        scores.load_officials(tmp_path / "missing.xlsx")
    (tmp_path / "bad.xlsx").write_bytes(b"not a workbook")
    with pytest.raises(scores.ScoresError, match="cannot read"):
        scores.load_officials(tmp_path / "bad.xlsx")
