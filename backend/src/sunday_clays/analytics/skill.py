"""Dynamic Gaussian skill model (C7): per-shooter Kalman filter, leave-one-out days.

Model: score = skill(shooter, t) + day(t) + noise. The filter runs on the RAW scale;
published values add the level L_t (mean raw day effect over held events in
(t - 364d, t]): rating = mu + L_t, difficulty = -(d_t - L_t) (positive = harder than a
typical recent day). expected = mu_i + d_-i = published rating minus published
leave-one-out difficulty, so residual = score - expected is the raw-model residual.
"""

import itertools
import math
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

DEFAULT_GRID: dict[str, tuple[float, ...]] = {
    "obs_var": (10, 12, 14, 16, 20),
    "drift_var_per_week": (0.05, 0.15, 0.3),
    "difficulty_var": (2, 4, 9),
    "prior_mu": (28, 30, 32),
    "prior_var": (36, 49),
}
CALIBRATION_GRID: dict[str, tuple[float, ...]] = {
    "obs_var": (12, 14, 16),
    "drift_var_per_week": (0.05, 0.15, 0.3),
    "difficulty_var": (2, 4, 9),
    "prior_mu": (30,),
    "prior_var": (49,),
}
GRID_KEYS: tuple[str, ...] = (
    "obs_var",
    "drift_var_per_week",
    "difficulty_var",
    "prior_mu",
    "prior_var",
)
BURN_IN_HELD_EVENTS = 8
LEVEL_WINDOW = timedelta(days=364)
MIN_SCORE = 0
MAX_SCORE = 50

ROUND_OUTPUT_COLUMNS: tuple[str, ...] = (
    "round_id",
    "expected",
    "residual",
    "mu_before",
    "var_before",
    "mu_after",
    "var_after",
)
EVENT_OUTPUT_COLUMNS: tuple[str, ...] = ("event_date", "difficulty", "d_raw", "level")
HISTORY_COLUMNS: tuple[str, ...] = ("shooter_id", "event_date", "mu", "var")
PREDICTION_COLUMNS: tuple[str, ...] = (
    "shooter_id",
    "attend_prob",
    "expected",
    "sd",
    "p_win",
    "p_podium",
)


@dataclass(frozen=True)
class SkillParams:
    prior_mu: float = 30.0
    prior_var: float = 49.0
    obs_var: float = 14.0
    drift_var_per_week: float = 0.3
    difficulty_var: float = 4.0
    max_var: float = 49.0

    def __post_init__(self) -> None:
        """Variances must be > 0 and drift >= 0 (NaN fails both), else ValueError."""
        positive = (
            ("prior_var", self.prior_var),
            ("obs_var", self.obs_var),
            ("difficulty_var", self.difficulty_var),
            ("max_var", self.max_var),
        )
        for name, value in positive:
            if not value > 0:
                raise ValueError(f"SkillParams.{name} must be > 0, got {value!r}")
        if not self.drift_var_per_week >= 0:
            raise ValueError(
                f"SkillParams.drift_var_per_week must be >= 0, got {self.drift_var_per_week!r}"
            )


DEFAULT_PARAMS = SkillParams()


@dataclass(frozen=True)
class SkillResult:
    rounds: pd.DataFrame  # ROUND_OUTPUT_COLUMNS (published scale for mu_*)
    events: pd.DataFrame  # EVENT_OUTPUT_COLUMNS
    history: pd.DataFrame  # HISTORY_COLUMNS (published mu)
    # shooter -> (mu, var, last_date) on the raw scale
    final_state: dict[int, tuple[float, float, date]]
    current_level: float  # L at the last event


@dataclass(frozen=True)
class _Event:
    event_date: date
    held: bool
    round_ids: IntArray
    scores: FloatArray
    round_shooter: IntArray  # index into `shooters` for each round
    shooters: tuple[int, ...]
    counts: FloatArray  # k_i
    means: FloatArray  # mean score of shooter i that day


@dataclass
class _Collected:
    rounds: list[pd.DataFrame]
    events: list[tuple[date, float, float, float]]
    history: list[pd.DataFrame]


def _prepare(rounds: pd.DataFrame) -> list[_Event]:
    """Group rounds by event; shooters ascending, rounds by (name_key, ordinal)."""
    ordered = rounds.sort_values(
        ["event_date", "shooter_id", "name_key", "ordinal"], kind="mergesort"
    )
    events: list[_Event] = []
    for event_date, group in ordered.groupby("event_date", sort=True):
        shooter_ids = group["shooter_id"].to_numpy(dtype=np.int64)
        unique, inverse, counts = np.unique(shooter_ids, return_inverse=True, return_counts=True)
        scores = group["score"].to_numpy(dtype=np.float64)
        sums = np.bincount(inverse, weights=scores)
        events.append(
            _Event(
                event_date=cast(date, event_date),
                held=bool(group["held"].iloc[0]),
                round_ids=group["round_id"].to_numpy(dtype=np.int64),
                scores=scores,
                round_shooter=inverse.astype(np.int64),
                shooters=tuple(int(s) for s in unique),
                counts=counts.astype(np.float64),
                means=sums / counts,
            )
        )
    return events


