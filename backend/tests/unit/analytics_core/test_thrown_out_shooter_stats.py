"""Profile stats, splits, odometer, PBs and Sunday notables with a thrown-out Sunday (T3b)."""

from collections.abc import Callable
from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import profile
from sunday_clays.api.routes.events import event_notables
from sunday_clays.api.routes.shooters import (
    SplitBy,
    SplitOut,
    odometer,
    personal_bests,
    shooter_stats,
    splits,
)

AS_OF = date(2026, 9, 27)
AUG30, SEP6, SEP13, SEP20 = (
    date(2026, 8, 30),
    date(2026, 9, 6),
    date(2026, 9, 13),
    date(2026, 9, 20),
)

MakeRounds = Callable[..., pd.DataFrame]


def _profile_rounds(make_rounds: MakeRounds) -> pd.DataFrame:
    return make_rounds(
        [
            {
                "event_date": AUG30,
                "shooter_id": 1,
                "score": 50,
                "stats_excluded": True,
                "is_best_round": True,
                "event_rank": 2.0,
                "percentile": 75.0,
            },
            {
                "event_date": SEP6,
                "shooter_id": 1,
                "score": 40,
                "is_best_round": True,
                "event_rank": 1.0,
                "percentile": 100.0,
                "adjusted": 5.0,
            },
            {
                "event_date": SEP13,
                "shooter_id": 1,
                "score": 50,
                "stats_excluded": True,
                "is_best_round": True,
                "event_rank": 1.0,
                "percentile": 100.0,
            },
            {
                "event_date": SEP20,
                "shooter_id": 1,
                "score": 30,
                "is_best_round": True,
                "event_rank": 3.0,
                "percentile": 50.0,
                "adjusted": -5.0,
            },
        ],
        stats_excluded=False,
    )


def test_shooter_stats_keep_official_counts_and_leave_scores_out(make_rounds: MakeRounds) -> None:
    s = shooter_stats(_profile_rounds(make_rounds))
    assert (s.n_rounds, s.n_events, s.n_excluded) == (4, 4, 2)
    assert (s.avg_score, s.median_score, s.best_score, s.avg_adjusted) == (35.0, 35.0, 40, 0.0)
    assert (s.wins, s.podiums, s.avg_percentile) == (2, 4, 81.25)


def test_splits_count_every_round_and_drop_a_key_with_none_in_the_average(
    make_rounds: MakeRounds,
) -> None:
    rounds = _profile_rounds(make_rounds)
    assert splits(rounds, SplitBy.YEAR) == [
        SplitOut(
            key="2026",
            n_rounds=4,
            n_events=4,
            n_excluded=2,
            avg=35.0,
            median=35.0,
            best=40,
            avg_adjusted=0.0,
        )
    ]
    assert splits(rounds, SplitBy.MONTH) == [
        SplitOut(
            key="2026-09",
            n_rounds=3,
            n_events=3,
            n_excluded=1,
            avg=35.0,
            median=35.0,
            best=40,
            avg_adjusted=0.0,
        )
    ]


def test_odometer_counts_clays_but_hit_rate_and_pbs_leave_thrown_out_sundays(
    make_rounds: MakeRounds,
) -> None:
    rounds = _profile_rounds(make_rounds)
    o = odometer(rounds, None, 0)
    assert (o.clays_thrown, o.clays_broken, o.rounds, o.hit_pct) == (200, 170, 4, 0.7)
    assert [(p.scope, p.key, p.score, p.event_date) for p in personal_bests(rounds)] == [
        ("overall", "all", 40, SEP6),
        ("year", "2026", 40, SEP6),
    ]
    assert personal_bests(rounds.loc[rounds["stats_excluded"]]) == []


