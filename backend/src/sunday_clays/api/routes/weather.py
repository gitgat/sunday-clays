"""Weather page API: events with weather, the club model, band effects, sensitivity, turnout."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from sunday_clays.analytics import weather_effects
from sunday_clays.api.routes._filters import round_type_param
from sunday_clays.db import SessionDep
from sunday_clays.domain.round_type import RoundType

router = APIRouter()


class WeatherEventOut(BaseModel):
    event_date: date
    round_type: str
    head_count: int | None
    has_scores: bool
    n_rounds: int
    median: float | None
    mean: float | None
    top_score: int | None
    difficulty: float | None
    temp_f: float
    apparent_f: float | None
    precip_in: float
    wind_mph: float | None
    gust_mph: float
    wind_dir_deg: float | None
    cloud_pct: float
    humidity_pct: float | None
    pressure_hpa: float | None
    condition: str
    temp_band: str
    wind_band: str
    precip_band: str


class WeatherTermOut(BaseModel):
    name: str
    coef: float
    se: float
    mean: float | None


class WeatherModelOut(BaseModel):
    terms: list[WeatherTermOut]
    sigma2: float
    n_events: int


class WeatherBandOut(BaseModel):
    dimension: str
    band: str
    n_events: int
    n_rounds: int
    mean_score: float | None
    mean_difficulty: float | None


class WeatherEffectsOut(BaseModel):
    model: WeatherModelOut | None
    n_events: int
    bands: list[WeatherBandOut]


class WeatherScaleOut(BaseModel):
    covariate: str
    mean: float
    sd: float


class WeatherTauOut(BaseModel):
    covariate: str
    tau2: float


class WeatherSensitivityTermOut(BaseModel):
    covariate: str
    beta: float | None
    se: float | None
    shrunk: float
    per_unit: float


class WeatherShooterOut(BaseModel):
    shooter_id: int
    display_name: str
    n_rounds: int
    terms: list[WeatherSensitivityTermOut]


class WeatherSensitivityOut(BaseModel):
    scales: list[WeatherScaleOut]
    tau2: list[WeatherTauOut]
    shooters: list[WeatherShooterOut]


class WeatherTurnoutOut(BaseModel):
    dimension: str
    band: str
    n_events: int
    mean_head_count: float
    median_head_count: float


def _model_out(model: weather_effects.ClubModel | None) -> WeatherModelOut | None:
    if model is None:
        return None
    names = ("intercept", *model.covariates)
    means: tuple[float | None, ...] = (None, *model.means)
    terms = [
        WeatherTermOut(name=n, coef=c, se=s, mean=m)
        for n, c, s, m in zip(names, model.coef, model.se, means, strict=True)
    ]
    return WeatherModelOut(terms=terms, sigma2=model.sigma2, n_events=model.n_events)


@router.get("/api/weather/events")
def weather_events(session: SessionDep) -> list[WeatherEventOut]:
    return [
        WeatherEventOut.model_validate(asdict(e)) for e in weather_effects.weather_events(session)
    ]


@router.get("/api/weather/effects")
def weather_effects_route(
    session: SessionDep,
    round_types: list[RoundType] = round_type_param,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> WeatherEffectsOut:
    """The club model is fitted over all history; only the bands honour `from`/`to`."""
    result = weather_effects.effects(
        session, tuple(sorted(set(round_types))), date_from or date.min, date_to or date.max
    )
    return WeatherEffectsOut(
        model=_model_out(result.model),
        n_events=result.n_events,
        bands=[WeatherBandOut.model_validate(asdict(b)) for b in result.bands],
    )


@router.get("/api/weather/sensitivity")
def weather_sensitivity(session: SessionDep) -> WeatherSensitivityOut:
    result = weather_effects.sensitivity(session)
    return WeatherSensitivityOut(
        scales=[WeatherScaleOut.model_validate(asdict(s)) for s in result.scales],
        tau2=[WeatherTauOut(covariate=c, tau2=t) for c, t in result.tau2],
        shooters=[WeatherShooterOut.model_validate(asdict(s)) for s in result.shooters],
    )


@router.get("/api/weather/turnout")
def weather_turnout(
    session: SessionDep,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> list[WeatherTurnoutOut]:
    stats = weather_effects.turnout_stats(session, date_from or date.min, date_to or date.max)
    return [WeatherTurnoutOut.model_validate(asdict(t)) for t in stats]
