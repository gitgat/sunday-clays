"""GET /api/leaderboards (C8): one leaderboard, time-sliced by as_of; rating climbers (Plan 12)."""

from collections.abc import Sequence
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    LeaderboardRow,
    ShooterStatus,
    leaderboard_event_dates,
    leaderboard_for,
)
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()


class LeaderboardRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    status: ShooterStatus | None
    value: float
    n_rounds: int


class LeaderboardOut(BaseModel):
    period: LeaderboardPeriod
    metric: LeaderboardMetric
    as_of: date
    min_rounds_applied: int
    n_eligible: int
    event_dates: list[date]
    since: date | None = None
    # The dates the board counts: `start` is None for "from the beginning"; `end` is `as_of`.
    start: date | None = None
    end: date
    rows: list[LeaderboardRowOut]


@router.get("/api/leaderboards")
def get_leaderboard(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    period: LeaderboardPeriod = LeaderboardPeriod.SEASON,
    metric: LeaderboardMetric = LeaderboardMetric.AVG_SCORE,
    as_of: date | None = None,
    since: date | None = None,
    round_types: list[RoundType] = _filters.round_type_param,
    gauge: Annotated[str | None, Query(max_length=40)] = None,
    status: ShooterStatus | None = None,
) -> LeaderboardOut:
    day = as_of if as_of is not None else _filters.latest_scored_day(session, settings.timezone)
    if since is not None and since > day:
        raise DomainError("invalid_range", "'since' must be on or before 'as_of'")
    # A canonical memo key: reordered or repeated ?round_type= values share one entry.
    filters = LeaderboardFilters(
        round_types=tuple(sorted(set(round_types))), gauge=gauge, status=status
    )
    board = leaderboard_for(session, period, metric, day, filters, since)
    return LeaderboardOut(
        period=board.period,
        metric=board.metric,
        as_of=board.as_of,
        min_rounds_applied=board.min_rounds_applied,
        n_eligible=board.n_eligible,
        event_dates=list(leaderboard_event_dates(session)),
        since=board.since,
        start=board.start,
        end=board.as_of,
        rows=[LeaderboardRowOut.model_validate(row) for row in board.records()],
    )


class ClimberOut(BaseModel):
    shooter_id: int
    display_name: str
    gain: float  # points of rating gained over the window (always > 0)
    n_rounds: int


class MoversOut(BaseModel):
    period: LeaderboardPeriod
    as_of: date
    # The dates the gain covers: `start` is None for "from the beginning"; `end` is `as_of`.
    start: date | None = None
    end: date
    rows: list[ClimberOut]


def rating_climbers(rows: Sequence[LeaderboardRow]) -> list[ClimberOut]:
    """The rating-gain board as chart rows: the gain in rating points, biggest first.

    Rating is never ranked (owner rule): no places, no rank, only how much each shooter gained.
    """
    return [
        ClimberOut(
            shooter_id=row.shooter_id,
            display_name=row.display_name,
            gain=round(row.value, 2),
            n_rounds=row.n_rounds,
        )
        for row in rows
    ]


@router.get("/api/leaderboards/movers")
def get_rating_movers(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    period: LeaderboardPeriod = LeaderboardPeriod.SEASON,
    as_of: date | None = None,
    since: date | None = None,
    status: ShooterStatus | None = None,
) -> MoversOut:
    """Biggest rating gains over the window (the `rating_gain` board, climbers only).

    Follows the header window like the leaderboards do: `since` replaces the period's start.
    """
    day = as_of if as_of is not None else _filters.latest_scored_day(session, settings.timezone)
    _filters.check_window(since, day)
    filters = LeaderboardFilters(status=status)
    board = leaderboard_for(session, period, LeaderboardMetric.RATING_GAIN, day, filters, since)
    return MoversOut(
        period=board.period,
        as_of=board.as_of,
        start=board.start,
        end=board.as_of,
        rows=rating_climbers(board.records()),
    )