def test_shooter_insights_keep_placings_and_leave_scores_out(make_rounds: MakeRounds) -> None:
    history = pd.DataFrame(columns=["shooter_id", "event_date", "mu", "var"])
    shooters = pd.DataFrame({"shooter_id": [1], "left_censored": [False]})
    ins = profile.shooter_insights(_profile_rounds(make_rounds), history, shooters, 1, AS_OF)
    assert (ins.n_rounds, ins.wins, ins.podiums, ins.avg_percentile) == (4, 2, 4, 81.25)
    assert (ins.floor, ins.ceiling, ins.recent_n) == (
        pytest.approx(31.0),
        pytest.approx(39.0),
        2,
    )


def test_learning_curve_k_counts_a_thrown_out_sunday_but_plots_no_value(
    make_rounds: MakeRounds,
) -> None:
    rounds = make_rounds(
        [
            {"event_date": SEP6, "shooter_id": 1, "score": 40, "adjusted": 2.0},
            {"event_date": SEP13, "shooter_id": 1, "score": 50, "stats_excluded": True},
            {"event_date": SEP20, "shooter_id": 1, "score": 44, "adjusted": 4.0},
        ],
        stats_excluded=False,
    )
    shooters = pd.DataFrame({"shooter_id": [1], "left_censored": [False]})
    curve = profile.learning_curve(rounds, shooters, 1)
    assert [(p.k, p.value) for p in curve] == [(1, 2.0), (3, 4.0)]


def test_residual_stats_and_rust_skip_thrown_out_rounds_but_not_the_attendance(
    make_rounds: MakeRounds,
) -> None:
    def day(w: int) -> date:
        return date(2026, 1, 4) + timedelta(weeks=w)

    five = [
        {"event_date": day(w), "shooter_id": 1, "score": 40, "residual": r}
        for w, r in zip(range(5), (0.0, 0.0, 0.0, 0.0, -6.0), strict=True)
    ]
    late = {
        "event_date": day(5),
        "shooter_id": 1,
        "score": 50,
        "residual": -10.0,
        "stats_excluded": True,
    }
    rounds = make_rounds([*five, late], stats_excluded=False)
    assert profile.bad_day_rate(rounds) == pytest.approx(0.2)
    assert profile.form(rounds) == (pytest.approx(-1.2), "steady")
    rust = make_rounds(
        [
            {"event_date": day(0), "shooter_id": 1, "score": 40, "residual": 2.0},
            {"event_date": day(5), "shooter_id": 1, "score": 40, "residual": -4.0},
            {
                "event_date": day(6),
                "shooter_id": 1,
                "score": 50,
                "residual": 10.0,
                "stats_excluded": True,
            },
            {"event_date": day(7), "shooter_id": 1, "score": 40, "residual": 0.0},
        ],
        stats_excluded=False,
    )
    assert profile.rust_effect(rust) == (pytest.approx(-5.0), 1)
    no_layoff = make_rounds(
        [
            {"event_date": day(0), "shooter_id": 2, "score": 40, "residual": 0.0},
            {"event_date": day(3), "shooter_id": 2, "score": 50, "stats_excluded": True},
            {"event_date": day(4), "shooter_id": 2, "score": 40, "residual": 3.0},
        ],
        stats_excluded=False,
    )
    # guard part: day 3 is attendance, so there is no 28-day gap
    assert profile.rust_effect(no_layoff) == (None, 0)


def test_pb_notables_skip_a_thrown_out_sunday_and_its_score(make_rounds: MakeRounds) -> None:
    days = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(7)]
    rounds = make_rounds(
        [
            {"event_date": d, "shooter_id": 1, "score": s, "stats_excluded": i == 5}
            for i, (d, s) in enumerate(zip(days, (40, 40, 40, 40, 40, 50, 45), strict=True))
        ],
        is_best_round=True,
    )
    shooters = pd.DataFrame(
        {
            "shooter_id": [1],
            "display_name": ["Hadley, Ike"],
            "first_event": [days[0]],
            "left_censored": [False],
        }
    )
    assert event_notables(rounds, shooters, days[5]) == []
    assert [(n.kind, n.detail) for n in event_notables(rounds, shooters, days[6])] == [
        ("pb", "New personal best 45 (was 40)")
    ]
