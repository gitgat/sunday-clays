"""Station endpoints over the committed fixtures (Plan 10 T4a).

Literal expectations were computed independently from
backend/tests/fixtures/stations_2026-09-27.xlsx with openpyxl (2 sheets, 37 entries, stations 4-10
with targets 7,7,7,7,7,7,8)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from sunday_clays.analytics.frames import wind_band
from sunday_clays.domain.rules import RuleType, create_rule


def scalar(session: Any, sql: str, **params: Any) -> Any:
    return session.execute(text(sql), params).scalar_one()


def test_station_overview_on_fixture(fx_viewer_client, fx_session):
    body = fx_viewer_client.get("/api/stations").json()
    assert (body["era"], body["n_events"], body["resets"]) == ("current", 2, [])
    stations = {s["station_no"]: s for s in body["stations"]}
    assert sorted(stations) == [4, 5, 6, 7, 8, 9, 10]
    nine = stations[9]
    assert (
        nine["hits"],
        nine["n_targets"],
        nine["n_rounds"],
        nine["n_events"],
        nine["clean_rate"],
    ) == (
        130,
        259,
        37,
        2,
        0.0,
    )
    assert (nine["era"], nine["era_start"], nine["leaders"]) == (0, None, [])
    assert nine["hit_pct"] == pytest.approx(130 / 259)
    assert (nine["ci_low"], nine["ci_high"]) == pytest.approx((0.432572, 0.571215), abs=1e-5)
    assert nine["deff"] == pytest.approx(1.321341, abs=1e-5)
    assert nine["separator"] == pytest.approx(0.615142, abs=1e-5)
    assert stations[10]["clean_rate"] == pytest.approx(4 / 37)
    assert stations[7]["deff"] == 1.0
    assert len(body["by_event"]) == 14
    linked = scalar(
        fx_session,
        "SELECT count(DISTINCT shooter_id) FROM station_hits WHERE shooter_id IS NOT NULL",
    )
    assert len(body["matrix"]) == 7 * linked


def test_stations_route_round_type_filter(fx_viewer_client):
    none = fx_viewer_client.get("/api/stations", params={"round_type": "sporting"}).json()
    assert (none["stations"], none["n_events"]) == ([], 0)
    both = fx_viewer_client.get(
        "/api/stations", params={"round_type": "super_sporting", "era": "all"}
    ).json()
    assert (both["era"], both["n_events"], both["stations"][0]["era"]) == ("all", 2, None)


def test_station_reset_splits_eras_on_fixture(fx_viewer_client, fx_session):
    create_rule(
        fx_session,
        RuleType.STATION_RESET,
        {"station_no": 9, "effective_date": "2026-09-10", "note": "new presentation"},
        None,
    )
    current = {s["station_no"]: s for s in fx_viewer_client.get("/api/stations").json()["stations"]}
    assert (
        current[9]["era"],
        current[9]["era_start"],
        current[9]["hits"],
        current[9]["n_targets"],
    ) == (
        1,
        "2026-09-10",
        44,
        91,
    )
    assert current[4]["n_targets"] == 259  # other stations keep every event
    detail = fx_viewer_client.get("/api/stations/9").json()
    assert [(e["era"], e["era_start"], e["hits"], e["n_targets"]) for e in detail["eras"]] == [
        (0, None, 86, 168),
        (1, "2026-09-10", 44, 91),
    ]
    assert detail["resets"] == [
        {"label": "9", "station_no": 9, "effective_date": "2026-09-10", "note": "new presentation"}
    ]


def test_stations_route_uses_todays_date_for_the_current_era(
    fx_viewer_client, fx_session, monkeypatch
):
    from datetime import date

    from sunday_clays.api.routes import _filters

    create_rule(
        fx_session,
        RuleType.STATION_RESET,
        {"station_no": 9, "effective_date": "2027-01-01", "note": "future"},
        None,
    )
    monkeypatch.setattr(_filters, "today_local", lambda _tz: date(2026, 12, 31))
    before = {s["station_no"]: s for s in fx_viewer_client.get("/api/stations").json()["stations"]}
    assert (before[9]["era"], before[9]["era_start"], before[9]["n_targets"]) == (0, None, 259)
    monkeypatch.setattr(_filters, "today_local", lambda _tz: date(2027, 1, 2))
    after = {s["station_no"]: s for s in fx_viewer_client.get("/api/stations").json()["stations"]}
    assert (after[9]["era"], after[9]["era_start"]) == (1, "2027-01-01")


def test_station_with_no_sheet_since_its_reset_stays_in_the_overview(
    fx_viewer_client, fx_session, monkeypatch
):
    from datetime import date

    from sunday_clays.api.routes import _filters

    create_rule(
        fx_session,
        RuleType.STATION_RESET,
        {"station_no": 9, "effective_date": "2026-10-05", "note": "after the last sheet"},
        None,
    )
    monkeypatch.setattr(_filters, "today_local", lambda _tz: date(2026, 10, 6))
    body = fx_viewer_client.get("/api/stations").json()
    current = {s["station_no"]: s for s in body["stations"]}
    assert sorted(current) == [4, 5, 6, 7, 8, 9, 10]
    assert (current[9]["era"], current[9]["era_start"]) == (1, "2026-10-05")
    assert (current[9]["hits"], current[9]["n_targets"], current[9]["n_rounds"]) == (0, 0, 0)
    assert current[9]["hit_pct"] is None
    assert current[9]["ci_low"] is None
    assert not [e for e in body["by_event"] if e["station_no"] == 9]
    assert current[4]["n_targets"] == 259


def test_station_detail_on_fixture(fx_viewer_client, fx_session):
    body = fx_viewer_client.get("/api/stations/9").json()
    [era] = body["eras"]
    assert (era["era"], era["hits"], era["n_targets"]) == (0, 130, 259)
    assert [e["event_date"] for e in body["by_event"]] == ["2026-09-06", "2026-09-13"]
    # Plan 12: the fx world loads the committed weather fixture, so both Sundays have a band.
    gusts = (
        fx_session.execute(
            text(
                "SELECT gust_mph FROM event_weather "
                "WHERE event_date IN ('2026-09-06', '2026-09-13')"
            )
        )
        .scalars()
        .all()
    )
    assert len(gusts) == 2
    assert body["wind"]
    assert sorted(c["band"] for c in body["wind"]) == sorted({wind_band(g) for g in gusts})
    assert body["leaders"] == []  # nobody has 3 appearances in 2 events


def test_unknown_station_is_404(fx_viewer_client):
    response = fx_viewer_client.get("/api/stations/99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "station_not_found"


def test_shooter_station_deltas_on_fixture(fx_viewer_client, fx_session):
    shooter_id = scalar(
        fx_session, "SELECT shooter_id FROM shooter_aliases WHERE name_key = 'hadley ike'"
    )
    body = fx_viewer_client.get(f"/api/shooters/{shooter_id}/stations").json()
    rows = {s["station_no"]: s for s in body["stations"]}
    assert sorted(rows) == [4, 5, 6, 7, 8, 9, 10]
    assert all(r["n_rounds"] == 2 for r in rows.values())
    assert rows[9]["n"] == 14
    assert rows[9]["field_pct"] == pytest.approx(130 / 259)
    # Hadley hit 2 + 4 of 14 at station 9; κ = 2·7: (6 + 14·130/259)/28 - 130/259
    assert (rows[9]["hits"], rows[9]["hit_pct"]) == (6, pytest.approx(6 / 14))
    assert rows[9]["delta"] == pytest.approx(-0.036680, abs=1e-5)
    assert rows[10]["delta"] == pytest.approx(0.048986, abs=1e-5)


def test_shooter_stations_unknown_shooter_is_404(fx_viewer_client):
    response = fx_viewer_client.get("/api/shooters/999999/stations")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"


def test_shooter_without_station_entries_has_no_rows(fx_viewer_client, fx_session):
    shooter_id = scalar(
        fx_session,
        "SELECT min(shooter_id) FROM shooter_profiles WHERE shooter_id NOT IN"
        " (SELECT shooter_id FROM station_hits WHERE shooter_id IS NOT NULL)",
    )
    body = fx_viewer_client.get(f"/api/shooters/{shooter_id}/stations").json()
    assert body == {
        "shooter_id": shooter_id,
        "last_reset_date": None,
        "coverage": {
            "n_rounds": 0,
            "n_sundays": 0,
            "first_date": None,
            "last_date": None,
            "latest_date": None,
        },
        "stations": [],
    }


def test_shooter_stations_round_type_filter(fx_viewer_client, fx_session):
    shooter_id = scalar(
        fx_session, "SELECT shooter_id FROM shooter_aliases WHERE name_key = 'hadley ike'"
    )
    body = fx_viewer_client.get(
        f"/api/shooters/{shooter_id}/stations", params={"round_type": "sporting"}
    ).json()
    assert body["stations"] == []


def test_station_detail_round_type_filter_keeps_the_station(fx_viewer_client):
    response = fx_viewer_client.get("/api/stations/9", params={"round_type": "sporting"})
    assert response.status_code == 200
    body = response.json()
    assert (body["station_no"], body["eras"], body["by_event"], body["wind"]) == (9, [], [], [])


def test_unknown_era_is_rejected(fx_viewer_client):
    assert fx_viewer_client.get("/api/stations", params={"era": "next"}).status_code == 422


def _pin_gusts(session):
    """Pin the fixture weather rows' gusts (Plan 12); each UPDATE must hit exactly one row."""
    for day, gust in (("2026-09-06", 12.0), ("2026-09-13", 4.0)):
        result = session.execute(
            text("UPDATE event_weather SET gust_mph = :g WHERE event_date = :d"),
            {"d": day, "g": gust},
        )
        assert result.rowcount == 1, f"no event_weather row for {day}"


