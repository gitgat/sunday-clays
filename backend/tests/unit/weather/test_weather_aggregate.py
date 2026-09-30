"""Event-window aggregation per C7 (pure)."""

from __future__ import annotations

import json
from dataclasses import fields, replace
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from sunday_clays.weather import forecast, sync
from sunday_clays.weather.aggregate import (
    ACCUMULATED_FIELDS,
    WINDOW_FIELDS,
    WindowWeather,
    aggregate_window,
    circular_mean_deg,
    condition_label,
)
from sunday_clays.weather.client import WINDOW_HOURS, HourlyObs, parse_hourly

EVENT = date(2026, 9, 13)
RECORDED = Path(__file__).parents[2] / "fixtures" / "open_meteo" / "archive_2026-09-13.json"
MEASURED = tuple(f.name for f in fields(HourlyObs) if f.name != "ts_local")


def hour(h: int, **overrides: Any) -> HourlyObs:
    base = HourlyObs(
        ts_local=datetime.combine(date(2026, 9, 13), time(h)),
        temp_f=60.0,
        apparent_f=58.0,
        precip_in=0.0,
        rain_in=0.0,
        wind_mph=5.0,
        gust_mph=9.0,
        wind_dir_deg=180.0,
        cloud_pct=10.0,
        humidity_pct=70.0,
        pressure_hpa=1015.0,
        weather_code=0,
    )
    return replace(base, **overrides)


def test_recorded_2026_09_13_window_matches_hand_computed_values() -> None:
    body = json.loads(RECORDED.read_text(encoding="utf-8"))
    rows = parse_hourly(body, ZoneInfo("America/Los_Angeles"))
    # 10:00/11:00/12:00 rows: temp 57.1/59.6/58.8, apparent 52.7/56.1/55.8,
    # wind 10.7/8.8/7.9 from 201/215/219 deg, cloud 100 x3, humidity 78/72/75,
    # pressure 1016.2/1017.1/1017.3; precip 0.004+0.004 (11, 12); gust max(23.7, 18.8)
    assert aggregate_window(EVENT, rows) == WindowWeather(
        temp_f=58.5,
        apparent_f=54.9,
        precip_in=0.008,
        wind_mph=9.1,
        gust_mph=23.7,
        wind_dir_deg=211.0,
        cloud_pct=100.0,
        humidity_pct=75.0,
        pressure_hpa=1016.9,
        condition="windy",
    )


@pytest.mark.parametrize(("rain_hour", "expected_in"), [(12, 0.05), (11, 0.05), (10, 0.0)])
def test_window_uses_preceding_hour_accumulations(rain_hour: int, expected_in: float) -> None:
    hours = [hour(h, precip_in=0.05 if h == rain_hour else 0.0) for h in (10, 11, 12)]
    summary = aggregate_window(EVENT, hours)
    assert summary is not None
    assert summary.precip_in == expected_in
    assert summary.condition == ("rain" if expected_in else "clear")


def test_gust_is_the_max_of_the_11_and_12_rows() -> None:
    hours = [hour(10, gust_mph=30.0), hour(11, gust_mph=12.0), hour(12, gust_mph=21.0)]
    summary = aggregate_window(EVENT, hours)
    assert summary is not None
    assert (summary.gust_mph, summary.condition) == (21.0, "windy")


@pytest.mark.parametrize(
    ("directions", "speeds", "expected"),
    [
        ((350.0, 10.0, 180.0), (10.0, 10.0, 0.0), 0.0),  # wraps through north, not 180
        ((0.0, 90.0, 90.0), (10.0, 10.0, 0.0), 45.0),  # calm hour carries no weight
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), None),  # dead calm has no direction
    ],
)
def test_wind_direction_is_speed_weighted_circular_mean(
    directions: tuple[float, float, float],
    speeds: tuple[float, float, float],
    expected: float | None,
) -> None:
    assert circular_mean_deg(directions, speeds) == expected
    hours = [
        hour(h, wind_dir_deg=d, wind_mph=s)
        for h, d, s in zip((10, 11, 12), directions, speeds, strict=True)
    ]
    summary = aggregate_window(EVENT, hours)
    assert summary is not None
    assert summary.wind_dir_deg == expected


