from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    leaderboard,
)
from sunday_clays.analytics.points import event_points, points_for_rank, season_points

if TYPE_CHECKING:
    from conftest import FrameBuilder

D1, D2 = date(2026, 1, 4), date(2026, 1, 11)


@pytest.mark.parametrize(
    ("rank", "points"),
    [(1, 11), (2, 9), (3, 7), (4, 6), (5, 5), (6, 4), (7, 3), (8, 2), (9, 1), (30, 1)],
)
def test_points_for_rank_includes_participation(rank: int, points: int) -> None:
    assert points_for_rank(rank) == points


def test_tied_finish_shares_points(fb: FrameBuilder) -> None:
    for sid, name in [(1, "Ace, Amy"), (2, "Bee, Bob"), (3, "Cy, Cal"), (4, "Dee, Dot")]:
        fb.shooter(sid, name)
    fb.day(D1, {1: 45, 2: 45, 3: 44, 4: 43})
    pts = event_points(fb.rounds())
    assert dict(zip(pts["shooter_id"], pts["points"], strict=True)) == {1: 11, 2: 11, 3: 7, 4: 6}
    board = leaderboard(fb.frames(), LeaderboardPeriod.SEASON, LeaderboardMetric.SEASON_POINTS, D1)
    assert board.rows[["shooter_id", "rank", "value"]].values.tolist() == [
        [1, 1, 11.0],
        [2, 1, 11.0],
        [3, 3, 7.0],
        [4, 4, 6.0],
    ]


def test_season_points_count_only_best_round_per_event(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.day(D1, {1: 45, 2: 40}).round(D1, 1, 30, ordinal=2).day(D2, {2: 41, 1: 39})
    body = season_points(fb.rounds())
    assert dict(zip(body["shooter_id"], body["value"], strict=True)) == {1: 11 + 9, 2: 9 + 11}
    assert dict(zip(body["shooter_id"], body["n_rounds"], strict=True)) == {1: 2, 2: 2}


def test_season_points_under_gauge_filter_keep_full_field_rank(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.round(D1, 1, 45).round(D1, 2, 40, gauge_class="Sub-Gauge")
    board = leaderboard(
        fb.frames(),
        LeaderboardPeriod.SEASON,
        LeaderboardMetric.SEASON_POINTS,
        D1,
        LeaderboardFilters(gauge="Sub-Gauge"),
    )
    assert board.rows[["shooter_id", "rank", "value"]].values.tolist() == [[2, 1, 9.0]]


def test_event_points_ignore_non_best_round_even_with_rank(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    fb.round(D1, 1, 45).round(D1, 1, 30, ordinal=2, event_rank=1.0)
    pts = event_points(fb.rounds())
    assert pts["points"].tolist() == [11]
