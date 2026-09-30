from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from sunday_clays.analytics.leaderboards import (
    Leaderboard,
    LeaderboardMetric,
    LeaderboardPeriod,
    canonical_window,
    leaderboard,
    make_leaderboard_frames,
)

if TYPE_CHECKING:
    from conftest import FrameBuilder

ALL = LeaderboardPeriod.ALL_TIME
SEASON = LeaderboardPeriod.SEASON
YTD = LeaderboardPeriod.YTD


def values(board: Leaderboard) -> dict[int, float]:
    return dict(zip(board.rows["shooter_id"], board.rows["value"], strict=True))


def _weekly(fb: FrameBuilder, sid: int, start: date, n: int, score: int, mu: float) -> None:
    for week in range(n):
        day = start + timedelta(weeks=week)
        fb.round(day, sid, score).rating(sid, day, mu)


def test_rating_gain_excludes_prior_washout(fb: FrameBuilder) -> None:
    fb.shooter(1, "Washout, Wes").shooter(2, "Regular, Rae").shooter(3, "Short, Sam")
    before, inside = date(2025, 1, 5), date(2026, 1, 4)
    _weekly(fb, 1, before, 4, 10, 15.0)  # only 4 rounds before the season: not eligible
    _weekly(fb, 2, before, 10, 30, 30.0)
    _weekly(fb, 3, before, 12, 30, 30.0)
    _weekly(fb, 1, inside, 6, 45, 40.0)  # +25 would top the board if the washout counted
    _weekly(fb, 2, inside, 5, 35, 33.5)
    _weekly(fb, 3, inside, 4, 45, 44.0)  # only 4 rounds inside the season: not eligible
    board = leaderboard(fb.frames(), YTD, LeaderboardMetric.RATING_GAIN, date(2026, 3, 1))
    assert values(board) == {2: 3.5}
    assert board.rows["n_rounds"].tolist() == [5]


