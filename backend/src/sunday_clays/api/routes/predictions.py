"""GET /api/predictions/next: next Sunday's forecast, predicted field median and expected scores."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sunday_clays.analytics import predictions
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session
from sunday_clays.weather.aggregate import aggregate_window
from sunday_clays.weather.forecast import load_forecast, next_event_sunday

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session, scope="function")]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class PredictionForecastOut(BaseModel):
    fetched_at: datetime
    temp_f: float
    apparent_f: float
    precip_in: float
    wind_mph: float
    gust_mph: float
    cloud_pct: float
    condition: str


class PredictionShooterOut(BaseModel):
    shooter_id: int
    display_name: str
    attend_prob: float
    expected: float
    sd: float


class NextPredictionsOut(BaseModel):
    target_date: date
    model_ready: bool
    forecast: PredictionForecastOut | None
    difficulty: float | None
    difficulty_sd: float | None
    difficulty_source: Literal["weather", "intercept", "prior", "none"]
    field_median: float | None
    expected_turnout: float
    shooters: list[PredictionShooterOut]


def local_now(tz: str) -> datetime:
    """The current wall-clock time in the club's timezone (tests pin this)."""
    return datetime.now(ZoneInfo(tz))


@router.get("/api/predictions/next")
def next_sunday(session: SessionDep, settings: SettingsDep) -> NextPredictionsOut:
    target = next_event_sunday(local_now(settings.timezone))
    stored = load_forecast(session, target)
    window = None if stored is None else aggregate_window(target, stored.hours)
    result = predictions.next_predictions(
        session, target, window, None if stored is None else stored.fetched_at
    )
    forecast = None
    if stored is not None and window is not None:
        forecast = PredictionForecastOut(
            fetched_at=stored.fetched_at,
            temp_f=window.temp_f,
            apparent_f=window.apparent_f,
            precip_in=window.precip_in,
            wind_mph=window.wind_mph,
            gust_mph=window.gust_mph,
            cloud_pct=window.cloud_pct,
            condition=window.condition,
        )
    return NextPredictionsOut(
        target_date=result.target_date,
        model_ready=result.model_ready,
        forecast=forecast,
        difficulty=result.difficulty.difficulty,
        difficulty_sd=result.difficulty.sd,
        difficulty_source=result.difficulty.source,
        field_median=result.field_median,
        expected_turnout=result.expected_turnout,
        shooters=[PredictionShooterOut.model_validate(asdict(r)) for r in result.shooters],
    )
