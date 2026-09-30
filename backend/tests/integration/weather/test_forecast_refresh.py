"""forecast_refresh: next Sunday's hours go to forecast_cache, never weather_hourly."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any, Self
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from sqlalchemy import Table, func, select
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.jobs.handlers import load_handlers
from sunday_clays.models import Base
from sunday_clays.weather import forecast as forecast_module
from sunday_clays.weather.client import HOURLY_VARIABLES, HourlyObs, WeatherApiError
from sunday_clays.weather.forecast import (
    StoredForecast,
    forecast_refresh_handler,
    load_forecast,
    refresh_forecast,
)

LA = ZoneInfo("America/Los_Angeles")
MONDAY = datetime(2026, 9, 28, 9, 0, tzinfo=LA)  # next event Sunday: 2026-10-04
TARGET = date(2026, 10, 4)
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARGON2_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$zAaUsgjT4w79Q1k1Gfv6xA"
    "$8hnJDkRbYWn07p0LLDJamRY8+s/GuMmthqmaBq6Aris"
)
UNITS = {
    "time": "unixtime",
    "temperature_2m": "°F",
    "apparent_temperature": "°F",
    "precipitation": "inch",
    "rain": "inch",
    "wind_speed_10m": "mp/h",
    "wind_gusts_10m": "mp/h",
    "wind_direction_10m": "°",
    "cloud_cover": "%",
    "relative_humidity_2m": "%",
    "pressure_msl": "hPa",
    "weather_code": "wmo code",
}
ALL_HOURS = tuple(range(24))
SPRING_FORWARD_HOURS = tuple(h for h in ALL_HOURS if h != 2)  # 02:00-02:59 never happens


def table(name: str) -> Table:
    return Base.metadata.tables[name]


def day(target: date, temp_f: float = 55.0) -> list[HourlyObs]:
    return [
        HourlyObs(
            ts_local=datetime.combine(target, time(h)),
            temp_f=temp_f + h / 10,
            apparent_f=temp_f - 2,
            precip_in=0.01 if h == 11 else 0.0,
            rain_in=0.0,
            wind_mph=6.0,
            gust_mph=14.0,
            wind_dir_deg=225.0,
            cloud_pct=60.0,
            humidity_pct=80.0,
            pressure_hpa=1012.5,
            weather_code=None if h == 0 else 2,
        )
        for h in range(24)
    ]


def with_values(hours: list[HourlyObs], hour: int, **changes: Any) -> list[HourlyObs]:
    """``hours`` with the given fields of the ``hour``:00 row replaced."""
    return [replace(obs, **changes) if obs.ts_local.hour == hour else obs for obs in hours]


class FakeForecast:
    """Stands in for Open-Meteo's forecast API; records every request."""

    def __init__(self, hours: list[HourlyObs]) -> None:
        self.hours = hours
        self.calls: list[tuple[int, int]] = []

    def archive(self, start: date, end: date) -> list[HourlyObs]:
        raise AssertionError("forecast_refresh must not call the archive API")

    def forecast(self, *, past_days: int, forecast_days: int) -> list[HourlyObs]:
        self.calls.append((past_days, forecast_days))
        return list(self.hours)


def cache_rows(session: Session) -> list[Any]:
    cache = table("forecast_cache")
    return list(session.execute(select(cache)).all())