def test_season_rating_gain_needs_only_3_rounds_in_the_last_8_sundays(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob").shooter(3, "Cy, Cal")
    _weekly(fb, 1, date(2025, 10, 5), 10, 30, 30.0)  # 10 rounds before the window
    _weekly(fb, 2, date(2025, 10, 5), 10, 30, 30.0)
    _weekly(fb, 3, date(2025, 10, 5), 10, 30, 30.0)
    as_of = date(2026, 3, 1)  # window starts 2026-01-05: Sundays Jan 11 .. Mar 1
    _weekly(fb, 1, date(2026, 2, 15), 3, 40, 34.0)  # 3 inside: eligible
    _weekly(fb, 2, date(2026, 2, 22), 2, 40, 39.0)  # 2 inside: not eligible
    _weekly(fb, 3, date(2025, 12, 14), 3, 40, 38.0)  # all three before Jan 5: none inside
    board = leaderboard(fb.frames(), SEASON, LeaderboardMetric.RATING_GAIN, as_of)
    assert values(board) == {1: 4.0}
    assert board.min_rounds_applied == 3


def test_rating_gain_all_time_starts_after_tenth_round(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    start = date(2025, 1, 5)
    for week in range(15):
        day = start + timedelta(weeks=week)
        fb.round(day, 1, 40).rating(1, day, 20.0 + week)  # mu after 10th round = 29, last = 34
    for week in range(14):  # 14 rounds < 15: not eligible
        day = start + timedelta(weeks=week)
        fb.round(day, 2, 40).rating(2, day, 10.0 + 3 * week)
    board = leaderboard(fb.frames(), ALL, LeaderboardMetric.RATING_GAIN, date(2026, 1, 4))
    assert values(board) == {1: 5.0}
    assert board.min_rounds_applied == 15


def test_empty_frames_give_empty_board(fb: FrameBuilder) -> None:
    frames = make_leaderboard_frames(fb.rounds(), fb.events(), fb.history())
    for metric in LeaderboardMetric:
        board = leaderboard(frames, ALL, metric, date(2026, 1, 4))
        assert board.n_eligible == 0
        assert board.records() == []


def test_rating_gain_with_since_uses_the_last_rating_before_it(fb: FrameBuilder) -> None:
    fb.shooter(1, "Nine, Ned").shooter(2, "TenFour, Tia").shooter(3, "TenFive, Tom")
    since = date(2026, 1, 4)
    _weekly(fb, 1, since - timedelta(weeks=9), 9, 30, 20.0)  # 9 before: not eligible
    _weekly(fb, 2, since - timedelta(weeks=10), 10, 30, 20.0)
    _weekly(fb, 3, since - timedelta(weeks=10), 10, 30, 21.0)
    _weekly(fb, 1, since, 6, 40, 40.0)
    _weekly(fb, 2, since, 4, 40, 40.0)  # 4 inside: not eligible
    _weekly(fb, 3, since, 5, 40, 30.0)
    as_of = since + timedelta(weeks=5)
    board = leaderboard(fb.frames(), SEASON, LeaderboardMetric.RATING_GAIN, as_of, since=since)
    assert values(board) == {3: 9.0}  # 30 at as_of minus 21 at the last Sunday before since
    assert board.rows["n_rounds"].tolist() == [5]
    assert board.min_rounds_applied == 5


def test_rating_gain_since_jan_1_equals_ytd(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    _weekly(fb, 1, date(2025, 1, 5), 12, 30, 30.0)
    _weekly(fb, 2, date(2025, 1, 5), 12, 30, 25.0)
    _weekly(fb, 1, date(2026, 1, 4), 6, 40, 36.0)
    _weekly(fb, 2, date(2026, 1, 4), 6, 40, 27.0)
    frames = fb.frames()
    as_of = date(2026, 3, 1)
    ytd = leaderboard(frames, YTD, LeaderboardMetric.RATING_GAIN, as_of)
    custom = leaderboard(frames, ALL, LeaderboardMetric.RATING_GAIN, as_of, since=date(2026, 1, 1))
    assert ytd.n_eligible == 2
    pd.testing.assert_frame_equal(custom.rows, ytd.rows)


def test_rating_gain_lists_only_gainers(fb: FrameBuilder) -> None:
    fb.shooter(1, "Up, Uma").shooter(2, "Flat, Fay").shooter(3, "Down, Dan")
    for sid, start_mu, end_mu in ((1, 30.0, 34.0), (2, 30.0, 30.0), (3, 30.0, 27.0)):
        _weekly(fb, sid, date(2025, 10, 5), 10, 30, start_mu)
        _weekly(fb, sid, date(2026, 2, 8), 5, 35, end_mu)
    board = leaderboard(fb.frames(), YTD, LeaderboardMetric.RATING_GAIN, date(2026, 3, 8))
    assert values(board) == {1: 4.0}  # no flat, no loss: nobody is ranked for going down
    assert board.n_eligible == 1


@pytest.mark.parametrize(
    ("period", "as_of", "since", "expected"),
    [
        (ALL, date(2026, 3, 1), date(2026, 1, 1), (YTD, None)),
        (ALL, date(2026, 3, 1), date(2026, 1, 5), (SEASON, None)),
        (ALL, date(2026, 3, 1), date(2025, 3, 3), (LeaderboardPeriod.ROLLING_12, None)),
        (SEASON, date(2026, 3, 1), date(2026, 1, 6), (SEASON, date(2026, 1, 6))),
        (ALL, date(2026, 3, 1), None, (ALL, None)),
    ],
)
def test_canonical_window_turns_a_named_start_back_into_its_period(
    period: LeaderboardPeriod,
    as_of: date,
    since: date | None,
    expected: tuple[LeaderboardPeriod, date | None],
) -> None:
    assert canonical_window(period, as_of, since) == expected


def test_a_board_carries_its_resolved_start(fb: FrameBuilder) -> None:
    frames = fb.frames()
    as_of = date(2026, 3, 1)
    assert leaderboard(frames, SEASON, LeaderboardMetric.WINS, as_of).start == date(2026, 1, 5)
    assert leaderboard(frames, ALL, LeaderboardMetric.WINS, as_of).start is None
    custom = leaderboard(frames, ALL, LeaderboardMetric.WINS, as_of, since=date(2026, 2, 1))
    assert custom.start == date(2026, 2, 1)
    assert (
        leaderboard(frames, ALL, LeaderboardMetric.WINS, as_of, since=date(2026, 1, 1)).period
        is YTD
    )
