"""Time-based job scheduling, evaluated on every worker poll (no in-memory timers) (C6)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Job

WEATHER_SYNC_LOCAL_HOUR = 14
FORECAST_INTERVAL = timedelta(hours=6)
ROLLUP_LOCAL_HOUR = 3  # Plan 16: page_view_rollup, once a local day, weather or not


def _created_since(session: Session, kind: str, since: datetime) -> bool:
    found = session.scalar(select(Job.id).where(Job.kind == kind, Job.created_at >= since).limit(1))
    return found is not None


def schedule_due(
    session: Session,
    now: datetime,
    *,
    weather_enabled: bool,
    timezone: str = "America/Los_Angeles",
) -> list[int]:
    """Enqueue page_view_rollup (daily after 03:00 local), and with weather on, weather_sync
    (daily after 14:00 local) and forecast_refresh (every 6 h), when due."""
    local_now = now.astimezone(ZoneInfo(timezone))
    job_ids: list[int] = []
    rollup_slot = local_now.replace(hour=ROLLUP_LOCAL_HOUR, minute=0, second=0, microsecond=0)
    if local_now >= rollup_slot and not _created_since(session, "page_view_rollup", rollup_slot):
        job_ids.append(enqueue(session, "page_view_rollup", dedupe_key="page_view_rollup"))
    if not weather_enabled:
        return job_ids
    slot_start = local_now.replace(hour=WEATHER_SYNC_LOCAL_HOUR, minute=0, second=0, microsecond=0)
    if local_now >= slot_start and not _created_since(session, "weather_sync", slot_start):
        job_ids.append(enqueue(session, "weather_sync", dedupe_key="weather_sync"))
    if not _created_since(session, "forecast_refresh", now - FORECAST_INTERVAL):
        job_ids.append(enqueue(session, "forecast_refresh", dedupe_key="forecast_refresh"))
    return job_ids