def test_station_wind_on_fixture_with_weather(fx_viewer_client, fx_session):
    _pin_gusts(fx_session)
    wind = fx_viewer_client.get("/api/stations/9").json()["wind"]
    assert [
        (c["band"], c["band_order"], c["n_targets"], c["n_events"], c["sufficient"]) for c in wind
    ] == [("<10", 4.0, 91, 1, False), ("10-20", 12.0, 168, 1, False)]
    assert [c["hit_pct"] for c in wind] == pytest.approx([44 / 91, 86 / 168])
    assert [(c["ci_low"], c["ci_high"]) for c in wind] == [
        pytest.approx((0.378970, 0.589526), abs=1e-5),
        pytest.approx((0.420856, 0.602170), abs=1e-5),
    ]


def _add_station_nine_sheet(session: Any, day: str, entries: dict[str | None, int]) -> None:
    """A station-9-only sheet (7 targets); a None key is a name that matched no shooter."""
    session.execute(
        text(
            "INSERT INTO events (event_date, round_type, round_type_source, n_rounds,"
            " n_shooters, has_scores, has_stations, results_complete)"
            " VALUES (:d, 'super_sporting', 'stations', 0, 0, false, true, false)"
            " ON CONFLICT (event_date) DO NOTHING"
        ),
        {"d": day},
    )
    session.execute(
        text(
            "INSERT INTO station_layouts (event_date, station_no, target_count, source_import_id)"
            " VALUES (:d, 9, 7, 0)"
        ),
        {"d": day},
    )
    for row, (key, hits) in enumerate(entries.items(), start=1):
        shooter_id = None
        if key is not None:
            shooter_id = scalar(
                session, "SELECT shooter_id FROM shooter_aliases WHERE name_key = :k", k=key
            )
        session.execute(
            text(
                "INSERT INTO station_hits (event_date, station_no, sheet_id, entry_row, name_key,"
                " shooter_id, round_id, hits) VALUES (:d, 9, 0, :row, :k, :s, NULL, :h)"
            ),
            {"d": day, "row": row, "k": key or "nobody zed", "s": shooter_id, "h": hits},
        )


