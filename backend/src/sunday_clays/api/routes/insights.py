"""GET /api/insights/* (Plan 12, spec §3.7): read-only feeds over the stored insights."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights import select as sel
from sunday_clays.analytics.insights.picks import picked
from sunday_clays.analytics.insights.store import (
    InsightRow,
    get_new_since,
    insights_table,
    load_picks,
    load_rows,
)
from sunday_clays.analytics.insights.templates import plain
from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.explorer.spec import QuerySpec
from sunday_clays.models import Base

router = APIRouter(tags=["insights"])

PolarityOut = Literal["positive", "neutral", "field_negative", "mixed"]
POLARITIES: dict[str, PolarityOut] = {
    "positive": "positive",
    "neutral": "neutral",
    "field_negative": "field_negative",
    "mixed": "mixed",
}


class InsightSegmentOut(BaseModel):
    t: Literal["text", "shooter", "num", "date", "trophy", "station"]
    v: str
    id: int | None = None


class InsightWindowOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: date = Field(alias="from")
    to: date


class InsightChartOut(BaseModel):
    type: Literal["explorer", "page"]
    label: str
    label_you: str | None = None
    spec: QuerySpec | None = None
    chart_type: Literal["bar", "line"] | None = None
    route: str | None = None
    anchor: str | None = None
    params: dict[str, str] = {}
    highlight: dict[str, list[str | int]] = {}
    ref: float | None = None
    compare: QuerySpec | None = None
    window: InsightWindowOut
    also: list[InsightChartOut] = []


class InsightOut(BaseModel):
    key: str
    kind: str
    family: str
    subject_type: str
    subject_id: str
    anchor_date: date | None
    polarity: PolarityOut
    kudos: bool
    is_new: bool
    headline: list[InsightSegmentOut]
    headline_you: list[InsightSegmentOut] | None
    headline_text: str
    how: list[list[InsightSegmentOut]]
    how_you: list[list[InsightSegmentOut]] | None
    chart: InsightChartOut
    rank_score: float


class InsightKudosOut(BaseModel):
    shooter_id: int
    display_name: str
    insight: InsightOut


class InsightFeedOut(BaseModel):
    data_version: int
    as_of: date | None
    pinned: InsightOut | None = None
    hero: InsightOut | None = None
    spotlight: InsightOut | None = None
    conditions: InsightOut | None = None
    top: list[InsightOut] = []
    kudos: list[InsightKudosOut] = []
    more: list[InsightOut] = []
    n_more: int = 0


def supersedes_of(kind_id: str) -> frozenset[str]:
    """A kind's supersedes set; a row of a kind no longer in code supersedes nothing."""
    try:
        return registry.get(kind_id).supersedes
    except KeyError:
        return frozenset()


def insight_out(row: InsightRow, new_since: int | None) -> InsightOut:
    chart: dict[str, Any] = dict(row.chart)
    return InsightOut(
        key=row.key,
        kind=row.kind,
        family=row.family,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        anchor_date=row.anchor_date,
        polarity=POLARITIES[row.polarity],
        kudos=row.kudos,
        is_new=row.is_new_since(new_since) and row.kind not in sel.NEVER_NEW,
        headline=[InsightSegmentOut.model_validate(s) for s in row.headline],
        headline_you=None
        if row.headline_you is None
        else [InsightSegmentOut.model_validate(s) for s in row.headline_you],
        headline_text=plain(row.headline),
        how=[[InsightSegmentOut.model_validate(s) for s in b] for b in row.how],
        how_you=None
        if row.how_you is None
        else [[InsightSegmentOut.model_validate(s) for s in b] for b in row.how_you],
        chart=InsightChartOut.model_validate(chart),
        rank_score=row.rank_score,
    )


def _maybe(row: InsightRow | None, new_since: int | None) -> InsightOut | None:
    return None if row is None else insight_out(row, new_since)


def held_dates(session: Session) -> list[date]:
    events = Base.metadata.tables["events"]
    query = (
        select(events.c.event_date).where(events.c.results_complete).order_by(events.c.event_date)
    )
    return list(session.scalars(query))


def names(session: Session, ids: set[int]) -> dict[int, str]:
    profiles = Base.metadata.tables["shooter_profiles"]
    query = select(profiles.c.shooter_id, profiles.c.display_name).where(
        profiles.c.shooter_id.in_(sorted(ids))
    )
    return {int(sid): str(name) for sid, name in session.execute(query)}


