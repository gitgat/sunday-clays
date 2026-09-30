"""Plan 11 Task 2: pure weather-effects rules (no database)."""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics import frames
from sunday_clays.analytics.skill import SkillParams, run_skill_model
from sunday_clays.analytics.weather_effects import (
    COVARIATES,
    ZScale,
    band_summary,
    eb_shrink,
    fit_club_model,
    fit_shooter,
    shooter_sensitivity,
    turnout,
    weather_event_rows,
    with_bands,
    z_scales,
)

D0 = date(2024, 1, 7)


def _events(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Weather events with defaults for every column the pure functions read."""
    base: dict[str, object] = {
        "round_type": "sporting",
        "head_count": 20.0,
        "has_scores": True,
        "results_complete": True,
        "n": 20.0,
        "median": 35.0,
        "mean": 35.0,
        "top_score": 45.0,
        "difficulty": 0.0,
        "temp_f": 60.0,
        "apparent_f": 58.0,
        "precip_in": 0.0,
        "wind_mph": 5.0,
        "gust_mph": 8.0,
        "wind_dir_deg": 180.0,
        "cloud_pct": 50.0,
        "humidity_pct": 70.0,
        "pressure_hpa": 1015.0,
        "condition": "partly_cloudy",
    }
    records = []
    for i, row in enumerate(rows):
        records.append({"event_date": D0 + timedelta(days=7 * i), **base, **row})
    return with_bands(pd.DataFrame(records))


# --- club model -----------------------------------------------------------------------------


def test_fit_recovers_exact_linear_relation() -> None:
    temps = [40.0, 55.0, 62.0, 71.0, 48.0, 80.0, 66.0, 59.0]
    gusts = [5.0, 12.0, 22.0, 8.0, 30.0, 15.0, 3.0, 18.0]
    precs = [0.0, 0.1, 0.0, 0.3, 0.05, 0.0, 0.2, 0.0]
    clouds = [10.0, 90.0, 40.0, 75.0, 20.0, 0.0, 60.0, 35.0]
    rows = []
    for t, g, p, c, n in zip(
        temps, gusts, precs, clouds, [5, 30, 12, 8, 20, 25, 9, 14], strict=True
    ):
        y = 1.0 + 0.1 * t + 0.3 * g + 5.0 * p - 0.02 * c
        rows.append(
            {"temp_f": t, "gust_mph": g, "precip_in": p, "cloud_pct": c, "n": n, "difficulty": y}
        )
    model = fit_club_model(_events(rows))
    assert model is not None
    assert model.covariates == COVARIATES
    assert model.coef == pytest.approx((1.0, 0.1, 0.3, 5.0, -0.02), abs=1e-9)
    assert model.sigma2 == pytest.approx(0.0, abs=1e-12)
    assert model.n_events == 8
    assert model.means == pytest.approx((60.125, 14.125, 0.08125, 41.25))


def test_intercept_only_fit_is_weighted_mean() -> None:
    # Weights 1, 1, 2 (mean 4/3) -> normalised 0.75, 0.75, 1.5.
    # Weighted mean = (1 + 2 + 8) / 4 = 2.75; residuals -1.75, -0.75, 1.25;
    # sigma2 = (0.75*3.0625 + 0.75*0.5625 + 1.5*1.5625) / (3 - 1) = 5.0625 / 2 = 2.53125;
    # se = sqrt(2.53125 / 3) = sqrt(0.84375).
    events = _events(
        [
            {"difficulty": 1.0, "n": 1.0},
            {"difficulty": 2.0, "n": 1.0},
            {"difficulty": 4.0, "n": 2.0},
        ]
    )
    model = fit_club_model(events, ())
    assert model is not None
    assert model.coef == pytest.approx((2.75,))
    assert model.sigma2 == pytest.approx(2.53125)
    assert model.se == pytest.approx((math.sqrt(0.84375),))
    assert model.predict({}) == pytest.approx(2.75)


def test_fit_returns_none_when_covariate_constant() -> None:
    rows = [
        {
            "temp_f": 40.0 + 5 * i,
            "gust_mph": float(i),
            "cloud_pct": 10.0 * i,
            "difficulty": float(i % 3),
        }
        for i in range(10)
    ]
    assert fit_club_model(_events(rows)) is None  # precip_in is 0.0 everywhere


def test_fit_returns_none_with_too_few_events() -> None:
    rows = [
        {
            "temp_f": 40.0 + 7 * i,
            "gust_mph": float(3 * i % 11),
            "precip_in": 0.1 * (i % 2),
            "cloud_pct": 13.0 * i,
            "difficulty": float(i),
        }
        for i in range(5)
    ]
    assert fit_club_model(_events(rows)) is None  # 5 events, 5 parameters


def test_fit_ignores_events_without_difficulty() -> None:
    events = _events(
        [
            {"difficulty": 1.0},
            {"difficulty": 3.0},
            {"difficulty": float("nan")},
            {"difficulty": 2.0, "n": 0.0},
        ]
    )
    model = fit_club_model(events, ())
    assert model is not None
    assert model.n_events == 2
    assert model.coef == pytest.approx((2.0,))


def test_model_predict_uses_named_covariates() -> None:
    rows = []
    for i in range(12):
        t, g, p, c = 40.0 + 3 * i, float((5 * i) % 17), 0.05 * (i % 3), float((11 * i) % 90)
        rows.append(
            {
                "temp_f": t,
                "gust_mph": g,
                "precip_in": p,
                "cloud_pct": c,
                "difficulty": 2.0 - 0.05 * t + 0.2 * g,
            }
        )
    model = fit_club_model(_events(rows))
    assert model is not None
    x = {"temp_f": 50.0, "gust_mph": 20.0, "precip_in": 0.0, "cloud_pct": 80.0}
    assert model.predict(x) == pytest.approx(2.0 - 2.5 + 4.0)


def test_club_weather_model_recovers_event_effect() -> None:
    """True day effect on scores = -0.3 * gust; the published difficulty slope should be ~ +0.3."""
    rng = np.random.default_rng(7)
    n_shooters, n_events = 80, 104
    skills = rng.normal(32.0, 5.0, n_shooters)
    rows: list[dict[str, object]] = []
    weather: list[dict[str, object]] = []
    for t in range(n_events):
        day = D0 + timedelta(days=7 * t)
        gust = float(rng.uniform(0.0, 30.0))
        weather.append(
            {
                "event_date": day,
                "temp_f": float(rng.uniform(35.0, 90.0)),
                "gust_mph": gust,
                "precip_in": float(rng.choice([0.0, 0.0, 0.0, 0.05, 0.2])),
                "cloud_pct": float(rng.uniform(0.0, 100.0)),
            }
        )
        for s in np.flatnonzero(rng.random(n_shooters) < 0.75):
            score = int(np.clip(np.rint(skills[s] - 0.3 * gust + rng.normal(0.0, 3.0)), 0, 50))
            rows.append({"event_date": day, "shooter_id": int(s) + 1, "score": score})
    rounds = pd.DataFrame(rows)
    rounds["round_id"] = np.arange(1, len(rounds) + 1)
    rounds["name_key"] = [f"shooter {s}" for s in rounds["shooter_id"]]
    rounds["ordinal"] = 1
    rounds["held"] = True
    result = run_skill_model(rounds, SkillParams())
    n = rounds.groupby("event_date").size().rename("n").reset_index()
    events = (
        result.events[["event_date", "difficulty"]]
        .merge(n, on="event_date")
        .merge(pd.DataFrame(weather), on="event_date")
    )
    model = fit_club_model(events)
    assert model is not None
    gust_slope = model.coef[1 + COVARIATES.index("gust_mph")]
    assert gust_slope == pytest.approx(0.3, abs=0.1)


# --- bands and turnout ----------------------------------------------------------------------


def test_with_bands_rounds_float32_precipitation() -> None:
    events = _events([{"precip_in": 0.019999999552965164}, {"precip_in": 0.0}])
    assert events["precip_in"].tolist() == [0.02, 0.0]
    assert events["precip_band"].tolist() == [frames.precip_band(0.02), frames.precip_band(0.0)]


def test_band_summary_orders_bands_and_counts_rounds() -> None:
    events = _events(
        [
            {"temp_f": 80.0, "difficulty": 1.0},
            {"temp_f": 35.0, "difficulty": -2.0},
            {"temp_f": 60.0, "difficulty": float("nan")},
            {"temp_f": 65.0, "has_scores": False},
        ]
    )
    days = events["event_date"].tolist()
    rounds = pd.DataFrame(
        {
            "event_date": [days[0], days[0], days[1], days[2], days[2], days[2]],
            "score": [40, 44, 30, 35, 36, 37],
        }
    )
    temp = [s for s in band_summary(events, rounds) if s.dimension == "temp_band"]
    assert [s.band for s in temp] == [
        frames.temp_band(35.0),
        frames.temp_band(60.0),
        frames.temp_band(80.0),
    ]
    assert [(s.n_events, s.n_rounds, s.mean_score, s.mean_difficulty) for s in temp] == [
        (1, 1, 30.0, -2.0),
        (1, 3, 36.0, None),
        (1, 2, 42.0, 1.0),
    ]


def test_band_summary_orders_conditions_by_rule_then_unknown() -> None:
    events = _events([{"condition": c} for c in ["clear", "fog", "rain", "overcast"]])
    rounds = pd.DataFrame({"event_date": events["event_date"], "score": [30, 31, 32, 33]})
    conditions = [s.band for s in band_summary(events, rounds) if s.dimension == "condition"]
    assert conditions == ["rain", "overcast", "clear", "fog"]


def test_with_bands_adds_time_of_year_from_season_label() -> None:
    events = _events([{}, {}])
    events["event_date"] = [date(2024, 12, 1), date(2025, 3, 2)]
    assert with_bands(events)["time_of_year"].tolist() == ["winter", "spring"]


def test_band_summary_orders_time_of_year_winter_to_fall() -> None:
    days = [date(2024, 10, 6), date(2024, 7, 7), date(2024, 12, 1), date(2025, 4, 6)]
    events = _events([{} for _ in days])
    events["event_date"] = days
    events = with_bands(events)
    rounds = pd.DataFrame({"event_date": days, "score": [30, 31, 32, 33]})
    seasons = [s for s in band_summary(events, rounds) if s.dimension == "time_of_year"]
    assert [(s.band, s.n_events, s.mean_score) for s in seasons] == [
        ("winter", 1, 32.0),
        ("spring", 1, 33.0),
        ("summer", 1, 31.0),
        ("fall", 1, 30.0),
    ]


def test_turnout_by_time_of_year() -> None:
    days = [date(2024, 12, 1), date(2025, 1, 5), date(2024, 6, 2)]
    events = _events([{"head_count": 10.0}, {"head_count": 20.0}, {"head_count": 30.0}])
    events["event_date"] = days
    stats = [s for s in turnout(with_bands(events)) if s.dimension == "time_of_year"]
    assert [(s.band, s.n_events, s.mean_head_count) for s in stats] == [
        ("winter", 2, 15.0),
        ("summer", 1, 30.0),
    ]


def test_turnout_uses_head_counts_per_band() -> None:
    events = _events(
        [
            {"gust_mph": 5.0, "head_count": 10.0, "has_scores": False},
            {"gust_mph": 25.0, "head_count": 20.0},
            {"gust_mph": 6.0, "head_count": 31.0},
            {"gust_mph": 7.0, "head_count": float("nan")},
        ]
    )
    wind = [s for s in turnout(events) if s.dimension == "wind_band"]
    assert [(s.band, s.n_events, s.mean_head_count, s.median_head_count) for s in wind] == [
        (frames.wind_band(5.0), 2, 20.5, 20.5),
        (frames.wind_band(25.0), 1, 20.0, 20.0),
    ]


# --- sensitivity ----------------------------------------------------------------------------


def test_z_scales_use_sample_sd_and_zero_without_spread() -> None:
    scales = {s.covariate: s for s in z_scales(_events([{"temp_f": 40.0}, {"temp_f": 60.0}]))}
    assert (scales["temp_f"].mean, scales["temp_f"].sd) == pytest.approx((50.0, math.sqrt(200.0)))
    assert scales["precip_in"].sd == 0.0
    single = {s.covariate: s for s in z_scales(_events([{"temp_f": 40.0}]))}
    assert (single["temp_f"].mean, single["temp_f"].sd) == (40.0, 0.0)


def test_eb_shrink_matches_hand_computed_values() -> None:
    # var([1, 1, -1, 3], ddof=1) = 8/3; mean(se^2) = (0.04 + 1 + 0.04 + 0.04) / 4 = 0.28
    # tau2 = 8/3 - 0.28 = 2.386667; factor = tau2 / (tau2 + se^2)
    tau2, shrunk = eb_shrink([1.0, 1.0, -1.0, 3.0], [0.2, 1.0, 0.2, 0.2])
    assert tau2 == pytest.approx(2.3866667, rel=1e-6)
    assert shrunk == pytest.approx([0.9835165, 0.7047244, -0.9835165, 2.9505495], rel=1e-6)


def test_eb_shrink_single_shooter_shrinks_to_zero() -> None:
    assert eb_shrink([2.5], [0.1]) == (0.0, [0.0])


def test_eb_shrink_without_between_shooter_signal_is_zero() -> None:
    # var([1.0, 1.2], ddof=1) = 0.02 < mean(se^2) = 1.0 -> tau2 = 0 -> everything shrinks to 0
    assert eb_shrink([1.0, 1.2], [1.0, 1.0]) == (0.0, [0.0, 0.0])


def _sensitivity_rounds(spec: dict[int, tuple[int, float]], seed: int = 3) -> pd.DataFrame:
    """spec: shooter_id -> (n_rounds, true residual change per mph of gust)."""
    rng = np.random.default_rng(seed)
    rows = []
    for shooter_id, (n_rounds, slope) in spec.items():
        for i in range(n_rounds):
            gust = float(rng.uniform(0.0, 30.0))
            rows.append(
                {
                    "shooter_id": shooter_id,
                    "display_name": f"Shooter {shooter_id:02d}",
                    "event_date": D0 + timedelta(days=7 * i),
                    "residual": slope * (gust - 15.0) + float(rng.normal(0.0, 2.0)),
                    "temp_f": float(rng.uniform(35.0, 90.0)),
                    "gust_mph": gust,
                    "precip_in": float(rng.choice([0.0, 0.0, 0.1])),
                }
            )
    return pd.DataFrame(rows)


SCALES = (
    ZScale("temp_f", 60.0, 15.0),
    ZScale("gust_mph", 15.0, 8.0),
    ZScale("precip_in", 0.03, 0.05),
)


def test_sensitivity_shrinks_small_samples() -> None:
    spec = {1: (200, -0.2), 2: (12, -0.2), 3: (60, 0.1), 4: (60, -0.05), 5: (60, 0.2), 6: (60, 0.0)}
    result = shooter_sensitivity(_sensitivity_rounds(spec), SCALES)
    gust = {
        s.shooter_id: next(t for t in s.terms if t.covariate == "gust_mph") for s in result.shooters
    }
    assert gust[1].beta is not None
    assert gust[2].beta is not None
    assert gust[1].se is not None
    assert gust[2].se is not None
    assert gust[2].se > gust[1].se
    factor_many = gust[1].shrunk / gust[1].beta
    factor_few = gust[2].shrunk / gust[2].beta
    assert 0.0 < factor_few < factor_many <= 1.0
    tau2 = dict(result.tau2)
    assert tau2["gust_mph"] > 0.0


def test_sensitivity_requires_ten_rounds() -> None:
    rounds = _sensitivity_rounds({1: (10, 0.1), 2: (9, 0.1)})
    rounds.loc[len(rounds)] = {
        **rounds.iloc[0].to_dict(),
        "shooter_id": 2,
        "residual": float("nan"),
    }
    assert [s.shooter_id for s in shooter_sensitivity(rounds, SCALES).shooters] == [1]


def test_sensitivity_drops_constant_covariate() -> None:
    rounds = _sensitivity_rounds({1: (20, 0.1), 2: (20, -0.1)})
    rounds.loc[rounds["shooter_id"] == 1, "precip_in"] = 0.0
    result = shooter_sensitivity(rounds, SCALES)
    one = {t.covariate: t for t in result.shooters[0].terms}
    assert one["precip_in"].beta is None
    assert one["precip_in"].se is None
    assert one["precip_in"].shrunk == 0.0
    assert one["gust_mph"].beta is not None


def test_sensitivity_zero_club_sd_leaves_covariate_out() -> None:
    scales = (
        ZScale("temp_f", 60.0, 15.0),
        ZScale("gust_mph", 15.0, 8.0),
        ZScale("precip_in", 0.0, 0.0),
    )
    result = shooter_sensitivity(_sensitivity_rounds({1: (20, 0.1), 2: (20, 0.3)}), scales)
    for shooter in result.shooters:
        precip = next(t for t in shooter.terms if t.covariate == "precip_in")
        assert (precip.beta, precip.shrunk, precip.per_unit) == (None, 0.0, 0.0)


def test_sensitivity_rank_deficient_fit_has_no_betas() -> None:
    rounds = _sensitivity_rounds({1: (15, 0.1)})
    rounds["temp_f"] = 15.0 + 2.0 * rounds["gust_mph"]  # temp is a linear function of gust
    assert fit_shooter(rounds, SCALES) == {}
    terms = shooter_sensitivity(rounds, SCALES).shooters[0].terms
    assert all(t.beta is None and t.shrunk == 0.0 for t in terms)


def test_sensitivity_per_unit_effect_scales_by_club_sd() -> None:
    spec = {1: (40, -0.2), 2: (40, 0.2), 3: (40, 0.0)}
    result = shooter_sensitivity(_sensitivity_rounds(spec), SCALES)
    for shooter in result.shooters:
        gust = next(t for t in shooter.terms if t.covariate == "gust_mph")
        assert gust.per_unit == pytest.approx(gust.shrunk * 10.0 / 8.0)
    assert [s.display_name for s in result.shooters] == ["Shooter 01", "Shooter 02", "Shooter 03"]


def test_weather_event_rows_convert_missing_values_to_none() -> None:
    events = _events(
        [
            {
                "head_count": float("nan"),
                "median": float("nan"),
                "difficulty": float("nan"),
                "wind_dir_deg": float("nan"),
            },
            {"head_count": 23.0, "top_score": 49.0},
        ]
    )
    days = events["event_date"].tolist()
    rounds = pd.DataFrame({"event_date": [days[1]] * 3, "score": [40, 41, 49]})
    first, second = weather_event_rows(events, rounds)
    assert (
        first.head_count,
        first.median,
        first.difficulty,
        first.wind_dir_deg,
        first.n_rounds,
    ) == (
        None,
        None,
        None,
        None,
        0,
    )
    assert (second.head_count, second.top_score, second.n_rounds) == (23, 49, 3)
    assert second.temp_band == frames.temp_band(60.0)
