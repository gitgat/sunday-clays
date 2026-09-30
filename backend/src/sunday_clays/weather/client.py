"""Open-Meteo archive and forecast client for the club's hourly weather.

Every request asks for UTC unix timestamps, and this module converts them to
America/Los_Angeles wall-clock hours. Open-Meteo's own ``timezone=`` option applies one
fixed UTC offset to a whole response, so a January date fetched in September would come
back labelled an hour late.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Any, Final, Protocol, Self
from zoneinfo import ZoneInfo

import httpx

from sunday_clays.config import Settings

WINDOW_HOURS: Final[tuple[int, ...]] = (10, 11, 12)
"""Local hourly stamps of the 10:00-12:00 event window (C7)."""

HOURLY_VARIABLES: Final[tuple[str, ...]] = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "cloud_cover",
    "relative_humidity_2m",
    "pressure_msl",
    "weather_code",
)
EXPECTED_UNITS: Final[Mapping[str, str]] = {
    "temperature_2m": "°F",
    "apparent_temperature": "°F",
    "precipitation": "inch",
    "rain": "inch",
    "wind_speed_10m": "mp/h",
    "wind_gusts_10m": "mp/h",
    "pressure_msl": "hPa",
}
REQUEST_OPTIONS: Final[Mapping[str, str]] = {
    "temperature_unit": "fahrenheit",
    "wind_speed_unit": "mph",
    "precipitation_unit": "inch",
    "timeformat": "unixtime",
}
USER_AGENT: Final = "sunday-clays/1 (+https://sundayclays.claysmasher.com)"
TIMEOUT_S: Final = 30.0


class WeatherApiError(Exception):
    """Open-Meteo was unreachable or answered with something this client cannot use."""


@dataclass(frozen=True)
class HourlyObs:
    """One local hour of weather; fields match the ``weather_hourly`` columns (C4)."""

    ts_local: datetime
    temp_f: float | None
    apparent_f: float | None
    precip_in: float | None
    rain_in: float | None
    wind_mph: float | None
    gust_mph: float | None
    wind_dir_deg: float | None
    cloud_pct: float | None
    humidity_pct: float | None
    pressure_hpa: float | None
    weather_code: int | None


class HourlySource(Protocol):
    """What the weather jobs need from a provider (``OpenMeteoClient`` in prod)."""

    def archive(self, start: date, end: date) -> list[HourlyObs]: ...

    def forecast(self, *, past_days: int, forecast_days: int) -> list[HourlyObs]: ...


def _number(value: Any) -> float | None:
    """A finite JSON number as ``float``; no coercion of bools, strings, NaN or inf."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"expected a JSON number, got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("expected a finite number")
    return number