@pytest.fixture
def weather_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    for name in (
        "DATABASE_URL_FILE",
        "SESSION_SECRET_FILE",
        "VIEWER_PASSWORD_HASH_FILE",
        "ADMIN_PASSWORD_HASH_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    monkeypatch.setenv("SESSION_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("VIEWER_PASSWORD_HASH", ARGON2_HASH)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", ARGON2_HASH)
    monkeypatch.setenv("APP_VERSION", "test")
    monkeypatch.setenv("OPEN_METEO_ARCHIVE_URL", ARCHIVE_URL)
    monkeypatch.setenv("OPEN_METEO_FORECAST_URL", FORECAST_URL)
    monkeypatch.setenv("TIMEZONE", "America/Los_Angeles")
    monkeypatch.setenv("WEATHER_ENABLED", "true")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_refresh_stores_next_sundays_hours(session: Session) -> None:
    source = FakeForecast(day(date(2026, 10, 3)) + day(TARGET) + day(date(2026, 10, 5)))
    assert refresh_forecast(session, source, now_local=MONDAY) == TARGET
    assert source.calls == [(0, 8)]  # 6 days ahead + 2 covers the target's UTC hours
    assert load_forecast(session, TARGET) == StoredForecast(
        target_date=TARGET, hours=tuple(day(TARGET)), fetched_at=MONDAY
    )


def test_refresh_replaces_the_previous_forecast(session: Session) -> None:
    refresh_forecast(session, FakeForecast(day(TARGET, temp_f=50.0)), now_local=MONDAY)
    later = MONDAY + timedelta(hours=6)
    refresh_forecast(session, FakeForecast(day(TARGET, temp_f=65.0)), now_local=later)
    assert len(cache_rows(session)) == 1
    stored = load_forecast(session, TARGET)
    assert stored is not None
    assert (stored.hours[10].temp_f, stored.fetched_at) == (66.0, later)


def test_refresh_without_target_hours_raises_and_keeps_old_row(
    session: Session,
) -> None:
    refresh_forecast(session, FakeForecast(day(TARGET)), now_local=MONDAY)
    with pytest.raises(WeatherApiError, match="no hours for 2026-10-04"):
        refresh_forecast(
            session,
            FakeForecast(day(date(2026, 10, 3))),
            now_local=MONDAY + timedelta(hours=6),
        )
    stored = load_forecast(session, TARGET)
    assert stored is not None
    assert stored.fetched_at == MONDAY


@pytest.mark.parametrize(
    ("hours", "missing"),
    [
        pytest.param(
            [obs for obs in day(TARGET) if obs.ts_local.hour != 11], "11:00 row", id="no-11:00"
        ),
        pytest.param(with_values(day(TARGET), 10, temp_f=None), "10:00 temp_f", id="temp"),
        pytest.param(
            with_values(day(TARGET), 12, wind_dir_deg=None), "12:00 wind_dir_deg", id="wind-dir"
        ),
        pytest.param(with_values(day(TARGET), 11, precip_in=None), "11:00 precip_in", id="precip"),
        pytest.param(with_values(day(TARGET), 12, gust_mph=None), "12:00 gust_mph", id="gust"),
    ],
)
def test_refresh_with_an_incomplete_window_raises_and_keeps_old_row(
    session: Session, hours: list[HourlyObs], missing: str
) -> None:
    refresh_forecast(session, FakeForecast(day(TARGET)), now_local=MONDAY)
    with pytest.raises(
        WeatherApiError, match=f"2026-10-04 is missing event-window values: {missing}$"
    ):
        refresh_forecast(session, FakeForecast(hours), now_local=MONDAY + timedelta(hours=6))
    assert load_forecast(session, TARGET) == StoredForecast(
        target_date=TARGET, hours=tuple(day(TARGET)), fetched_at=MONDAY
    )


def test_refresh_keeps_nulls_the_window_does_not_need(session: Session) -> None:
    # C7: precipitation and gusts cover the preceding hour, so only 11:00 and 12:00 need
    # them; rain_in and weather_code are never aggregated; other hours are stored as they are.
    hours = with_values(day(TARGET), 10, precip_in=None, gust_mph=None)
    hours = with_values(hours, 11, rain_in=None, weather_code=None)
    hours = with_values(hours, 9, temp_f=None, wind_dir_deg=None)
    refresh_forecast(session, FakeForecast(hours), now_local=MONDAY)
    assert load_forecast(session, TARGET) == StoredForecast(
        target_date=TARGET, hours=tuple(hours), fetched_at=MONDAY
    )


def test_load_forecast_without_a_row_returns_none(session: Session) -> None:
    assert load_forecast(session, TARGET) is None


def test_forecast_refresh_does_not_touch_weather_hourly(session: Session) -> None:
    refresh_forecast(session, FakeForecast(day(TARGET)), now_local=MONDAY)
    hourly = table("weather_hourly")
    assert session.scalar(select(func.count()).select_from(hourly)) == 0


def test_the_worker_discovers_the_forecast_refresh_handler() -> None:
    assert load_handlers()["forecast_refresh"] is forecast_refresh_handler


@pytest.fixture
def freeze_clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[datetime], None]:
    """Make the forecast module's ``datetime.now(tz)`` return a fixed instant."""

    def freeze(instant: datetime) -> None:
        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz: tzinfo | None = None) -> Self:
                return cls.fromtimestamp(instant.timestamp(), tz)

        monkeypatch.setattr(forecast_module, "datetime", FrozenDatetime)

    return freeze


