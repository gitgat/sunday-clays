"""GET /api/shooters/{id}/export over directly seeded live rows (spec 2026-10-01 §4.1)."""

import time
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
# Gross-regression ceiling only (an accidental N+1 or full-table scan per round), not the 300 ms
# target: CI runners with coverage vary too much for that. 300 ms is checked in production (Task 5).
CI_CEILING_SECONDS = 1.0
SPORTING = (("4", 8), ("5", 8), ("6", 6), ("7", 8), ("8", 6), ("9", 8), ("10", 6))
SPORTING_HITS = (6, 7, 5, 6, 5, 7, 5)  # 41


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


def _export(client: TestClient, shooter_id: int) -> dict[str, Any]:
    response = client.get(f"/api/shooters/{shooter_id}/export")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


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


def test_export_shape(seed: Any, session: Session, viewer_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    rid = seed.round(D1, jane, 41, gauge_class="12 Gauge", status="member")
    _station_entry(session, D1, rid, jane, "doe jane", SPORTING, SPORTING_HITS)
    seed.finish()

    body = _export(viewer_client, jane)

    assert body["schema_version"] == 1
    assert body["club"] == {
        "name": "Tri-County Gun Club",
        "event_name": "Sunday Clays",
        "city": "Sherwood",
        "region": "OR",
    }
    assert body["shooter"] == {"id": jane, "display_name": "Doe, Jane"}
    assert body["generated_at"].endswith("Z")
    # no import or rule exists in a seeded database, so updated_at falls back to generated_at
    assert body["rounds"] == [
        {
            "round_key": "2026-09-06:doe jane:1",
            "event_date": "2026-09-06",
            "ordinal": 1,
            "round_type": "sporting",
            "score": 41,
            "target_count": 50,
            "gauge_class": "12 Gauge",
            "status": "member",
            "updated_at": body["generated_at"],
            "stations": [
                {"order": n, "station_label": label, "target_count": targets, "hits": hits}
                for n, ((label, targets), hits) in enumerate(
                    zip(SPORTING, SPORTING_HITS, strict=True), start=1
                )
            ],
        }
    ]


def test_round_without_station_data_has_no_stations_and_fifty_targets(
    seed: Any, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 38, gauge_class=None, status=None)
    seed.finish()

    (only,) = _export(viewer_client, jane)["rounds"]

    assert (only["stations"], only["target_count"], only["score"]) == ([], 50, 38)
    assert (only["gauge_class"], only["status"]) == (None, None)


def test_two_round_day_lists_ordinals_1_and_2_in_date_order(
    seed: Any, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D2, jane, 41)
    seed.round(D2, jane, 35)
    seed.round(D1, jane, 30)
    seed.finish()

    rounds = _export(viewer_client, jane)["rounds"]

    assert [(r["round_key"], r["ordinal"], r["score"]) for r in rounds] == [
        ("2026-09-06:doe jane:1", 1, 30),
        ("2026-09-13:doe jane:1", 1, 41),
        ("2026-09-13:doe jane:2", 2, 35),
    ]


def test_super_sporting_event(seed: Any, viewer_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.event(D1, round_type="super_sporting")
    seed.round(D1, jane, 44)
    seed.finish()

    assert _export(viewer_client, jane)["rounds"][0]["round_type"] == "super_sporting"


def test_lettered_stations_come_out_in_station_order(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    rid = seed.round(D1, jane, 39, ordinal=1)
    shuffled = (("8", 8), ("7A", 6), ("4", 7), ("10", 7), ("7", 8), ("5", 7), ("6", 7))
    _station_entry(session, D1, rid, jane, "doe jane", shuffled, (6, 4, 5, 6, 7, 5, 6))
    seed.finish()

    stations = _export(viewer_client, jane)["rounds"][0]["stations"]

    assert [(s["order"], s["station_label"], s["target_count"], s["hits"]) for s in stations] == [
        (1, "4", 7, 5),
        (2, "5", 7, 5),
        (3, "6", 7, 6),
        (4, "7", 8, 7),
        (5, "7A", 6, 4),
        (6, "8", 8, 6),
        (7, "10", 7, 6),
    ]


def test_unlinked_station_entries_are_not_a_rounds_stations(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    # the same day's sheet has an entry for an unmatched name: round_id is NULL
    _station_entry(session, D1, None, jane, "doe jayne", SPORTING, SPORTING_HITS)
    seed.finish()

    (only,) = _export(viewer_client, jane)["rounds"]

    assert (only["stations"], only["target_count"]) == ([], 50)


def test_station_data_is_exported_as_recorded(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    rid = seed.round(D1, jane, 40)
    short_layout = (("4", 8), ("5", 8), ("6", 6), ("7", 8), ("8", 6), ("9", 8), ("10", 4))  # 48
    _station_entry(session, D1, rid, jane, "doe jane", short_layout, (8, 8, 6, 8, 6, 8, 4))  # 48
    seed.finish()

    (only,) = _export(viewer_client, jane)["rounds"]

    assert only["score"] == 40
    assert only["target_count"] == 48 == sum(s["target_count"] for s in only["stations"])
    assert sum(s["hits"] for s in only["stations"]) == 48


def test_merged_same_day_rounds_get_distinct_keys_and_day_ordinals(
    seed: Any, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)  # "doe jane", ordinal 1
    seed.round(D1, jane, 38, name_key="doe j", ordinal=1)  # a merged spelling, also ordinal 1
    seed.finish()

    rounds = _export(viewer_client, jane)["rounds"]

    assert [(r["round_key"], r["ordinal"], r["score"]) for r in rounds] == [
        ("2026-09-06:doe j:1", 1, 38),
        ("2026-09-06:doe jane:1", 2, 41),
    ]


def test_same_day_order_follows_day_ordinals_not_the_db_collation(
    seed: Any, viewer_client: TestClient
) -> None:
    # en_US.utf8 ignores spaces, so it sorts "dela ann" before "de la roe ann"; codepoint order
    # (and so day_ordinals) puts "de la roe ann" first, because ' ' < 'l'.
    ann = seed.shooter("De La Roe, Ann")
    seed.round(D1, ann, 40, name_key="dela ann", ordinal=1)  # a merged spelling
    seed.round(D1, ann, 37, name_key="de la roe ann", ordinal=1)
    seed.finish()

    rounds = _export(viewer_client, ann)["rounds"]

    assert [(r["round_key"], r["ordinal"]) for r in rounds] == [
        ("2026-09-06:de la roe ann:1", 1),
        ("2026-09-06:dela ann:1", 2),
    ]


def test_export_requires_a_session(seed: Any, anon_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    seed.finish()

    response = anon_client.get(f"/api/shooters/{jane}/export")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_admin_sessions_can_export_too(seed: Any, admin_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    seed.finish()

    assert len(_export(admin_client, jane)["rounds"]) == 1


def test_unknown_shooter_is_404(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/shooters/999999/export")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "shooter_not_found", "message": "No shooter with id 999999"}
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
    body = _export(fx_viewer_client, top)
    elapsed = time.perf_counter() - started

    assert body["rounds"]
    assert elapsed < CI_CEILING_SECONDS, f"export took {elapsed:.3f}s"