def _integer(value: Any) -> int:
    """An integral JSON number as ``int``; bools, strings and 3.7-style floats raise."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"expected an integral JSON number, got {value!r}")
    return value


def _code(value: Any) -> int | None:
    return None if value is None else _integer(value)


def parse_hourly(payload: Any, tz: ZoneInfo) -> list[HourlyObs]:
    """Turn an Open-Meteo ``timeformat=unixtime`` body into local wall-clock hours.

    Rows are sorted by ``ts_local`` with one row per local hour: on the autumn DST
    change the repeated 01:00 keeps its daylight-time occurrence (the earlier UTC
    stamp), whatever order the response lists the stamps in.
    """
    try:
        units = payload["hourly_units"]
        hourly = payload["hourly"]
        stamps = list(hourly["time"])
        columns = {name: list(hourly[name]) for name in HOURLY_VARIABLES}
        wrong = {n: units.get(n) for n, unit in EXPECTED_UNITS.items() if units.get(n) != unit}
    except (KeyError, TypeError, AttributeError) as exc:
        raise WeatherApiError(f"Open-Meteo response is malformed: {exc!r}") from exc
    if wrong:
        raise WeatherApiError(f"Open-Meteo returned unexpected units {wrong}")
    if any(len(values) != len(stamps) for values in columns.values()):
        raise WeatherApiError("Open-Meteo hourly arrays have different lengths")
    rows: dict[datetime, HourlyObs] = {}
    utc_of: dict[datetime, int] = {}
    try:
        for i, raw_stamp in enumerate(stamps):
            stamp = _integer(raw_stamp)
            aware = datetime.fromtimestamp(stamp, UTC).astimezone(tz)
            ts_local = aware.replace(tzinfo=None, fold=0)
            if ts_local in utc_of and utc_of[ts_local] <= stamp:
                continue  # an earlier UTC stamp (daylight time) already holds this hour
            utc_of[ts_local] = stamp
            rows[ts_local] = HourlyObs(
                ts_local=ts_local,
                temp_f=_number(columns["temperature_2m"][i]),
                apparent_f=_number(columns["apparent_temperature"][i]),
                precip_in=_number(columns["precipitation"][i]),
                rain_in=_number(columns["rain"][i]),
                wind_mph=_number(columns["wind_speed_10m"][i]),
                gust_mph=_number(columns["wind_gusts_10m"][i]),
                wind_dir_deg=_number(columns["wind_direction_10m"][i]),
                cloud_pct=_number(columns["cloud_cover"][i]),
                humidity_pct=_number(columns["relative_humidity_2m"][i]),
                pressure_hpa=_number(columns["pressure_msl"][i]),
                weather_code=_code(columns["weather_code"][i]),
            )
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        # OSError: gmtime() rejects some huge stamps with EOVERFLOW instead of OverflowError
        raise WeatherApiError(
            "Open-Meteo returned a non-numeric or out-of-range hourly value"
        ) from exc
    return sorted(rows.values(), key=lambda row: row.ts_local)


def _reason(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("reason"), str):
        return str(body["reason"])
    return response.text[:200]


class OpenMeteoClient:
    """Blocking Open-Meteo client for one location; use it as a context manager."""

    def __init__(
        self,
        *,
        archive_url: str,
        forecast_url: str,
        lat: float,
        lon: float,
        timezone: str,
    ) -> None:
        self._archive_url = archive_url
        self._forecast_url = forecast_url
        self._location = {"latitude": str(lat), "longitude": str(lon)}
        self._tz = ZoneInfo(timezone)
        self._http = httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT})

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            archive_url=settings.open_meteo_archive_url,
            forecast_url=settings.open_meteo_forecast_url,
            lat=settings.club_lat,
            lon=settings.club_lon,
            timezone=settings.timezone,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._http.close()

    def archive(self, start: date, end: date) -> list[HourlyObs]:
        """Every hour of the UTC days ``start``..``end`` (inclusive), archive API."""
        window = {"start_date": start.isoformat(), "end_date": end.isoformat()}
        return self._get(self._archive_url, window)

    def forecast(self, *, past_days: int, forecast_days: int) -> list[HourlyObs]:
        """Hours from ``past_days`` UTC days back to ``forecast_days`` days ahead."""
        window = {"past_days": str(past_days), "forecast_days": str(forecast_days)}
        return self._get(self._forecast_url, window)

    def _get(self, url: str, window: Mapping[str, str]) -> list[HourlyObs]:
        params = {
            **self._location,
            **window,
            "hourly": ",".join(HOURLY_VARIABLES),
            **REQUEST_OPTIONS,
        }
        try:
            response = self._http.get(url, params=params)
        except httpx.HTTPError as exc:
            raise WeatherApiError(f"Open-Meteo request failed: {type(exc).__name__}") from exc
        if response.status_code != httpx.codes.OK:
            raise WeatherApiError(f"Open-Meteo HTTP {response.status_code}: {_reason(response)}")
        try:
            body = response.json()
        except ValueError as exc:
            raise WeatherApiError("Open-Meteo returned invalid JSON") from exc
        return parse_hourly(body, self._tz)
