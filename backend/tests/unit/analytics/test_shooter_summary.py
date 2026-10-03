"""Summary card facts (Plan 19 §3.6.1, D14, D18) on hand-built frames."""

from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import personal_best, summary
from sunday_clays.api.routes import events

D0 = date(2026, 1, 4)
ME = 3


def sunday(i: int) -> date:
    return D0 + timedelta(weeks=i)


def frames_for(
    scores: dict[int, list[int]], special: tuple[int, ...] = (), held_extra: tuple[int, ...] = ()
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """scores: Sunday index -> this shooter's regular scores that day."""
    rounds = pd.DataFrame(
        [(sunday(i), ME, s) for i, ss in scores.items() for s in ss],
        columns=["event_date", "shooter_id", "score"],
    )
    days = sorted({*scores, *special, *held_extra})
    appearances = pd.DataFrame(
        [(sunday(i), ME) for i in sorted({*scores, *special})], columns=["event_date", "shooter_id"]
    )
    calendar = pd.DataFrame(
        [(sunday(i), True, "special" if i in special else "regular") for i in days],
        columns=["event_date", "results_complete", "kind"],
    )
    return rounds, appearances, calendar


def run(
    scores: dict[int, list[int]],
    date_from: date | None,
    date_to: date,
    *,
    special: tuple[int, ...] = (),
    held_extra: tuple[int, ...] = (),
    awards: tuple[tuple[str, date], ...] = (),
) -> summary.ShooterSummary:
    rounds, appearances, calendar = frames_for(scores, special, held_extra)
    return summary.compute_summary(
        ME, "Hadley, Ike", rounds, appearances, calendar, list(awards), date_from, date_to
    )


def test_the_card_and_the_sunday_page_share_one_pb_rule() -> None:
    """D18: one source. Kills a copied constant or a re-implemented comparison in either place."""
    assert summary.is_new_pb is personal_best.is_new_pb
    assert events.is_new_pb is personal_best.is_new_pb
    assert events.PB_MIN_PRIOR_ROUNDS is personal_best.PB_MIN_PRIOR_ROUNDS
    assert personal_best.PB_MIN_PRIOR_ROUNDS == 5
    assert not hasattr(summary, "PB_MIN_PRIOR_ROUNDS")


@pytest.mark.parametrize(
    ("score", "previous_best", "n_prior", "expected"),
    [
        (45, 40, 5, True),  # exactly 5 earlier rounds counts (kills > 5)
        (45, 40, 4, False),
        (45, 45, 5, False),  # equal is not a PB (kills >=)
        (45, None, 5, False),
    ],
)
def test_is_new_pb(score: int, previous_best: int | None, n_prior: int, expected: bool) -> None:
    assert personal_best.is_new_pb(score, previous_best, n_prior) is expected


def test_rounds_average_and_best_in_the_window() -> None:
    result = run({0: [40], 1: [44, 46], 2: [41]}, sunday(1), sunday(2))
    assert (result.sundays, result.rounds, result.average) == (2, 3, 43.7)
    assert result.best == summary.BestRound(46, sunday(1))


def test_a_pb_needs_five_earlier_rounds_and_a_strictly_higher_score() -> None:
    four_before = {0: [40], 1: [40], 2: [40], 3: [40], 4: [45]}
    assert run(four_before, None, sunday(4)).pbs_set == 0  # 4 earlier rounds: not yet
    five_before = {0: [40], 1: [40], 2: [40], 3: [40], 4: [40], 5: [45]}
    assert run(five_before, None, sunday(5)).pbs_set == 1  # exactly 5 counts (kills > 5)
    tie = {0: [40], 1: [40], 2: [40], 3: [40], 4: [45], 5: [45]}
    assert run(tie, None, sunday(5)).pbs_set == 0  # 45 again ties, not a new PB (kills >=)


def test_earlier_rounds_before_the_window_count_toward_the_pb_rule() -> None:
    history = {0: [40], 1: [40], 2: [40], 3: [40], 4: [40], 5: [45]}
    assert run(history, sunday(5), sunday(5)).pbs_set == 1


def test_window_edges_are_inclusive() -> None:
    result = run({0: [40], 1: [41], 2: [42]}, sunday(0), sunday(2))
    assert result.sundays == 3
    assert result.rounds == 3


def test_the_streak_counts_only_sundays_inside_the_window() -> None:
    result = run({i: [40] for i in range(6)}, sunday(3), sunday(5))
    assert result.longest_streak == 3


def test_a_special_only_shooter_has_sundays_and_nothing_else() -> None:
    result = run({}, sunday(0), sunday(2), special=(1,))
    assert (result.sundays, result.special_sundays, result.rounds) == (1, 1, 0)
    assert result.average is None
    assert result.best is None
    assert result.pbs_set == 0


def test_an_empty_window() -> None:
    result = run({5: [40]}, sunday(0), sunday(2))
    assert result.sundays == 0
    assert result.rounds == 0
    assert result.longest_streak == 0


def test_an_open_start_covers_everything_up_to_to() -> None:
    assert run({0: [40], 1: [41], 9: [50]}, None, sunday(2)).rounds == 2


def test_trophies_leave_out_competition_and_name_three_newest() -> None:
    awards = (
        ("events:5", sunday(1)),  # Events Attended, Silver
        ("iron_streak:1", sunday(2)),
        ("doubleheader", sunday(2)),
        ("first_win", sunday(2)),  # D14: never counted or named
        ("station_top_gun", sunday(2)),  # D14 too, though the registry files it under "stations"
        ("years_active:1", sunday(0)),
        ("events:1", date(2025, 1, 5)),  # before the window
    )
    result = run({0: [40], 1: [41], 2: [42]}, sunday(0), sunday(2), awards=awards)
    assert result.trophies == 4
    assert result.trophy_names == (
        "Doubleheader",
        "Iron Streak — Bronze",
        "Events Attended — Silver",
    )


@pytest.mark.parametrize(
    ("code", "title"),
    [
        ("events:5", "Events Attended — Silver"),
        ("doubleheader", "Doubleheader"),
        ("station_cleaner:1", "Station Cleaner — Bronze"),  # a stations trophy D14 does not name
        ("first_win", None),
        ("podium", None),
        ("station_top_gun", None),
        ("hardest_station_clean", None),
        ("nope", None),
    ],
)
def test_trophy_title(code: str, title: str | None) -> None:
    assert summary.trophy_title(code) == title


def test_nothing_after_the_window_end_leaks_in() -> None:
    """No-leak: later Sundays, rounds, specials and trophies never change a window's answer."""
    base_awards = (("events:5", sunday(1)),)
    early = run({0: [40], 1: [44], 2: [41]}, sunday(0), sunday(2), awards=base_awards)
    later = run(
        {0: [40], 1: [44], 2: [41], 3: [50], 4: [50]},
        sunday(0),
        sunday(2),
        special=(3,),
        awards=(*base_awards, ("doubleheader", sunday(3))),
    )
    assert later == early
