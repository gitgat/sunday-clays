"""The header time window (since / as_of) on the three station endpoints (date-filters DF-3).

The fixtures carry two station Sundays (stations 4-10); a third, synthetic Sunday with a
station 7 and a lettered 7A is added so a window can exclude one; 7A is checked in every param."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import text

from sunday_clays.domain.rules import RuleType, create_rule

LATE = "2026-11-08"
SHOOTERS = ("abernathy preston", "hadley ike")


def _scalar(session: Any, sql: str, **params: Any) -> Any:
    return session.execute(text(sql), params).scalar_one()


def _fixture_days(session: Any) -> list[str]:
    return [
        d.isoformat()
        for (d,) in session.execute(
            text(
                "SELECT DISTINCT event_date FROM station_hits WHERE event_date < :late ORDER BY 1"
            ),
            {"late": LATE},
        ).all()
    ]


def _add_late_sheet(session: Any) -> dict[str, int]:
    """One later Sunday: station 7 (7 targets) and 7A (6 targets), Abernathy perfect,
    Hadley 1 hit."""
    ids = {
        key: _scalar(session, "SELECT shooter_id FROM shooter_aliases WHERE name_key = :k", k=key)
        for key in SHOOTERS
    }
    session.execute(
        text(
            "INSERT INTO events (event_date, round_type, round_type_source, n_rounds, n_shooters,"
            " has_scores, has_stations, results_complete)"
            " VALUES (:d, 'super_sporting', 'stations', 0, 0, false, true, false)"
        ),
        {"d": LATE},
    )
    for label, targets in (("7", 7), ("7A", 6)):
        session.execute(
            text(
                "INSERT INTO station_layouts (event_date, station_no, station_label, target_count,"
                " source_import_id) VALUES (:d, 7, :l, :t, 0)"
            ),
            {"d": LATE, "l": label, "t": targets},
        )
    for row, key in enumerate(SHOOTERS, start=1):
        for label, perfect in (("7", 7), ("7A", 6)):
            session.execute(
                text(
                    "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id,"
                    " entry_row, name_key, shooter_id, round_id, hits)"
                    " VALUES (:d, 7, :l, 0, :row, :k, :s, NULL, :h)"
                ),
                {
                    "d": LATE,
                    "l": label,
                    "row": row,
                    "k": key,
                    "s": ids[key],
                    "h": perfect if row == 1 else 1,
                },
            )
    return ids


def _by_label(body: dict[str, Any]) -> dict[str, Any]:
    return {s["label"]: s for s in body["stations"]}


def test_a_window_that_excludes_a_sunday_changes_hit_pct(fx_viewer_client, fx_session):
    _add_late_sheet(fx_session)
    everything = _by_label(fx_viewer_client.get("/api/stations").json())
    late_only = _by_label(fx_viewer_client.get("/api/stations", params={"since": LATE}).json())
    assert late_only["7"]["n_events"] == 1
    assert late_only["7"]["hit_pct"] == pytest.approx(8 / 14)
    assert everything["7"]["n_events"] == 3
    assert everything["7"]["hit_pct"] != late_only["7"]["hit_pct"]
    assert (late_only["7A"]["n_targets"], late_only["7A"]["hits"]) == (12, 7)
    assert sorted(late_only) == ["7", "7A"]  # the fixture stations have no sheet in this window


def test_no_leak_the_window_bounds_every_figure(fx_viewer_client, fx_session):
    _add_late_sheet(fx_session)
    first, second = _fixture_days(fx_session)
    body = fx_viewer_client.get("/api/stations", params={"since": first, "as_of": first}).json()
    assert body["n_events"] == 1
    assert {e["event_date"] for e in body["by_event"]} == {first}
    assert all(s["n_events"] == 1 for s in body["stations"])
    assert set(_by_label(body)) == {"4", "5", "6", "7", "8", "9", "10"}
    total_rounds = sum(c["n_rounds"] for c in body["matrix"])
    assert total_rounds == sum(s["n_rounds"] for s in body["stations"])
    both = fx_viewer_client.get("/api/stations", params={"since": first, "as_of": second}).json()
    assert both["n_events"] == 2
    assert {e["event_date"] for e in both["by_event"]} == {first, second}
    # as_of alone cuts the late Sunday off; since is inclusive
    upto = fx_viewer_client.get("/api/stations", params={"as_of": second}).json()
    assert "7A" not in _by_label(upto)
    assert (
        fx_viewer_client.get("/api/stations", params={"since": second}).json()["n_events"] == 2
    )  # the second fixture day and the late one


def test_coverage_is_counted_inside_the_window_and_reports_the_latest_sheet(
    fx_viewer_client, fx_session
):
    first, second = _fixture_days(fx_session)
    scored = _scalar(
        fx_session,
        "SELECT count(*) FROM events WHERE has_scores AND event_date BETWEEN :a AND :b",
        a=first,
        b=second,
    )
    body = fx_viewer_client.get("/api/stations", params={"since": first, "as_of": first}).json()
    cov = body["coverage"]
    assert (cov["n_station_sundays"], cov["first_date"], cov["last_date"]) == (1, first, first)
    assert cov["latest_date"] == second
    assert cov["n_scored_sundays"] == _scalar(
        fx_session,
        "SELECT count(*) FROM events WHERE has_scores AND event_date = :a",
        a=first,
    )
    both_days = fx_viewer_client.get("/api/stations", params={"since": first, "as_of": second})
    assert both_days.json()["coverage"]["n_scored_sundays"] == scored


def test_an_empty_window_gives_empty_lists_not_an_error(fx_viewer_client, fx_session):
    _first, second = _fixture_days(fx_session)
    after = (date.fromisoformat(second) + timedelta(days=1)).isoformat()
    response = fx_viewer_client.get("/api/stations", params={"since": after})
    assert response.status_code == 200
    body = response.json()
    assert (body["stations"], body["by_event"], body["matrix"], body["n_events"]) == ([], [], [], 0)
    assert body["coverage"]["n_station_sundays"] == 0
    assert body["coverage"]["latest_date"] == second
    reversed_ = fx_viewer_client.get("/api/stations", params={"since": second, "as_of": after})
    assert reversed_.status_code == 200
    swapped = fx_viewer_client.get("/api/stations", params={"since": after, "as_of": second})
    assert swapped.status_code == 200
    assert swapped.json()["stations"] == []


def test_the_window_and_the_setup_choice_apply_together(fx_viewer_client, fx_session):
    first, second = _fixture_days(fx_session)
    create_rule(
        fx_session,
        RuleType.STATION_RESET,
        {"station_no": 9, "effective_date": second, "note": "new presentation"},
        None,
    )
    both = _by_label(fx_viewer_client.get("/api/stations", params={"since": first}).json())
    assert both["9"]["n_events"] == 1  # current setup only: the second Sunday
    everyday = _by_label(
        fx_viewer_client.get("/api/stations", params={"since": first, "era": "all"}).json()
    )
    assert everyday["9"]["n_events"] == 2
    windowed = _by_label(
        fx_viewer_client.get("/api/stations", params={"as_of": first, "era": "current"}).json()
    )
    # as_of before the reset: the current setup (era 1) is listed but has no Sunday in view
    assert (windowed["9"]["n_events"], windowed["9"]["era"]) == (0, 1)


def test_station_detail_follows_the_window_for_7a(fx_viewer_client, fx_session):
    _add_late_sheet(fx_session)
    full = fx_viewer_client.get("/api/stations/7A").json()
    assert [e["event_date"] for e in full["by_event"]] == [LATE]
    early = fx_viewer_client.get("/api/stations/7A", params={"as_of": "2026-10-01"})
    assert early.status_code == 200  # a real station with nothing in the window: empty, not 404
    body = early.json()
    assert (body["label"], body["by_event"], body["eras"], body["leaders"], body["wind"]) == (
        "7A",
        [],
        [],
        [],
        [],
    )
    seven = fx_viewer_client.get("/api/stations/7", params={"since": LATE}).json()
    assert [e["event_date"] for e in seven["by_event"]] == [LATE]
    assert seven["eras"][0]["n_events"] == 1
    assert fx_viewer_client.get("/api/stations/7a", params={"since": LATE}).json()["label"] == "7A"
    unknown = fx_viewer_client.get("/api/stations/9Z", params={"since": LATE})
    assert unknown.status_code == 404


def test_station_wind_uses_only_windowed_hits(fx_viewer_client, fx_session):
    first, second = _fixture_days(fx_session)
    for day, gust in ((first, 4.0), (second, 22.0)):
        fx_session.execute(
            text("UPDATE event_weather SET gust_mph = :g WHERE event_date = :d"),
            {"d": day, "g": gust},
        )
    full = fx_viewer_client.get("/api/stations/9").json()["wind"]
    one = fx_viewer_client.get("/api/stations/9", params={"since": second}).json()["wind"]
    assert sum(w["n_events"] for w in full) == 2
    assert sum(w["n_events"] for w in one) == 1
    assert len(one) == 1


def test_shooter_stations_follow_the_window(fx_viewer_client, fx_session):
    ids = _add_late_sheet(fx_session)
    first, _second = _fixture_days(fx_session)
    sid = ids["hadley ike"]
    full = fx_viewer_client.get(f"/api/shooters/{sid}/stations").json()
    assert full["coverage"]["n_sundays"] == 3
    assert full["coverage"]["latest_date"] == LATE
    late = fx_viewer_client.get(f"/api/shooters/{sid}/stations", params={"since": LATE}).json()
    assert sorted(s["label"] for s in late["stations"]) == ["7", "7A"]
    by = {s["label"]: s for s in late["stations"]}
    assert (by["7A"]["hits"], by["7A"]["n"], by["7A"]["n_rounds"]) == (1, 6, 1)
    assert by["7A"]["field_pct"] == pytest.approx(7 / 12)  # the field is windowed too
    assert late["coverage"] == {
        "n_rounds": 1,
        "n_sundays": 1,
        "first_date": LATE,
        "last_date": LATE,
        "latest_date": LATE,
    }
    empty = fx_viewer_client.get(
        f"/api/shooters/{sid}/stations", params={"since": "2027-01-01"}
    ).json()
    assert empty["stations"] == []
    assert empty["coverage"]["n_sundays"] == 0
    assert (empty["coverage"]["first_date"], empty["coverage"]["latest_date"]) == (None, LATE)
    early = fx_viewer_client.get(f"/api/shooters/{sid}/stations", params={"as_of": first}).json()
    assert early["coverage"]["n_sundays"] == 1
    assert early["coverage"]["latest_date"] == LATE  # not windowed


def test_last_reset_date_is_the_newest_reset_up_to_today(fx_viewer_client, fx_session, monkeypatch):
    from sunday_clays.api.routes import _filters

    _first, second = _fixture_days(fx_session)
    sid = _scalar(
        fx_session, "SELECT shooter_id FROM shooter_aliases WHERE name_key = 'hadley ike'"
    )
    assert fx_viewer_client.get("/api/stations").json()["last_reset_date"] is None
    assert fx_viewer_client.get(f"/api/shooters/{sid}/stations").json()["last_reset_date"] is None
    for station, effective in ((9, second), (4, "2026-09-01"), (5, "2999-01-01")):
        create_rule(
            fx_session,
            RuleType.STATION_RESET,
            {"station_no": station, "effective_date": effective, "note": "reset"},
            None,
        )
    monkeypatch.setattr(_filters, "today_local", lambda _tz: date(2026, 12, 31))
    assert fx_viewer_client.get("/api/stations").json()["last_reset_date"] == second
    assert fx_viewer_client.get(f"/api/shooters/{sid}/stations").json()["last_reset_date"] == second
