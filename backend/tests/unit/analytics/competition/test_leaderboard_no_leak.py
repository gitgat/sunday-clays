from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardFrames,
    LeaderboardMetric,
    LeaderboardPeriod,
    leaderboard,
)

if TYPE_CHECKING:
    from conftest import FrameBuilder

AS_OF = date(2026, 3, 1)
FIRST = date(2024, 10, 6)
MERGED_ALIAS = "aaa merged alias"


def _season(fb: FrameBuilder, weeks: int, start: date) -> None:
    for week in range(weeks):
        day = start + timedelta(weeks=week)
        for sid in (1, 2, 3):
            score = 30 + (sid * 7 + week * 3) % 15
            fb.round(day, sid, score)
            fb.rating(sid, day, 28.0 + sid + 0.1 * week)
        if week % 3 == 0:
            fb.round(day, 1, 25, ordinal=2)


def _build(fb: FrameBuilder, *, with_future: bool) -> FrameBuilder:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob", status="guest").shooter(3, "Cy, Cal")
    fb.shooter(4, "Late, Lou")
    _season(fb, 73, FIRST)  # 2024-10-06 .. 2026-02-22
    if with_future:
        _season(fb, 10, date(2026, 3, 8))
        for week in range(10):
            day = date(2026, 3, 8) + timedelta(weeks=week)
            fb.round(day, 4, 50).rating(4, day, 45.0)
        # An alias merged into Cy later, whose key sorts before every past name (D6 tie key).
        fb.round(date(2026, 3, 15), 3, 20, ordinal=2, name_key=MERGED_ALIAS)
    return fb


@pytest.fixture(scope="module")
def worlds(make_builder: type[FrameBuilder]) -> tuple[LeaderboardFrames, LeaderboardFrames]:
    past = _build(make_builder(), with_future=False).frames()
    full = _build(make_builder(), with_future=True).frames()
    return past, full


@pytest.mark.parametrize("metric", list(LeaderboardMetric))
@pytest.mark.parametrize("period", list(LeaderboardPeriod))
@pytest.mark.parametrize(
    "filters", [LeaderboardFilters(), LeaderboardFilters(status="member", gauge="unspecified")]
)
def test_leaderboard_no_leak(
    worlds: tuple[LeaderboardFrames, LeaderboardFrames],
    metric: LeaderboardMetric,
    period: LeaderboardPeriod,
    filters: LeaderboardFilters,
) -> None:
    past = leaderboard(worlds[0], period, metric, AS_OF, filters)
    full = leaderboard(worlds[1], period, metric, AS_OF, filters)
    assert past.min_rounds_applied == full.min_rounds_applied
    pd.testing.assert_frame_equal(past.rows, full.rows)
    assert past.n_eligible > 0


def test_no_leak_world_has_ties_a_later_alias_could_reorder(
    worlds: tuple[LeaderboardFrames, LeaderboardFrames],
) -> None:
    past = leaderboard(worlds[0], LeaderboardPeriod.SEASON, LeaderboardMetric.EVENTS, AS_OF)
    assert past.rows["rank"].tolist() == [1, 1, 1]
    assert past.rows["shooter_id"].tolist() == [1, 2, 3]
    assert (worlds[1].rounds["name_key"] == MERGED_ALIAS).sum() == 1


def test_later_alias_never_reorders_past_ties_or_moves_top_cut(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Zed, Zoe")
    fb.day(date(2026, 1, 4), {1: 45, 2: 45})
    before = leaderboard(
        fb.frames(), LeaderboardPeriod.SEASON, LeaderboardMetric.BEST_SCORE, date(2026, 1, 4)
    )
    fb.round(date(2026, 3, 8), 2, 30, name_key="aaa zed alias")
    frames = fb.frames()
    assert frames.shooters.set_index("shooter_id")["sort_key"].to_dict() == {
        1: "ace amy",
        2: "aaa zed alias",
    }
    after = leaderboard(
        frames, LeaderboardPeriod.SEASON, LeaderboardMetric.BEST_SCORE, date(2026, 1, 4)
    )
    assert before.rows[["rank", "shooter_id", "value"]].values.tolist() == [[1, 1, 45], [1, 2, 45]]
    pd.testing.assert_frame_equal(before.rows, after.rows)
    assert [r.shooter_id for r in after.records(top=1)] == [1]


SINCE = date(2025, 11, 2)


@pytest.mark.parametrize("metric", list(LeaderboardMetric))
def test_since_board_ignores_rounds_before_since_and_after_as_of(
    worlds: tuple[LeaderboardFrames, LeaderboardFrames],
    make_builder: type[FrameBuilder],
    metric: LeaderboardMetric,
) -> None:
    past, full = worlds
    board = leaderboard(past, LeaderboardPeriod.SEASON, metric, AS_OF, since=SINCE)
    assert board.n_eligible > 0
    with_future = leaderboard(full, LeaderboardPeriod.SEASON, metric, AS_OF, since=SINCE)
    pd.testing.assert_frame_equal(board.rows, with_future.rows)
    if metric is LeaderboardMetric.RATING_GAIN:
        return  # by design rounds before since feed its starting rating and n_before
    # Extra rounds strictly before since (and their Sunday) leave the range board alone.
    early = _build(make_builder(), with_future=False)
    early.round(date(2025, 10, 26), 1, 50, ordinal=3).round(date(2025, 10, 26), 2, 1, ordinal=3)
    changed = leaderboard(early.frames(), LeaderboardPeriod.SEASON, metric, AS_OF, since=SINCE)
    pd.testing.assert_frame_equal(board.rows, changed.rows)


SEASON_START = AS_OF - timedelta(days=55)  # 2026-01-05: the season window's first day
ROUND_METRICS = [m for m in LeaderboardMetric if m is not LeaderboardMetric.RATING_GAIN]


@pytest.mark.parametrize("metric", ROUND_METRICS)
@pytest.mark.parametrize(
    ("period", "old_day"),
    [
        (LeaderboardPeriod.SEASON, SEASON_START - timedelta(days=1)),
        (LeaderboardPeriod.YTD, date(2025, 12, 28)),
    ],
)
def test_season_and_ytd_boards_ignore_rounds_before_their_window(
    worlds: tuple[LeaderboardFrames, LeaderboardFrames],
    make_builder: type[FrameBuilder],
    metric: LeaderboardMetric,
    period: LeaderboardPeriod,
    old_day: date,
) -> None:
    board = leaderboard(worlds[0], period, metric, AS_OF)
    assert board.n_eligible > 0
    older = _build(make_builder(), with_future=False)
    older.round(old_day, 1, 50, ordinal=3).round(old_day, 2, 1, ordinal=3)
    changed = leaderboard(older.frames(), period, metric, AS_OF)
    pd.testing.assert_frame_equal(board.rows, changed.rows)
    assert board.min_rounds_applied == changed.min_rounds_applied
