import math
from collections.abc import Callable
from dataclasses import fields
from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import profile

AS_OF = date(2026, 9, 27)


def _weeks_back(n: int) -> list[date]:
    return [AS_OF - timedelta(days=7 * k) for k in reversed(range(n))]


def _history(rows: list[tuple[int, date, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["shooter_id", "event_date", "mu"]).assign(var=4.0)


def _shooters(censored: set[int], ids: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"shooter_id": ids, "left_censored": [i in censored for i in ids]})


def test_floor_and_ceiling_use_last_twenty_rounds(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds([(d, 1, s) for d, s in zip(_weeks_back(25), range(1, 26), strict=True)])
    floor, ceiling, n = profile.floor_ceiling(rounds)
    # last 20 scores are 6..25: P10 = 6 + 0.1*19, P90 = 6 + 0.9*19
    assert (floor, ceiling, n) == (pytest.approx(7.9), pytest.approx(23.1), 20)
    assert profile.floor_ceiling(rounds.iloc[0:0]) == (None, None, 0)


def test_bad_day_rate_counts_residual_at_or_below_minus_six(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    dates = _weeks_back(5)
    rounds = make_rounds(
        [
            {"event_date": d, "shooter_id": 1, "score": 30, "residual": r}
            for d, r in zip(dates, [-7.0, -6.0, -5.9, 2.0, math.nan], strict=True)
        ]
    )
    assert profile.bad_day_rate(rounds) == 0.5
    assert profile.bad_day_rate(rounds.assign(residual=math.nan)) is None


@pytest.mark.parametrize(
    ("residuals", "value", "label"),
    [
        ([9.0, 4.0, 3.0, 3.0, 2.0, 3.0], 3.0, "hot"),
        ([0.0, -4.0, -3.0, -2.0, -3.0, -3.0], -3.0, "cold"),
        ([1.0, 2.0, -2.0, 0.0, 1.0], 0.4, "steady"),
    ],
)
def test_form_is_mean_residual_of_last_five(
    make_rounds: Callable[..., pd.DataFrame],
    residuals: list[float],
    value: float,
    label: str,
) -> None:
    dates = _weeks_back(len(residuals))
    rounds = make_rounds(
        [
            {"event_date": d, "shooter_id": 1, "score": 30, "residual": r}
            for d, r in zip(dates, residuals, strict=True)
        ]
    )
    assert profile.form(rounds) == (pytest.approx(value), label)
    assert profile.form(rounds.tail(4)) == (None, None)


def test_learning_curve_vs_club_median_excluding_left_censored(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d = _weeks_back(3)
    specs = [
        {"event_date": d[0], "shooter_id": 1, "score": 30, "adjusted": -4.0},
        {"event_date": d[1], "shooter_id": 1, "score": 30, "adjusted": 0.0},
        {"event_date": d[1], "shooter_id": 1, "score": 34, "adjusted": 2.0},
        {"event_date": d[0], "shooter_id": 2, "score": 30, "adjusted": -2.0},
        {"event_date": d[1], "shooter_id": 2, "score": 30, "adjusted": 6.0},
        {"event_date": d[2], "shooter_id": 2, "score": 30, "adjusted": 8.0},
        {"event_date": d[0], "shooter_id": 3, "score": 30, "adjusted": 20.0},
        {
            "event_date": d[2],
            "shooter_id": 1,
            "score": 30,
            "adjusted": math.nan,
            "held": False,
        },
    ]
    curve = profile.learning_curve(make_rounds(specs), _shooters({3}, [1, 2, 3]), 1)

    assert curve == (
        profile.LearningPoint(k=1, value=-4.0, club_median=-3.0, n_club=2),
        profile.LearningPoint(k=2, value=1.0, club_median=3.5, n_club=2),
    )


def test_rust_effect_after_28_day_layoff(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d0 = date(2026, 1, 4)
    dates = [
        d0,
        d0 + timedelta(days=7),
        d0 + timedelta(days=42),
        d0 + timedelta(days=49),
        d0 + timedelta(days=76),
    ]
    rounds = make_rounds(
        [
            {"event_date": d, "shooter_id": 1, "score": 30, "residual": r}
            for d, r in zip(dates, [0.0, 2.0, -4.0, 2.0, 1.0], strict=True)
        ]
    )
    # gaps: 7, 35 (layoff), 7, 27 (not a layoff) -> post-layoff = [-4]; others mean 1.25
    effect, n = profile.rust_effect(rounds)
    assert (effect, n) == (pytest.approx(-4.0 - 1.25), 1)
    assert profile.rust_effect(rounds.iloc[:2]) == (None, 0)
    exactly = make_rounds(
        [
            {"event_date": d0, "shooter_id": 1, "score": 30, "residual": 0.0},
            {
                "event_date": d0 + timedelta(days=28),
                "shooter_id": 1,
                "score": 30,
                "residual": -3.0,
            },
        ]
    )
    # a gap of exactly 28 days (3 Sundays missed) is a layoff
    assert profile.rust_effect(exactly) == (-3.0, 1)
    only_post = make_rounds(
        [
            {"event_date": d0, "shooter_id": 1, "score": 30, "held": False},
            {
                "event_date": d0 + timedelta(days=50),
                "shooter_id": 1,
                "score": 30,
                "residual": -3.0,
            },
        ]
    )
    # the gap is measured from the non-held date; no residual round is left for "other"
    assert profile.rust_effect(only_post) == (None, 1)


def test_peak_prefers_earliest_date_on_ties() -> None:
    d = _weeks_back(3)
    history = _history([(1, d[0], 35.0), (1, d[1], 37.0), (1, d[2], 37.0)])
    assert profile.peak(history) == (37.0, d[1])
    assert profile.peak(history.iloc[0:0]) == (None, None)


def test_milestone_projection_from_26_week_rate() -> None:
    recent = set(_weeks_back(13))  # 13 events in the last 26 weeks -> 0.5 per week
    older = {AS_OF - timedelta(days=400 + 7 * k) for k in range(11)}
    m = profile.milestone(recent | older, AS_OF)  # 24 events -> next tier 25
    assert (m.next_events, m.events_to_go, m.weekly_rate) == (25, 1, 0.5)
    assert m.projected_date == AS_OF + timedelta(days=14)
    stale = profile.milestone(older, AS_OF)
    assert (stale.next_events, stale.weekly_rate, stale.projected_date) == (
        25,
        0.0,
        None,
    )
    done = profile.milestone({AS_OF - timedelta(days=7 * k) for k in range(250)}, AS_OF)
    assert (done.next_events, done.events_to_go, done.projected_date) == (
        None,
        None,
        None,
    )


def test_milestone_projection_counts_whole_weeks_exactly() -> None:
    # 15 events in the last 26 weeks and 35 in all: 15 to go at 15/26 per week is exactly
    # 26 weeks, which float division (15 / (15 / 26) = 26.000000000000004) would round up
    recent = set(_weeks_back(15))
    older = {AS_OF - timedelta(days=400 + 7 * k) for k in range(20)}
    m = profile.milestone(recent | older, AS_OF)
    assert (m.next_events, m.events_to_go, m.weekly_rate) == (50, 15, 15 / 26)
    assert m.projected_date == AS_OF + timedelta(weeks=26)


def test_milestone_rate_window_is_the_last_182_days() -> None:
    # (as_of - 182d, as_of]: 181 days back counts, 182 days back does not
    edge = {AS_OF - timedelta(days=181), AS_OF - timedelta(days=182)}
    assert profile.milestone(edge, AS_OF).weekly_rate == 1 / 26


def test_milestone_ignores_dates_after_as_of() -> None:
    # C7 no-leak: dates after as_of count toward neither the total nor the 26-week rate
    recent = set(_weeks_back(13))  # includes as_of itself, which counts
    older = {AS_OF - timedelta(days=400 + 7 * k) for k in range(11)}
    future = {AS_OF + timedelta(days=k) for k in (1, 7, 14, 21, 28)}
    assert profile.milestone(recent | older | future, AS_OF) == profile.Milestone(
        next_events=25,
        events_to_go=1,
        weekly_rate=0.5,
        projected_date=AS_OF + timedelta(days=14),
    )
    assert profile.milestone(future, AS_OF) == profile.Milestone(
        next_events=1, events_to_go=1, weekly_rate=0.0, projected_date=None
    )


def test_learning_curve_beyond_every_uncensored_career_has_no_club_median(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d = _weeks_back(2)
    specs = [
        {"event_date": d[0], "shooter_id": 1, "score": 30, "adjusted": 1.0},
        {"event_date": d[1], "shooter_id": 1, "score": 30, "adjusted": 3.0},
        {"event_date": d[1], "shooter_id": 2, "score": 30, "adjusted": -1.0},
    ]
    # shooter 1 is left_censored, so the club at k=2 has nobody left in it
    curve = profile.learning_curve(make_rounds(specs), _shooters({1}, [1, 2]), 1)
    assert curve == (
        profile.LearningPoint(k=1, value=1.0, club_median=-1.0, n_club=1),
        profile.LearningPoint(k=2, value=3.0, club_median=None, n_club=0),
    )


def test_insights_wins_podiums_and_percentile(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d = _weeks_back(3)
    rounds = make_rounds(
        [
            {
                "event_date": d[0],
                "shooter_id": 1,
                "score": 40,
                "is_best_round": True,
                "event_rank": 1.0,
                "percentile": 1.0,
            },
            {
                "event_date": d[0],
                "shooter_id": 1,
                "score": 20,
                "is_best_round": False,
                "event_rank": math.nan,
            },
            {
                "event_date": d[1],
                "shooter_id": 1,
                "score": 30,
                "is_best_round": True,
                "event_rank": 3.0,
                "percentile": 0.5,
            },
            {
                "event_date": d[2],
                "shooter_id": 1,
                "score": 25,
                "is_best_round": True,
                "event_rank": 6.0,
                "percentile": 0.0,
            },
        ]
    )
    out = profile.shooter_insights(rounds, _history([]), _shooters(set(), [1]), 1, AS_OF)
    assert (out.wins, out.podiums, out.n_rounds) == (1, 2, 4)
    assert out.avg_percentile == pytest.approx(0.5)
    assert out.peak_mu is None


def test_insights_no_leak(make_rounds: Callable[..., pd.DataFrame]) -> None:
    weeks = _weeks_back(16)  # weeks[15] is AS_OF
    # Shooter 1: 10 events with a 49-day layoff (weeks 4 -> 11); two bad days (-7, -8), the
    # second on the return; ranks and percentiles spread below the top.
    # (week, score, residual, adjusted, event_rank, percentile, mu)
    mine = [
        (0, 30, -7.0, -2.0, 1.0, 1.0, 30.0),
        (1, 32, 1.0, 0.0, 2.0, 0.8, 31.0),
        (2, 28, 2.0, -3.0, 4.0, 0.4, 32.0),
        (3, 35, 0.0, 3.0, 3.0, 0.6, 33.0),
        (4, 31, -1.0, -1.0, 5.0, 0.2, 34.0),
        (11, 25, -8.0, -5.0, 6.0, 0.0, 31.0),
        (12, 33, 3.0, 1.0, 2.0, 0.8, 32.0),
        (13, 34, 1.0, 2.0, 1.0, 1.0, 34.0),
        (14, 29, 0.0, -2.0, 4.0, 0.4, 33.0),
        (15, 36, 2.0, 4.0, 3.0, 0.6, 33.0),
    ]

    def row(d: date, s: int, score: int, residual: float, adjusted: float) -> dict[str, object]:
        return {
            "event_date": d,
            "shooter_id": s,
            "score": score,
            "residual": residual,
            "adjusted": adjusted,
            "is_best_round": True,
        }

    specs = [
        row(weeks[w], 1, score, r, a) | {"event_rank": rank, "percentile": pct}
        for w, score, r, a, rank, pct, _ in mine
    ]
    # Shooter 2 (uncensored) also returns from a 49-day layoff (weeks 3 -> 10); shooter 3
    # (left_censored) shoots every week.
    specs += [
        row(weeks[w], 2, 30, -4.0 if w == 10 else 0.0, 1.0)
        for w in (0, 1, 2, 3, 10, 11, 12, 13, 14, 15)
    ]
    specs += [row(d, 3, 40, 1.0, 20.0) for d in weeks]
    rounds = make_rounds(specs)
    history = _history([(1, weeks[w], mu) for w, *_, mu in mine])
    shooters = _shooters({3}, [1, 2, 3, 4])

    # After AS_OF: shooters 1 and 2 return from another 49-day layoff (shooter 1 with a -9
    # bad day, then hot), and newcomer 4 starts the day after AS_OF, landing at k=1 of the
    # club learning curve.
    later = [AS_OF + timedelta(weeks=w) for w in (7, 8, 9, 10)]
    future = [
        row(d, 1, 50, r, 9.0) | {"event_rank": 1.0, "percentile": 1.0}
        for d, r in zip(later, [-9.0, 9.0, 9.0, 9.0], strict=True)
    ]
    future += [row(d, 2, 30, 0.0, 9.0) for d in later]
    future += [row(d, 4, 45, 5.0, 9.0) for d in [AS_OF + timedelta(days=1), *later]]
    more_rounds = pd.concat(
        [
            rounds,
            make_rounds([spec | {"round_id": 1000 + i} for i, spec in enumerate(future)]),
        ],
        ignore_index=True,
    )
    more_history = pd.concat([history, _history([(1, d, 99.0) for d in later])], ignore_index=True)

    base = profile.shooter_insights(rounds, history, shooters, 1, AS_OF)
    assert profile.shooter_insights(more_rounds, more_history, shooters, 1, AS_OF) == base

    # The comparison above can only catch a leak in a field the future rows would move.
    # Every field is populated at AS_OF ...
    assert (base.n_rounds, base.recent_n, base.wins, base.podiums) == (10, 10, 2, 6)
    assert (base.bad_day_rate, base.form_label) == (0.2, "steady")
    assert base.avg_percentile == pytest.approx(0.58)
    assert (base.peak_mu, base.peak_date) == (34.0, weeks[4])
    assert base.rust.n == 1
    assert base.rust.effect == pytest.approx(-8.0 - 1 / 9)
    assert base.rust.club_effect == pytest.approx(-6.0 - 17 / 34)
    assert base.learning_curve[0] == profile.LearningPoint(
        k=1, value=-2.0, club_median=-0.5, n_club=2
    )
    assert (base.milestone.events_to_go, base.milestone.projected_date) == (
        15,
        AS_OF + timedelta(weeks=39),
    )
    # ... and every field moves once the future rows are in view.
    ahead = profile.shooter_insights(more_rounds, more_history, shooters, 1, later[-1])
    same = [f.name for f in fields(base) if getattr(ahead, f.name) == getattr(base, f.name)]
    assert same == []
    same_rust = [
        f.name
        for f in fields(base.rust)
        if getattr(ahead.rust, f.name) == getattr(base.rust, f.name)
    ]
    assert same_rust == []
    assert ahead.milestone.events_to_go == 11
    # the club side of the curve moves too, not only shooter 1's own points
    assert ahead.learning_curve[0] == profile.LearningPoint(
        k=1, value=-2.0, club_median=1.0, n_club=3
    )


def test_the_sundays_milestone_counts_special_sundays(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    from sunday_clays.analytics import frames

    days = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(9)]
    special_day = days[-1] + timedelta(weeks=1)
    rounds = make_rounds([(d, 1, 30) for d in days])
    special = frames.appearances_from_rounds(make_rounds([(special_day, 1, 30)]))
    seen = pd.concat(
        [frames.appearances_from_rounds(rounds), special.assign(kind="special")],
        ignore_index=True,
    )
    shooters = pd.DataFrame(
        [(1, "Shooter 1", "member", days[0], special_day, 9, 10, False)],
        columns=list(frames.SHOOTER_COLUMNS),
    )
    history = pd.DataFrame(columns=list(frames.RATING_COLUMNS))

    base = profile.shooter_insights(rounds, history, shooters, 1, special_day)
    counted = profile.shooter_insights(rounds, history, shooters, 1, special_day, seen)

    assert (base.milestone.next_events, base.milestone.events_to_go) == (10, 1)
    assert (counted.milestone.next_events, counted.milestone.events_to_go) == (25, 15)
    assert counted.n_rounds == base.n_rounds == 9
