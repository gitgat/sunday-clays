"""GET /api/leaderboards/history (C8): the time-machine frames behind the race page."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from sunday_clays.analytics.leaderboard_history import leaderboard_history_for
from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    ShooterStatus,
)
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()


class LeaderboardHistoryRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shooter_id: int
    display_name: str
    status: ShooterStatus | None
    value: float
    rank: int


class LeaderboardHistoryFrameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_date: date
    rows: list[LeaderboardHistoryRowOut]


class LeaderboardHistoryOut(BaseModel):
    period: LeaderboardPeriod
    metric: LeaderboardMetric
    frames: list[LeaderboardHistoryFrameOut]


@router.get("/api/leaderboards/history", response_model=LeaderboardHistoryOut)
def get_leaderboard_history(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    period: LeaderboardPeriod = LeaderboardPeriod.SEASON,
    metric: LeaderboardMetric = LeaderboardMetric.SEASON_POINTS,
    top: Annotated[int, Query(ge=1, le=500)] = 10,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    since: date | None = None,
    round_types: list[RoundType] = _filters.round_type_param,
    gauge: Annotated[str | None, Query(max_length=40)] = None,
    status: ShooterStatus | None = None,
) -> LeaderboardHistoryOut:
    end = date_to if date_to is not None else _filters.latest_scored_day(session, settings.timezone)
    start = date_from or since or date(end.year, 1, 1)
    if since is not None and since > start:
        raise DomainError("invalid_range", "'since' must be on or before 'from'")
    if start > end:
        raise DomainError("invalid_range", "'from' must be on or before 'to'")
    filters = LeaderboardFilters(
        round_types=tuple(sorted(set(round_types))), gauge=gauge, status=status
    )
    frames = leaderboard_history_for(session, period, metric, top, start, end, filters, since)
    return LeaderboardHistoryOut(
        period=period,
        metric=metric,
        frames=[LeaderboardHistoryFrameOut.model_validate(frame) for frame in frames],
    )
