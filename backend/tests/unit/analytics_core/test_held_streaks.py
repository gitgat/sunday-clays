from collections.abc import Callable
from datetime import date, timedelta

import pandas as pd

from sunday_clays.analytics import frames
from sunday_clays.analytics.streaks import held_event_dates, streaks

W = [date(2026, 1, 4) + timedelta(days=7 * k) for k in range(8)]


def _by_shooter(frame: pd.DataFrame) -> dict[int, tuple[int, int]]:
    return {
        int(r.shooter_id): (int(r.current_streak), int(r.longest_streak))
        for r in frame.itertuples()
    }


def test_attendance_only_event_does_not_break_streak(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = make_events(
        [
            W[0],
            W[1],
            {"event_date": W[2], "results_complete": False, "has_scores": False},
            W[3],
        ]
    )
    rounds = make_rounds([(W[0], 1, 30), (W[1], 1, 30), (W[3], 1, 30)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (3, 3)}


def test_incomplete_scored_event_is_skipped_even_when_attended(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = make_events([W[0], {"event_date": W[1], "results_complete": False}, W[2]])
    rounds = make_rounds([(W[0], 1, 30), (W[1], 1, 30), (W[2], 1, 30), (W[1], 2, 30)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (2, 2), 2: (0, 0)}


def test_missed_held_event_breaks_and_current_needs_latest(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = make_events(W[:6])
    rounds = make_rounds(
        [
            (W[0], 1, 30),
            (W[1], 1, 30),
            (W[2], 1, 30),
            (W[4], 1, 30),
            (W[5], 1, 30),
            (W[0], 2, 30),
            (W[1], 2, 30),
        ]
    )

    assert _by_shooter(streaks(rounds, events, None)) == {1: (2, 3), 2: (0, 2)}


def test_as_of_limits_and_no_leak(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    rounds = make_rounds([(d, 1, 30) for d in W[:4]] + [(W[3], 2, 30)])
    events = make_events(W[:4])
    more_rounds = pd.concat([rounds, make_rounds([(W[5], 1, 30), (W[5], 3, 30)])])
    more_events = make_events(W[:6])

    base = streaks(rounds, events, W[3])
    pd.testing.assert_frame_equal(base, streaks(more_rounds, more_events, W[3]))
    assert _by_shooter(base) == {1: (4, 4), 2: (1, 1)}
    assert _by_shooter(streaks(rounds, events, W[1])) == {1: (2, 2)}


def test_held_event_dates_filters_and_sorts(
    make_events: Callable[..., pd.DataFrame],
) -> None:
    events = make_events([W[2], W[0], {"event_date": W[1], "results_complete": False}])
    assert held_event_dates(events, None) == [W[0], W[2]]
    assert held_event_dates(events, W[1]) == [W[0]]


def test_held_event_dates_no_leak(make_events: Callable[..., pd.DataFrame]) -> None:
    events = make_events(W[:4])
    more_events = make_events([*W[:4], W[5], {"event_date": W[6], "results_complete": False}])

    assert held_event_dates(more_events, W[3]) == held_event_dates(events, W[3]) == W[:4]


def test_no_rounds_gives_empty_frame(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    empty = streaks(make_rounds([(W[0], 1, 30)]).iloc[0:0], make_events([W[0]]), None)
    assert empty.empty
    assert list(empty.columns) == ["shooter_id", "current_streak", "longest_streak"]


def _with_special(events: pd.DataFrame, *days: date) -> pd.DataFrame:
    calendar = frames.calendar_from_events(events)
    calendar.loc[calendar["event_date"].isin(days), "kind"] = frames.EVENT_KIND_SPECIAL
    return calendar


def test_a_special_sunday_extends_the_run_of_everyone_who_came(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = _with_special(make_events(W[:4]), W[2])
    rounds = make_rounds([(W[0], 1, 30), (W[1], 1, 30), (W[2], 1, 55), (W[3], 1, 30)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (4, 4)}


def test_a_special_sunday_never_breaks_the_run_of_anyone_who_skipped_it(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = _with_special(make_events(W[:4]), W[2])
    rounds = make_rounds([(W[0], 2, 30), (W[1], 2, 30), (W[3], 2, 30), (W[2], 1, 40)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (0, 1), 2: (3, 3)}


def test_a_special_latest_sunday_does_not_end_a_current_run(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = _with_special(make_events(W[:4]), W[3])
    rounds = make_rounds(
        [(W[1], 1, 30), (W[2], 1, 30), (W[1], 2, 30), (W[2], 2, 30), (W[3], 2, 50)]
    )

    assert _by_shooter(streaks(rounds, events, None)) == {1: (2, 2), 2: (3, 3)}


def test_a_missed_regular_sunday_still_breaks_a_run_through_a_special_one(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = _with_special(make_events(W[:5]), W[1])
    rounds = make_rounds([(W[0], 1, 30), (W[1], 1, 50), (W[3], 1, 30), (W[4], 1, 30)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (2, 2)}
