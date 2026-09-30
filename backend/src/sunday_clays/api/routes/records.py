"""GET /api/records (Plan 09 T3): club records as of today, round-type filterable."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from sunday_clays.analytics.records import RECORD_LIMIT, records_for
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()


class RecordRoundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    value: float


class RecordJumpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    prev_event_date: date
    from_score: int
    to_score: int
    value: float


class RecordShooterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    value: float


class RecordRatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    value: float


class RecordsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    as_of: date
    highest_scores: list[RecordRoundOut]
    perfect_rounds: list[RecordRoundOut]
    biggest_adjusted: list[RecordRoundOut]
    biggest_jumps: list[RecordJumpOut]
    most_events: list[RecordShooterOut]
    longest_streaks: list[RecordShooterOut]
    highest_ratings: list[RecordRatingOut]
    since: date | None = None
    # Per list: every row that qualifies, and how many rows cut by `limit` tie with the last one.
    totals: dict[str, int]
    tied_more: dict[str, int]


MAX_LIMIT = 500


def _parse_limit(limit: str) -> int | None:
    """`all` = every row (None); otherwise a row count from 1 to MAX_LIMIT."""
    if limit == "all":
        return None
    count = int(limit)
    if count > MAX_LIMIT:
        raise DomainError("invalid_limit", f"'limit' must be 'all' or at most {MAX_LIMIT}")
    return count


@router.get("/api/records")
def get_records(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    round_types: list[RoundType] = _filters.round_type_param,
    since: date | None = None,
    as_of: date | None = None,
    limit: Annotated[str, Query(pattern=r"^(all|[1-9][0-9]{0,2})$")] = str(RECORD_LIMIT),
) -> RecordsOut:
    """Club records over ``[since, as_of]``; both are optional.

    The default end is the latest scored Sunday. ``limit`` (default 10, ``all``, or up to 500)
    caps every list; ``totals`` says how many rows each list has before the cap.
    """
    day = as_of if as_of is not None else _filters.latest_scored_day(session, settings.timezone)
    if since is not None and since > day:
        raise DomainError("invalid_range", "'since' must be on or before 'as_of'")
    return RecordsOut.model_validate(
        records_for(session, day, tuple(sorted(set(round_types))), since, _parse_limit(limit))
    )
