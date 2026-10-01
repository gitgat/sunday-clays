"""Admin Analytics (Plan 16): read-only site usage for the admin page.

Admin-only by discovery (``admin_*``), never ETagged or stored (``/api/admin/`` in api/etag.py).
Nothing here mutates, so nothing is audited.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, NamedTuple
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sunday_clays.api.routes._filters import check_window
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain import site_analytics as usage
from sunday_clays.domain.site_analytics import Span

router = APIRouter(prefix="/api/admin/analytics", tags=["admin"])


class Window(NamedTuple):
    tz: str
    span: Span


def _now(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)


def analytics_window(
    settings: Annotated[Settings, Depends(get_settings)],
    since: date | None = None,
    as_of: date | None = None,
) -> Window:
    """``as_of`` defaults to today in the club's timezone; no ``since`` reaches back to the data."""
    end = as_of if as_of is not None else _now(ZoneInfo(settings.timezone)).date()
    check_window(since, end)
    return Window(settings.timezone, Span(since, end))


WindowDep = Annotated[Window, Depends(analytics_window)]


class VisitorDayOut(BaseModel):
    day: date
    devices: int


class VisitorWeekOut(BaseModel):
    week: date
    devices: int


class VisitorsOut(BaseModel):
    days: list[VisitorDayOut]
    weeks: list[VisitorWeekOut]
    busiest: list[VisitorDayOut]


class PageKindViewsOut(BaseModel):
    page_kind: str
    views: int


class BumpDayOut(BaseModel):
    day: date
    bumps: int


class TopInsightOut(BaseModel):
    key: str
    headline: str | None
    bumps: int


class BumpsOut(BaseModel):
    days: list[BumpDayOut]
    top: list[TopInsightOut]
    devices: int
    devices_all_time: int


class MeStatesOut(BaseModel):
    picked: int
    skipped: int
    none: int


class WeekMeStatesOut(MeStatesOut):
    week: date


class UptakeOut(BaseModel):
    weeks: list[WeekMeStatesOut]
    latest: MeStatesOut
    latest_since: date | None


@router.get("/visitors")
def visitors(session: SessionDep, window: WindowDep) -> VisitorsOut:
    result = usage.visitors(session, window.tz, window.span)
    return VisitorsOut(
        days=[VisitorDayOut(day=d.day, devices=d.devices) for d in result.days],
        weeks=[VisitorWeekOut(week=w.week, devices=w.devices) for w in result.weeks],
        busiest=[VisitorDayOut(day=d.day, devices=d.devices) for d in result.busiest],
    )


@router.get("/pages")
def pages(session: SessionDep, window: WindowDep) -> list[PageKindViewsOut]:
    return [
        PageKindViewsOut(page_kind=k.page_kind, views=k.views)
        for k in usage.page_kinds(session, window.tz, window.span)
    ]


@router.get("/bumps")
def bumps(session: SessionDep, window: WindowDep) -> BumpsOut:
    result = usage.bumps(session, window.tz, window.span)
    return BumpsOut(
        days=[BumpDayOut(day=d.day, bumps=d.bumps) for d in result.days],
        top=[TopInsightOut(key=t.key, headline=t.headline, bumps=t.bumps) for t in result.top],
        devices=result.devices,
        devices_all_time=result.devices_all_time,
    )


@router.get("/me-states")
def me_states(session: SessionDep, window: WindowDep) -> UptakeOut:
    result = usage.uptake(session, window.tz, window.span)
    latest = result.latest
    return UptakeOut(
        weeks=[
            WeekMeStatesOut(week=w.week, picked=w.picked, skipped=w.skipped, none=w.none)
            for w in result.weeks
        ],
        latest=MeStatesOut(picked=latest.picked, skipped=latest.skipped, none=latest.none),
        latest_since=result.latest_since,
    )
