"""Open-Meteo client: requests, local-time conversion, parsing and errors."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

from sunday_clays.config import Settings
from sunday_clays.weather.client import (
    HOURLY_VARIABLES,
    HourlyObs,
    OpenMeteoClient,
    WeatherApiError,
    parse_hourly,
)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
LA = ZoneInfo("America/Los_Angeles")
RECORDED = Path(__file__).parents[2] / "fixtures" / "open_meteo" / "archive_2026-09-13.json"
ARGON2_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$zAaUsgjT4w79Q1k1Gfv6xA"
    "$8hnJDkRbYWn07p0LLDJamRY8+s/GuMmthqmaBq6Aris"
)
ALL_VARIABLES = (
    "temperature_2m,apparent_temperature,precipitation,rain,wind_speed_10m,wind_gusts_10m,"
    "wind_direction_10m,cloud_cover,relative_humidity_2m,pressure_msl,weather_code"
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


def recorded() -> dict[str, Any]:
    body: dict[str, Any] = json.loads(RECORDED.read_text(encoding="utf-8"))
    return body


def utc_stamp(year: int, month: int, day: int, hour: int) -> int:
    return int(datetime(year, month, day, hour, tzinfo=UTC).timestamp())


def body_for(stamps: list[int], **columns: list[Any]) -> dict[str, Any]:
    """A complete Open-Meteo body (keys as recorded); unset columns are 1.0."""
    hourly: dict[str, list[Any]] = {"time": stamps}
    for name in HOURLY_VARIABLES:
        hourly[name] = columns.get(name, [1.0] * len(stamps))
    return {
        "latitude": 45.377853,
        "longitude": -122.816895,
        "generationtime_ms": 0.3,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 79.0,
        "hourly_units": dict(UNITS),
        "hourly": hourly,
    }


def make_client() -> OpenMeteoClient:
    return OpenMeteoClient(
        archive_url=ARCHIVE_URL,
        forecast_url=FORECAST_URL,
        lat=45.3525,
        lon=-122.8082,
        timezone="America/Los_Angeles",
    )


def test_archive_sends_club_location_units_and_unixtime() -> None:
    with respx.mock() as router:
        route = router.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=recorded()))
        with make_client() as client:
            client.archive(date(2026, 9, 13), date(2026, 9, 14))
    assert dict(route.calls.last.request.url.params) == {
        "latitude": "45.3525",
        "longitude": "-122.8082",
        "start_date": "2026-09-13",
        "end_date": "2026-09-14",
        "hourly": ALL_VARIABLES,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timeformat": "unixtime",
    }


def test_forecast_sends_past_and_forecast_days() -> None:
    with respx.mock() as router:
        route = router.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=recorded()))
        with make_client() as client:
            client.forecast(past_days=7, forecast_days=1)
    assert dict(route.calls.last.request.url.params) == {
        "latitude": "45.3525",
        "longitude": "-122.8082",
        "past_days": "7",
        "forecast_days": "1",
        "hourly": ALL_VARIABLES,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timeformat": "unixtime",
    }


def test_from_settings_maps_every_client_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DATABASE_URL_FILE",
        "SESSION_SECRET_FILE",
        "VIEWER_PASSWORD_HASH_FILE",
        "ADMIN_PASSWORD_HASH_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.model_validate(
        {
            "database_url": "postgresql+psycopg://unused:unused@localhost:5432/unused",
            "session_secret": "0123456789abcdef0123456789abcdef",
            "viewer_password_hash": ARGON2_HASH,
            "admin_password_hash": ARGON2_HASH,
            "app_version": "test",
            "club_lat": 1.5,
            "club_lon": -2.5,
            "timezone": "UTC",
            "open_meteo_archive_url": "https://a.test/archive",
            "open_meteo_forecast_url": "https://f.test/forecast",
        }
    )
    with respx.mock() as router:
        archive = router.get("https://a.test/archive").mock(
            return_value=httpx.Response(200, json=recorded())
        )
        forecast = router.get("https://f.test/forecast").mock(
            return_value=httpx.Response(200, json=recorded())
        )
        with OpenMeteoClient.from_settings(settings) as client:
            rows = client.archive(date(2026, 9, 13), date(2026, 9, 14))
            client.forecast(past_days=0, forecast_days=1)
    sent_archive = archive.calls.last.request.url.params
    sent_forecast = forecast.calls.last.request.url.params
    # each URL receives its own kind of request, at the configured coordinates
    assert (sent_archive.get("start_date"), sent_forecast.get("past_days")) == (
        "2026-09-13",
        "0",
    )
    for params in (sent_archive, sent_forecast):
        assert (params["latitude"], params["longitude"]) == ("1.5", "-2.5")
    # timezone="UTC": the first recorded stamp, 2026-09-13T00:00Z, stays at 00:00
    assert rows[0].ts_local == datetime.combine(date(2026, 9, 13), time(0))


def test_recorded_archive_rows_are_local_wall_clock_hours() -> None:
    with respx.mock() as router:
        router.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=recorded()))
        with make_client() as client:
            rows = client.archive(date(2026, 9, 13), date(2026, 9, 14))
    assert len(rows) == 48
    # 2026-09-13T00:00Z is 17:00 PDT on the 12th
    assert rows[0].ts_local == datetime.combine(date(2026, 9, 12), time(17))
    assert rows[-1].ts_local == datetime.combine(date(2026, 9, 14), time(16))
    ten = next(row for row in rows if row.ts_local == datetime.combine(date(2026, 9, 13), time(10)))
    assert ten == HourlyObs(
        ts_local=datetime.combine(date(2026, 9, 13), time(10)),
        temp_f=57.1,
        apparent_f=52.7,
        precip_in=0.0,
        rain_in=0.0,
        wind_mph=10.7,
        gust_mph=23.7,
        wind_dir_deg=201.0,
        cloud_pct=100.0,
        humidity_pct=78.0,
        pressure_hpa=1016.2,
        weather_code=3,
    )


def test_winter_timestamps_use_standard_time_offset() -> None:
    # 18:00Z-20:00Z on 2026-01-04 are 10:00-12:00 PST (UTC-8), not PDT (UTC-7)
    stamps = [utc_stamp(2026, 1, 4, h) for h in (18, 19, 20)]
    body = body_for(stamps)
    rows = parse_hourly(body, LA)
    assert [row.ts_local for row in rows] == [
        datetime.combine(date(2026, 1, 4), time(10)),
        datetime.combine(date(2026, 1, 4), time(11)),
        datetime.combine(date(2026, 1, 4), time(12)),
    ]


def test_fall_back_repeated_local_hour_keeps_first() -> None:
    # 08:00Z = 01:00 PDT; 09:00Z = 01:00 PST (clocks fell back); 10:00Z = 02:00 PST
    stamps = [
        utc_stamp(2025, 11, 2, 8),
        utc_stamp(2025, 11, 2, 9),
        utc_stamp(2025, 11, 2, 10),
    ]
    rows = parse_hourly(body_for(stamps, temperature_2m=[40.0, 41.0, 42.0]), LA)
    assert [(row.ts_local, row.temp_f) for row in rows] == [
        (datetime.combine(date(2025, 11, 2), time(1)), 40.0),
        (datetime.combine(date(2025, 11, 2), time(2)), 42.0),
    ]


def test_fall_back_keeps_daylight_hour_whatever_the_array_order() -> None:
    # same hours as above, listed latest first: the earlier UTC stamp (01:00 PDT) still wins
    stamps = [
        utc_stamp(2025, 11, 2, 10),
        utc_stamp(2025, 11, 2, 9),
        utc_stamp(2025, 11, 2, 8),
    ]
    rows = parse_hourly(body_for(stamps, temperature_2m=[42.0, 41.0, 40.0]), LA)
    assert [(row.ts_local, row.temp_f) for row in rows] == [
        (datetime.combine(date(2025, 11, 2), time(1)), 40.0),
        (datetime.combine(date(2025, 11, 2), time(2)), 42.0),
    ]


def test_each_variable_maps_to_its_column() -> None:
    body = body_for(
        [utc_stamp(2026, 9, 13, 17)],
        temperature_2m=[1.5],
        apparent_temperature=[2.5],
        precipitation=[0.03],
        rain=[0.02],
        wind_speed_10m=[5.5],
        wind_gusts_10m=[6.5],
        wind_direction_10m=[270],
        cloud_cover=[40],
        relative_humidity_2m=[55],
        pressure_msl=[1010.5],
        weather_code=[61],
    )
    assert parse_hourly(body, LA) == [
        HourlyObs(
            ts_local=datetime.combine(date(2026, 9, 13), time(10)),
            temp_f=1.5,
            apparent_f=2.5,
            precip_in=0.03,
            rain_in=0.02,
            wind_mph=5.5,
            gust_mph=6.5,
            wind_dir_deg=270.0,
            cloud_pct=40.0,
            humidity_pct=55.0,
            pressure_hpa=1010.5,
            weather_code=61,
        )
    ]


def test_null_values_become_none() -> None:
    nulls: dict[str, list[Any]] = {name: [None] for name in HOURLY_VARIABLES}
    rows = parse_hourly(body_for([utc_stamp(2026, 9, 20, 17)], **nulls), LA)
    assert rows == [
        HourlyObs(
            ts_local=datetime.combine(date(2026, 9, 20), time(10)),
            temp_f=None,
            apparent_f=None,
            precip_in=None,
            rain_in=None,
            wind_mph=None,
            gust_mph=None,
            wind_dir_deg=None,
            cloud_pct=None,
            humidity_pct=None,
            pressure_hpa=None,
            weather_code=None,
        )
    ]


def test_unexpected_units_are_rejected() -> None:
    body = body_for([utc_stamp(2026, 9, 13, 17)])
    body["hourly_units"]["temperature_2m"] = "°C"
    with pytest.raises(WeatherApiError, match="unexpected units"):
        parse_hourly(body, LA)


def test_missing_variable_is_rejected() -> None:
    body = body_for([utc_stamp(2026, 9, 13, 17)])
    del body["hourly"]["pressure_msl"]
    with pytest.raises(WeatherApiError, match="malformed"):
        parse_hourly(body, LA)


def test_mismatched_array_lengths_are_rejected() -> None:
    body = body_for([utc_stamp(2026, 9, 13, 17)], temperature_2m=[1.0, 2.0])
    with pytest.raises(WeatherApiError, match="different lengths"):
        parse_hourly(body, LA)


def test_non_numeric_value_is_rejected() -> None:
    body = body_for([utc_stamp(2026, 9, 13, 17)], temperature_2m=["n/a"])
    with pytest.raises(WeatherApiError, match="non-numeric"):
        parse_hourly(body, LA)


@pytest.mark.parametrize(
    "value",
    [True, False, float("nan"), float("inf"), float("-inf"), "12.5", "n/a", [1.0]],
)
def test_measurement_must_be_a_finite_json_number(value: Any) -> None:
    # no coercion: a bool is not 1.0 and a numeric string is not a number
    body = body_for([utc_stamp(2026, 9, 13, 17)], temperature_2m=[value])
    with pytest.raises(WeatherApiError, match="non-numeric"):
        parse_hourly(body, LA)


@pytest.mark.parametrize("value", [True, False, 3.7, -0.5, float("nan"), float("inf"), "3", "n/a"])
def test_weather_code_must_be_integral(value: Any) -> None:
    # 3.7 must not be truncated to code 3, nor "3" parsed as one
    body = body_for([utc_stamp(2026, 9, 13, 17)], weather_code=[value])
    with pytest.raises(WeatherApiError, match="non-numeric"):
        parse_hourly(body, LA)


def test_integral_float_weather_code_becomes_int() -> None:
    body = body_for([utc_stamp(2026, 9, 13, 17)], weather_code=[61.0])
    (row,) = parse_hourly(body, LA)
    assert row.weather_code == 61
    assert type(row.weather_code) is int


@pytest.mark.parametrize("stamp", [True, 1789257600.5, "1789257600", None])
def test_timestamp_must_be_integral(stamp: Any) -> None:
    # the same strictness as weather codes: never truncate or parse a stamp
    with pytest.raises(WeatherApiError, match="non-numeric"):
        parse_hourly(body_for([stamp]), LA)


@pytest.mark.parametrize("stamp", [10**17, -(10**17), 10**12, 10**20])
def test_out_of_range_timestamp_is_rejected(stamp: int) -> None:
    # gmtime() fails with OSError (EOVERFLOW) near 1e17 on macOS and Linux; the
    # others raise ValueError (year out of range) or OverflowError (beyond time_t)
    with pytest.raises(WeatherApiError, match="out-of-range"):
        parse_hourly(body_for([stamp]), LA)


def test_http_error_reason_surfaces() -> None:
    reason = "Parameter 'start_date' is out of allowed range"
    with respx.mock() as router:
        router.get(ARCHIVE_URL).mock(
            return_value=httpx.Response(400, json={"error": True, "reason": reason})
        )
        with (
            make_client() as client,
            pytest.raises(WeatherApiError, match="HTTP 400: Parameter"),
        ):
            client.archive(date(1900, 1, 1), date(1900, 1, 2))


def test_http_error_without_json_body_shows_text() -> None:
    with respx.mock() as router:
        router.get(ARCHIVE_URL).mock(return_value=httpx.Response(502, text="Bad Gateway"))
        with (
            make_client() as client,
            pytest.raises(WeatherApiError, match="HTTP 502: Bad Gateway"),
        ):
            client.archive(date(2026, 9, 13), date(2026, 9, 14))


def test_invalid_json_on_success_is_rejected() -> None:
    with respx.mock() as router:
        router.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, text="<html>busy</html>"))
        with (
            make_client() as client,
            pytest.raises(WeatherApiError, match="invalid JSON"),
        ):
            client.archive(date(2026, 9, 13), date(2026, 9, 14))


def test_transport_error_is_wrapped() -> None:
    with respx.mock() as router:
        router.get(FORECAST_URL).mock(side_effect=httpx.ConnectError)
        with (
            make_client() as client,
            pytest.raises(WeatherApiError, match="ConnectError"),
        ):
            client.forecast(past_days=0, forecast_days=1)