def test_station_leaders_after_two_more_sheets(fx_viewer_client, fx_session):
    """Station 9 totals per shooter = the two fixture sheets + these synthetic sheets."""
    _add_station_nine_sheet(
        fx_session,
        "2026-09-20",
        {
            "abernathy preston": 7,
            "hadley ike": 6,
            "mcginnis alvin": 5,
            "mcmurtry zeb": 3,
            "kaplan noel": 5,
            "nordquist sherman": 6,
            None: 7,
        },
    )
    _add_station_nine_sheet(fx_session, "2026-09-27", {"nordquist sherman": 6, None: 7})
    ids = {
        key: scalar(fx_session, "SELECT shooter_id FROM shooter_aliases WHERE name_key = :k", k=key)
        for key in (
            "abernathy preston",
            "nordquist sherman",
            "hadley ike",
            "mcmurtry zeb",
            "kaplan noel",
        )
    }
    # McMurtry and Kaplan tie at 11/21: the lower shooter_id leads
    tied = sorted([ids["mcmurtry zeb"], ids["kaplan noel"]])
    expected = [
        (ids["abernathy preston"], 17),
        (ids["nordquist sherman"], 16),
        (ids["hadley ike"], 12),
        (tied[0], 11),
        (tied[1], 11),
    ]
    overview = fx_viewer_client.get("/api/stations").json()
    nine = {s["station_no"]: s for s in overview["stations"]}[9]
    assert [(r["shooter_id"], r["hits"]) for r in nine["leaders"]] == expected  # top 5
    assert all((r["n_targets"], r["n_rounds"]) == (21, 3) for r in nine["leaders"])
    assert nine["leaders"][0]["hit_pct"] == pytest.approx(17 / 21)
    assert nine["leaders"][0]["display_name"] == "Abernathy, Preston"
    assert {s["station_no"]: s for s in overview["stations"]}[4]["leaders"] == []
    detail = fx_viewer_client.get("/api/stations/9").json()
    assert [(r["shooter_id"], r["hits"]) for r in detail["leaders"]][:5] == expected
    assert [r["hits"] for r in detail["leaders"][5:]] == [8]  # McGinnis: top 10 in the detail


