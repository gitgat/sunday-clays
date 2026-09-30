"""The ``rebuild`` job: rebuild live tables, recompute analytics, request missing weather (C6)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.store import set_new_since
from sunday_clays.analytics.pipeline import get_data_version, run_pipeline
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.jobs.handlers import handler
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Event, EventWeather


@handler("rebuild")
def handle_rebuild(session: Session, payload: dict[str, Any]) -> None:
    rebuild_live(session)
    set_new_since(session, get_data_version(session) + 1)  # the generation run_pipeline writes
    run_pipeline(session)
    lacking_weather = session.scalar(
        select(Event.event_date)
        .outerjoin(EventWeather, EventWeather.event_date == Event.event_date)
        .where(EventWeather.event_date.is_(None))
        .limit(1)
    )
    if lacking_weather is not None:
        enqueue(session, "weather_sync", dedupe_key="weather_sync")