def feed_out(session: Session, feed: sel.Feed) -> InsightFeedOut:
    new_since = get_new_since(session)  # read once per request
    display = names(session, {chip.shooter_id for chip in feed.kudos})
    chips = [chip for chip in feed.kudos if chip.shooter_id in display]  # no profile: no chip
    return InsightFeedOut(
        data_version=get_data_version(session),
        as_of=feed.as_of,
        pinned=_maybe(feed.pinned, new_since),
        hero=_maybe(feed.hero, new_since),
        spotlight=_maybe(feed.spotlight, new_since),
        conditions=_maybe(feed.conditions, new_since),
        top=[insight_out(r, new_since) for r in feed.top],
        kudos=[
            InsightKudosOut(
                shooter_id=chip.shooter_id,
                display_name=display[chip.shooter_id],
                insight=insight_out(chip.row, new_since),
            )
            for chip in chips
        ],
        more=[insight_out(r, new_since) for r in feed.more],
        n_more=feed.n_more,
    )


def empty_feed(session: Session, as_of: date | None) -> InsightFeedOut:
    return InsightFeedOut(data_version=get_data_version(session), as_of=as_of)


@router.get("/api/insights/shooters/{id}")
def shooter_insights_feed(
    shooter_id: Annotated[int, Path(alias="id")],
    session: SessionDep,
    show_all: Annotated[bool, Query(alias="all")] = False,
) -> InsightFeedOut:
    """`all=true` lifts the "More insights" cap so every remaining insight comes back."""
    profiles = Base.metadata.tables["shooter_profiles"]
    known = session.scalar(select(profiles.c.shooter_id).where(profiles.c.shooter_id == shooter_id))
    if known is None:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    held = held_dates(session)
    if not held:
        return empty_feed(session, None)
    t = insights_table()
    rows = load_rows(session, t.c.subject_type == "shooter", t.c.subject_id == str(shooter_id))
    return feed_out(
        session,
        sel.feed_profile(
            rows, shooter_id, held[-1], held, supersedes_of, None if show_all else sel.MORE_CAP
        ),
    )


@router.get("/api/insights/sundays/{date}")
def sunday_insights_feed(
    day: Annotated[date, Path(alias="date")], session: SessionDep
) -> InsightFeedOut:
    events = Base.metadata.tables["events"]
    held = session.scalar(select(events.c.results_complete).where(events.c.event_date == day))
    if held is None:
        raise NotFoundError("event_not_found", f"No Sunday on {day.isoformat()}")
    if not held:
        return empty_feed(session, day)
    t = insights_table()
    rows = load_rows(
        session,
        or_(t.c.anchor_date == day, t.c.params["kudos_sunday"].astext == day.isoformat()),
    )
    return feed_out(session, sel.feed_sunday(rows, day, supersedes_of))


@router.get("/api/insights/home")
def home_insights_feed(session: SessionDep) -> InsightFeedOut:
    held = held_dates(session)
    if not held:
        return empty_feed(session, None)
    ref = held[-1]
    t = insights_table()
    recent = held[-sel.HOME_SUNDAYS :]
    rows = load_rows(
        session,
        or_(
            t.c.anchor_date.in_(recent),
            t.c.anchor_date.is_(None),
            t.c.params["kudos_sunday"].astext == ref.isoformat(),
        ),
    )
    hero, spotlight = picked(rows, load_picks(session, ref), ref)
    feed = sel.feed_home(rows, ref, held, supersedes_of, hero=hero, spotlight=spotlight)
    return feed_out(session, feed)


def page_feed(session: Session, page: str, *where: ColumnElement[bool]) -> InsightFeedOut:
    """Club, leaderboards, records and stations: the page's rows, latest Sunday as reference."""
    held = held_dates(session)
    if not held:
        return empty_feed(session, None)
    t = insights_table()
    rows = load_rows(session, t.c.pages.contains([page]), *where)
    return feed_out(session, sel.feed_page(rows, page, held[-1], held, supersedes_of))


@router.get("/api/insights/club")
def club_insights_feed(session: SessionDep) -> InsightFeedOut:
    return page_feed(session, "club")


@router.get("/api/insights/leaderboards")
def leaderboards_insights_feed(
    session: SessionDep, season: Annotated[int | None, Query(ge=1900, le=2999)] = None
) -> InsightFeedOut:
    """The leaderboard insights for the calendar year of the latest Sunday (the points race and
    year-to-date rating gain); any other year is an empty feed in v1."""
    held = held_dates(session)
    if held and season is not None and season != held[-1].year:
        return empty_feed(session, held[-1])
    return page_feed(session, "leaderboards")


@router.get("/api/insights/records")
def records_insights_feed(session: SessionDep) -> InsightFeedOut:
    return page_feed(session, "records")


@router.get("/api/insights/stations")
def stations_insights_feed(session: SessionDep) -> InsightFeedOut:
    """Empty while the station kinds are dormant (fewer than 8 Sundays with station sheets)."""
    return page_feed(session, "stations")
