import math
import warnings
from collections.abc import Callable
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from scipy.stats import multivariate_normal

from sunday_clays.analytics.skill import (
    CALIBRATION_GRID,
    SkillParams,
    _prepare,
    _run,
    calibrate,
    predict,
    run_skill_model,
)

ON = date(2026, 10, 4)
Simulate = Callable[..., tuple[pd.DataFrame, np.ndarray]]


@pytest.mark.parametrize(
    ("obs_var", "drift", "difficulty_var"),
    [(14.0, 0.15, 4.0), (16.0, 0.05, 9.0), (12.0, 0.3, 2.0)],
)
def test_calibrate_recovers_generating_params(
    simulate_skill_rounds: Simulate, obs_var: float, drift: float, difficulty_var: float
) -> None:
    rounds = simulate_skill_rounds(
        200, 60, 150, drift=drift, obs_var=obs_var, difficulty_var=difficulty_var
    )[0]

    best = calibrate(rounds, CALIBRATION_GRID)

    assert (best.obs_var, best.drift_var_per_week, best.difficulty_var) == (
        obs_var,
        drift,
        difficulty_var,
    )
    assert (best.prior_mu, best.prior_var, best.max_var) == (30.0, 49.0, 49.0)


# Values given unsorted. obs_var=1 sorts first and is implausible for obs_var=14 data, so
# it wins only while no event is scored: scoring even one event makes every obs_var=1
# point lose. The 8- and 9-event tests below pin BURN_IN_HELD_EVENTS from both sides.
IMPLAUSIBLE_FIRST_GRID = {**CALIBRATION_GRID, "obs_var": (12, 1), "prior_var": (49, 36)}


def test_calibrate_ties_keep_lexicographically_first_point(
    simulate_skill_rounds: Simulate,
) -> None:
    # 8 held events are all burn-in, so every grid point scores 0.0.
    rounds = simulate_skill_rounds(1, 10, 8, drift=0.15, obs_var=14.0, difficulty_var=4.0)[0]

    best = calibrate(rounds, IMPLAUSIBLE_FIRST_GRID)

    assert best == SkillParams(
        prior_mu=30.0,
        prior_var=36.0,
        obs_var=1.0,
        drift_var_per_week=0.05,
        difficulty_var=2.0,
        max_var=36.0,
    )


