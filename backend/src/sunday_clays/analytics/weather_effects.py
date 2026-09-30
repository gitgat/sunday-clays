"""Weather effects: club difficulty model, per-shooter sensitivity, band summaries and turnout.

Pure functions work on DataFrames; the ``@cached_by_data_version`` entry points at the bottom read
the C4 tables and the Plan 06 frames.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.domain.round_type import RoundType

COVARIATES: Final[tuple[str, ...]] = ("temp_f", "gust_mph", "precip_in", "cloud_pct")
SENSITIVITY_COVARIATES: Final[tuple[str, ...]] = ("temp_f", "gust_mph", "precip_in")
MIN_SENSITIVITY_ROUNDS: Final = 10
EFFECT_UNITS: Final[Mapping[str, float]] = {"temp_f": 10.0, "gust_mph": 10.0, "precip_in": 0.1}
BAND_DIMENSIONS: Final[tuple[str, ...]] = (
    "temp_band",
    "wind_band",
    "precip_band",
    "condition",
    "time_of_year",
)
BAND_SOURCES: Final[Mapping[str, str]] = {
    "temp_band": "temp_f",
    "wind_band": "gust_mph",
    "precip_band": "precip_in",
}
CONDITION_ORDER: Final[tuple[str, ...]] = ("rain", "windy", "overcast", "partly_cloudy", "clear")
WEATHER_FIELDS: Final[tuple[str, ...]] = (
    "temp_f",
    "apparent_f",
    "precip_in",
    "wind_mph",
    "gust_mph",
    "wind_dir_deg",
    "cloud_pct",
    "humidity_pct",
    "pressure_hpa",
)
_EVENT_NUMERIC: Final[tuple[str, ...]] = (
    "head_count",
    "n",
    "median",
    "mean",
    "top_score",
    "difficulty",
    *WEATHER_FIELDS,
)
_WEATHER_EVENTS_SQL: Final = """
SELECT e.event_date, e.round_type, e.head_count, e.has_scores, e.results_complete,
       m.n, m.median, m.mean, m.top_score, m.difficulty,
       w.temp_f, w.apparent_f, w.precip_in, w.wind_mph, w.gust_mph, w.wind_dir_deg,
       w.cloud_pct, w.humidity_pct, w.pressure_hpa, w.condition
