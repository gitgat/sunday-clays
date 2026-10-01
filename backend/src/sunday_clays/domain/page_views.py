"""Anonymous page views (Plan 16): count a visit at most once per device and page kind every 30
minutes, and roll raw visits older than about 90 days into day and week totals.

Nothing here stores a name, a URL or an IP address. A device id is the random UUID a browser keeps
in localStorage ("sc.device"); after the rollup only counts remain. Buckets are the club's local
day and local ISO week (Monday to Sunday). Every grouped bucket is computed once in a subquery and
grouped by that column: psycopg binds parameters server-side, so a GROUP BY that repeats
``timezone($n, at)`` would not match the select list's ``timezone($m, at)``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Final, Literal, get_args
from zoneinfo import ZoneInfo

from sqlalchemy import (
    ColumnElement,
    Date,
    Subquery,
    Text,
    cast,
    delete,
    func,
    insert,
    literal,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.models import PageKindRollup, PageView, PageViewRollup

PageKind = Literal[
    "home",
    "profile",
    "event",
    "leaderboards",
    "records",
    "club",
    "stations",
    "weather",
    "yir",
    "explorer",
    "achievements",
    "race",
    "compare",
    "events-list",
    "admin",
    "other",
]
MeState = Literal["picked", "skipped", "none"]
Period = Literal["day", "week"]

PAGE_KINDS: Final[tuple[str, ...]] = get_args(PageKind)
ME_STATES: Final[tuple[str, ...]] = get_args(MeState)
PERIODS: Final[tuple[Period, ...]] = ("day", "week")
DEDUPE_WINDOW: Final = timedelta(minutes=30)
RAW_DAYS: Final = 90
# pg_advisory_xact_lock class key for one device+kind's dedupe check (rebuild_live holds 7263003)
DEDUPE_LOCK_KEY: Final = 7263004


def record_page_view(
    session: Session, device_id: uuid.UUID, page_kind: str, me_state: str, now: datetime
) -> bool:
    """Store one view unless this device was counted on this kind in the last 30 minutes.

    The advisory lock serialises two identical beacons that arrive together, so the second one
    sees the first after it commits. Returns whether the view was stored.
    """
    session.execute(
        select(
            func.pg_advisory_xact_lock(DEDUPE_LOCK_KEY, func.hashtext(f"{device_id}:{page_kind}"))
        )
    )
    recent = session.scalar(
        select(PageView.id)
        .where(
            PageView.device_id == device_id,
            PageView.page_kind == page_kind,
            PageView.at > now - DEDUPE_WINDOW,
        )
        .limit(1)
    )
    if recent is not None:
        return False
    session.execute(
        insert(PageView).values(device_id=device_id, page_kind=page_kind, me_state=me_state, at=now)
    )
    return True


def rollup_cutoff(today: date) -> date:
    """The Monday on or before ``today - RAW_DAYS``: every raw day before it is a whole week."""
    edge = today - timedelta(days=RAW_DAYS)
    return edge - timedelta(days=edge.weekday())


def local_midnight(day: date, tz: str) -> datetime:
    """The instant ``day`` starts in the club's timezone."""
    return datetime.combine(day, time(), ZoneInfo(tz))


def bucket_of(period: Period, tz: str) -> ColumnElement[date]:
    """A view's local day, or the Monday of its local ISO week."""
    local = func.timezone(tz, PageView.at)
    if period == "day":
        return cast(local, Date)
    return cast(func.date_trunc("week", local), Date)


def latest_states(tz: str, period: Period | None, *where: ColumnElement[bool]) -> Subquery:
    """Each device's last me_state per local day or week (or over every matching row when
    ``period`` is None): one row per (bucket, device), the latest by time, then by id."""
    partition: list[Any] = [PageView.device_id]
    columns: list[Any] = [PageView.device_id, PageView.me_state]
    if period is not None:
        bucket = bucket_of(period, tz)
        partition.insert(0, bucket)
        columns.insert(0, bucket.label("bucket"))
    rank = func.row_number().over(
        partition_by=partition, order_by=(PageView.at.desc(), PageView.id.desc())
    )
    ranked = select(*columns, rank.label("rank")).where(*where).subquery("ranked")
    keep = [column for column in ranked.c if column.key != "rank"]
    return select(*keep).where(ranked.c.rank == 1).subquery("latest")


def state_counts(latest: Subquery) -> tuple[ColumnElement[Any], ...]:
    """Devices, then how many of them last answered picked, skipped and none."""
    me = latest.c.me_state
    return (
        func.count(),
        func.count().filter(me == "picked"),
        func.count().filter(me == "skipped"),
        func.count().filter(me == "none"),
    )


@dataclass(frozen=True)
class RollupReport:
    cutoff: date
    rolled: int  # raw rows counted into the rollups and deleted


def rollup_page_views(session: Session, today: date, tz: str) -> RollupReport:
    """Fold raw views before local midnight of ``rollup_cutoff(today)`` into day and week rows
    and per-day kind counts, then delete them, all in the caller's transaction.

    Days and weeks are counted separately from the raw rows (a week's devices is not the sum of
    its days). ON CONFLICT DO NOTHING makes a repeat harmless; the server stamps ``at``, so no
    raw row can appear later on a rolled day.
    """
    cutoff = rollup_cutoff(today)
    old = PageView.at < local_midnight(cutoff, tz)
    rolled = session.scalar(select(func.count()).select_from(PageView).where(old)) or 0
    for period in PERIODS:
        latest = latest_states(tz, period, old)
        counts = select(
            cast(literal(period), Text), latest.c.bucket, *state_counts(latest)
        ).group_by(latest.c.bucket)
        session.execute(
            pg_insert(PageViewRollup)
            .from_select(
                ["period", "start_day", "devices", "me_picked", "me_skipped", "me_none"], counts
            )
            .on_conflict_do_nothing(index_elements=["period", "start_day"])
        )
    raw = select(bucket_of("day", tz).label("day"), PageView.page_kind).where(old).subquery()
    # ON CONFLICT DO NOTHING assumes no raw row ever lands in an already-rolled bucket. That holds
    # because ``at`` is server-stamped and the cutoff only moves forward. Changing TIMEZONE
    # westward would break it (local midnight moves later, so a rolled day could gain rows).
    per_kind = select(raw.c.day, raw.c.page_kind, func.count()).group_by(raw.c.day, raw.c.page_kind)
    session.execute(
        pg_insert(PageKindRollup)
        .from_select(["day", "page_kind", "views"], per_kind)
        .on_conflict_do_nothing(index_elements=["day", "page_kind"])
    )
    session.execute(delete(PageView).where(old))
    return RollupReport(cutoff, rolled)