def test_calibrate_grid_missing_a_key_raises_key_error(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds([(ON, 1, 30), (ON, 2, 35)])
    grid = {k: v for k, v in CALIBRATION_GRID.items() if k != "prior_mu"}

    with pytest.raises(KeyError, match="prior_mu"):
        calibrate(rounds, grid)


@pytest.mark.parametrize("extra", ["max_var", "newcomer_drift_var_per_week"])
def test_calibrate_rejects_unknown_grid_keys(
    make_rounds: Callable[..., pd.DataFrame], extra: str
) -> None:
    # max_var is derived (= prior_var), and C7's optional newcomer drift is not implemented:
    # a grid naming either would otherwise be silently ignored.
    rounds = make_rounds([(ON, 1, 30), (ON, 2, 35)])

    with pytest.raises(ValueError, match=f"unknown keys: \\['{extra}'\\]"):
        calibrate(rounds, {**CALIBRATION_GRID, extra: (49,)})


def test_calibrate_grid_with_a_zero_variance_fails_at_params(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds([(ON, 1, 30), (ON, 2, 35)])

    with pytest.raises(ValueError, match=r"SkillParams\.obs_var must be > 0"):
        calibrate(rounds, {**CALIBRATION_GRID, "obs_var": (0, 12)})


def test_calibrate_scores_the_ninth_held_event(simulate_skill_rounds: Simulate) -> None:
    # Same seed: the first 8 events equal the tie test's; only event 9 is scored.
    rounds = simulate_skill_rounds(1, 10, 9, drift=0.15, obs_var=14.0, difficulty_var=4.0)[0]

    best = calibrate(rounds, IMPLAUSIBLE_FIRST_GRID)

    assert best.obs_var == 12.0  # the implausible first point is not chosen


def test_calibration_objective_is_the_explicit_mvn_after_burn_in(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    # 10 weekly events, 9 of them held (week 4 is not): only the last one is scored,
    # because the burn-in counts held events only. At the last event shooter 1 shoots
    # two rounds (same-shooter covariance) and shooter 4 is new (prior state).
    p = SkillParams(obs_var=12.0, drift_var_per_week=0.15, difficulty_var=4.0)
    weeks = [ON + timedelta(days=7 * w) for w in range(10)]
    specs: list[dict[str, object]] = []
    for w, day in enumerate(weeks[:-1]):
        if w == 4:
            specs.append({"event_date": day, "shooter_id": 3, "score": 20, "held": False})
            continue
        specs += [
            {"event_date": day, "shooter_id": 1, "score": 38 + w % 3},
            {"event_date": day, "shooter_id": 2, "score": 30 - 3 * (w % 2)},
            {"event_date": day, "shooter_id": 3, "score": 25 + w},
        ]
    last = weeks[-1]
    specs += [
        {"event_date": last, "shooter_id": 1, "score": 41},
        {"event_date": last, "shooter_id": 1, "score": 35},
        {"event_date": last, "shooter_id": 2, "score": 27},
        {"event_date": last, "shooter_id": 4, "score": 33},
    ]
    rounds = make_rounds(specs)

    # Pre-event state of the scored event from the public filter output (raw scale).
    result = run_skill_model(rounds, p)
    level = result.events.set_index("event_date").loc[last, "level"]
    scored = result.rounds.merge(rounds[["round_id", "event_date", "shooter_id", "score"]])
    scored = scored[scored["event_date"] == last]
    shooters = np.array(sorted(scored["shooter_id"].unique()))
    z = (scored["shooter_id"].to_numpy()[:, None] == shooters[None, :]).astype(float)
    var = scored.groupby("shooter_id")["var_before"].first().loc[shooters].to_numpy()
    n = len(scored)
    sigma = p.obs_var * np.eye(n) + z @ np.diag(var) @ z.T + p.difficulty_var * np.ones((n, n))
    mean = scored["mu_before"].to_numpy() - level
    explicit = multivariate_normal(mean, sigma).logpdf(scored["score"].to_numpy(dtype=float))

    # The objective is private: calibrate only returns its argmax.
    loglik, _, _ = _run(_prepare(rounds), p, None)
    burn_in_only, _, _ = _run(_prepare(rounds[rounds["event_date"] < last]), p, None)

    assert n == 4
    assert explicit < 0.0
    assert loglik == pytest.approx(explicit, rel=1e-12)
    assert burn_in_only == 0.0


def _state(
    *items: tuple[int, float, float, date],
) -> dict[int, tuple[float, float, date]]:
    return {sid: (mu, var, last) for sid, mu, var, last in items}


TINY = SkillParams(obs_var=1e-6, drift_var_per_week=0.0)


def test_predict_expected_and_sd_formula() -> None:
    p = SkillParams()
    state = _state(
        (1, 30.0, 1.0, ON - timedelta(days=70)),
        (3, 25.0, 40.0, ON - timedelta(days=700)),
    )

    out = predict(
        state,
        [1, 2, 3],
        ON,
        p,
        level=1.5,
        difficulty=2.0,
        difficulty_sd=3.0,
        n_sims=200,
    ).set_index("shooter_id")

    assert out.loc[1, "expected"] == pytest.approx(30.0 + 1.5 - 2.0)
    assert out.loc[1, "sd"] == pytest.approx(math.sqrt(1.0 + 0.3 * 10 + 14.0 + 9.0))
    assert out.loc[2, "expected"] == pytest.approx(30.0 + 1.5 - 2.0)  # unknown -> prior
    assert out.loc[2, "sd"] == pytest.approx(math.sqrt(49.0 + 14.0 + 9.0))
    # shooter 3's variance is capped at max_var (= prior_var 49)
    assert out.loc[3, "sd"] == pytest.approx(math.sqrt(49.0 + 14.0 + 9.0))
    assert out["attend_prob"].tolist() == [1.0, 1.0, 1.0]
    no_difficulty = predict(state, [1], ON, p, level=1.5, n_sims=10)
    assert no_difficulty["expected"].iloc[0] == pytest.approx(31.5)


@pytest.mark.parametrize(
    ("var", "days_after_on"),
    # Unclamped, -52 weeks of drift would shrink 16 to 0.4 and -100 weeks would turn 4
    # negative (sqrt -> NaN plus a RuntimeWarning).
    [(16.0, 364), (4.0, 700)],
)
def test_predict_last_date_after_on_adds_no_drift(var: float, days_after_on: int) -> None:
    p = SkillParams()
    state = _state((1, 30.0, var, ON + timedelta(days=days_after_on)), (2, 28.0, 9.0, ON))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = predict(state, [1, 2], ON, p, level=0.0, n_sims=200).set_index("shooter_id")

    assert out.loc[1, "sd"] == pytest.approx(math.sqrt(var + p.obs_var))  # var unchanged
    assert out[["expected", "sd", "p_win", "p_podium"]].notna().all().all()


def test_predict_ties_count_as_wins() -> None:
    state = _state((1, 35.0, 1e-6, ON), (2, 35.0, 1e-6, ON))
    out = predict(state, [1, 2], ON, TINY, level=0.0, n_sims=500)
    assert out["p_win"].tolist() == [1.0, 1.0]
    assert out["p_podium"].tolist() == [1.0, 1.0]


def test_predict_attendance_scales_field() -> None:
    state = _state((1, 30.0, 1e-6, ON), (2, 45.0, 1e-6, ON), (3, 44.0, 1e-6, ON))
    everyone = predict(state, [1, 2, 3], ON, TINY, level=0.0, n_sims=500)
    alone = predict(
        state,
        [1, 2, 3],
        ON,
        TINY,
        level=0.0,
        n_sims=500,
        attend_prob={1: 1.0, 2: 0.0, 3: 0.0},
    )

    assert everyone["p_win"].iloc[0] == 0.0
    assert alone["p_win"].iloc[0] == 1.0
    assert alone["attend_prob"].tolist() == [1.0, 0.0, 0.0]
    # shooter 2 never attends, so its conditional odds are undefined
    assert math.isnan(alone["p_win"].iloc[1])


def test_predict_podium_counts_strictly_better_shooters() -> None:
    state = _state(
        (1, 40.0, 1e-6, ON),
        (2, 35.0, 1e-6, ON),
        (3, 30.0, 1e-6, ON),
        (4, 25.0, 1e-6, ON),
    )
    out = predict(state, [1, 2, 3, 4], ON, TINY, level=0.0, n_sims=200)
    assert out["p_podium"].tolist() == [1.0, 1.0, 1.0, 0.0]
    assert out["p_win"].tolist() == [1.0, 0.0, 0.0, 0.0]


def test_predict_one_shared_day_effect_per_simulation() -> None:
    state = _state((1, 30.0, 1e-6, ON), (2, 31.0, 1e-6, ON))
    out = predict(state, [1, 2], ON, TINY, level=0.0, difficulty_sd=10.0, n_sims=4000)
    # A shared effect keeps the 1-point gap; shooter 1 only ties when both clip at 50.
    assert out["p_win"].iloc[1] == 1.0
    assert out["p_win"].iloc[0] < 0.1


def test_predict_integer_level_shift_leaves_odds_unchanged() -> None:
    state = _state((1, 30.0, 4.0, ON), (2, 28.0, 4.0, ON), (3, 26.0, 9.0, ON))
    base = predict(state, [1, 2, 3], ON, SkillParams(), level=0.0, n_sims=3000, seed=5)
    shifted = predict(state, [1, 2, 3], ON, SkillParams(), level=3.0, n_sims=3000, seed=5)
    assert shifted["p_win"].tolist() == base["p_win"].tolist()
    assert shifted["p_podium"].tolist() == base["p_podium"].tolist()
    assert (shifted["expected"] - base["expected"]).tolist() == [3.0, 3.0, 3.0]


def test_predict_is_seeded() -> None:
    state = _state((1, 30.0, 4.0, ON), (2, 29.0, 4.0, ON))
    a = predict(state, [1, 2], ON, SkillParams(), level=0.0, n_sims=2000, seed=1)
    b = predict(state, [1, 2], ON, SkillParams(), level=0.0, n_sims=2000, seed=1)
    c = predict(state, [1, 2], ON, SkillParams(), level=0.0, n_sims=2000, seed=2)
    pd.testing.assert_frame_equal(a, b)
    assert a["p_win"].tolist() != c["p_win"].tolist()


def test_predict_single_and_no_shooters() -> None:
    solo = predict(_state((1, 30.0, 4.0, ON)), [1], ON, SkillParams(), level=0.0, n_sims=100)
    assert solo["p_win"].tolist() == [1.0]
    empty = predict({}, [], ON, SkillParams(), level=0.0)
    assert empty.empty
    assert list(empty.columns) == [
        "shooter_id",
        "attend_prob",
        "expected",
        "sd",
        "p_win",
        "p_podium",
    ]


def test_predict_expected_matches_recent_scores(simulate_skill_rounds: Simulate) -> None:
    rounds = simulate_skill_rounds(102, 40, 100, drift=0.0, obs_var=14.0, difficulty_var=4.0)[0]
    result = run_skill_model(rounds)
    last = rounds["event_date"].max()
    recent = rounds[rounds["event_date"] > last - timedelta(days=7 * 20)]

    out = predict(
        result.final_state,
        sorted(rounds["shooter_id"].unique()),
        last + timedelta(days=7),
        SkillParams(),
        level=result.current_level,
    )

    assert abs(out["expected"].mean() - recent["score"].mean()) < 0.5
