"""Time-based job scheduling, evaluated on every worker poll (no in-memory timers) (C6)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Job

WEATHER_SYNC_LOCAL_HOUR = 14
FORECAST_INTERVAL = timedelta(hours=6)


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
    """Enqueue weather_sync (daily after 14:00 local) and forecast_refresh (every 6 h) when due."""
    if not weather_enabled:
        return []
    local_now = now.astimezone(ZoneInfo(timezone))
    slot_start = local_now.replace(hour=WEATHER_SYNC_LOCAL_HOUR, minute=0, second=0, microsecond=0)
    job_ids: list[int] = []
    if local_now >= slot_start and not _created_since(session, "weather_sync", slot_start):
        job_ids.append(enqueue(session, "weather_sync", dedupe_key="weather_sync"))
    if not _created_since(session, "forecast_refresh", now - FORECAST_INTERVAL):
        job_ids.append(enqueue(session, "forecast_refresh", dedupe_key="forecast_refresh"))
    return job_ids
