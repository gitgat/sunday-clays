"""``forecast_refresh`` job: next Sunday's hourly forecast into ``forecast_cache``.

The payload is ``{"target_date": "YYYY-MM-DD", "hours": [HourlyObs as JSON, ...]}``
holding every local hour of the target date. Consumers summarize the event window
with ``weather.aggregate.aggregate_window(target_date, stored.hours)`` and key any
cache on ``fetched_at`` (C7). Forecast hours never enter ``weather_hourly``. A refresh
whose window lacks a value C7 needs fails and keeps the previous row.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Final
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.jobs.handlers import handler
from sunday_clays.models import Base
from sunday_clays.weather.aggregate import ACCUMULATED_FIELDS, ACCUMULATION_HOURS, WINDOW_FIELDS
from sunday_clays.weather.client import (
    WINDOW_HOURS,
    HourlyObs,
    HourlySource,
    OpenMeteoClient,
    WeatherApiError,
)

SUNDAY: Final = 6
EVENT_END_HOUR: Final = 12
_HOURS: Final = TypeAdapter(list[HourlyObs])


@dataclass(frozen=True)
class StoredForecast:
    target_date: date
    hours: tuple[HourlyObs, ...]
    fetched_at: datetime


def next_event_sunday(now_local: datetime) -> date:
    """Today while a Sunday event is still ahead or running (before 12:00), else the
    coming Sunday."""
    today = now_local.date()
    if today.weekday() == SUNDAY and now_local.hour < EVENT_END_HOUR:
        return today
    return today + timedelta(days=(SUNDAY - today.weekday()) % 7 or 7)


def _missing_window_values(day_hours: Sequence[HourlyObs]) -> list[str]:
    """What C7's window aggregation would lack in one date's hours (``"11:00 precip_in"``).

    Empty exactly when every 10:00/11:00/12:00 row is present with the values the
    aggregation reads (``weather.aggregate``'s ``WINDOW_FIELDS`` of every window row and
    ``ACCUMULATED_FIELDS`` of the ``ACCUMULATION_HOURS`` rows), i.e. when ``aggregate_window``
    can summarize the date.
    """
    by_hour = {obs.ts_local.hour: obs for obs in day_hours}
    missing: list[str] = []
    for hour in WINDOW_HOURS:
        obs = by_hour.get(hour)
        if obs is None:
            missing.append(f"{hour:02d}:00 row")
            continue
        needed = WINDOW_FIELDS + (ACCUMULATED_FIELDS if hour in ACCUMULATION_HOURS else ())
        missing.extend(f"{hour:02d}:00 {name}" for name in needed if getattr(obs, name) is None)
    return missing


def refresh_forecast(session: Session, source: HourlySource, *, now_local: datetime) -> date:
    """Fetch and upsert the forecast for the next event Sunday; returns that date.

    ``forecast_days`` covers the target's last local hour (UTC runs up to a day ahead).
    With no hours for the target, or a window missing a value C7 needs, the previous
    cached row is kept and the job fails.
    """
    target = next_event_sunday(now_local)
    days_ahead = (target - now_local.date()).days
    fetched = source.forecast(past_days=0, forecast_days=days_ahead + 2)
    hours = [obs for obs in fetched if obs.ts_local.date() == target]
    if not hours:
        raise WeatherApiError(f"Open-Meteo forecast has no hours for {target.isoformat()}")
    missing = _missing_window_values(hours)
    if missing:
        raise WeatherApiError(
            f"Open-Meteo forecast for {target.isoformat()} is missing event-window values: "
            + ", ".join(missing)
        )
    table = Base.metadata.tables["forecast_cache"]
    payload = {
        "target_date": target.isoformat(),
        "hours": _HOURS.dump_python(hours, mode="json"),
    }
    stmt = pg_insert(table).values(target_date=target, payload=payload, fetched_at=now_local)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[table.c.target_date],
            set_={
                "payload": stmt.excluded.payload,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
    )
    return target


def load_forecast(session: Session, target_date: date) -> StoredForecast | None:
    """The cached forecast for ``target_date``, or None when none was fetched."""
    table = Base.metadata.tables["forecast_cache"]
    row = session.execute(
        select(table.c.payload, table.c.fetched_at).where(table.c.target_date == target_date)
    ).one_or_none()
    if row is None:
        return None
    hours = _HOURS.validate_python(row.payload["hours"])
    return StoredForecast(target_date=target_date, hours=tuple(hours), fetched_at=row.fetched_at)


@handler("forecast_refresh")
def forecast_refresh_handler(session: Session, payload: dict[str, Any]) -> None:
    """Job entry point; the payload is ignored (the clock picks the target date)."""
    settings = get_settings()
    if not settings.weather_enabled:
        return
    now_local = datetime.now(ZoneInfo(settings.timezone))
    with OpenMeteoClient.from_settings(settings) as client:
        refresh_forecast(session, client, now_local=now_local)