def test_missing_window_row_skips_event() -> None:
    assert aggregate_window(EVENT, [hour(10), hour(11)]) is None


def test_rows_from_another_date_do_not_count() -> None:
    other_day = [
        replace(hour(h), ts_local=datetime.combine(date(2026, 9, 12), time(h)))
        for h in (10, 11, 12)
    ]
    assert aggregate_window(EVENT, [hour(10), hour(11), *other_day]) is None


def test_null_needed_value_skips_event() -> None:
    assert aggregate_window(EVENT, [hour(10), hour(11), hour(12, temp_f=None)]) is None
    # the 10:00 precipitation is not needed (it covers 09:00-10:00), so it may be null
    assert aggregate_window(EVENT, [hour(10, precip_in=None), hour(11), hour(12)]) is not None


@pytest.mark.parametrize("field", MEASURED)
@pytest.mark.parametrize("null_hour", WINDOW_HOURS)
def test_needed_values_match_the_forecast_completeness_rule(null_hour: int, field: str) -> None:
    # aggregate_window and forecast_refresh share one definition of what C7 needs: a null
    # the forecast would reject must skip the event, and every other null must not
    hours = [hour(h, **({field: None} if h == null_hour else {})) for h in WINDOW_HOURS]
    needed = bool(forecast._missing_window_values(hours))
    assert (aggregate_window(EVENT, hours) is None) == needed
    never_read = {"rain_in", "weather_code"}
    preceding_hour = {"precip_in", "gust_mph"}  # the 10:00 values cover 09:00-10:00
    assert needed == (field not in never_read and not (null_hour == 10 and field in preceding_hour))


def test_weather_sync_requires_the_shared_c7_values() -> None:
    # sync, forecast and aggregate take the C7 values from one definition (weather.aggregate)
    assert (*WINDOW_FIELDS, *ACCUMULATED_FIELDS) == sync.REQUIRED_FIELDS


@pytest.mark.parametrize("field", MEASURED)
def test_sync_forecast_and_aggregate_refuse_the_same_nulls(field: str) -> None:
    # 12:00 is read for every C7 value, so a null there is refused by all three or by none
    noon = hour(12, **{field: None})
    window = [hour(10), hour(11), noon]
    refused = {
        "sync": not sync._is_complete(noon),
        "forecast": bool(forecast._missing_window_values(window)),
        "aggregate": aggregate_window(EVENT, window) is None,
    }
    expected = field not in {"rain_in", "weather_code"}
    assert refused == dict.fromkeys(refused, expected)


def test_float32_noise_does_not_flip_rain_threshold() -> None:
    float32_hundredth = 0.009999999776482582  # a Postgres real 0.01, read in binary format
    hours = [hour(h, precip_in=float32_hundredth) for h in (10, 11, 12)]
    summary = aggregate_window(EVENT, hours)
    assert summary is not None
    assert (summary.precip_in, summary.condition) == (0.02, "rain")


@pytest.mark.parametrize(
    ("precip_in", "gust_mph", "cloud_pct", "expected"),
    [
        (0.02, 25.0, 90.0, "rain"),
        (0.019, 20.0, 90.0, "windy"),
        (0.0, 19.9, 75.0, "overcast"),
        (0.0, 0.0, 74.9, "partly_cloudy"),
        (0.0, 0.0, 30.0, "partly_cloudy"),
        (0.0, 0.0, 29.9, "clear"),
    ],
)
def test_condition_label_rule_order(
    precip_in: float, gust_mph: float, cloud_pct: float, expected: str
) -> None:
    label = condition_label(precip_in=precip_in, gust_mph=gust_mph, cloud_pct=cloud_pct)
    assert label == expected
