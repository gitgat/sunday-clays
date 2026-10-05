"""GET /api/shooters/{id}/claysmasher-export over directly seeded live rows.

The body is a zip of ClaySmasher Scores CSV import files, one per discipline the shooter has
rounds in (the CSV layout itself is pinned in tests/unit/api/test_claysmasher_helpers.py).
"""

import csv
import io
import time
import zipfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from sunday_clays.station_label import label_number

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)
# Gross-regression ceiling only (an accidental N+1 or full-table scan per round).
CI_CEILING_SECONDS = 1.0
SPORTING = (("4", 8), ("5", 8), ("6", 6), ("7", 8), ("8", 6), ("9", 8), ("10", 6))
SPORTING_HITS = (6, 7, 5, 6, 5, 7, 5)  # 41
SPORTING_CSV = "claysmasher-sporting.csv"
SUPER_CSV = "claysmasher-super-sporting.csv"


def _url(shooter_id: int) -> str:
    return f"/api/shooters/{shooter_id}/claysmasher-export"


def _station_entry(
    session: Session,
    d: date,
    round_id: int | None,
    shooter_id: int,
    key: str,
    layout: Sequence[tuple[str, int]],
    hits: Sequence[int],
    entry_row: int = 1,
) -> None:
    """One station-sheet entry as rebuild writes it: the event's layout plus this entry's hits."""
    for (label, targets), value in zip(layout, hits, strict=True):
        session.execute(
            text(
                "INSERT INTO station_layouts (event_date, station_no, station_label,"
                " target_count, source_import_id) VALUES (:d, :no, :l, :t, 0)"
                " ON CONFLICT (event_date, station_label) DO NOTHING"
            ),
            {"d": d, "no": label_number(label), "l": label, "t": targets},
        )
        session.execute(
            text(
                "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id,"
                " entry_row, name_key, shooter_id, round_id, hits)"
                " VALUES (:d, :no, :l, 0, :row, :k, :s, :r, :h)"
            ),
            {
                "d": d,
                "no": label_number(label),
                "l": label,
                "row": entry_row,
                "k": key,
                "s": shooter_id,
                "r": round_id,
                "h": value,
            },
        )


def _export(client: TestClient, shooter_id: int) -> dict[str, str]:
    """File name -> CSV text from the zip the route returns."""
    response = client.get(_url(shooter_id))
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}


def _records(csv_text: str) -> list[dict[str, str]]:
    """Rows as ClaySmasher reads them: '#' lines dropped, then keyed by the header row."""
    rows = [r for r in csv.reader(io.StringIO(csv_text, newline="")) if not r[0].startswith("#")]
    head, *body = rows
    return [dict(zip(head, row, strict=True)) for row in body]


