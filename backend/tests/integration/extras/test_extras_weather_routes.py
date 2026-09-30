"""Plan 11 Task 2: weather routes over the committed-fixture world (C2 `fx_*` fixtures).

The fixture world has no weather (no network in tests), so each test first deletes any
`event_weather` rows and inserts its own inside the per-test savepoint, which is rolled back.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames

# event_date: (temp_f, gust_mph, precip_in, cloud_pct, condition)
WEATHER: dict[date, tuple[float, float, float, float, str]] = {
    date(2018, 12, 30): (35.0, 4.0, 0.0, 90.0, "overcast"),  # attendance only, head count 7
    date(2026, 8, 16): (80.0, 12.0, 0.0, 10.0, "clear"),  # 48 rounds
    date(2026, 8, 23): (88.0, 22.0, 0.1, 60.0, "rain"),  # 29 rounds
    date(2026, 8, 30): (75.0, 8.0, 0.0, 20.0, "clear"),  # 36 rounds
    date(2026, 9, 6): (65.0, 15.0, 0.02, 85.0, "rain"),  # super sporting, 24 rounds
    date(2026, 9, 13): (60.0, 25.0, 0.3, 100.0, "rain"),  # super sporting, 13 rounds
    date(2026, 9, 27): (58.0, 6.0, 0.0, 40.0, "partly_cloudy"),  # 23 rounds
}
INSERT = text(
    "INSERT INTO event_weather (event_date, temp_f, apparent_f, precip_in, wind_mph, gust_mph,"
    " wind_dir_deg, cloud_pct, humidity_pct, pressure_hpa, condition, source)"
    " VALUES (:d, :t, :t - 2, :p, :g / 2, :g, 200, :c, 60, 1015, :cond, 'archive')"
)
# Deterministic weather for every held event from 2025 on (84 events): temp = 30 + day of month,
# gust = 2 x month, rain 0.1 in on odd days, cloud = 7 x day mod 100.
INSERT_2025_ON = text(
    "INSERT INTO event_weather (event_date, temp_f, apparent_f, precip_in, wind_mph, gust_mph,"
    " wind_dir_deg, cloud_pct, humidity_pct, pressure_hpa, condition, source)"
    " SELECT event_date, 30 + EXTRACT(DAY FROM event_date), 28 + EXTRACT(DAY FROM event_date),"
    " CASE WHEN EXTRACT(DAY FROM event_date)::int % 2 = 1 THEN 0.1 ELSE 0 END,"
    " EXTRACT(MONTH FROM event_date), 2 * EXTRACT(MONTH FROM event_date), 200,"
    " (7 * EXTRACT(DAY FROM event_date)::int) % 100, 60, 1015, 'clear', 'archive'"
    " FROM events WHERE results_complete AND event_date >= DATE '2025-01-01'"
)


def _reset_weather(session: Session) -> None:
    session.execute(text("DELETE FROM event_weather"))


def _add_seven(session: Session) -> None:
    _reset_weather(session)
    for day, (temp, gust, precip, cloud, condition) in WEATHER.items():
        session.execute(
            INSERT, {"d": day, "t": temp, "g": gust, "p": precip, "c": cloud, "cond": condition}
        )


def _bands(body: list[dict[str, Any]], dimension: str) -> dict[str, dict[str, Any]]:
    return {b["band"]: b for b in body if b["dimension"] == dimension}


def _shooter_id(session: Session, name_key: str) -> int:
    return int(
        session.execute(
            text("SELECT shooter_id FROM shooter_aliases WHERE name_key = :k"), {"k": name_key}
        ).scalar_one()
    )


def test_weather_endpoints_empty_without_weather(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    _reset_weather(fx_session)
    assert fx_viewer_client.get("/api/weather/events").json() == []
    assert fx_viewer_client.get("/api/weather/effects").json() == {
        "model": None,
        "n_events": 0,
        "bands": [],
    }
    sensitivity = fx_viewer_client.get("/api/weather/sensitivity").json()
    assert sensitivity["shooters"] == []
    assert [t["tau2"] for t in sensitivity["tau2"]] == [0.0, 0.0, 0.0]
    assert fx_viewer_client.get("/api/weather/turnout").json() == []


def test_weather_events_list_every_event_with_weather(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    _add_seven(fx_session)
    body = fx_viewer_client.get("/api/weather/events").json()
    assert [row["event_date"] for row in body] == [d.isoformat() for d in sorted(WEATHER)]
    by_date = {row["event_date"]: row for row in body}
    attendance_only = by_date["2018-12-30"]
    assert (attendance_only["has_scores"], attendance_only["n_rounds"]) == (False, 0)
    assert (attendance_only["head_count"], attendance_only["median"]) == (7, None)
    assert attendance_only["difficulty"] is None
    station_day = by_date["2026-09-13"]
    assert (station_day["round_type"], station_day["n_rounds"], station_day["head_count"]) == (
        "super_sporting",
        13,
        13,
    )
    assert station_day["difficulty"] is not None
    assert station_day["temp_band"] == frames.temp_band(60.0)
    assert (station_day["precip_in"], station_day["precip_band"]) == (0.3, frames.precip_band(0.3))
    assert by_date["2026-09-06"]["precip_band"] == frames.precip_band(0.02)


def test_round_type_filter_restricts_rounds(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    _add_seven(fx_session)
    everything = fx_viewer_client.get("/api/weather/effects").json()
    assert everything["n_events"] == 7
    assert everything["model"]["n_events"] == 6  # scored events with difficulty
    assert [t["name"] for t in everything["model"]["terms"]] == [
        "intercept",
        "temp_f",
        "gust_mph",
        "precip_in",
        "cloud_pct",
    ]
    mild = _bands(everything["bands"], "temp_band")[str(frames.temp_band(60.0))]
    # 2026-09-06 (24 rounds, 884 broken), 09-13 (13, 448) and 09-27 (23, 900): 2232 / 60
    assert (mild["n_events"], mild["n_rounds"]) == (3, 60)
    assert mild["mean_score"] == pytest.approx(37.2)

    filtered = fx_viewer_client.get(
        "/api/weather/effects", params={"round_type": "super_sporting"}
    ).json()
    assert filtered["n_events"] == 2
    assert filtered["model"] is None  # 2 events cannot fit 5 parameters
    temp_bands = _bands(filtered["bands"], "temp_band")
    assert list(temp_bands) == [frames.temp_band(60.0)]
    only = temp_bands[str(frames.temp_band(60.0))]
    assert (only["n_events"], only["n_rounds"]) == (2, 37)
    assert only["mean_score"] == pytest.approx(36.0)  # (884 + 448) / 37


def test_turnout_groups_head_counts_by_band(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    _add_seven(fx_session)
    body = fx_viewer_client.get("/api/weather/turnout").json()
    temp = _bands(body, "temp_band")
    expected = {
        frames.temp_band(35.0): (1, 7.0, 7.0),
        frames.temp_band(60.0): (3, 20.0, 23.0),  # head counts 24, 13, 23
        frames.temp_band(75.0): (2, 42.0, 42.0),  # 48, 36
        frames.temp_band(88.0): (1, 29.0, 29.0),
    }
    assert {
        band: (row["n_events"], row["mean_head_count"], row["median_head_count"])
        for band, row in temp.items()
    } == expected
    assert list(temp) == list(expected)  # coldest band first
    precip = _bands(body, "precip_band")
    assert precip[str(frames.precip_band(0.0))]["mean_head_count"] == pytest.approx(28.5)
    assert precip[str(frames.precip_band(0.3))]["mean_head_count"] == pytest.approx(22.0)


def test_time_of_year_groups_bands_and_turnout_winter_to_fall(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    _add_seven(fx_session)
    turnout = _bands(fx_viewer_client.get("/api/weather/turnout").json(), "time_of_year")
    # 2018-12-30 (December) is winter; the August Sundays are summer; the September ones fall.
    assert list(turnout) == ["winter", "summer", "fall"]
    assert {b: (r["n_events"], r["mean_head_count"]) for b, r in turnout.items()} == {
        "winter": (1, 7.0),
        "summer": (3, pytest.approx(113 / 3)),
        "fall": (3, pytest.approx(20.0)),
    }
    bands = _bands(fx_viewer_client.get("/api/weather/effects").json()["bands"], "time_of_year")
    assert list(bands) == ["summer", "fall"]  # the winter Sunday has attendance only
    only_fall = fx_viewer_client.get("/api/weather/turnout", params={"from": "2026-09-01"}).json()
    assert list(_bands(only_fall, "time_of_year")) == ["fall"]


def test_sensitivity_and_club_model_over_the_last_two_seasons(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    _reset_weather(fx_session)
    fx_session.execute(INSERT_2025_ON)
    effects = fx_viewer_client.get("/api/weather/effects").json()
    assert effects["model"]["n_events"] == 84
    assert effects["model"]["sigma2"] > 0

    body = fx_viewer_client.get("/api/weather/sensitivity").json()
    scales = {s["covariate"]: (s["mean"], s["sd"]) for s in body["scales"]}
    assert scales["temp_f"] == pytest.approx((45.380952, 8.900934), rel=1e-5)
    assert scales["gust_mph"] == pytest.approx((11.476190, 6.453683), rel=1e-5)
    assert scales["precip_in"] == pytest.approx((0.0523810, 0.0502432), rel=1e-4)
    assert len(body["shooters"]) == 53  # shooters with >= 10 rounds at those 84 events
    hadley = next(
        s for s in body["shooters"] if s["shooter_id"] == _shooter_id(fx_session, "hadley ike")
    )
    assert hadley["n_rounds"] == 78
    assert all(t["tau2"] >= 0 for t in body["tau2"])
    for shooter in body["shooters"]:
        for term in shooter["terms"]:
            if term["beta"] is None:
                assert term["shrunk"] == 0.0
            else:
                assert abs(term["shrunk"]) <= abs(term["beta"]) + 1e-12


def test_date_window_limits_bands_and_turnout_but_not_the_model(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    _add_seven(fx_session)
    window = {"from": "2026-08-23", "to": "2026-09-06"}
    effects = fx_viewer_client.get("/api/weather/effects", params=window).json()
    assert effects["n_events"] == 7  # club model and count still cover all history
    assert effects["model"]["n_events"] == 6
    temps = _bands(effects["bands"], "temp_band")
    assert sum(b["n_events"] for b in temps.values()) == 3  # 08-23, 08-30, 09-06
    assert frames.temp_band(35.0) not in temps  # 2018 attendance-only day is outside

    turnout = fx_viewer_client.get("/api/weather/turnout", params=window).json()
    assert sum(t["n_events"] for t in _bands(turnout, "temp_band").values()) == 3
    open_start = fx_viewer_client.get("/api/weather/turnout", params={"to": "2018-12-30"}).json()
    assert sum(t["n_events"] for t in _bands(open_start, "temp_band").values()) == 1
    open_end = fx_viewer_client.get("/api/weather/turnout", params={"from": "2026-09-27"}).json()
    assert sum(t["n_events"] for t in _bands(open_end, "temp_band").values()) == 1
