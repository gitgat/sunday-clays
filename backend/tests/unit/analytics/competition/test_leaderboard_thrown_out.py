"""Leaderboards leave out a Sunday with a station thrown out (score boards only)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from sunday_clays.analytics.leaderboard_history import leaderboard_history
from sunday_clays.analytics.leaderboards import (
    LeaderboardMetric,
    LeaderboardPeriod,
    custom_min_rounds,
    leaderboard,
    scaled_min_rounds,
)

if TYPE_CHECKING:
    from conftest import FrameBuilder

D1, D2, D3 = date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18)
SEASON = LeaderboardPeriod.SEASON
M = LeaderboardMetric


def values(board):  # type: ignore[no-untyped-def]
    return dict(zip(board.rows["shooter_id"], board.rows["value"], strict=True))


def test_score_boards_leave_out_a_thrown_out_sunday_and_count_boards_keep_it(
    fb: FrameBuilder,
) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.day(D1, {1: 40, 2: 30}).day(D2, {1: 50, 2: 20}, stats_excluded=True).day(D3, {1: 44, 2: 36})
    frames = fb.frames()
    avg = leaderboard(frames, SEASON, M.AVG_SCORE, D3)
    assert values(avg) == {1: 42.0, 2: 33.0}
    assert avg.rows["n_rounds"].tolist() == [2, 2]
    assert values(leaderboard(frames, SEASON, M.BEST_SCORE, D3)) == {1: 44.0, 2: 36.0}
    assert values(leaderboard(frames, SEASON, M.AVG_ADJUSTED, D3)) == {1: 4.5, 2: -4.5}
    assert values(leaderboard(frames, SEASON, M.WINS, D3)) == {1: 3.0, 2: 0.0}
    assert values(leaderboard(frames, SEASON, M.ROUNDS, D3)) == {1: 3.0, 2: 3.0}
    assert values(leaderboard(frames, SEASON, M.EVENTS, D3)) == {1: 3.0, 2: 3.0}


def test_the_average_board_minimum_counts_only_sundays_in_the_average(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    days = [D1 + timedelta(weeks=i) for i in range(5)]
    for i, d in enumerate(days):
        fb.day(d, {1: 40}, stats_excluded=i in (1, 2, 3))
    events = fb.events()
    assert scaled_min_rounds(events, SEASON, days[-1]) == 1  # E = 2 (5 would give 2)
    assert custom_min_rounds(events, days[0], days[-1]) == 1


def test_rating_gain_eligibility_counts_thrown_out_rounds(fb: FrameBuilder) -> None:  # guard
    fb.shooter(1, "Ace, Amy")
    before = [date(2025, 10, 5) + timedelta(weeks=i) for i in range(10)]
    inside = [date(2026, 2, 15), date(2026, 2, 22), date(2026, 3, 1)]
    for i, d in enumerate(before + inside):
        fb.day(d, {1: 40}, stats_excluded=i == 4)
    fb.rating(1, before[-1], 30.0).rating(1, inside[-1], 33.0)
    board = leaderboard(fb.frames(), SEASON, M.RATING_GAIN, inside[-1])
    assert [(r.shooter_id, r.value, r.n_rounds) for r in board.records()] == [(1, 3.0, 3)]


def test_history_keeps_a_frame_for_a_thrown_out_sunday(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").day(D1, {1: 40}).day(D2, {1: 50}, stats_excluded=True).day(
        D3, {1: 44}
    )
    history = leaderboard_history(fb.frames(), SEASON, M.AVG_SCORE, top=3, date_from=D1, date_to=D3)
    assert [f.event_date for f in history] == [D1, D2, D3]
    assert [[(r.value, r.n_rounds) for r in f.rows] for f in history] == [
        [(40.0, 1)],
        [(40.0, 1)],
        [(42.0, 2)],
    ]
