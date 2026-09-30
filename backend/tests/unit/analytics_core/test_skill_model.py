import math
from collections.abc import Callable
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics.skill import SkillParams, run_skill_model

D = date(2026, 1, 4)
Simulate = Callable[..., tuple[pd.DataFrame, np.ndarray]]


def test_update_equals_closed_form_loo(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    # One held event, three new shooters; shooter 1 shot two rounds.
    rounds = make_rounds(
        [
            {"event_date": D, "shooter_id": 1, "score": 40, "round_id": 1},
            {"event_date": D, "shooter_id": 1, "score": 34, "round_id": 2},
            {"event_date": D, "shooter_id": 2, "score": 28, "round_id": 3},
            {"event_date": D, "shooter_id": 3, "score": 33, "round_id": 4},
        ]
    )
    p = SkillParams()
    result = run_skill_model(rounds, p)

    # Independent joint-Gaussian posterior over theta = (mu1, mu2, mu3, d);
    # one design row per round.
    design = np.array([[1, 0, 0, 1], [1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1]], dtype=float)
    y = np.array([40.0, 34.0, 28.0, 33.0])
    prior_mean = np.array([30.0, 30.0, 30.0, 0.0])
    prior_prec = np.diag([1 / 49, 1 / 49, 1 / 49, 1 / 4])

    def posterior(rows: list[int]) -> tuple[np.ndarray, np.ndarray]:
        h = design[rows]
        cov = np.linalg.inv(prior_prec + h.T @ h / p.obs_var)
        return cov @ (prior_prec @ prior_mean + h.T @ y[rows] / p.obs_var), cov

    mean, cov = posterior([0, 1, 2, 3])
    level = result.events["level"].iloc[0]
    by_round = result.rounds.set_index("round_id")
    assert result.events["d_raw"].iloc[0] == pytest.approx(mean[3])
    for rid, j in ((1, 0), (3, 1), (4, 2)):
        assert by_round.loc[rid, "mu_after"] - level == pytest.approx(mean[j])
        assert by_round.loc[rid, "var_after"] == pytest.approx(cov[j, j])
    # expected = mu_i + E[d | everyone else's rounds]
    d_without = {
        1: posterior([2, 3])[0][3],
        3: posterior([0, 1, 3])[0][3],
        4: posterior([0, 1, 2])[0][3],
    }
    for rid, d_loo in d_without.items():
        assert by_round.loc[rid, "expected"] == pytest.approx(30.0 + d_loo)
    assert by_round.loc[2, "expected"] == pytest.approx(30.0 + d_without[1])


def test_same_day_rounds_share_pre_event_state(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            (D, 1, 35),
            (D, 2, 30),
            (D + timedelta(days=7), 1, 44),
            (D + timedelta(days=7), 1, 38),
            (D + timedelta(days=7), 2, 31),
        ]
    )
    out = run_skill_model(rounds).rounds.merge(rounds[["round_id", "event_date", "shooter_id"]])
    pair = out[(out["shooter_id"] == 1) & (out["event_date"] == D + timedelta(days=7))]

    assert len(pair) == 2
    for column in ("mu_before", "var_before", "mu_after", "var_after", "expected"):
        assert pair[column].nunique() == 1
    assert pair["residual"].max() - pair["residual"].min() == pytest.approx(6.0)