@contextmanager
def _statements(session: Session) -> Iterator[list[str]]:
    seen: list[str] = []

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        seen.append(statement)

    connection = session.connection()
    event.listen(connection, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(connection, "before_cursor_execute", record)


def test_the_download_is_a_zip_named_for_the_shooter(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    rid = seed.round(D1, jane, 41, gauge_class="12 Gauge")
    _station_entry(session, D1, rid, jane, "doe jane", SPORTING, SPORTING_HITS)
    seed.finish()

    response = viewer_client.get(_url(jane))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == (
        'attachment; filename="claysmasher-doe-jane-scores.zip"'
    )
    files = _export(viewer_client, jane)
    assert list(files) == [SPORTING_CSV]
    assert "# Shooter: Doe, Jane" in files[SPORTING_CSV]
    (record,) = _records(files[SPORTING_CSV])
    assert record["Date"] == "09/06/2026"
    assert (record["Name"], record["Location"]) == ("Sunday Clays", "Tri-County Gun Club")
    assert (record["Total Hits"], record["Total Targets"]) == ("41", "50")
    assert record["Notes"] == "Imported from Sunday Clays; class: 12 Gauge"
    assert [record[f"Station {n} Hits"] for n in range(1, 8)] == [str(h) for h in SPORTING_HITS]
    assert [record[f"Station {n} Targets"] for n in range(1, 8)] == [str(t) for _, t in SPORTING]


def test_round_without_station_data_has_blank_stations_and_fifty_targets(
    seed: Any, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 38, gauge_class=None, status=None)
    seed.finish()

    (record,) = _records(_export(viewer_client, jane)[SPORTING_CSV])

    assert (record["Total Hits"], record["Total Targets"]) == ("38", "50")
    assert record["Notes"] == "Imported from Sunday Clays"
    assert all(record[f"Station {n} Hits"] == "" for n in range(1, 16))


def test_rounds_come_in_date_then_day_order(seed: Any, viewer_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D2, jane, 41)
    seed.round(D2, jane, 35)
    seed.round(D1, jane, 30)
    seed.finish()

    records = _records(_export(viewer_client, jane)[SPORTING_CSV])

    assert [(r["Date"], r["Name"], r["Total Hits"]) for r in records] == [
        ("09/06/2026", "Sunday Clays", "30"),
        ("09/13/2026", "Sunday Clays", "41"),
        ("09/13/2026", "Sunday Clays (round 2)", "35"),
    ]


def test_each_discipline_gets_its_own_file(seed: Any, viewer_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.event(D2, round_type="super_sporting")
    seed.round(D1, jane, 41)
    seed.round(D2, jane, 44)
    seed.finish()

    files = _export(viewer_client, jane)

    assert sorted(files) == [SPORTING_CSV, SUPER_CSV]
    assert [r["Total Hits"] for r in _records(files[SPORTING_CSV])] == ["41"]
    assert [r["Date"] for r in _records(files[SUPER_CSV])] == ["09/13/2026"]
    assert "Super Sport" in files[SUPER_CSV].splitlines()[0]


def test_a_super_sporting_only_shooter_gets_only_that_file(
    seed: Any, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.event(D1, round_type="super_sporting")
    seed.round(D1, jane, 44)
    seed.finish()

    assert list(_export(viewer_client, jane)) == [SUPER_CSV]


def test_lettered_stations_come_out_in_station_order(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    rid = seed.round(D1, jane, 39, ordinal=1)
    shuffled = (("8", 8), ("7A", 6), ("4", 7), ("10", 7), ("7", 8), ("5", 7), ("6", 7))
    _station_entry(session, D1, rid, jane, "doe jane", shuffled, (6, 4, 5, 6, 7, 5, 6))
    seed.finish()

    (record,) = _records(_export(viewer_client, jane)[SPORTING_CSV])

    pairs = [(record[f"Station {n} Hits"], record[f"Station {n} Targets"]) for n in range(1, 8)]
    # station order 4, 5, 6, 7, 7A, 8, 10
    assert pairs == [
        ("5", "7"),
        ("5", "7"),
        ("6", "7"),
        ("7", "8"),
        ("4", "6"),
        ("6", "8"),
        ("6", "7"),
    ]


def test_unlinked_station_entries_are_not_a_rounds_stations(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    # the same day's sheet has an entry for an unmatched name: round_id is NULL
    _station_entry(session, D1, None, jane, "doe jayne", SPORTING, SPORTING_HITS)
    seed.finish()

    (record,) = _records(_export(viewer_client, jane)[SPORTING_CSV])

    assert (record["Total Targets"], record["Station 1 Hits"]) == ("50", "")


def test_station_data_is_exported_as_recorded(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    rid = seed.round(D1, jane, 40)
    short_layout = (("4", 8), ("5", 8), ("6", 6), ("7", 8), ("8", 6), ("9", 8), ("10", 4))  # 48
    _station_entry(session, D1, rid, jane, "doe jane", short_layout, (8, 8, 6, 8, 6, 8, 4))
    seed.finish()

    (record,) = _records(_export(viewer_client, jane)[SPORTING_CSV])

    assert (record["Total Hits"], record["Total Targets"]) == ("40", "48")


def test_merged_same_day_rounds_are_numbered_by_day_ordinal(
    seed: Any, viewer_client: TestClient
) -> None:
    # en_US.utf8 ignores spaces, so it sorts "dela ann" before "de la roe ann"; codepoint order
    # (and so day_ordinals) puts "de la roe ann" first, because ' ' < 'l'.
    ann = seed.shooter("De La Roe, Ann")
    seed.round(D1, ann, 40, name_key="dela ann", ordinal=1)  # a merged spelling
    seed.round(D1, ann, 37, name_key="de la roe ann", ordinal=1)
    seed.finish()

    records = _records(_export(viewer_client, ann)[SPORTING_CSV])

    assert [(r["Name"], r["Total Hits"]) for r in records] == [
        ("Sunday Clays", "37"),
        ("Sunday Clays (round 2)", "40"),
    ]


def test_export_requires_a_session(seed: Any, anon_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    seed.finish()

    response = anon_client.get(_url(jane))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_admin_sessions_can_export_too(seed: Any, admin_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    seed.finish()

    assert list(_export(admin_client, jane)) == [SPORTING_CSV]


def test_unknown_shooter_is_404(viewer_client: TestClient) -> None:
    response = viewer_client.get(_url(999999))

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "shooter_not_found", "message": "No shooter with id 999999"}
    }


def test_a_shooter_without_exportable_rounds_is_404_no_exportable_rounds(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    seed.finish()
    session.execute(text("DELETE FROM rounds WHERE shooter_id = :s"), {"s": jane})

    response = viewer_client.get(_url(jane))

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "no_exportable_rounds",
            "message": "There are no Sunday rounds to export yet.",
        }
    }


def test_query_count_does_not_grow_with_rounds(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    one = seed.shooter("Doe, Jane")
    many = seed.shooter("Roe, Rick")
    seed.round(D1, one, 41)
    for week in range(6):
        d = D1 + timedelta(weeks=week)
        rid = seed.round(d, many, 30 + week)
        _station_entry(session, d, rid, many, "roe rick", SPORTING, SPORTING_HITS, entry_row=2)
    seed.finish()

    with _statements(session) as small:
        _export(viewer_client, one)
    with _statements(session) as big:
        _export(viewer_client, many)

    assert len(big) == len(small)


@pytest.mark.slow
def test_the_largest_fx_history_exports_under_the_ceiling(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    top = fx_session.execute(
        text(
            "SELECT shooter_id FROM rounds GROUP BY shooter_id"
            " ORDER BY count(*) DESC, shooter_id LIMIT 1"
        )
    ).scalar_one()
    _export(fx_viewer_client, top)  # warm-up: imports, first-request setup

    started = time.perf_counter()
    files = _export(fx_viewer_client, top)
    elapsed = time.perf_counter() - started

    assert files
    assert elapsed < CI_CEILING_SECONDS, f"export took {elapsed:.3f}s"
