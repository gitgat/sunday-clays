"""Plan 11 Task 1: GET /api/predictions/next (expected scores only), empty and fixture worlds."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.weather_effects import club_regression
from sunday_clays.api.routes import predictions as predictions_route
from sunday_clays.weather.client import HourlyObs
from sunday_clays.weather.forecast import refresh_forecast

LA = ZoneInfo("America/Los_Angeles")
MONDAY = datetime(2026, 9, 28, 9, 0, tzinfo=LA)  # the fixture's last event was 2026-09-27
TARGET = date(2026, 10, 4)
INSERT_2025_ON = text(
    "INSERT INTO event_weather (event_date, temp_f, apparent_f, precip_in, wind_mph, gust_mph,"
    " wind_dir_deg, cloud_pct, humidity_pct, pressure_hpa, condition, source)"
    " SELECT event_date, 30 + EXTRACT(DAY FROM event_date), 28 + EXTRACT(DAY FROM event_date),"
    " CASE WHEN EXTRACT(DAY FROM event_date)::int % 2 = 1 THEN 0.1 ELSE 0 END,"
    " EXTRACT(MONTH FROM event_date), 2 * EXTRACT(MONTH FROM event_date), 200,"
    " (7 * EXTRACT(DAY FROM event_date)::int) % 100, 60, 1015, 'clear', 'archive'"
    " FROM events WHERE results_complete AND event_date >= DATE '2025-01-01'"
)


class FakeForecast:
    """A Plan 05 `HourlySource` returning fixed forecast hours for TARGET."""

    def __init__(self, hours: list[HourlyObs]) -> None:
        self.hours = hours

    def archive(self, start: date, end: date) -> list[HourlyObs]:
        raise AssertionError("predictions never read the archive")

    def forecast(self, *, past_days: int, forecast_days: int) -> list[HourlyObs]:
        return self.hours


def _hours(*, temp: float, gust: float, skip: tuple[int, ...] = ()) -> list[HourlyObs]:
    # Window per C7: mean temp/cloud of 10-12, max gust of 11-12, rain = sum of 11 and 12.
    return [
        HourlyObs(
            ts_local=datetime.combine(TARGET, time(h)),  # naive local wall-clock (Plan 05)
            temp_f=temp,
            apparent_f=temp - 2,
            precip_in=0.01,
            rain_in=0.01,
            wind_mph=gust / 2,
            gust_mph=gust,
            wind_dir_deg=200.0,
            cloud_pct=80.0,
            humidity_pct=90.0,
            pressure_hpa=1010.0,
            weather_code=61,
        )
        for h in range(24)
        if h not in skip
    ]


@pytest.fixture
def monday(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(predictions_route, "local_now", lambda tz: MONDAY)


def _shooter_id(session: Session, name_key: str) -> int:
    return int(
        session.execute(
            text("SELECT shooter_id FROM shooter_aliases WHERE name_key = :k"), {"k": name_key}
        ).scalar_one()
    )


def _get(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/predictions/next")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_predictions_before_pipeline_are_empty(viewer_client: TestClient, monday: None) -> None:
    assert _get(viewer_client) == {
        "target_date": "2026-10-04",
        "model_ready": False,
        "forecast": None,
        "difficulty": None,
        "difficulty_sd": None,
        "difficulty_source": "none",
        "field_median": None,
        "expected_turnout": 0.0,
        "shooters": [],
    }


def test_predictions_for_next_sunday_from_the_fixture(
    fx_session: Session, fx_viewer_client: TestClient, monday: None
) -> None:
    body = _get(fx_viewer_client)
    assert (body["target_date"], body["model_ready"], body["forecast"]) == (
        "2026-10-04",
        True,
        None,
    )
    # No forecast is stored, so the day difficulty is the intercept-only fit (typical Sunday).
    intercept = club_regression(fx_session, (), ())
    assert intercept is not None
    assert body["difficulty_source"] == "intercept"
    assert body["difficulty"] == pytest.approx(intercept.coef[0])
    assert body["difficulty_sd"] == pytest.approx(math.sqrt(intercept.sigma2))
    shooters = body["shooters"]
    # The last 13 scored events before 2026-10-04 run 2026-06-14 .. 2026-09-27; 80 shooters
    # attended at least one of them, 353 attendances in all.
    assert len(shooters) == 80
    assert body["expected_turnout"] == pytest.approx(353 / 13)
    by_id = {s["shooter_id"]: s for s in shooters}
    assert by_id[_shooter_id(fx_session, "hadley ike")]["attend_prob"] == 1.0
    assert by_id[_shooter_id(fx_session, "kaplan noel")]["attend_prob"] == pytest.approx(11 / 13)
    assert by_id[_shooter_id(fx_session, "finnegan stanton")]["attend_prob"] == pytest.approx(
        4 / 13
    )
    assert _shooter_id(fx_session, "gilchrist melvin") not in by_id
    # Expected score only: no win or podium odds anywhere, and never ordered by score.
    for s in shooters:
        assert set(s) == {"shooter_id", "display_name", "attend_prob", "expected", "sd"}
        assert 0.0 <= s["expected"] <= 50.0
        assert s["sd"] > 0
    names = [(s["display_name"], s["shooter_id"]) for s in shooters]
    assert names == sorted(names)
    assert body["field_median"] in [s["expected"] for s in shooters]
    assert not {"p_win", "p_podium", "win_chance"} & set(body)


def test_forecast_sets_weather_difficulty(
    fx_session: Session, fx_viewer_client: TestClient, monday: None
) -> None:
    fx_session.execute(text("DELETE FROM event_weather"))
    fx_session.execute(INSERT_2025_ON)
    refresh_forecast(fx_session, FakeForecast(_hours(temp=50.0, gust=18.0)), now_local=MONDAY)
    body = _get(fx_viewer_client)
    assert body["difficulty_source"] == "weather"
    forecast = body["forecast"]
    assert (forecast["temp_f"], forecast["gust_mph"], forecast["cloud_pct"]) == (50.0, 18.0, 80.0)
    assert (forecast["precip_in"], forecast["condition"]) == (0.02, "rain")
    model = fx_viewer_client.get("/api/weather/effects").json()["model"]
    x = {"intercept": 1.0, "temp_f": 50.0, "gust_mph": 18.0, "precip_in": 0.02, "cloud_pct": 80.0}
    assert body["difficulty"] == pytest.approx(
        sum(t["coef"] * x[t["name"]] for t in model["terms"])
    )
    assert body["difficulty_sd"] == pytest.approx(math.sqrt(model["sigma2"]))


def test_prediction_cache_key_includes_forecast_fetched_at(
    fx_session: Session, fx_viewer_client: TestClient, monday: None
) -> None:
    fx_session.execute(text("DELETE FROM event_weather"))
    fx_session.execute(INSERT_2025_ON)
    version = text("SELECT value FROM app_state WHERE key = 'data_version'")
    before = fx_session.execute(version).scalar_one()
    assert _get(fx_viewer_client)["difficulty_source"] == "intercept"  # memoised: no forecast

    refresh_forecast(fx_session, FakeForecast(_hours(temp=50.0, gust=18.0)), now_local=MONDAY)
    first = _get(fx_viewer_client)
    later = MONDAY + timedelta(hours=6)
    refresh_forecast(fx_session, FakeForecast(_hours(temp=62.0, gust=5.0)), now_local=later)
    second = _get(fx_viewer_client)

    assert fx_session.execute(version).scalar_one() == before  # no rebuild or recompute
    assert first["difficulty_source"] == second["difficulty_source"] == "weather"
    assert first["forecast"]["fetched_at"] != second["forecast"]["fetched_at"]
    assert second["forecast"]["temp_f"] == 62.0
    assert first["difficulty"] != second["difficulty"]


def test_incomplete_forecast_window_is_ignored(
    fx_session: Session, fx_viewer_client: TestClient, monday: None
) -> None:
    # `refresh_forecast` refuses an incomplete window, so store one directly.
    fx_session.execute(text("DELETE FROM event_weather"))
    hours = _hours(temp=50.0, gust=18.0, skip=(11,))
    fx_session.execute(
        text(
            "INSERT INTO forecast_cache (target_date, payload, fetched_at)"
            " VALUES (:d, CAST(:p AS jsonb), :f)"
        ),
        {
            "d": TARGET,
            "p": json.dumps(
                {
                    "target_date": TARGET.isoformat(),
                    "hours": TypeAdapter(list[HourlyObs]).dump_python(hours, mode="json"),
                }
            ),
            "f": MONDAY,
        },
    )
    body = _get(fx_viewer_client)
    params = fx_session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_params'")
    ).scalar_one()
    assert body["forecast"] is None
    assert (body["difficulty_source"], body["difficulty"]) == ("prior", None)
    assert body["difficulty_sd"] == pytest.approx(math.sqrt(params["difficulty_var"]))
    assert len(body["shooters"]) == 80


def test_local_now_reads_the_clock_in_the_club_zone() -> None:
    # Every route test pins local_now; this one runs the real clock seam.
    before = datetime.now(LA)
    now = predictions_route.local_now("America/Los_Angeles")
    after = datetime.now(LA)
    assert str(now.tzinfo) == "America/Los_Angeles"
    assert before <= now <= after


def test_no_scored_sunday_before_the_target_has_no_field(
    fx_viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    long_ago = datetime(2000, 1, 3, 9, 0, tzinfo=LA)
    monkeypatch.setattr(predictions_route, "local_now", lambda tz: long_ago)
    body = _get(fx_viewer_client)
    assert (body["target_date"], body["model_ready"]) == ("2000-01-09", True)
    assert (body["shooters"], body["field_median"], body["expected_turnout"]) == ([], None, 0.0)


def test_deceased_shooters_are_left_out_of_the_field(
    fx_session: Session, fx_viewer_client: TestClient, monday: None
) -> None:
    hadley = _shooter_id(fx_session, "hadley ike")
    fx_session.execute(
        text("UPDATE shooter_profiles SET status = 'deceased' WHERE shooter_id = :i"), {"i": hadley}
    )
    # hadley ike shot all 13 recent Sundays: one fewer shooter, turnout down by 13/13.
    after = _get(fx_viewer_client)
    assert hadley not in {s["shooter_id"] for s in after["shooters"]}
    assert len(after["shooters"]) == 79
    assert after["expected_turnout"] == pytest.approx((353 - 13) / 13 + 0.0)