def test_published_difficulty_sign_and_centering(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rng = np.random.default_rng(7)
    specs = []
    for week in range(60):
        bump = 8 if week == 59 else 0
        for shooter in range(1, 11):
            specs.append(
                (
                    D + timedelta(days=7 * week),
                    shooter,
                    25 + shooter + bump + int(rng.integers(-2, 3)),
                )
            )
    events = run_skill_model(make_rounds(specs)).events

    assert events["difficulty"].iloc[-1] < -3  # everyone shot 8 higher: an easy day
    for i, row in events.iterrows():
        window = events[
            (events["event_date"] > row["event_date"] - timedelta(days=364)) & (events.index <= i)
        ]
        assert row["level"] == pytest.approx(window["d_raw"].mean())
        assert row["difficulty"] == pytest.approx(-(row["d_raw"] - row["level"]))
    assert len(window) == 52  # the window really drops events older than 364 days


def test_non_held_event_carries_state_forward(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d2, d3 = D + timedelta(days=14), D + timedelta(days=28)
    rounds = make_rounds(
        [
            (D, 1, 35),
            (D, 2, 30),
            {"event_date": d2, "shooter_id": 1, "score": 20, "held": False},
            (d3, 1, 36),
            (d3, 2, 29),
        ]
    )
    p = SkillParams()
    result = run_skill_model(rounds, p)
    out = result.rounds.merge(rounds[["round_id", "event_date", "shooter_id"]])
    first = out[(out["shooter_id"] == 1) & (out["event_date"] == D)].iloc[0]
    carried = out[out["event_date"] == d2].iloc[0]
    third = out[(out["shooter_id"] == 1) & (out["event_date"] == d3)].iloc[0]
    events = result.events.set_index("event_date")

    assert math.isnan(carried["expected"])
    assert math.isnan(carried["residual"])
    assert carried["mu_before"] == carried["mu_after"] == pytest.approx(first["mu_after"])
    assert carried["var_before"] == pytest.approx(first["var_after"] + 2 * p.drift_var_per_week)
    assert carried["var_after"] == carried["var_before"]
    assert math.isnan(events.loc[d2, "difficulty"])
    assert events.loc[d2, "level"] == events.loc[D, "level"]
    assert third["var_before"] == pytest.approx(carried["var_after"] + 2 * p.drift_var_per_week)
    history = result.history[result.history["shooter_id"] == 1]
    assert history["event_date"].tolist() == [D, d2, d3]


def test_level_is_zero_until_the_first_held_event(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds([{"event_date": D, "shooter_id": 1, "score": 30, "held": False}])
    result = run_skill_model(rounds)
    assert result.events["level"].tolist() == [0.0]
    assert result.current_level == 0.0
    assert result.history["mu"].tolist() == [30.0]  # prior_mu + level 0


def test_variance_is_capped_at_max_var(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    later = D + timedelta(days=7 * 520)
    rounds = make_rounds([(D, 1, 35), (D, 2, 30), (later, 1, 36), (later, 2, 31)])
    out = run_skill_model(rounds).rounds.merge(rounds[["round_id", "event_date"]])
    assert (out[out["event_date"] == later]["var_before"] == 49.0).all()


def test_history_and_final_state(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds([(D, 1, 35), (D, 2, 30), (D + timedelta(days=7), 1, 40)])
    result = run_skill_model(rounds)
    merged = result.rounds.merge(rounds[["round_id", "event_date", "shooter_id"]])
    last = merged.iloc[-1]
    level = result.current_level

    mu, var, last_date = result.final_state[1]
    assert last_date == D + timedelta(days=7)
    assert mu + level == pytest.approx(last["mu_after"])
    assert var == pytest.approx(last["var_after"])
    assert result.final_state[2][2] == D
    assert level == result.events["level"].iloc[-1]
    assert len(result.history) == 3


def test_empty_rounds_give_empty_result(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    result = run_skill_model(make_rounds([(D, 1, 30)]).iloc[0:0])
    assert result.rounds.empty
    assert result.events.empty
    assert result.history.empty
    assert result.final_state == {}
    assert result.current_level == 0.0


def test_no_leak_fixed_params(simulate_skill_rounds: Simulate) -> None:
    past, _ = simulate_skill_rounds(3, 12, 30)
    future, _ = simulate_skill_rounds(4, 12, 10)
    cutoff = past["event_date"].max()
    future = future.assign(
        round_id=future["round_id"] + 10_000,
        event_date=[d + timedelta(days=7 * 40) for d in future["event_date"]],
    )
    alone = run_skill_model(past)
    extended = run_skill_model(pd.concat([past, future], ignore_index=True))

    def upto(result_frame: pd.DataFrame, key: str) -> pd.DataFrame:
        return result_frame.sort_values(key).reset_index(drop=True)

    pd.testing.assert_frame_equal(
        upto(alone.rounds, "round_id"),
        upto(extended.rounds[extended.rounds["round_id"] < 10_000], "round_id"),
    )
    pd.testing.assert_frame_equal(
        alone.events, extended.events[extended.events["event_date"] <= cutoff]
    )
    pd.testing.assert_frame_equal(
        alone.history,
        extended.history[extended.history["event_date"] <= cutoff].reset_index(drop=True),
    )


def test_synthetic_skills_recovered(simulate_skill_rounds: Simulate) -> None:
    rounds, skills = simulate_skill_rounds(0, 30, 120)
    result = run_skill_model(rounds)
    published = np.array(
        [result.final_state[s + 1][0] + result.current_level for s in range(len(skills))]
    )
    assert np.abs(published - skills).mean() < 1.6
    assert np.corrcoef(published, skills)[0, 1] > 0.95


@pytest.mark.parametrize("field", ["prior_var", "obs_var", "difficulty_var", "max_var"])
@pytest.mark.parametrize("value", [0.0, -1.0, math.nan])
def test_skill_params_rejects_non_positive_variances(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=rf"SkillParams\.{field} must be > 0"):
        SkillParams(**{field: value})


@pytest.mark.parametrize("value", [-0.1, math.nan])
def test_skill_params_rejects_negative_drift(value: float) -> None:
    with pytest.raises(ValueError, match=r"SkillParams\.drift_var_per_week must be >= 0"):
        SkillParams(drift_var_per_week=value)


def test_skill_params_accepts_zero_drift_and_tiny_variances() -> None:
    tiny = SkillParams(
        prior_mu=-5.0,
        prior_var=1e-9,
        obs_var=1e-9,
        drift_var_per_week=0.0,
        difficulty_var=1e-9,
        max_var=1e-9,
    )
    assert tiny.drift_var_per_week == 0.0
    assert tiny.prior_mu == -5.0  # prior_mu is a location, not validated
