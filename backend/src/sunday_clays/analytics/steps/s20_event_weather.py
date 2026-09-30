"""Recompute step 20 (C6): rebuild ``event_weather`` from ``weather_hourly``."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, fields
from datetime import date, datetime, time
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import RecomputeStep
from sunday_clays.models import Base
from sunday_clays.weather.aggregate import aggregate_window
from sunday_clays.weather.client import WINDOW_HOURS, HourlyObs

OBS_COLUMNS: Final[tuple[str, ...]] = tuple(
    field.name for field in fields(HourlyObs) if field.name != "ts_local"
)
"""The ``weather_hourly`` measurement columns, named as the ``HourlyObs`` fields (C4)."""


def run(session: Session) -> None:
    """Replace all ``event_weather`` rows; an incomplete window gets no row."""
    tables = Base.metadata.tables
    events, hourly, event_weather = (
        tables["events"],
        tables["weather_hourly"],
        tables["event_weather"],
    )
    dates: list[date] = list(session.scalars(select(events.c.event_date)).all())
    stamps = [datetime.combine(d, time(h)) for d in dates for h in WINDOW_HOURS]
    hours: dict[date, list[HourlyObs]] = defaultdict(list)
    sources: dict[date, set[str]] = defaultdict(set)
    for row in session.execute(select(hourly).where(hourly.c.ts_local.in_(stamps))).mappings():
        obs = HourlyObs(ts_local=row["ts_local"], **{name: row[name] for name in OBS_COLUMNS})
        hours[obs.ts_local.date()].append(obs)
        sources[obs.ts_local.date()].add(row["source"])
    values: list[dict[str, Any]] = []
    for event_date in sorted(hours):
        summary = aggregate_window(event_date, hours[event_date])
        if summary is None:
            continue
        source = "forecast" if "forecast" in sources[event_date] else "archive"
        values.append({"event_date": event_date, **asdict(summary), "source": source})
    session.execute(delete(event_weather))
    if values:
        session.execute(insert(event_weather), values)


STEP = RecomputeStep(name="event_weather", order=20, run=run)