def test_stations_without_station_data(viewer_client):
    body = viewer_client.get("/api/stations").json()
    assert body == {
        "era": "current",
        "n_events": 0,
        "last_reset_date": None,
        "stations": [],
        "by_event": [],
        "matrix": [],
        "resets": [],
        "coverage": {
            "n_station_sundays": 0,
            "first_date": None,
            "last_date": None,
            "n_scored_sundays": 0,
            "latest_date": None,
        },
    }
    response = viewer_client.get("/api/stations/4")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "station_not_found"


def test_reset_without_a_note_lists_none(fx_viewer_client, fx_session):
    """A stored payload without `note` (C5 has always required one) still lists cleanly."""
    create_rule(
        fx_session,
        RuleType.STATION_RESET,
        {"station_no": 4, "effective_date": "2026-09-10", "note": "new trap"},
        None,
    )
    fx_session.execute(
        text(
            "INSERT INTO rules (rule_type, payload) VALUES ('station_reset',"
            ' \'{"station_no": 5, "effective_date": "2026-09-10"}\'::jsonb)'
        )
    )
    resets = fx_viewer_client.get("/api/stations").json()["resets"]
    assert [(r["station_no"], r["note"]) for r in resets] == [(4, "new trap"), (5, None)]


def _hadley_id(session: Any) -> int:
    return int(
        scalar(session, "SELECT shooter_id FROM shooter_aliases WHERE name_key = 'hadley ike'")
    )


def _reset_station_nine(session: Any) -> None:
    create_rule(
        session,
        RuleType.STATION_RESET,
        {"station_no": 9, "effective_date": "2026-09-10", "note": "new presentation"},
        None,
    )


def test_matrix_cells_carry_their_round_counts(fx_viewer_client, fx_session):
    matrix = fx_viewer_client.get("/api/stations").json()["matrix"]
    hadley = [c for c in matrix if c["shooter_id"] == _hadley_id(fx_session)]
    assert len(hadley) == 7
    assert {c["n_rounds"] for c in hadley} == {2}


def test_station_wind_follows_the_era_toggle(fx_viewer_client, fx_session):
    _pin_gusts(fx_session)
    _reset_station_nine(fx_session)
    current = fx_viewer_client.get("/api/stations/9").json()
    assert [c["band"] for c in current["wind"]] == ["<10"]  # only the post-reset Sunday
    assert len(current["eras"]) == 2  # the era chart still lists every setup
    everything = fx_viewer_client.get("/api/stations/9", params={"era": "all"}).json()
    assert [c["band"] for c in everything["wind"]] == ["<10", "10-20"]


def test_shooter_station_deltas_follow_the_era_toggle(fx_viewer_client, fx_session):
    _reset_station_nine(fx_session)
    url = f"/api/shooters/{_hadley_id(fx_session)}/stations"
    everything = fx_viewer_client.get(url, params={"era": "all"}).json()
    assert {s["station_no"]: s["n_rounds"] for s in everything["stations"]}[9] == 2
    current = fx_viewer_client.get(url).json()
    assert {s["station_no"]: s["n_rounds"] for s in current["stations"]}[9] == 1
    assert {s["station_no"]: s["n_rounds"] for s in current["stations"]}[4] == 2


def test_stations_coverage_counts_station_and_scored_sundays(fx_viewer_client, fx_session):
    """Coverage = Sundays with station sheets (any era) against scored Sundays, per round-type
    filter; the era switch does not change it."""
    station_days = [
        d.isoformat()
        for (d,) in fx_session.execute(
            text("SELECT DISTINCT event_date FROM station_hits ORDER BY event_date")
        ).all()
    ]
    scored = scalar(fx_session, "SELECT count(*) FROM events WHERE has_scores")
    expected = {
        "n_station_sundays": len(station_days),
        "first_date": station_days[0],
        "last_date": station_days[-1],
        "n_scored_sundays": scored,
        "latest_date": station_days[-1],
    }
    assert len(station_days) == 2
    for era in ("current", "all"):
        assert fx_viewer_client.get("/api/stations", params={"era": era}).json()["coverage"] == (
            expected
        )
    none = fx_viewer_client.get("/api/stations", params={"round_type": "sporting"}).json()
    assert none["coverage"]["n_station_sundays"] == 0
    assert none["coverage"]["first_date"] is None
    assert none["coverage"]["last_date"] is None
    assert none["coverage"]["latest_date"] is None
    sporting = scalar(
        fx_session, "SELECT count(*) FROM events WHERE has_scores AND round_type = 'sporting'"
    )
    assert none["coverage"]["n_scored_sundays"] == sporting
