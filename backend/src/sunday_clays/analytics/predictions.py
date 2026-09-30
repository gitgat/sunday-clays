"""Next-Sunday predictions: attendance, day difficulty from the forecast and expected scores.

Expected score only (owner decision): no win or podium odds and no ranking of shooters by
predicted score. `skill.predict` is called with a single simulation because only its
deterministic `expected` and `sd` columns are used.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, skill, weather_effects
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.skill import SkillParams
from sunday_clays.analytics.weather_effects import ClubModel
from sunday_clays.weather.aggregate import WindowWeather

ATTENDANCE_WINDOW: Final = 13
PARAM_FIELDS: Final[tuple[str, ...]] = (
    "prior_mu",
    "prior_var",
    "obs_var",
    "drift_var_per_week",
    "difficulty_var",
    "max_var",
)
DifficultySource = Literal["weather", "intercept", "prior", "none"]


@dataclass(frozen=True)
class DifficultyChoice:
    source: DifficultySource
    difficulty: float | None
    sd: float | None


@dataclass(frozen=True)
class SkillSnapshot:
    params: SkillParams
    level: float
    state: Mapping[int, tuple[float, float, date]]


@dataclass(frozen=True)
class PredictionRow:
    shooter_id: int
    display_name: str
    attend_prob: float
    expected: float
    sd: float


@dataclass(frozen=True)
class NextPrediction:
    target_date: date
    model_ready: bool
    difficulty: DifficultyChoice
    field_median: float | None
    expected_turnout: float
    shooters: tuple[PredictionRow, ...]


def _as_dates(values: pd.Series) -> pd.Series:
    return pd.Series(pd.to_datetime(values).dt.date, index=values.index, dtype=object)


def attendance_probs(rounds: pd.DataFrame, events: pd.DataFrame, on: date) -> dict[int, float]:
    """(# of the last 13 has_scores events before `on` attended) / 13, for shooters with p > 0."""
    event_dates = _as_dates(events["event_date"])
    scored = sorted(
        {d for d, has in zip(event_dates, events["has_scores"], strict=True) if has and d < on}
    )
    window = set(scored[-ATTENDANCE_WINDOW:])
    attended = rounds.assign(event_date=_as_dates(rounds["event_date"]))
    attended = attended[attended["event_date"].isin(window)]
    counts = attended.groupby("shooter_id")["event_date"].nunique()
    ids, attended_counts = counts.index.tolist(), counts.tolist()
    return {int(s): int(n) / ATTENDANCE_WINDOW for s, n in zip(ids, attended_counts, strict=True)}


def weighted_median(values: Sequence[float], weights: Sequence[float]) -> float | None:
    """Lower weighted median: the smallest value whose cumulative weight reaches half the total."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    keep = w > 0
    if not bool(keep.any()):
        return None
    order = np.argsort(v[keep], kind="stable")
    ordered, cumulative = v[keep][order], np.cumsum(w[keep][order])
    return float(ordered[int(np.searchsorted(cumulative, cumulative[-1] / 2.0, side="left"))])


def choose_difficulty(
    forecast: Mapping[str, float] | None,
    full: ClubModel | None,
    intercept: ClubModel | None,
    params: SkillParams | None,
) -> DifficultyChoice:
    """Forecast x club model, else the intercept-only fit, else the skill prior's day variance."""
    if forecast is not None and full is not None:
        return DifficultyChoice("weather", full.predict(forecast), math.sqrt(full.sigma2))
    if intercept is not None:
        return DifficultyChoice("intercept", intercept.coef[0], math.sqrt(intercept.sigma2))
    if params is not None:
        return DifficultyChoice("prior", None, math.sqrt(params.difficulty_var))
    return DifficultyChoice("none", None, None)


def parse_skill_params(value: object) -> SkillParams | None:
    """`app_state.skill_params` (an asdict of SkillParams) back into SkillParams, else None."""
    if not isinstance(value, dict):
        return None
    try:
        return SkillParams(**{name: float(value[name]) for name in PARAM_FIELDS})
    except (KeyError, TypeError, ValueError):
        return None


def forecast_covariates(window: WindowWeather) -> dict[str, float]:
    return {name: float(getattr(window, name)) for name in weather_effects.COVARIATES}


def prediction_rows(pred: pd.DataFrame, names: Mapping[int, str]) -> list[PredictionRow]:
    """Rows from `skill.predict` output, alphabetical (never ordered by predicted score)."""
    rows = [
        PredictionRow(
            shooter_id=int(rec["shooter_id"]),
            display_name=names[int(rec["shooter_id"])],
            attend_prob=float(rec["attend_prob"]),
            expected=min(50.0, max(0.0, float(rec["expected"]))),
            sd=float(rec["sd"]),
        )
        for rec in pred.to_dict("records")
    ]
    rows.sort(key=lambda r: (r.display_name, r.shooter_id))
    return rows


def _app_state(session: Session, key: str) -> object:
    return session.execute(
        text("SELECT value FROM app_state WHERE key = :key"), {"key": key}
    ).scalar_one_or_none()


@cached_by_data_version
def skill_snapshot(session: Session) -> SkillSnapshot | None:
    """Re-run the s30 skill model with the stored params; None until s30 has stored both keys."""
    params = parse_skill_params(_app_state(session, "skill_params"))
    level = _app_state(session, "skill_level")
    if params is None or not isinstance(level, (int, float)):
        return None
    result = skill.run_skill_model(frames.load_rounds(session), params)
    return SkillSnapshot(params=params, level=float(level), state=dict(result.final_state))


def _scored_events(session: Session) -> pd.DataFrame:
    rows = session.execute(text("SELECT event_date, has_scores FROM events")).all()
    return pd.DataFrame([tuple(r) for r in rows], columns=["event_date", "has_scores"])


def _display_names(session: Session) -> dict[int, str]:
    rows = session.execute(text("SELECT shooter_id, display_name FROM shooter_profiles")).all()
    return {int(r[0]): str(r[1]) for r in rows}


def _deceased_ids(session: Session) -> set[int]:
    rows = session.execute(
        text("SELECT shooter_id FROM shooter_profiles WHERE status = 'deceased'")
    ).all()
    return {int(r[0]) for r in rows}


@cached_by_data_version
def next_predictions(
    session: Session,
    target_date: date,
    forecast: WindowWeather | None,
    fetched_at: datetime | None,
) -> NextPrediction:
    """Predictions for `target_date`; the memo key includes the forecast and `fetched_at` (C7)."""
    snapshot = skill_snapshot(session)
    choice = choose_difficulty(
        None if forecast is None else forecast_covariates(forecast),
        weather_effects.club_regression(session, (), weather_effects.COVARIATES),
        weather_effects.club_regression(session, (), ()),
        None if snapshot is None else snapshot.params,
    )
    if snapshot is None:
        return NextPrediction(target_date, False, choice, None, 0.0, ())
    deceased = _deceased_ids(session)  # nobody who has died is expected next Sunday
    probs = {
        s: p
        for s, p in attendance_probs(
            frames.load_rounds(session), _scored_events(session), target_date
        ).items()
        if s not in deceased
    }
    if not probs:
        return NextPrediction(target_date, True, choice, None, 0.0, ())
    pred = skill.predict(
        snapshot.state,
        sorted(probs),
        target_date,
        snapshot.params,
        snapshot.level,
        difficulty=choice.difficulty,
        difficulty_sd=choice.sd or 0.0,
        attend_prob=probs,
        n_sims=1,  # win/podium odds are not used, so skip the simulation cost
    )
    rows = prediction_rows(pred, _display_names(session))
    median = weighted_median([r.expected for r in rows], [r.attend_prob for r in rows])
    return NextPrediction(
        target_date=target_date,
        model_ready=True,
        difficulty=choice,
        field_median=median,
        expected_turnout=float(sum(probs.values())),
        shooters=tuple(rows),
    )