def _event_loglik(ev: _Event, mu: FloatArray, var: FloatArray, params: SkillParams) -> float:
    """log N(y_t; m_t, obs_var*I + Z diag(var) Z^T + difficulty_var*11^T)."""
    idx = ev.round_shooter
    same = idx[:, None] == idx[None, :]
    cov = np.where(same, var[idx][:, None], 0.0) + params.difficulty_var
    cov[np.diag_indices_from(cov)] += params.obs_var
    resid = ev.scores - mu[idx]
    _, logdet = np.linalg.slogdet(cov)
    quad = float(resid @ np.linalg.solve(cov, resid))
    return -0.5 * (len(resid) * math.log(2 * math.pi) + float(logdet) + quad)


def _run(
    events: list[_Event], params: SkillParams, collected: _Collected | None
) -> tuple[float, dict[int, tuple[float, float, date]], float]:
    """Filter every event in date order -> (log-lik after burn-in, state, level).

    The log-likelihood is accumulated only for calibration runs (`collected is None`);
    `run_skill_model` passes a collector and ignores it.
    """
    mu: dict[int, float] = {}
    var: dict[int, float] = {}
    last: dict[int, date] = {}
    window: deque[tuple[date, float]] = deque()
    level = 0.0
    loglik = 0.0
    held_seen = 0
    for ev in events:
        n = len(ev.shooters)
        m = np.empty(n)
        v = np.empty(n)
        for j, shooter in enumerate(ev.shooters):
            if shooter in mu:
                weeks = (ev.event_date - last[shooter]).days / 7.0
                m[j] = mu[shooter]
                v[j] = min(var[shooter] + params.drift_var_per_week * weeks, params.max_var)
            else:
                m[j] = params.prior_mu
                v[j] = params.prior_var
        while window and window[0][0] <= ev.event_date - LEVEL_WINDOW:
            window.popleft()
        if ev.held:
            held_seen += 1
            if collected is None and held_seen > BURN_IN_HELD_EVENTS:
                loglik += _event_loglik(ev, m, v, params)
            obs = params.obs_var / ev.counts
            w = 1.0 / (v + obs)
            r = ev.means - m
            precision = float(w.sum()) + 1.0 / params.difficulty_var
            total = float((w * r).sum())
            d = total / precision
            precision_loo = precision - w
            d_loo = (total - w * r) / precision_loo
            gain = v / (v + obs + 1.0 / precision_loo)
            m_after = m + gain * (ev.means - m - d_loo)
            v_after = v * (1.0 - gain)
            window.append((ev.event_date, d))
            level = sum(x for _, x in window) / len(window)
        else:
            d_loo = np.full(n, np.nan)
            m_after, v_after = m, v
            if window:
                level = sum(x for _, x in window) / len(window)
            d = math.nan
        if collected is not None:
            idx = ev.round_shooter
            expected = m[idx] + d_loo[idx]
            collected.rounds.append(
                pd.DataFrame(
                    {
                        "round_id": ev.round_ids,
                        "expected": expected,
                        "residual": ev.scores - expected,
                        "mu_before": m[idx] + level,
                        "var_before": v[idx],
                        "mu_after": m_after[idx] + level,
                        "var_after": v_after[idx],
                    }
                )
            )
            collected.events.append(
                (ev.event_date, -(d - level) if ev.held else math.nan, d, level)
            )
            collected.history.append(
                pd.DataFrame(
                    {
                        "shooter_id": np.array(ev.shooters, dtype=np.int64),
                        "event_date": [ev.event_date] * n,
                        "mu": m_after + level,
                        "var": v_after,
                    }
                )
            )
        for j, shooter in enumerate(ev.shooters):
            mu[shooter] = float(m_after[j])
            var[shooter] = float(v_after[j])
            last[shooter] = ev.event_date
    state = {s: (mu[s], var[s], last[s]) for s in mu}
    return loglik, state, level


def _concat(frames: list[pd.DataFrame], columns: Sequence[str]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in columns})
    return pd.concat(frames, ignore_index=True)


def run_skill_model(rounds: pd.DataFrame, params: SkillParams = DEFAULT_PARAMS) -> SkillResult:
    """Run the online filter over every event in `rounds`.

    Required columns: round_id, event_date, shooter_id, name_key, ordinal, score, held.
    Held events update skills and difficulty; non-held events carry each attendee's
    drift-inflated state forward (expected/residual/difficulty NaN).
    """
    collected = _Collected(rounds=[], events=[], history=[])
    _, state, level = _run(_prepare(rounds), params, collected)
    events = pd.DataFrame(collected.events, columns=list(EVENT_OUTPUT_COLUMNS))
    return SkillResult(
        rounds=_concat(collected.rounds, ROUND_OUTPUT_COLUMNS),
        events=events,
        history=_concat(collected.history, HISTORY_COLUMNS),
        final_state=state,
        current_level=level,
    )