def forecast_response(now: datetime) -> Callable[[httpx.Request], httpx.Response]:
    """Open-Meteo's forecast API as called at ``now``: constant weather for every hour
    from that UTC day's midnight, ``forecast_days`` whole UTC days long."""
    midnight = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    def respond(request: httpx.Request) -> httpx.Response:
        days = int(request.url.params["forecast_days"])
        stamps = [int(midnight.timestamp()) + 3600 * i for i in range(24 * days)]
        hourly: dict[str, list[Any]] = {"time": stamps}
        hourly.update({name: [1.0] * len(stamps) for name in HOURLY_VARIABLES})
        body = {
            "latitude": 45.33783,
            "longitude": -122.817825,
            "generationtime_ms": 0.3,
            "utc_offset_seconds": 0,
            "timezone": "GMT",
            "timezone_abbreviation": "GMT",
            "elevation": 79.0,
            "hourly_units": UNITS,
            "hourly": hourly,
        }
        return httpx.Response(200, json=body)

    return respond


@pytest.mark.parametrize(
    ("now", "target", "forecast_days", "local_hours"),
    [
        pytest.param(
            datetime(2026, 10, 4, 8, 0, tzinfo=LA), TARGET, 2, ALL_HOURS, id="sun-morning"
        ),
        pytest.param(
            datetime(2026, 10, 4, 12, 0, tzinfo=LA),
            date(2026, 10, 11),
            9,
            ALL_HOURS,
            id="sun-12:00",
        ),
        pytest.param(
            datetime(2026, 10, 3, 23, 59, tzinfo=LA), TARGET, 3, ALL_HOURS, id="sat-23:59"
        ),
        # the repeated 01:00 is stored once (its daylight-time occurrence)
        pytest.param(
            datetime(2026, 11, 1, 8, 0, tzinfo=LA),
            date(2026, 11, 1),
            2,
            ALL_HOURS,
            id="fall-back-sun",
        ),
        pytest.param(
            datetime(2027, 3, 14, 8, 0, tzinfo=LA),
            date(2027, 3, 14),
            2,
            SPRING_FORWARD_HOURS,
            id="spring-fwd-sun",
        ),
    ],
)
def test_forecast_refresh_handler_fetches_open_meteo(
    session: Session,
    weather_env: pytest.MonkeyPatch,
    freeze_clock: Callable[[datetime], None],
    now: datetime,
    target: date,
    forecast_days: int,
    local_hours: tuple[int, ...],
) -> None:
    freeze_clock(now)
    with respx.mock() as router:
        route = router.get(FORECAST_URL).mock(side_effect=forecast_response(now))
        forecast_refresh_handler(session, {})
    assert route.call_count == 1
    params = route.calls.last.request.url.params
    assert (params["past_days"], params["forecast_days"]) == ("0", str(forecast_days))
    assert [row.target_date for row in cache_rows(session)] == [target]
    stored = load_forecast(session, target)
    assert stored is not None
    assert stored.fetched_at == now
    assert [obs.ts_local for obs in stored.hours] == [
        datetime.combine(target, time(h)) for h in local_hours
    ]


def test_forecast_refresh_handler_noop_when_disabled(
    session: Session, weather_env: pytest.MonkeyPatch
) -> None:
    weather_env.setenv("WEATHER_ENABLED", "false")
    get_settings.cache_clear()
    with respx.mock(assert_all_called=False) as router:
        route = router.get(FORECAST_URL).mock(side_effect=forecast_response(MONDAY))
        forecast_refresh_handler(session, {})
    assert not route.called
    assert cache_rows(session) == []
