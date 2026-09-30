"""Year in Review (club and shooter) and "On this day"."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sunday_clays.analytics import yir
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session, scope="function")]
SettingsDep = Annotated[Settings, Depends(get_settings)]
YearPath = Annotated[int, Path(ge=2000, le=2100)]


class YirTotalsOut(BaseModel):
    year: int
    scored_events: int
    held_events: int
    rounds: int
    shooters: int
    clays_thrown: int
    clays_broken: int
    avg_score: float | None


class YirTopRoundOut(BaseModel):
    shooter_id: int
    display_name: str
    event_date: date
    score: int


class YirEventStatOut(BaseModel):
    event_date: date
    value: float


class YirMonthOut(BaseModel):
    month: int
    events: int
    rounds: int
    avg_score: float | None


class YirClubOut(BaseModel):
    year: int
    years: list[int]
    totals: YirTotalsOut
    events: int
    newcomers: int
    perfect_rounds: int
    top_rounds: list[YirTopRoundOut]
    mean_head_count: float | None
    busiest: YirEventStatOut | None
    hardest: YirEventStatOut | None
    easiest: YirEventStatOut | None
    trophies: int
    months: list[YirMonthOut]
    previous: YirTotalsOut | None


class YirShooterTotalsOut(BaseModel):
    year: int
    events: int
    rounds: int
    clays_thrown: int
    clays_broken: int
    avg_score: float | None


class YirPbOut(BaseModel):
    event_date: date
    score: int


class YirShooterMonthOut(BaseModel):
    month: int
    rounds: int
    avg_score: float | None
    club_avg_score: float | None


class YirShooterOut(BaseModel):
    year: int
    shooter_id: int
    display_name: str
    totals: YirShooterTotalsOut
    best: YirTopRoundOut | None
    wins: int
    podiums: int
    best_finish: int | None
    pbs: list[YirPbOut]
    trophies: int
    rating_start: float | None
    rating_end: float | None
    attendance_rank: int | None
    n_shooters: int
    months: list[YirShooterMonthOut]
    previous: YirShooterTotalsOut | None


class OnThisDayWinnerOut(BaseModel):
    shooter_id: int
    display_name: str
    score: int


class OnThisDayItemOut(BaseModel):
    years_ago: int
    event_date: date
    has_scores: bool
    head_count: int | None
    n_shooters: int
    top_score: int | None
    median: float | None
    winners: list[OnThisDayWinnerOut]


class OnThisDayOut(BaseModel):
    on: date
    items: list[OnThisDayItemOut]


@router.get("/api/yir/{year}")
def yir_club(
    session: SessionDep,
    year: YearPath,
    round_type: list[RoundType] = _filters.round_type_param,
) -> YirClubOut:
    data = yir.load_yir_frames(session)
    club = yir.club_year(yir.filter_round_types(data, round_type), year)
    return YirClubOut.model_validate({**asdict(club), "years": yir.scored_years(data)})


@router.get("/api/yir/{year}/shooters/{id}")
def yir_shooter(
    session: SessionDep,
    year: YearPath,
    shooter_id: Annotated[int, Path(alias="id")],
    round_type: list[RoundType] = _filters.round_type_param,
) -> YirShooterOut:
    data = yir.load_yir_frames(session)
    if shooter_id not in set(data.profiles["shooter_id"]):
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}.")
    return YirShooterOut.model_validate(
        asdict(yir.shooter_year(yir.filter_round_types(data, round_type), shooter_id, year))
    )


@router.get("/api/on-this-day")
def on_this_day(
    session: SessionDep,
    settings: SettingsDep,
    on: Annotated[date | None, Query(alias="date")] = None,
) -> OnThisDayOut:
    day = _filters.resolve_as_of(on, settings.timezone)
    items = yir.on_this_day(yir.load_yir_frames(session), day)
    return OnThisDayOut(on=day, items=[OnThisDayItemOut.model_validate(asdict(i)) for i in items])