FROM events AS e
JOIN event_weather AS w ON w.event_date = e.event_date
LEFT JOIN event_metrics AS m ON m.event_date = e.event_date
ORDER BY e.event_date
"""
_EVENT_COLUMNS: Final[tuple[str, ...]] = (
    "event_date",
    "round_type",
    "head_count",
    "has_scores",
    "results_complete",
    "n",
    "median",
    "mean",
    "top_score",
    "difficulty",
    *WEATHER_FIELDS,
    "condition",
)


@dataclass(frozen=True)
class ClubModel:
    """WLS fit of published event difficulty on weather; coef/se start with the intercept."""

    covariates: tuple[str, ...]
    coef: tuple[float, ...]
    se: tuple[float, ...]
    sigma2: float
    n_events: int
    means: tuple[float, ...]

    def predict(self, x: Mapping[str, float]) -> float:
        slopes = zip(self.coef[1:], self.covariates, strict=True)
        return self.coef[0] + sum(beta * x[name] for beta, name in slopes)


@dataclass(frozen=True)
class BandStat:
    dimension: str
    band: str
    n_events: int
    n_rounds: int
    mean_score: float | None
    mean_difficulty: float | None


@dataclass(frozen=True)
class TurnoutStat:
    dimension: str
    band: str
    n_events: int
    mean_head_count: float
    median_head_count: float


@dataclass(frozen=True)
class ZScale:
    covariate: str
    mean: float
    sd: float


@dataclass(frozen=True)
class SensitivityTerm:
    covariate: str
    beta: float | None
    se: float | None
    shrunk: float
    per_unit: float


@dataclass(frozen=True)
class ShooterSensitivity:
    shooter_id: int
    display_name: str
    n_rounds: int
    terms: tuple[SensitivityTerm, ...]


@dataclass(frozen=True)
class Sensitivity:
    scales: tuple[ZScale, ...]
    tau2: tuple[tuple[str, float], ...]
    shooters: tuple[ShooterSensitivity, ...]


@dataclass(frozen=True)
class WeatherEvent:
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


@dataclass(frozen=True)
class Effects:
    model: ClubModel | None
    n_events: int
    bands: tuple[BandStat, ...]


def _opt_float(value: object) -> float | None:
    """A finite number as float; None, NaN and non-numbers become None."""
    if isinstance(value, (int, float)) and not math.isnan(value):
        return float(value)
    return None


def _opt_int(value: object) -> int | None:
    number = _opt_float(value)
    return None if number is None else round(number)


def with_bands(events: pd.DataFrame) -> pd.DataFrame:
    """Round precipitation to 3 dp (float4 storage); add the Plan 06 weather band columns and the
    time of year (`frames.season_label`)."""
    out = events.copy()
    out["precip_in"] = out["precip_in"].astype(float).round(3)
    out["temp_band"] = [frames.temp_band(float(v)) for v in out["temp_f"]]
    out["wind_band"] = [frames.wind_band(float(v)) for v in out["gust_mph"]]
    out["precip_band"] = [frames.precip_band(float(v)) for v in out["precip_in"]]
    out["time_of_year"] = [frames.season_label(day) for day in out["event_date"]]
    return out


def fit_club_model(
    events: pd.DataFrame, covariates: Sequence[str] = COVARIATES
) -> ClubModel | None:
    """WLS of `difficulty` on [1, *covariates] with weights `n` normalised to mean 1.

    Returns None when there are no more events than parameters or the design is rank-deficient
    (for example a covariate that never varies), so callers can fall back.
    """
    data = events.dropna(subset=["difficulty", "n", *covariates])
    data = data[data["n"].astype(float) > 0]
    n_events, n_params = len(data), len(covariates) + 1
    if n_events <= n_params:
        return None
    x = np.column_stack(
        [np.ones(n_events), *(data[name].to_numpy(dtype=float) for name in covariates)]
    )
    if int(np.linalg.matrix_rank(x)) < n_params:
        return None
    y = data["difficulty"].to_numpy(dtype=float)
    weights = data["n"].to_numpy(dtype=float)
    weights = weights / weights.mean()
    xtw = x.T * weights
    xtwx = xtw @ x
    beta = np.linalg.solve(xtwx, xtw @ y)
    resid = y - x @ beta
    sigma2 = float(np.sum(weights * resid**2) / (n_events - n_params))
    cov = sigma2 * np.linalg.inv(xtwx)
    se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    return ClubModel(
        covariates=tuple(covariates),
        coef=tuple(float(b) for b in beta),
        se=tuple(float(s) for s in se),
        sigma2=sigma2,
        n_events=n_events,
        means=tuple(float(data[name].astype(float).mean()) for name in covariates),
    )


def _band_order(dimension: str, band: str, group: pd.DataFrame) -> tuple[float, str]:
    if dimension == "time_of_year":
        return (float(frames.SEASONS.index(band)), band)
    if dimension == "condition":
        rank = CONDITION_ORDER.index(band) if band in CONDITION_ORDER else len(CONDITION_ORDER)
        return (float(rank), band)
    return (float(group[BAND_SOURCES[dimension]].astype(float).min()), band)


def _groups(frame: pd.DataFrame, dimension: str) -> list[tuple[str, pd.DataFrame]]:
    pairs = [(str(key), group) for key, group in frame.groupby(dimension, sort=False)]
    return sorted(pairs, key=lambda pair: _band_order(dimension, pair[0], pair[1]))


def band_summary(events: pd.DataFrame, rounds: pd.DataFrame) -> tuple[BandStat, ...]:
    """Per weather band: scored events, their rounds, mean score and mean published difficulty."""
    scored = events[events["has_scores"].astype(bool)]
    scores = rounds[["event_date", "score"]]
    stats: list[BandStat] = []
    for dimension in BAND_DIMENSIONS:
        for band, group in _groups(scored, dimension):
            band_rounds = scores[scores["event_date"].isin(set(group["event_date"]))]
            difficulty = group["difficulty"].dropna().astype(float)
            stats.append(
                BandStat(
                    dimension=dimension,
                    band=band,
                    n_events=len(group),
                    n_rounds=len(band_rounds),
                    mean_score=_opt_float(band_rounds["score"].astype(float).mean()),
                    mean_difficulty=_opt_float(difficulty.mean()),
                )
            )
    return tuple(stats)


def turnout(events: pd.DataFrame) -> tuple[TurnoutStat, ...]:
    """Head count per weather band over every event with weather and a recorded head count."""
    counted = events.dropna(subset=["head_count"])
    stats: list[TurnoutStat] = []
    for dimension in BAND_DIMENSIONS:
        for band, group in _groups(counted, dimension):
            heads = group["head_count"].astype(float)
            stats.append(
                TurnoutStat(
                    dimension=dimension,
                    band=band,
                    n_events=len(group),
                    mean_head_count=float(heads.mean()),
                    median_head_count=float(heads.median()),
                )
            )
    return tuple(stats)


def z_scales(events: pd.DataFrame) -> tuple[ZScale, ...]:
    """Club-wide mean and sample SD of each sensitivity covariate over every event with weather."""
    scales: list[ZScale] = []
    for name in SENSITIVITY_COVARIATES:
        values = events[name].dropna().astype(float)
        mean = _opt_float(values.mean()) or 0.0
        sd = _opt_float(values.std(ddof=1)) or 0.0
        scales.append(ZScale(covariate=name, mean=mean, sd=sd))
    return tuple(scales)


def eb_shrink(betas: Sequence[float], ses: Sequence[float]) -> tuple[float, list[float]]:
    """Empirical-Bayes shrinkage toward 0: tau2 = max(0, var(beta) - mean(se^2))."""
    if len(betas) < 2:
        return 0.0, [0.0 for _ in betas]
    b = np.asarray(betas, dtype=float)
    s2 = np.asarray(ses, dtype=float) ** 2
    tau2 = max(0.0, float(np.var(b, ddof=1)) - float(np.mean(s2)))
    if tau2 == 0.0:
        return 0.0, [0.0 for _ in betas]
    return tau2, [float(v) for v in b * tau2 / (tau2 + s2)]


def fit_shooter(rows: pd.DataFrame, scales: Sequence[ZScale]) -> dict[str, tuple[float, float]]:
    """OLS of `residual` on [1, z-scored covariates] for one shooter.

    A covariate with a zero club SD, or one that never varies within these rounds, is left out; a
    rank-deficient design yields no betas at all.
    """
    y = rows["residual"].to_numpy(dtype=float)
    used: list[str] = []
    columns: list[np.ndarray] = [np.ones(len(rows))]
    for scale in scales:
        values = rows[scale.covariate].to_numpy(dtype=float)
        if scale.sd > 0 and float(np.ptp(values)) > 0:
            used.append(scale.covariate)
            columns.append((values - scale.mean) / scale.sd)
    x = np.column_stack(columns)
    n_params = x.shape[1]
    if len(used) == 0 or len(rows) <= n_params or int(np.linalg.matrix_rank(x)) < n_params:
        return {}
    xtx = x.T @ x
    beta = np.linalg.solve(xtx, x.T @ y)
    resid = y - x @ beta
    sigma2 = float(resid @ resid) / (len(rows) - n_params)
    se = np.sqrt(np.clip(np.diag(sigma2 * np.linalg.inv(xtx)), 0.0, None))
    return {name: (float(beta[i + 1]), float(se[i + 1])) for i, name in enumerate(used)}


def shooter_sensitivity(rounds: pd.DataFrame, scales: Sequence[ZScale]) -> Sensitivity:
    """Per-shooter weather sensitivity of residuals, shrunk toward 0 per covariate."""
    needed = ["residual", *SENSITIVITY_COVARIATES]
    usable = rounds.dropna(subset=needed).copy()
    usable["precip_in"] = usable["precip_in"].astype(float).round(3)
    fits: list[tuple[int, str, int, dict[str, tuple[float, float]]]] = []
    for _, group in usable.groupby("shooter_id", sort=True):
        if len(group) >= MIN_SENSITIVITY_ROUNDS:
            shooter_id = int(group["shooter_id"].iloc[0])
            name = str(group["display_name"].iloc[-1])
            fits.append((shooter_id, name, len(group), fit_shooter(group, scales)))
    tau2: dict[str, float] = {}
    shrunk: dict[tuple[int, str], float] = {}
    for scale in scales:
        name = scale.covariate
        defined = [(sid, fit[name]) for sid, _, _, fit in fits if name in fit]
        tau2[name], values = eb_shrink([b for _, (b, _) in defined], [s for _, (_, s) in defined])
        for (sid, _), value in zip(defined, values, strict=True):
            shrunk[(sid, name)] = value
    by_name = {scale.covariate: scale for scale in scales}
    shooters = []
    for sid, display_name, n_rounds, fit in fits:
        terms = []
        for name in SENSITIVITY_COVARIATES:
            beta, se = fit.get(name, (None, None))
            value = shrunk.get((sid, name), 0.0)
            sd = by_name[name].sd
            per_unit = value * EFFECT_UNITS[name] / sd if sd > 0 else 0.0
            terms.append(SensitivityTerm(name, beta, se, value, per_unit))
        shooters.append(ShooterSensitivity(sid, display_name, n_rounds, tuple(terms)))
    shooters.sort(key=lambda s: (s.display_name, s.shooter_id))
    return Sensitivity(
        scales=tuple(scales),
        tau2=tuple((scale.covariate, tau2[scale.covariate]) for scale in scales),
        shooters=tuple(shooters),
    )


def weather_event_rows(events: pd.DataFrame, rounds: pd.DataFrame) -> tuple[WeatherEvent, ...]:
    """One row per event with weather, with its round count and bands."""
    counts = rounds.groupby("event_date").size()
    out: list[WeatherEvent] = []
    for rec in events.to_dict("records"):
        day = rec["event_date"]
        out.append(
            WeatherEvent(
                event_date=day,
                round_type=str(rec["round_type"]),
                head_count=_opt_int(rec["head_count"]),
                has_scores=bool(rec["has_scores"]),
                n_rounds=int(counts.get(day, 0)),
                median=_opt_float(rec["median"]),
                mean=_opt_float(rec["mean"]),
                top_score=_opt_int(rec["top_score"]),
                difficulty=_opt_float(rec["difficulty"]),
                temp_f=float(rec["temp_f"]),
                apparent_f=_opt_float(rec["apparent_f"]),
                precip_in=float(rec["precip_in"]),
                wind_mph=_opt_float(rec["wind_mph"]),
                gust_mph=float(rec["gust_mph"]),
                wind_dir_deg=_opt_float(rec["wind_dir_deg"]),
                cloud_pct=float(rec["cloud_pct"]),
                humidity_pct=_opt_float(rec["humidity_pct"]),
                pressure_hpa=_opt_float(rec["pressure_hpa"]),
                condition=str(rec["condition"]),
                temp_band=str(rec["temp_band"]),
                wind_band=str(rec["wind_band"]),
                precip_band=str(rec["precip_band"]),
            )
        )
    return tuple(out)


def _as_dates(values: pd.Series) -> pd.Series:
    return pd.Series(pd.to_datetime(values).dt.date, index=values.index, dtype=object)


@cached_by_data_version
def load_weather_events(session: Session) -> pd.DataFrame:
    """Events that have an `event_weather` row, with event metrics and weather bands (C4 SQL)."""
    result = session.execute(text(_WEATHER_EVENTS_SQL))
    events = pd.DataFrame([tuple(row) for row in result], columns=list(_EVENT_COLUMNS))
    for name in _EVENT_NUMERIC:
        events[name] = pd.to_numeric(events[name], errors="coerce").astype(float)
    events["event_date"] = _as_dates(events["event_date"])
    events["has_scores"] = events["has_scores"].astype(bool)
    return with_bands(events)


def _score_rounds(session: Session) -> pd.DataFrame:
    rounds = frames.load_rounds(session)
    out = rounds[["event_date", "shooter_id", "display_name", "score", "round_type"]].copy()
    out["event_date"] = _as_dates(out["event_date"])
    return out


@cached_by_data_version
def club_regression(
    session: Session,
    round_types: tuple[RoundType, ...] = (),
    covariates: tuple[str, ...] = COVARIATES,
) -> ClubModel | None:
    """The club model over events of the given round types (empty = all)."""
    events = frames.apply_round_type_filter(load_weather_events(session), round_types)
    return fit_club_model(events, covariates)


def _within(frame: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Rows whose `event_date` lies in [start, end] (inclusive)."""
    return frame[(frame["event_date"] >= start) & (frame["event_date"] <= end)]


@cached_by_data_version
def effects(
    session: Session,
    round_types: tuple[RoundType, ...] = (),
    start: date = date.min,
    end: date = date.max,
) -> Effects:
    """The club model and event count over all history; the band summary only over [start, end]."""
    events = frames.apply_round_type_filter(load_weather_events(session), round_types)
    rounds = frames.apply_round_type_filter(_score_rounds(session), round_types)
    return Effects(
        model=club_regression(session, round_types, COVARIATES),
        n_events=len(events),
        bands=band_summary(_within(events, start, end), _within(rounds, start, end)),
    )


@cached_by_data_version
def sensitivity(session: Session) -> Sensitivity:
    rounds = frames.load_rounds(session)
    return shooter_sensitivity(rounds, z_scales(load_weather_events(session)))


@cached_by_data_version
def turnout_stats(
    session: Session, start: date = date.min, end: date = date.max
) -> tuple[TurnoutStat, ...]:
    return turnout(_within(load_weather_events(session), start, end))


@cached_by_data_version
def weather_events(session: Session) -> tuple[WeatherEvent, ...]:
    return weather_event_rows(load_weather_events(session), _score_rounds(session))
