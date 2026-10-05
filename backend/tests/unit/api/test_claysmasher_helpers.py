"""Pure helpers behind the ClaySmasher scores export; no database.

The CSV layout is ClaySmasher's Scores CSV import format for the sporting family (its
ScoreCsvFormat): '#' comment lines, then Date, Name, Tournament?, Location, Course, Gun, Gauge,
Ammo, Weather, Total Hits, Total Targets, Notes and a Hits/Targets pair per station. ClaySmasher
reads it by header name, drops rows whose first cell starts with '#' and skips any row whose Name
contains "example".
"""

import csv
import io
import zipfile
from datetime import date

import pytest

from sunday_clays.api.routes._claysmasher import (
    CLUB_LOCATION,
    STATION_COLUMNS,
    TARGETS_PER_ROUND,
    ExportRound,
    ExportStation,
    day_ordinals,
    export_files,
    header,
    render_csv,
    round_name,
    shooter_slug,
    station_orders,
    zip_files,
)
from sunday_clays.domain.round_type import RoundType

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)
SPORTING = RoundType.SPORTING
SUPER = RoundType.SUPER_SPORTING
LAYOUT = (
    ("4", 8, 6),
    ("5", 8, 7),
    ("6", 6, 5),
    ("7", 8, 6),
    ("8", 6, 5),
    ("9", 8, 7),
    ("10", 6, 5),
)
FIXED = [
    "Date",
    "Name",
    "Tournament?",
    "Location",
    "Course",
    "Gun",
    "Gauge",
    "Ammo",
    "Weather",
    "Total Hits",
    "Total Targets",
    "Notes",
]


def _stations(layout: tuple[tuple[str, int, int], ...] = LAYOUT) -> tuple[ExportStation, ...]:
    return tuple(ExportStation(label, targets, hits) for label, targets, hits in layout)


def _round(
    day: date = D1,
    score: int = 41,
    *,
    number: int = 1,
    round_type: RoundType = SPORTING,
    gauge_class: str | None = None,
    stations: tuple[ExportStation, ...] = (),
) -> ExportRound:
    return ExportRound(day, number, round_type, score, gauge_class, stations)


def _rows(text: str) -> list[list[str]]:
    """Parse as ClaySmasher does: CSV rows, minus those whose first cell starts with '#'."""
    rows = list(csv.reader(io.StringIO(text, newline="")))
    return [row for row in rows if row and not row[0].lstrip().startswith("#")]


def _records(text: str) -> list[dict[str, str]]:
    head, *body = _rows(text)
    return [dict(zip(head, row, strict=True)) for row in body]


def test_station_orders_rank_labels_in_station_order() -> None:
    assert station_orders(["10", "7A", "4", "7", "8", "4"]) == {
        "4": 1,
        "7": 2,
        "7A": 3,
        "8": 4,
        "10": 5,
    }
    assert station_orders([]) == {}


def test_day_ordinals_number_a_shooters_rounds_per_day() -> None:
    keys = [(D1, "doe jane", 1), (D1, "doe j", 1), (D1, "doe jane", 2), (D2, "doe jane", 1)]
    assert day_ordinals(keys) == {
        (D1, "doe j", 1): 1,
        (D1, "doe jane", 1): 2,
        (D1, "doe jane", 2): 3,
        (D2, "doe jane", 1): 1,
    }


def test_a_round_without_stations_counts_fifty_targets() -> None:
    assert TARGETS_PER_ROUND == 50
    assert _round().target_count == 50
    assert _round(stations=_stations()).target_count == 50
    short = _stations((("4", 8, 8), ("5", 6, 6)))
    assert _round(stations=short).target_count == 14


def test_header_is_claysmashers_sporting_layout_with_fifteen_stations_minimum() -> None:
    assert STATION_COLUMNS == 15
    pairs = [col for n in range(1, 16) for col in (f"Station {n} Hits", f"Station {n} Targets")]
    assert header(0) == FIXED + pairs
    assert header(7) == FIXED + pairs
    assert header(17)[-4:] == [
        "Station 16 Hits",
        "Station 16 Targets",
        "Station 17 Hits",
        "Station 17 Targets",
    ]


def test_round_names_never_contain_example_and_number_extra_rounds() -> None:
    assert round_name(1) == "Sunday Clays"
    assert round_name(2) == "Sunday Clays (round 2)"
    assert all("example" not in round_name(n).casefold() for n in range(1, 5))


def test_a_round_with_stations_fills_totals_and_station_pairs_in_shot_order() -> None:
    text = render_csv([_round(stations=_stations())], SPORTING, "Doe, Jane")
    (record,) = _records(text)

    assert record["Date"] == "09/06/2026"
    assert record["Name"] == "Sunday Clays"
    assert record["Tournament?"] == ""
    assert record["Location"] == CLUB_LOCATION == "Tri-County Gun Club"
    for blank in ("Course", "Gun", "Gauge", "Ammo", "Weather"):
        assert record[blank] == ""
    assert (record["Total Hits"], record["Total Targets"]) == ("41", "50")
    assert [record[f"Station {n} Hits"] for n in range(1, 8)] == ["6", "7", "5", "6", "5", "7", "5"]
    assert [record[f"Station {n} Targets"] for n in range(1, 8)] == [
        "8",
        "8",
        "6",
        "8",
        "6",
        "8",
        "6",
    ]
    assert all(record[f"Station {n} Hits"] == "" for n in range(8, 16))
    assert all(record[f"Station {n} Targets"] == "" for n in range(8, 16))


