"""GET /api/shooters/{id}/insights?as_of= (Plan 06 T8)."""

from dataclasses import asdict
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from sunday_clays.analytics import frames
from sunday_clays.analytics.profile import shooter_insights
from sunday_clays.api.routes._filters import latest_scored_day
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError

router = APIRouter()


class LearningPointOut(BaseModel):
    k: int
    value: float
    club_median: float | None
    n_club: int


class RustOut(BaseModel):
    effect: float | None
    n: int
    club_effect: float | None


class MilestoneOut(BaseModel):
    next_events: int | None
    events_to_go: int | None
    weekly_rate: float
    projected_date: date | None


class ShooterInsightsOut(BaseModel):
    shooter_id: int
    as_of: date
    n_rounds: int
    floor: float | None
    ceiling: float | None
    recent_n: int
    bad_day_rate: float | None
    form: float | None
    form_label: Literal["hot", "cold", "steady"] | None
    wins: int
    podiums: int
    avg_percentile: float | None
    peak_mu: float | None
    peak_date: date | None
    learning_curve: list[LearningPointOut]
    rust: RustOut
    milestone: MilestoneOut


@router.get("/api/shooters/{id}/insights")
def get_shooter_insights(
    shooter_id: Annotated[int, Path(alias="id")],
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    as_of: date | None = None,
) -> ShooterInsightsOut:
    # Resolve the date before any memoized call (C7: never pass None).
    day = as_of if as_of is not None else latest_scored_day(session, settings.timezone)
    shooters = frames.load_shooters(session)
    if shooters.loc[shooters["shooter_id"] == shooter_id].empty:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    insights = shooter_insights(
        frames.load_rounds(session),
        frames.load_rating_history(session),
        shooters,
        shooter_id,
        day,
    )
    return ShooterInsightsOut.model_validate({"shooter_id": shooter_id, **asdict(insights)})
