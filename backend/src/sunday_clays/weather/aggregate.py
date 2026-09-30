"""Event-window weather (C7): the 10:00, 11:00 and 12:00 local rows -> one summary.

Values are rounded (1 dp; precipitation 3 dp; direction to whole degrees) before
the condition label is chosen, so float32 storage noise (a ``real`` 0.01 read in binary
format or cast to double precision is 0.0099999998) never moves a value across a threshold.

``WINDOW_FIELDS``, ``ACCUMULATION_HOURS`` and ``ACCUMULATED_FIELDS`` are the one definition
of what the aggregation reads; ``weather.forecast`` checks a forecast against the same names,
and ``weather.sync`` stores only hours that have all of them.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from statistics import fmean
from typing import Final

from sunday_clays.weather.client import WINDOW_HOURS, HourlyObs

WINDOW_FIELDS: Final[tuple[str, ...]] = (
    "temp_f",
    "apparent_f",
    "wind_mph",
    "wind_dir_deg",
    "cloud_pct",
    "humidity_pct",
    "pressure_hpa",
)
"""Read from every window row: means, and a speed-weighted circular mean for direction."""
ACCUMULATION_HOURS: Final[tuple[int, ...]] = (11, 12)
"""Open-Meteo precipitation and gusts cover the preceding hour, so only these rows count."""
ACCUMULATED_FIELDS: Final[tuple[str, ...]] = ("precip_in", "gust_mph")
"""Read from the ``ACCUMULATION_HOURS`` rows only: precipitation summed, gusts maxed."""
RAIN_IN: Final = 0.02
WINDY_GUST_MPH: Final = 20.0
OVERCAST_PCT: Final = 75.0
PARTLY_CLOUDY_PCT: Final = 30.0


@dataclass(frozen=True)
class WindowWeather:
    """One event's window summary; fields match the ``event_weather`` columns (C4)."""

    temp_f: float
    apparent_f: float
    precip_in: float
    wind_mph: float
    gust_mph: float
    wind_dir_deg: float | None
    cloud_pct: float
    humidity_pct: float
    pressure_hpa: float
    condition: str


def condition_label(*, precip_in: float, gust_mph: float, cloud_pct: float) -> str:
    """C7 rule order: rain, windy, overcast, partly_cloudy, clear."""
    if precip_in >= RAIN_IN:
        return "rain"
    if gust_mph >= WINDY_GUST_MPH:
        return "windy"
    if cloud_pct >= OVERCAST_PCT:
        return "overcast"
    if cloud_pct >= PARTLY_CLOUDY_PCT:
        return "partly_cloudy"
    return "clear"


def circular_mean_deg(directions: Sequence[float], speeds: Sequence[float]) -> float | None:
    """Speed-weighted mean compass direction in whole degrees; None when calm."""
    east = sum(s * math.sin(math.radians(d)) for d, s in zip(directions, speeds, strict=True))
    north = sum(s * math.cos(math.radians(d)) for d, s in zip(directions, speeds, strict=True))
    if math.hypot(east, north) < 1e-9:
        return None
    return float(round(math.degrees(math.atan2(east, north))) % 360)


def _values(rows: Sequence[HourlyObs], name: str) -> list[float] | None:
    """Field ``name`` of every row; None when any row lacks it."""
    values: list[float | None] = [getattr(obs, name) for obs in rows]
    present = [value for value in values if value is not None]
    return present if len(present) == len(values) else None


def aggregate_window(event_date: date, hours: Iterable[HourlyObs]) -> WindowWeather | None:
    """The event's window summary; None when a needed row or value is missing."""
    by_hour = {
        obs.ts_local.hour: obs
        for obs in hours
        if obs.ts_local.date() == event_date and obs.ts_local.hour in WINDOW_HOURS
    }
    if len(by_hour) < len(WINDOW_HOURS):
        return None
    window = [by_hour[h] for h in WINDOW_HOURS]
    late = [by_hour[h] for h in ACCUMULATION_HOURS]
    needed = {name: _values(window, name) for name in WINDOW_FIELDS} | {
        name: _values(late, name) for name in ACCUMULATED_FIELDS
    }
    col = {name: values for name, values in needed.items() if values is not None}
    if len(col) < len(needed):
        return None
    precip_in = round(sum(col["precip_in"]), 3)
    gust_mph = round(max(col["gust_mph"]), 1)
    cloud_pct = round(fmean(col["cloud_pct"]), 1)
    return WindowWeather(
        temp_f=round(fmean(col["temp_f"]), 1),
        apparent_f=round(fmean(col["apparent_f"]), 1),
        precip_in=precip_in,
        wind_mph=round(fmean(col["wind_mph"]), 1),
        gust_mph=gust_mph,
        wind_dir_deg=circular_mean_deg(col["wind_dir_deg"], col["wind_mph"]),
        cloud_pct=cloud_pct,
        humidity_pct=round(fmean(col["humidity_pct"]), 1),
        pressure_hpa=round(fmean(col["pressure_hpa"]), 1),
        condition=condition_label(precip_in=precip_in, gust_mph=gust_mph, cloud_pct=cloud_pct),
    )