def test_a_round_without_stations_leaves_every_station_blank() -> None:
    (record,) = _records(render_csv([_round(score=38)], SPORTING, "Doe, Jane"))

    assert (record["Total Hits"], record["Total Targets"]) == ("38", "50")
    assert all(record[f"Station {n} Hits"] == "" for n in range(1, 16))
    assert all(record[f"Station {n} Targets"] == "" for n in range(1, 16))


def test_station_columns_grow_past_fifteen_when_a_round_needs_them() -> None:
    many = tuple(ExportStation(str(n), 3, 2) for n in range(1, 18))  # 17 stations, 51 targets
    text = render_csv([_round(score=34, stations=many), _round(D2)], SPORTING, "Doe, Jane")
    head, first, second = _rows(text)

    assert head == header(17)
    assert len(first) == len(second) == len(head)
    record = dict(zip(head, first, strict=True))
    assert (record["Station 17 Hits"], record["Station 17 Targets"]) == ("2", "3")
    assert record["Total Targets"] == "51"


def test_notes_carry_the_source_and_the_gauge_class_the_gauge_column_stays_blank() -> None:
    (record,) = _records(render_csv([_round(gauge_class="20 Gauge")], SPORTING, "Doe, Jane"))

    assert record["Gauge"] == ""  # ClaySmasher only accepts 12/16/20/28/410 there
    assert record["Notes"] == "Imported from Sunday Clays; class: 20 Gauge"
    (plain,) = _records(render_csv([_round()], SPORTING, "Doe, Jane"))
    assert plain["Notes"] == "Imported from Sunday Clays"


def test_commas_quotes_and_unicode_are_quoted_and_kept() -> None:
    name = 'O\u2019Brien, Zo\u00eb "Ace"'
    text = render_csv([_round(gauge_class='Sub-gauge, "28"')], SPORTING, name)

    comments = [row for row in csv.reader(io.StringIO(text, newline="")) if row[0].startswith("#")]
    assert any(name in row[0] for row in comments)
    assert all(len(row) == 1 for row in comments)  # a comment line is one cell, whatever it holds
    (record,) = _records(text)
    assert record["Notes"] == 'Imported from Sunday Clays; class: Sub-gauge, "28"'
    assert '"Imported from Sunday Clays; class: Sub-gauge, ""28"""' in text


def test_rows_come_in_date_then_day_order_and_lines_end_in_crlf() -> None:
    rounds = [_round(D2, 35, number=2), _round(D2, 41), _round(D1, 30)]
    text = render_csv(rounds, SPORTING, "Doe, Jane")

    assert [(r["Date"], r["Name"], r["Total Hits"]) for r in _records(text)] == [
        ("09/06/2026", "Sunday Clays", "30"),
        ("09/13/2026", "Sunday Clays", "41"),
        ("09/13/2026", "Sunday Clays (round 2)", "35"),
    ]
    assert text.endswith("\r\n")
    assert "\n" not in text.replace("\r\n", "")


def test_the_file_opens_with_comment_lines_that_name_the_discipline() -> None:
    sporting = render_csv([_round()], SPORTING, "Doe, Jane").splitlines()
    super_sporting = render_csv([_round(round_type=SUPER)], SUPER, "Doe, Jane").splitlines()

    assert sporting[0].startswith("# ")
    assert "Sporting Clays" in sporting[0]
    assert "Super Sport" in super_sporting[0]
    first_data = next(i for i, line in enumerate(sporting) if not line.startswith(("#", '"#')))
    assert sporting[first_data].startswith("Date,Name,Tournament?,Location,Course,")


def test_render_csv_refuses_a_round_of_another_discipline() -> None:
    with pytest.raises(ValueError, match="super_sporting"):
        render_csv([_round(round_type=SUPER)], SPORTING, "Doe, Jane")


def test_export_files_split_by_discipline_and_skip_empty_ones() -> None:
    both = export_files([_round(D1), _round(D2, 44, round_type=SUPER)], "Doe, Jane")
    assert list(both) == ["claysmasher-sporting.csv", "claysmasher-super-sporting.csv"]
    assert [r["Date"] for r in _records(both["claysmasher-sporting.csv"])] == ["09/06/2026"]
    assert [r["Total Hits"] for r in _records(both["claysmasher-super-sporting.csv"])] == ["44"]

    assert list(export_files([_round(round_type=SUPER)], "Doe, Jane")) == [
        "claysmasher-super-sporting.csv"
    ]
    assert export_files([], "Doe, Jane") == {}


def test_zip_files_holds_each_csv_as_utf8() -> None:
    files = {"claysmasher-sporting.csv": "# Zo\u00eb\r\nDate\r\n"}
    with zipfile.ZipFile(io.BytesIO(zip_files(files))) as archive:
        assert archive.namelist() == ["claysmasher-sporting.csv"]
        assert archive.read("claysmasher-sporting.csv").decode("utf-8") == "# Zo\u00eb\r\nDate\r\n"
        assert archive.testzip() is None


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Doe, Jane", "doe-jane"),
        ('O\u2019Brien, Zo\u00eb "Ace"', "obrien-zoe-ace"),
        ("  De La Roe,  Ann  ", "de-la-roe-ann"),
        ("\u5c71\u7530", "shooter-7"),
    ],
)
def test_shooter_slug_is_ascii_for_the_download_filename(name: str, slug: str) -> None:
    assert shooter_slug(name, 7) == slug
