"""Plan 11 Task 1: pure next-Sunday prediction rules (no database). Expected score only."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics.predictions import (
    DifficultyChoice,
    PredictionRow,
    attendance_probs,
    choose_difficulty,
    forecast_covariates,
    parse_skill_params,
    prediction_rows,
    weighted_median,
)
from sunday_clays.analytics.skill import SkillParams
from sunday_clays.analytics.weather_effects import COVARIATES, ClubModel
from sunday_clays.weather.aggregate import WindowWeather

ON = date(2026, 10, 4)
SUNDAYS = [
    ON - timedelta(days=7 * k) for k in range(16, 0, -1)
]  # 16 Sundays before ON, oldest first


def _events(scored: list[date], attendance_only: tuple[date, ...] = ()) -> pd.DataFrame:
    rows = [(d, True) for d in scored] + [(d, False) for d in attendance_only]
    return pd.DataFrame(rows, columns=["event_date", "has_scores"])


def _rounds(rows: list[tuple[int, date]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["shooter_id", "event_date"])


def test_attendance_probs_counts_last_13_scored_events() -> None:
    # 16 scored Sundays; the window is the newest 13 (SUNDAYS[3:]); SUNDAYS[10] is attendance-only.
    scored = [d for i, d in enumerate(SUNDAYS) if i != 10]
    events = _events(scored, (SUNDAYS[10],))
    window = scored[-13:]  # SUNDAYS[2], SUNDAYS[3..9], SUNDAYS[11..15]
    rounds = _rounds(
        [(1, d) for d in scored]  # every scored event
        + [(2, SUNDAYS[0]), (2, SUNDAYS[1])]  # only before the window
        + [(3, window[0]), (3, window[-1]), (3, window[-1])]  # 2 dates, 3 rounds
        + [(4, ON)]  # the target day itself does not count
    )
    assert attendance_probs(rounds, events, ON) == {1: 1.0, 3: 2 / 13}


def test_attendance_probs_divides_by_13_even_with_fewer_events() -> None:
    events = _events(SUNDAYS[-3:])
    rounds = _rounds([(7, d) for d in SUNDAYS[-3:]])
    assert attendance_probs(rounds, events, ON) == {7: 3 / 13}


def test_attendance_probs_empty_without_scored_events() -> None:
    assert attendance_probs(_rounds([]), _events([], (SUNDAYS[0],)), ON) == {}


def test_attendance_probs_no_leak() -> None:
    events = _events(SUNDAYS)
    rounds = _rounds([(1, d) for d in SUNDAYS[::2]] + [(2, d) for d in SUNDAYS[-5:]])
    before = attendance_probs(rounds, events, ON)
    later = [ON + timedelta(days=7 * k) for k in range(0, 4)]
    grown_events = pd.concat([events, _events(later)], ignore_index=True)
    grown_rounds = pd.concat([rounds, _rounds([(1, d) for d in later] + [(9, d) for d in later])])
    assert attendance_probs(grown_rounds, grown_events, ON) == before


@pytest.mark.parametrize(
    ("values", "weights", "expected"),
    [
        pytest.param([30.0, 40.0, 35.0], [1.0, 1.0, 1.0], 35.0, id="odd-equal"),
        pytest.param([30.0, 40.0], [1.0, 1.0], 30.0, id="even-takes-lower"),
        pytest.param([30.0, 40.0], [0.2, 0.9], 40.0, id="weight-moves-median"),
        pytest.param([10.0, 30.0, 40.0], [0.0, 1.0, 1.0], 30.0, id="zero-weight-ignored"),
    ],
)
def test_weighted_median(values: list[float], weights: list[float], expected: float) -> None:
    assert weighted_median(values, weights) == expected


def test_weighted_median_without_weight_is_none() -> None:
    assert weighted_median([], []) is None
    assert weighted_median([31.0], [0.0]) is None


FULL = ClubModel(
    COVARIATES, (1.0, 0.02, 0.1, 3.0, 0.01), (0.1,) * 5, 4.0, 50, (55.0, 12.0, 0.05, 50.0)
)
INTERCEPT = ClubModel((), (0.4,), (0.2,), 2.25, 50, ())
FORECAST = {"temp_f": 50.0, "gust_mph": 20.0, "precip_in": 0.1, "cloud_pct": 80.0}


def test_choose_difficulty_uses_forecast_with_full_model() -> None:
    # 1 + 0.02*50 + 0.1*20 + 3*0.1 + 0.01*80 = 5.1; sd = sqrt(4)
    assert choose_difficulty(FORECAST, FULL, INTERCEPT, SkillParams()) == DifficultyChoice(
        "weather", pytest.approx(5.1), 2.0
    )


@pytest.mark.parametrize(
    ("forecast", "full"),
    [pytest.param(None, FULL, id="no-forecast"), pytest.param(FORECAST, None, id="no-full-model")],
)
def test_choose_difficulty_falls_back_to_intercept(
    forecast: dict[str, float] | None, full: ClubModel | None
) -> None:
    assert choose_difficulty(forecast, full, INTERCEPT, SkillParams()) == DifficultyChoice(
        "intercept", 0.4, 1.5
    )


def test_forecast_difficulty_falls_back_to_prior() -> None:
    params = SkillParams(difficulty_var=9.0)
    assert choose_difficulty(FORECAST, None, None, params) == DifficultyChoice("prior", None, 3.0)
    assert choose_difficulty(None, None, None, None) == DifficultyChoice("none", None, None)


def test_parse_skill_params_round_trips_stored_dict() -> None:
    stored = {
        "prior_mu": 30,
        "prior_var": 49.0,
        "obs_var": 12.0,
        "drift_var_per_week": 0.15,
        "difficulty_var": 2.0,
        "max_var": 49.0,
    }
    assert parse_skill_params(stored) == SkillParams(
        obs_var=12.0, drift_var_per_week=0.15, difficulty_var=2.0
    )


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param(None, id="absent"),
        pytest.param([30.0], id="not-a-dict"),
        pytest.param({"prior_mu": 30.0}, id="missing-fields"),
        pytest.param(
            {
                **dict.fromkeys(
                    (
                        "prior_mu",
                        "prior_var",
                        "obs_var",
                        "drift_var_per_week",
                        "difficulty_var",
                        "max_var",
                    ),
                    1.0,
                ),
                "obs_var": "x",
            },
            id="not-numeric",
        ),
    ],
)
def test_parse_skill_params_rejects_anything_else(stored: object) -> None:
    assert parse_skill_params(stored) is None


def test_forecast_covariates_reads_the_model_inputs() -> None:
    window = WindowWeather(61.0, 60.0, 0.04, 7.0, 18.0, 200.0, 85.0, 70.0, 1012.0, "rain")
    assert forecast_covariates(window) == {
        "temp_f": 61.0,
        "gust_mph": 18.0,
        "precip_in": 0.04,
        "cloud_pct": 85.0,
    }


def test_prediction_rows_are_alphabetical_and_carry_no_odds() -> None:
    pred = pd.DataFrame(
        {
            "shooter_id": [1, 2, 3],
            "attend_prob": [1.0, 0.5, 1 / 13],
            "expected": [38.0, 44.0, 30.0],
            "sd": [4.0, 4.1, 5.0],
            "p_win": [0.2, 0.4, math.nan],
            "p_podium": [0.5, 0.7, math.nan],
        }
    )
    names = {1: "Baker, Al", 2: "Able, Cy", 3: "Able, Bo"}
    rows = prediction_rows(pred, names)
    # Never ordered by predicted score: name, then id.
    assert [r.shooter_id for r in rows] == [3, 2, 1]
    assert (rows[1].attend_prob, rows[1].expected, rows[1].sd) == (0.5, 44.0, 4.1)
    assert not {"p_win", "p_podium", "win_chance"} & set(PredictionRow.__dataclass_fields__)


def test_prediction_rows_clip_expected_to_the_target_range() -> None:
    pred = pd.DataFrame(
        {
            "shooter_id": [1, 2],
            "attend_prob": [1.0, 1.0],
            "expected": [53.2, -1.5],
            "sd": [4.0, 4.0],
        }
    )
    rows = prediction_rows(pred, {1: "A", 2: "B"})
    assert [r.expected for r in rows] == [50.0, 0.0]