def calibrate(
    rounds: pd.DataFrame, grid: Mapping[str, Sequence[float]] = DEFAULT_GRID
) -> SkillParams:
    """Grid search maximizing the one-step-ahead log-likelihood (C7 objective).

    Held events after the first 8 are scored. Points are visited in lexicographic order
    of GRID_KEYS with values ascending; max() returns the first maximal item, so ties
    keep the lexicographically first point. max_var = prior_var. The grid's keys must be
    exactly GRID_KEYS: a missing key raises KeyError (Decision 11) and any other key
    (e.g. the derived max_var) raises ValueError naming it, rather than being ignored.
    No `assert` here: ruff S101 applies to src/.
    """
    unknown = sorted(set(grid) - set(GRID_KEYS))
    if unknown:
        raise ValueError(f"calibrate grid has unknown keys: {unknown}; expected {GRID_KEYS}")
    events = _prepare(rounds)
    combos = itertools.product(*(sorted(grid[key]) for key in GRID_KEYS))
    points = (dict(zip(GRID_KEYS, (float(x) for x in combo), strict=True)) for combo in combos)
    candidates = (SkillParams(**values, max_var=values["prior_var"]) for values in points)
    return max(candidates, key=lambda params: _run(events, params, None)[0])


def predict(
    state: Mapping[int, tuple[float, float, date]],
    shooter_ids: Sequence[int],
    on: date,
    params: SkillParams,
    level: float,
    difficulty: float | None = None,
    difficulty_sd: float = 0.0,
    attend_prob: Mapping[int, float] | None = None,
    n_sims: int = 10_000,
    seed: int = 0,
) -> pd.DataFrame:
    """Expected score, sd and win/podium odds for `shooter_ids` on `on` (C7 predict).

    Known shooters' var drifts from last_date to `on`, the gap clamped at 0 days so an
    earlier `on` never shrinks it. Unknown shooters start at (prior_mu, prior_var).
    expected = mu + level - (difficulty or 0); sd = sqrt(var + obs_var + difficulty_sd^2).
    Each simulation draws one shared day effect, attendance ~ Bernoulli(attend_prob)
    (missing -> 1.0), skill ~ N(mu, var) and noise, then rounds and clips scores to
    0..50. p_win and p_podium are conditional on attending (ties count as wins); NaN when
    the shooter never attends in the simulations.
    """
    ids = list(shooter_ids)
    n = len(ids)
    if n == 0:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in PREDICTION_COLUMNS})
    mu = np.empty(n)
    var = np.empty(n)
    for j, shooter in enumerate(ids):
        if shooter in state:
            m, v, last = state[shooter]
            mu[j] = m
            days = max((on - last).days, 0)  # `on` before last_date adds no drift
            var[j] = min(v + params.drift_var_per_week * days / 7.0, params.max_var)
        else:
            mu[j] = params.prior_mu
            var[j] = params.prior_var
    probs = np.array([1.0 if attend_prob is None else attend_prob.get(s, 1.0) for s in ids])
    expected = mu + level - (difficulty if difficulty is not None else 0.0)
    sd = np.sqrt(var + params.obs_var + difficulty_sd**2)

    rng = np.random.default_rng(seed)
    day = rng.standard_normal((n_sims, 1)) * difficulty_sd
    attends = rng.random((n_sims, n)) < probs
    skill = rng.standard_normal((n_sims, n)) * np.sqrt(var)
    noise = rng.standard_normal((n_sims, n)) * math.sqrt(params.obs_var)
    scores = np.clip(np.rint(expected + skill + noise + day), MIN_SCORE, MAX_SCORE)
    present = np.where(attends, scores, -np.inf)

    if n >= 2:
        top_two = np.partition(present, n - 2, axis=1)
        first, second = top_two[:, n - 1 : n], top_two[:, n - 2 : n - 1]
    else:
        first, second = present, np.full((n_sims, 1), -np.inf)
    best_other = np.where(present == first, second, first)
    wins = attends & (present >= best_other)
    better = np.stack([(present > present[:, [i]]).sum(axis=1) for i in range(n)], axis=1)
    podiums = attends & (better + 1 <= 3)
    n_attend = attends.sum(axis=0)
    safe = np.maximum(n_attend, 1)
    p_win = np.where(n_attend > 0, wins.sum(axis=0) / safe, np.nan)
    p_podium = np.where(n_attend > 0, podiums.sum(axis=0) / safe, np.nan)
    return pd.DataFrame(
        {
            "shooter_id": np.array(ids, dtype=np.int64),
            "attend_prob": probs,
            "expected": expected,
            "sd": sd,
            "p_win": p_win,
            "p_podium": p_podium,
        }
    )
