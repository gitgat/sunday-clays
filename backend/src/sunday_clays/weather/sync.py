"""``weather_sync`` job: fetch missing event-window weather into ``weather_hourly``."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import groupby
from typing import Any, Final
from zoneinfo import ZoneInfo

from sqlalchemy import Table, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.jobs.handlers import handler
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Base
from sunday_clays.weather.aggregate import ACCUMULATED_FIELDS, WINDOW_FIELDS
from sunday_clays.weather.client import (
    WINDOW_HOURS,
    HourlyObs,
    HourlySource,
    OpenMeteoClient,
)

ARCHIVE_MIN_AGE_DAYS: Final = 7  # "older than 6 days" -> archive API
FORECAST_PAST_DAYS: Final = 7
FORECAST_DAYS: Final = 1
WINDOW_CLOSED_HOUR: Final = 13  # an event date is fetched once local time reaches 13:00
UPSERT_CHUNK: Final = 1000
DEFAULT_TIMEZONE: Final = "America/Los_Angeles"  # C2 ``timezone`` default; the handler passes it
REQUIRED_FIELDS: Final[tuple[str, ...]] = (*WINDOW_FIELDS, *ACCUMULATED_FIELDS)
"""An hour is stored only when every value the event-window aggregation reads is present."""
MEASURED_COLUMNS: Final[tuple[str, ...]] = (*REQUIRED_FIELDS, "rain_in", "weather_code")
COMPARED_COLUMNS: Final[tuple[str, ...]] = (*MEASURED_COLUMNS, "source")


@dataclass(frozen=True)
class SyncResult:
    """``rows_upserted``/``window_rows_upserted`` count rows written (new or changed) only."""

    fetched_dates: tuple[date, ...]
    rows_upserted: int
    window_rows_upserted: int
    recompute_job_id: int | None


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def _wall_clock(now: datetime, timezone: str) -> datetime:
    """``now`` as wall-clock time in ``timezone``, whatever zone it arrived in.

    A naive value is rejected: ``astimezone`` would silently read it in the host's zone.
    """
    if now.tzinfo is None:
        raise ValueError("now_local must be timezone-aware")
    return now.astimezone(ZoneInfo(timezone))


def _archive_before(now_local: datetime) -> date:
    """Event dates strictly before this day are older than 6 days: archive API."""
    return now_local.date() - timedelta(days=ARCHIVE_MIN_AGE_DAYS - 1)


def dates_needing_weather(
    session: Session, now_local: datetime, *, timezone: str = DEFAULT_TIMEZONE
) -> list[date]:
    """Event dates whose 10:00/11:00/12:00 rows are missing, or still forecast-sourced
    although the date is older than 6 days.

    ``now_local`` must be timezone-aware; the 13:00 cutoff and the 6-day split are read on the
    wall clock of ``timezone``, whatever zone ``now_local`` is expressed in."""
    now_local = _wall_clock(now_local, timezone)
    events = _table("events")
    hourly = _table("weather_hourly")
    today = now_local.date()
    last = today if now_local.hour >= WINDOW_CLOSED_HOUR else today - timedelta(days=1)
    dates: list[date] = list(
        session.scalars(
            select(events.c.event_date)
            .where(events.c.event_date <= last)
            .order_by(events.c.event_date)
        ).all()
    )
    stamps = [datetime.combine(d, time(h)) for d in dates for h in WINDOW_HOURS]
    sources: dict[date, list[str]] = {d: [] for d in dates}
    found = session.execute(
        select(hourly.c.ts_local, hourly.c.source).where(hourly.c.ts_local.in_(stamps))
    )
    for ts_local, source in found:
        sources[ts_local.date()].append(source)
    archive_before = _archive_before(now_local)
    return [
        d
        for d, got in sources.items()
        if len(got) < len(WINDOW_HOURS) or (d < archive_before and "forecast" in got)
    ]


def _is_complete(obs: HourlyObs) -> bool:
    return all(getattr(obs, name) is not None for name in REQUIRED_FIELDS)


def _write_hourly(
    session: Session, rows: Sequence[tuple[HourlyObs, str]], *, fetched_at: datetime
) -> list[datetime]:
    """Insert new hours and overwrite changed ones; returns the ``ts_local`` of each row written.

    A row whose measured columns and ``source`` all equal the stored row (NULL-safe) is left
    untouched, ``fetched_at`` included: ``fetched_at`` is the fetch that last changed the row.
    """
    table = _table("weather_hourly")
    values = [
        {
            "ts_local": obs.ts_local,
            **{name: getattr(obs, name) for name in MEASURED_COLUMNS},
            "source": source,
            "fetched_at": fetched_at,
        }
        for obs, source in rows
    ]
    written: list[datetime] = []
    for start in range(0, len(values), UPSERT_CHUNK):
        stmt = pg_insert(table).values(values[start : start + UPSERT_CHUNK])
        stored = tuple_(*(table.c[name] for name in COMPARED_COLUMNS))
        incoming = tuple_(*(stmt.excluded[name] for name in COMPARED_COLUMNS))
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.ts_local],
            set_={name: stmt.excluded[name] for name in (*COMPARED_COLUMNS, "fetched_at")},
            where=stored.is_distinct_from(incoming),
        )
        written += session.scalars(stmt.returning(table.c.ts_local)).all()
    return written


def upsert_hourly(
    session: Session, rows: Sequence[tuple[HourlyObs, str]], *, fetched_at: datetime
) -> int:
    """Insert or overwrite ``weather_hourly`` rows keyed by ``ts_local``.

    Returns how many rows were written (new or changed); rows identical to the stored ones are
    skipped and keep their ``fetched_at``.
    """
    return len(_write_hourly(session, rows, fetched_at=fetched_at))


def sync_weather(
    session: Session,
    source: HourlySource,
    *,
    now_local: datetime,
    timezone: str = DEFAULT_TIMEZONE,
) -> SyncResult:
    """Fetch every missing event date, then upsert (a failed fetch writes nothing).

    ``now_local`` must be timezone-aware and is read on the wall clock of ``timezone``."""
    now_local = _wall_clock(now_local, timezone)
    needed = dates_needing_weather(session, now_local, timezone=timezone)
    archive_before = _archive_before(now_local)
    fetched: list[tuple[HourlyObs, str]] = []
    old = [d for d in needed if d < archive_before]
    for _year, group in groupby(old, key=lambda d: d.year):
        chunk = list(group)
        wanted = set(chunk)
        hours = source.archive(chunk[0], chunk[-1] + timedelta(days=1))
        fetched += [(obs, "archive") for obs in hours if obs.ts_local.date() in wanted]
    recent = {d for d in needed if d >= archive_before}
    if recent:
        hours = source.forecast(past_days=FORECAST_PAST_DAYS, forecast_days=FORECAST_DAYS)
        fetched += [(obs, "forecast") for obs in hours if obs.ts_local.date() in recent]
    complete = [(obs, src) for obs, src in fetched if _is_complete(obs)]
    written = _write_hourly(session, complete, fetched_at=now_local)
    window = sum(1 for ts_local in written if ts_local.hour in WINDOW_HOURS)
    job_id = enqueue(session, "recompute", dedupe_key="recompute") if window else None
    return SyncResult(tuple(needed), len(written), window, job_id)


@handler("weather_sync")
def weather_sync_handler(session: Session, payload: dict[str, Any]) -> None:
    """Job entry point; the payload is ignored (dates always come from ``events``)."""
    settings = get_settings()
    if not settings.weather_enabled:
        return
    now_local = datetime.now(ZoneInfo(settings.timezone))
    with OpenMeteoClient.from_settings(settings) as client:
        sync_weather(session, client, now_local=now_local, timezone=settings.timezone)
