"""Time-based job scheduling, evaluated on every worker poll (no in-memory timers) (C6)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.domain.features import LAST_WARM_KEY, infrastructure_switch_on
from sunday_clays.jobs.page_warm import RETRY_AFTER  # D35: the one 5-minute gap
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import AppState, Job

WEATHER_SYNC_LOCAL_HOUR = 14
FORECAST_INTERVAL = timedelta(hours=6)
ROLLUP_LOCAL_HOUR = 3  # Plan 16: page_view_rollup, once a local day, weather or not


def _page_warm_due(session: Session, now: datetime, timezone: str, app_version: str) -> bool:
    """The last warm-up's (data_version, local date, app_version) differs from now's, or it
    skipped or failed a target (D35: a partial or failed warm-up is retried), and none was tried
    in 5 minutes. app_version is in the cache key (D29), so a deploy makes every key cold."""
    current = (
        get_data_version(session),
        now.astimezone(ZoneInfo(timezone)).date().isoformat(),
        app_version,
    )
    raw = session.scalar(select(AppState.value).where(AppState.key == LAST_WARM_KEY))
    if isinstance(raw, dict):
        last = (raw.get("data_version"), raw.get("local_date"), raw.get("app_version"))
        incomplete = bool(raw.get("failed")) or bool(raw.get("skipped"))
    else:
        last, incomplete = None, True
    stale = last != current or incomplete
    return stale and not _created_since(session, "page_warm", now - RETRY_AFTER)


def _created_since(session: Session, kind: str, since: datetime) -> bool:
    found = session.scalar(select(Job.id).where(Job.kind == kind, Job.created_at >= since).limit(1))
    return found is not None


def schedule_due(
    session: Session,
    now: datetime,
    *,
    weather_enabled: bool,
    timezone: str = "America/Los_Angeles",
    page_cache_enabled: bool = False,
    app_version: str = "dev",
) -> list[int]:
    """Enqueue page_view_rollup and club_event_retention (daily after 03:00 local), page_warm
    (after every data_version change, deploy and each local midnight, with the page cache on),
    and with weather on, weather_sync (daily after 14:00 local) and forecast_refresh (every 6 h),
    when due."""
    local_now = now.astimezone(ZoneInfo(timezone))
    job_ids: list[int] = []
    if (
        page_cache_enabled
        and infrastructure_switch_on(session, "page_cache")
        and _page_warm_due(session, now, timezone, app_version)
    ):
        job_ids.append(enqueue(session, "page_warm", dedupe_key="page_warm"))
    rollup_slot = local_now.replace(hour=ROLLUP_LOCAL_HOUR, minute=0, second=0, microsecond=0)
    if local_now >= rollup_slot and not _created_since(session, "page_view_rollup", rollup_slot):
        job_ids.append(enqueue(session, "page_view_rollup", dedupe_key="page_view_rollup"))
    # Plan 20 §5.6: club-event sign-ups and unused emails, in the same daily 03:00 slot.
    if local_now >= rollup_slot and not _created_since(
        session, "club_event_retention", rollup_slot
    ):
        job_ids.append(enqueue(session, "club_event_retention", dedupe_key="club_event_retention"))
    if not weather_enabled:
        return job_ids
    slot_start = local_now.replace(hour=WEATHER_SYNC_LOCAL_HOUR, minute=0, second=0, microsecond=0)
    if local_now >= slot_start and not _created_since(session, "weather_sync", slot_start):
        job_ids.append(enqueue(session, "weather_sync", dedupe_key="weather_sync"))
    if not _created_since(session, "forecast_refresh", now - FORECAST_INTERVAL):
        job_ids.append(enqueue(session, "forecast_refresh", dedupe_key="forecast_refresh"))
    return job_ids
