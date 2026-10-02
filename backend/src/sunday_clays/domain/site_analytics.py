"""Read side of the admin Analytics page (Plan 16): visitors, page kinds, fist bumps and "Which
one are you?" uptake over a span of the club's local days.

Each read merges the rollups with the raw page_views still kept. The two never overlap: the
rollup deletes the raw rows it counts, in whole weeks (domain/page_views.py). The sets are small
(one rollup row per day and week, raw rows for at most 96 days, one fist bump per insight and
device), so each read loads its buckets once and filters by the span in Python (Decision 10).

Invariant (ruling P16-R1): a rollup row and a raw row never cover the same day or week, because
the rollup only takes whole weeks. Each read still keeps one source per key, raw over rollup
(``rolled | raw``), so a bug elsewhere can never double-count. A week's unique devices come from
its own week row or raw rows, never from summing days. A ``since`` before the first data is
clamped to the first data day (and no ``since`` starts there), so every series shares one axis
and a far-past ``since`` cannot zero-fill decades.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.templates import plain
from sunday_clays.domain.page_views import (
    Period,
    bucket_of,
    latest_states,
    local_midnight,
    state_counts,
)
from sunday_clays.models import FistBump, Insight, PageKindRollup, PageView, PageViewRollup

BUSIEST: Final = 5
TOP_INSIGHTS: Final = 10


@dataclass(frozen=True)
class Span:
    """Local days from ``since`` to ``as_of``; ``since`` None reaches back to the first data."""

    since: date | None
    as_of: date

    def has(self, day: date) -> bool:
        return (self.since is None or day >= self.since) and day <= self.as_of


@dataclass(frozen=True)
class VisitorDay:
    day: date
    devices: int


@dataclass(frozen=True)
class VisitorWeek:
    week: date
    devices: int


@dataclass(frozen=True)
class Visitors:
    days: list[VisitorDay]
    weeks: list[VisitorWeek]
    busiest: list[VisitorDay]


@dataclass(frozen=True)
class PageKindViews:
    page_kind: str
    views: int


@dataclass(frozen=True)
class BumpDay:
    day: date
    bumps: int


@dataclass(frozen=True)
class TopInsight:
    key: str
    headline: str | None  # None when the insight is no longer on the site
    bumps: int


@dataclass(frozen=True)
class Bumps:
    days: list[BumpDay]
    top: list[TopInsight]
    devices: int
    devices_all_time: int


@dataclass(frozen=True)
class MeStates:
    picked: int
    skipped: int
    none: int


@dataclass(frozen=True)
class WeekMeStates:
    week: date
    picked: int
    skipped: int
    none: int


@dataclass(frozen=True)
class Uptake:
    weeks: list[WeekMeStates]
    latest: MeStates
    latest_since: date | None


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _run(first: date | None, last: date, step_days: int) -> list[date]:
    """``first``, ``first + step``, … up to ``last``; empty when there is no start."""
    days: list[date] = []
    day = first
    while day is not None and day <= last:
        days.append(day)
        day += timedelta(days=step_days)
    return days


def _first(span: Span, days: Iterable[date]) -> date | None:
    """Where a zero-filled series starts: ``since``, else the first day with data up to as_of."""
    if span.since is not None:
        return span.since
    return min((day for day in days if day <= span.as_of), default=None)


def _weeks_from(first: date | None) -> date | None:
    # A mid-week ``since`` starts the first weekly bucket on that week's Monday.
    return None if first is None else monday(first)


def _earliest(session: Session, tz: str) -> date | None:
    """The first local day with any data: oldest raw view, rollup day or fist bump."""
    local_bump = cast(func.timezone(tz, FistBump.created_at), Date)
    first_view = session.scalar(select(func.min(PageView.at)))
    found = [
        session.scalar(
            select(func.min(PageViewRollup.start_day)).where(PageViewRollup.period == "day")
        ),
        session.scalar(select(func.min(PageKindRollup.day))),
        session.scalar(select(func.min(local_bump))),
        None if first_view is None else first_view.astimezone(ZoneInfo(tz)).date(),
    ]
    return min((day for day in found if day is not None), default=None)


def _clamped(session: Session, tz: str, span: Span) -> Span:
    """Start every series on the same day: ``since`` no earlier than the first data day, and
    with no ``since`` the first data day itself. With a ``since`` but no data at all, the span
    collapses to ``as_of`` so a far-past ``since`` cannot zero-fill decades. No ``since`` and no
    data stays open and every series is empty."""
    first = _earliest(session, tz)
    if first is None:
        return span if span.since is None else Span(span.as_of, span.as_of)
    if span.since is None or first > span.since:
        return Span(first, span.as_of)
    return span


def _rolled_devices(session: Session, period: Period) -> dict[date, int]:
    rows = session.execute(
        select(PageViewRollup.start_day, PageViewRollup.devices).where(
            PageViewRollup.period == period
        )
    )
    return dict(rows.all())


def _raw_devices(session: Session, tz: str, period: Period) -> dict[date, int]:
    raw = select(bucket_of(period, tz).label("bucket"), PageView.device_id).subquery()
    rows = session.execute(
        select(raw.c.bucket, func.count(func.distinct(raw.c.device_id))).group_by(raw.c.bucket)
    )
    return dict(rows.all())


def visitors(session: Session, tz: str, span: Span) -> Visitors:
    span = _clamped(session, tz, span)
    by_day = _rolled_devices(session, "day") | _raw_devices(session, tz, "day")
    by_week = _rolled_devices(session, "week") | _raw_devices(session, tz, "week")
    first = _first(span, by_day)
    days = [VisitorDay(day, by_day.get(day, 0)) for day in _run(first, span.as_of, 1)]
    weeks = [
        VisitorWeek(week, by_week.get(week, 0)) for week in _run(_weeks_from(first), span.as_of, 7)
    ]
    busiest = sorted(
        (day for day in days if day.devices > 0),
        key=lambda d: (-d.devices, -d.day.toordinal()),
    )[:BUSIEST]
    return Visitors(days, weeks, busiest)


def page_kinds(session: Session, tz: str, span: Span) -> list[PageKindViews]:
    span = _clamped(session, tz, span)
    raw = select(bucket_of("day", tz).label("day"), PageView.page_kind).subquery()
    raw_counts = select(raw.c.day, raw.c.page_kind, func.count()).group_by(
        raw.c.day, raw.c.page_kind
    )
    rolled = select(PageKindRollup.day, PageKindRollup.page_kind, PageKindRollup.views)
    by_key = {(d, k): v for d, k, v in session.execute(rolled)} | {
        (d, k): v for d, k, v in session.execute(raw_counts)
    }
    totals: Counter[str] = Counter()
    for (day, kind), views in by_key.items():
        if span.has(day):
            totals[kind] += views
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return [PageKindViews(kind, views) for kind, views in ranked]


def bumps(session: Session, tz: str, span: Span) -> Bumps:
    span = _clamped(session, tz, span)
    local_day = cast(func.timezone(tz, FistBump.created_at), Date)
    rows = [
        (day, key, device)
        for day, key, device in session.execute(
            select(local_day, FistBump.insight_key, FistBump.device_id)
        )
        if span.has(day)
    ]
    per_day = Counter(day for day, _, _ in rows)
    days = [BumpDay(day, per_day.get(day, 0)) for day in _run(_first(span, per_day), span.as_of, 1)]
    ranked = sorted(Counter(key for _, key, _ in rows).items(), key=lambda kv: (-kv[1], kv[0]))
    ranked = ranked[:TOP_INSIGHTS]
    headlines: dict[str, str] = {}
    if ranked:
        found = session.execute(
            select(Insight.key, Insight.headline).where(Insight.key.in_([k for k, _ in ranked]))
        )
        headlines = {key: plain(headline) for key, headline in found}
    all_time = session.scalar(select(func.count(func.distinct(FistBump.device_id)))) or 0
    return Bumps(
        days=days,
        top=[TopInsight(key, headlines.get(key), n) for key, n in ranked],
        devices=len({device for _, _, device in rows}),
        devices_all_time=all_time,
    )


def uptake(session: Session, tz: str, span: Span) -> Uptake:
    span = _clamped(session, tz, span)
    rolled = {
        start: (picked, skipped, none)
        for start, picked, skipped, none in session.execute(
            select(
                PageViewRollup.start_day,
                PageViewRollup.me_picked,
                PageViewRollup.me_skipped,
                PageViewRollup.me_none,
            ).where(PageViewRollup.period == "week")
        )
    }
    per_week = latest_states(tz, "week")
    raw = {
        week: (picked, skipped, none)
        for week, _, picked, skipped, none in session.execute(
            select(per_week.c.bucket, *state_counts(per_week)).group_by(per_week.c.bucket)
        )
    }
    by_week = rolled | raw
    weeks = [
        WeekMeStates(week, *by_week.get(week, (0, 0, 0)))
        for week in _run(_weeks_from(_first(span, by_week)), span.as_of, 7)
    ]
    nothing = Uptake(weeks, MeStates(0, 0, 0), None)
    first_raw = session.scalar(select(func.min(PageView.at)))
    if first_raw is None:
        return nothing
    kept_since = first_raw.astimezone(ZoneInfo(tz)).date()
    since = kept_since if span.since is None else max(span.since, kept_since)
    if since > span.as_of:
        return nothing
    latest = latest_states(
        tz,
        None,
        PageView.at >= local_midnight(since, tz),
        PageView.at < local_midnight(span.as_of + timedelta(days=1), tz),
    )
    _, picked, skipped, none = session.execute(select(*state_counts(latest))).one()
    return Uptake(weeks, MeStates(picked, skipped, none), since)
