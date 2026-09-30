"""A lettered station such as 7A is its own station end to end (owner rule 2026-09-29).

Synthetic sheets are added next to the committed fixtures (stations 4-10, two Sundays): three later
Sundays have both a 7 and a 7A column, so 7A has enough appearances to list leaders."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.rules import RuleType, create_rule

DAYS = ("2026-09-20", "2026-09-27", "2026-10-04")
SHOOTERS = ("abernathy preston", "hadley ike", "nordquist sherman")


def _scalar(session: Any, sql: str, **params: Any) -> Any:
    return session.execute(text(sql), params).scalar_one()


def _add_lettered_sheets(session: Any) -> dict[str, int]:
    """Stations 7 (7 targets) and 7A (6 targets) on DAYS; 7A hits differ by shooter."""
    ids = {
        key: _scalar(session, "SELECT shooter_id FROM shooter_aliases WHERE name_key = :k", k=key)
        for key in SHOOTERS
    }
    for day in DAYS:
        session.execute(
            text(
                "INSERT INTO events (event_date, round_type, round_type_source, n_rounds,"
                " n_shooters, has_scores, has_stations, results_complete)"
                " VALUES (:d, 'super_sporting', 'stations', 0, 0, false, true, false)"
                " ON CONFLICT (event_date) DO NOTHING"
            ),
            {"d": day},
        )
        for label, targets in (("7", 7), ("7A", 6)):
            session.execute(
                text(
                    "INSERT INTO station_layouts (event_date, station_no, station_label,"
                    " target_count, source_import_id) VALUES (:d, 7, :l, :t, 0)"
                ),
                {"d": day, "l": label, "t": targets},
            )
        for row, key in enumerate(SHOOTERS, start=1):
            for label, hits in (("7", 5), ("7A", 6 if key == "abernathy preston" else 3)):
                session.execute(
                    text(
                        "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id,"
                        " entry_row, name_key, shooter_id, round_id, hits)"
                        " VALUES (:d, 7, :l, 0, :row, :k, :s, NULL, :h)"
                    ),
                    {"d": day, "l": label, "row": row, "k": key, "s": ids[key], "h": hits},
                )
    return ids


def test_overview_lists_7a_after_7_and_apart_from_it(fx_viewer_client, fx_session):
    _add_lettered_sheets(fx_session)
    body = fx_viewer_client.get("/api/stations", params={"era": "all"}).json()
    labels = [s["label"] for s in body["stations"]]
    assert labels == ["4", "5", "6", "7", "7A", "8", "9", "10"]
    by = {s["label"]: s for s in body["stations"]}
    assert (by["7A"]["station_no"], by["7A"]["n_targets"], by["7A"]["n_events"]) == (7, 54, 3)
    assert by["7A"]["hits"] == 3 * (6 + 3 + 3)
    assert by["7"]["n_events"] == 5  # the two fixture Sundays and the three synthetic ones
    assert [r["hits"] for r in by["7A"]["leaders"]][:1] == [18]
    assert {e["label"] for e in body["by_event"] if e["station_no"] == 7} == {"7", "7A"}
    assert {c["label"] for c in body["matrix"] if c["station_no"] == 7} == {"7", "7A"}


def test_detail_takes_a_label_path_segment(fx_viewer_client, fx_session):
    ids = _add_lettered_sheets(fx_session)
    detail = fx_viewer_client.get("/api/stations/7A").json()
    assert (detail["label"], detail["station_no"]) == ("7A", 7)
    assert [e["event_date"] for e in detail["by_event"]] == list(DAYS)
    assert {e["label"] for e in detail["by_event"]} == {"7A"}
    assert detail["leaders"][0]["shooter_id"] == ids["abernathy preston"]
    lower = fx_viewer_client.get("/api/stations/7a").json()
    assert lower["label"] == "7A"
    plain = fx_viewer_client.get("/api/stations/7").json()  # 7 still works and never mixes in 7A
    assert (plain["label"], plain["station_no"]) == ("7", 7)
    assert {e["label"] for e in plain["by_event"]} == {"7"}
    assert len(plain["by_event"]) == 5


@pytest.mark.parametrize("path", ["7B", "x", "7AB", "0", "77"])
def test_a_label_that_is_not_a_station_is_404(fx_viewer_client, fx_session, path):
    _add_lettered_sheets(fx_session)
    response = fx_viewer_client.get(f"/api/stations/{path}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "station_not_found"


def test_shooter_breakdown_returns_labels(fx_viewer_client, fx_session):
    ids = _add_lettered_sheets(fx_session)
    body = fx_viewer_client.get(f"/api/shooters/{ids['abernathy preston']}/stations").json()
    labels = [s["label"] for s in body["stations"]]
    assert labels == ["4", "5", "6", "7", "7A", "8", "9", "10"]
    seven_a = next(s for s in body["stations"] if s["label"] == "7A")
    assert (seven_a["station_no"], seven_a["hits"], seven_a["n"], seven_a["n_rounds"]) == (
        7,
        18,
        18,
        3,
    )


def test_a_reset_on_7a_starts_a_new_era_for_7a_only(fx_viewer_client, fx_session):
    _add_lettered_sheets(fx_session)
    create_rule(
        fx_session,
        RuleType.STATION_RESET,
        {"station": "7a", "effective_date": "2026-09-27", "note": "new presentation"},
        None,
    )
    stored = _scalar(
        fx_session, "SELECT payload FROM rules WHERE rule_type = 'station_reset' ORDER BY id DESC"
    )
    assert stored == {
        "station": "7A",
        "effective_date": "2026-09-27",
        "note": "new presentation",
    }
    body = fx_viewer_client.get("/api/stations").json()
    by = {s["label"]: s for s in body["stations"]}
    assert (by["7A"]["era"], by["7A"]["era_start"], by["7A"]["n_events"]) == (1, "2026-09-27", 2)
    assert by["7"]["era"] == 0  # 7 has no reset
    assert by["7"]["n_events"] == 5
    assert [(r["label"], r["station_no"]) for r in body["resets"]] == [("7A", 7)]
    detail = fx_viewer_client.get("/api/stations/7A", params={"era": "all"}).json()
    assert [(e["era"], e["n_events"]) for e in detail["eras"]] == [(0, 1), (1, 2)]
    assert [r["label"] for r in detail["resets"]] == ["7A"]
    assert fx_viewer_client.get("/api/stations/7").json()["resets"] == []


def test_the_older_number_spelling_of_a_reset_still_works(fx_viewer_client, fx_session):
    create_rule(
        fx_session,
        RuleType.STATION_RESET,
        {"station_no": 9, "effective_date": "2026-09-10", "note": "new presentation"},
        None,
    )
    create_rule(
        fx_session,
        RuleType.STATION_RESET,
        {"station": 4, "effective_date": "2026-09-10", "note": "a number in the new spelling"},
        None,
    )
    fx_session.execute(
        text(
            "INSERT INTO rules (rule_type, payload) VALUES ('station_reset',"
            ' \'{"station": "100Z", "effective_date": "2026-09-10", "note": "no"}\'::jsonb)'
        )
    )
    resets = fx_viewer_client.get("/api/stations").json()["resets"]
    assert [(r["label"], r["station_no"]) for r in resets] == [("9", 9), ("4", 4)]


@pytest.mark.parametrize(
    "payload",
    [
        {"effective_date": "2026-09-10", "note": "x"},
        {"station_no": 7, "station": "7A", "effective_date": "2026-09-10", "note": "x"},
        {"station": "7AB", "effective_date": "2026-09-10", "note": "x"},
        {"station": 0, "effective_date": "2026-09-10", "note": "x"},
        {"station_no": 0, "effective_date": "2026-09-10", "note": "x"},
    ],
)
def test_a_reset_needs_exactly_one_valid_station(fx_session, payload):
    with pytest.raises(DomainError) as excinfo:
        create_rule(fx_session, RuleType.STATION_RESET, payload, None)
    assert excinfo.value.code == "invalid_rule"
