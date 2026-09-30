"""Club regulars, guest conversion, parity and trends (Plan 06 T9)."""

from dataclasses import asdict
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sunday_clays.analytics import club_insights, frames
from sunday_clays.api.routes._filters import latest_scored_day, resolve_as_of
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep

router = APIRouter()


class CoreShooterOut(BaseModel):
    shooter_id: int
    display_name: str
    events_attended: int
    share: float


class LapsedShooterOut(BaseModel):
    shooter_id: int
    display_name: str
    last_event: date


class RegularsOut(BaseModel):
    as_of: date
    n_held_window: int
    core: list[CoreShooterOut]
    lapsed: list[LapsedShooterOut]


class ConversionYearOut(BaseModel):
    year: int
    new_guests: int
    converted: int
    median_days_to_convert: float | None


class ParityYearOut(BaseModel):
    year: int
    n_events: int
    distinct_winners: int
    top3_share: float | None
    favorite_win_rate: float | None


class YearTrendOut(BaseModel):
    year: int
    events_held: int
    mean_head_count: float | None
    unique_shooters: int
    ytd_events: int
    ytd_rounds: int
    ytd_unique_shooters: int
    ytd_events_yoy: float | None


class EventTrendOut(BaseModel):
    event_date: date
    top_score: int
    median: float
    difficulty: float | None
    top_score_rolling8: float
    median_rolling8: float
    difficulty_rolling8: float | None


class MonthTrendOut(BaseModel):
    month: int
    n_events: int
    mean_head_count: float | None
    mean_median: float | None


class ClubTrendsOut(BaseModel):
    as_of: date
    years: list[YearTrendOut]
    events: list[EventTrendOut]
    months: list[MonthTrendOut]


@router.get("/api/club/regulars")
def get_regulars(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    as_of: date | None = None,
) -> RegularsOut:
    result = club_insights.regulars(
        frames.load_rounds(session),
        frames.load_events(session),
        as_of if as_of is not None else latest_scored_day(session, settings.timezone),
    )
    return RegularsOut.model_validate(asdict(result))


@router.get("/api/club/conversion")
def get_conversion(session: SessionDep) -> list[ConversionYearOut]:
    return [
        ConversionYearOut.model_validate(asdict(row))
        for row in club_insights.guest_conversion(frames.load_rounds(session))
    ]


@router.get("/api/club/parity")
def get_parity(session: SessionDep, by: Literal["year"] = "year") -> list[ParityYearOut]:
    return [
        ParityYearOut.model_validate(asdict(row))
        for row in club_insights.parity(frames.load_rounds(session))
    ]


@router.get("/api/club/trends")
def get_trends(
    session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> ClubTrendsOut:
    as_of = resolve_as_of(None, settings.timezone)
    rounds, events = frames.load_rounds(session), frames.load_events(session)
    return ClubTrendsOut(
        as_of=as_of,
        years=[
            YearTrendOut.model_validate(asdict(y))
            for y in club_insights.yearly_trends(rounds, events, as_of)
        ],
        events=[
            EventTrendOut.model_validate(asdict(e))
            for e in club_insights.event_trends(events, as_of)
        ],
        months=[
            MonthTrendOut.model_validate(asdict(m))
            for m in club_insights.seasonality(events, as_of)
        ],
    )
