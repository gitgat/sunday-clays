from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from sunday_clays.analytics.leaderboards import (
    Leaderboard,
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    LeaderboardRow,
    leaderboard,
)
from sunday_clays.domain.round_type import RoundType

if TYPE_CHECKING:
    from conftest import FrameBuilder

D1, D2, D3 = date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18)
ALL = LeaderboardPeriod.ALL_TIME
SEASON = LeaderboardPeriod.SEASON


def values(board: Leaderboard) -> dict[int, float]:
    return dict(zip(board.rows["shooter_id"], board.rows["value"], strict=True))


def test_avg_score_counts_every_round_of_multi_round_days(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    fb.round(D1, 1, 40).round(D1, 1, 30, ordinal=2).round(D2, 1, 35)
    board = leaderboard(fb.frames(), SEASON, LeaderboardMetric.AVG_SCORE, D2)
    assert board.records() == [
        LeaderboardRow(
            rank=1, shooter_id=1, display_name="Ace, Amy", status="member", value=35.0, n_rounds=3
        )
    ]


def test_avg_adjusted_skips_non_held_events(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.day(D1, {1: 40, 2: 30})  # median 35 -> +5 / -5
    fb.day(D2, {1: 20}, held=False)  # adjusted NULL at a non-held event
    frames = fb.frames()
    adjusted = leaderboard(frames, SEASON, LeaderboardMetric.AVG_ADJUSTED, D2)
    assert values(adjusted) == {1: 5.0, 2: -5.0}
    assert adjusted.rows["n_rounds"].tolist() == [1, 1]
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.AVG_SCORE, D2))[1] == 30.0


def test_best_score_is_max_single_round(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").day(D1, {1: 41}).day(D2, {1: 47}).day(D3, {1: 39})
    assert values(leaderboard(fb.frames(), ALL, LeaderboardMetric.BEST_SCORE, D3)) == {1: 47.0}


def test_wins_and_podiums_count_best_rounds_only(fb: FrameBuilder) -> None:
    for sid, name in [(1, "Ace, Amy"), (2, "Bee, Bob"), (3, "Cy, Cal"), (4, "Dee, Dot")]:
        fb.shooter(sid, name)
    fb.day(D1, {1: 45, 2: 40, 3: 35, 4: 20}).round(D1, 1, 44, ordinal=2)
    frames = fb.frames()
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.WINS, D1)) == {
        1: 1.0, 2: 0.0, 3: 0.0, 4: 0.0,
    }  # fmt: skip
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.PODIUMS, D1)) == {
        1: 1.0, 2: 1.0, 3: 1.0, 4: 0.0,
    }  # fmt: skip


def test_events_counts_distinct_dates_and_rounds_counts_rows(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    fb.round(D1, 1, 40).round(D1, 1, 38, ordinal=2).round(D2, 1, 35)
    frames = fb.frames()
    assert values(leaderboard(frames, ALL, LeaderboardMetric.EVENTS, D2)) == {1: 2.0}
    assert values(leaderboard(frames, ALL, LeaderboardMetric.ROUNDS, D2)) == {1: 3.0}


def test_events_board_counts_sundays_in_its_count_column(fb: FrameBuilder) -> None:
    """Labelled "Sundays" for Events, so the column is the Sunday count, not the round count."""
    fb.shooter(1, "Ace, Amy")
    fb.round(D1, 1, 40).round(D1, 1, 38, ordinal=2).round(D2, 1, 35)
    board = leaderboard(fb.frames(), ALL, LeaderboardMetric.EVENTS, D2)
    assert board.rows["n_rounds"].tolist() == [2]
    rounds = leaderboard(fb.frames(), ALL, LeaderboardMetric.ROUNDS, D2)
    assert rounds.rows["n_rounds"].tolist() == [3]


def test_ties_share_min_rank_and_order_by_name_key(fb: FrameBuilder) -> None:
    fb.shooter(1, "Zed, Al").shooter(2, "Abe, Bo").shooter(3, "Cy, Di")
    fb.day(D1, {1: 45, 2: 45, 3: 40})
    board = leaderboard(fb.frames(), SEASON, LeaderboardMetric.BEST_SCORE, D1)
    assert board.rows[["shooter_id", "rank"]].values.tolist() == [[2, 1], [1, 1], [3, 3]]


def test_threshold_drops_shooters_below_min_rounds(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    for week in range(8):
        fb.round(date(2026, 1, 4) + timedelta(weeks=week), 1, 40)
    for week in range(7):
        fb.round(date(2026, 1, 4) + timedelta(weeks=week), 2, 45)
    board = leaderboard(
        fb.frames(), LeaderboardPeriod.ROLLING_12, LeaderboardMetric.AVG_SCORE, date(2026, 3, 1)
    )
    assert (board.min_rounds_applied, board.n_eligible) == (8, 1)
    assert values(board) == {1: 40.0}


def test_filtered_wins_use_full_field_rank(fb: FrameBuilder) -> None:
    fb.shooter(1, "Guest, Gus", status="guest").shooter(2, "Member, Meg", status="member")
    fb.day(D1, {1: 45, 2: 44})
    frames = fb.frames()
    members = leaderboard(
        frames, SEASON, LeaderboardMetric.WINS, D1, LeaderboardFilters(status="member")
    )
    assert values(members) == {2: 0.0}
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.WINS, D1)) == {1: 1.0, 2: 0.0}


def test_status_filter_reads_shooter_status_not_row_status(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy", status="member").shooter(2, "Bee, Bob", status="guest")
    fb.round(D1, 1, 40, row_status="guest").round(D1, 2, 30)
    frames = fb.frames()
    member = LeaderboardFilters(status="member")
    guest = LeaderboardFilters(status="guest")
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.ROUNDS, D1, member)) == {1: 1.0}
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.ROUNDS, D1, guest)) == {2: 1.0}


def test_gauge_filter_matches_unspecified_for_null_gauge(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    fb.round(D1, 1, 40).round(D2, 1, 30, gauge_class="Sub-Gauge")
    frames = fb.frames()
    unspecified = LeaderboardFilters(gauge="unspecified")
    sub = LeaderboardFilters(gauge="Sub-Gauge")
    assert values(leaderboard(frames, ALL, LeaderboardMetric.AVG_SCORE, D2, unspecified)) == {}
    assert values(leaderboard(frames, ALL, LeaderboardMetric.BEST_SCORE, D2, unspecified)) == {
        1: 40.0
    }
    assert values(leaderboard(frames, ALL, LeaderboardMetric.BEST_SCORE, D2, sub)) == {1: 30.0}


def test_round_type_filter_counts_only_matching_events(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    fb.day(D1, {1: 40}, round_type="sporting").day(D2, {1: 30}, round_type="super_sporting")
    only_sporting = LeaderboardFilters(round_types=(RoundType.SPORTING,))
    board = leaderboard(fb.frames(), ALL, LeaderboardMetric.ROUNDS, D2, only_sporting)
    assert values(board) == {1: 1.0}


def test_values_are_rounded_to_two_decimals(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").day(D1, {1: 40}).day(D2, {1: 41}).day(D3, {1: 41})
    assert values(leaderboard(fb.frames(), SEASON, LeaderboardMetric.AVG_SCORE, D3)) == {1: 40.67}


def test_rolling12_window_counts_52_weekly_rounds(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    first = date(2025, 9, 28)  # exactly 364 days before as_of: outside (as_of - 364d, as_of]
    for week in range(53):
        fb.round(first + timedelta(weeks=week), 1, 40)
    board = leaderboard(
        fb.frames(), LeaderboardPeriod.ROLLING_12, LeaderboardMetric.ROUNDS, date(2026, 9, 27)
    )
    assert board.rows["value"].tolist() == [52.0]


def test_records_top_keeps_leading_rows_and_null_status(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob", status=None).shooter(3, "Cy, Cal")
    fb.day(D1, {1: 45, 2: 44, 3: 40})
    board = leaderboard(fb.frames(), SEASON, LeaderboardMetric.BEST_SCORE, D1)
    assert [row.shooter_id for row in board.records(top=2)] == [1, 2]
    assert board.records(top=2)[1] == LeaderboardRow(
        rank=2, shooter_id=2, display_name="Bee, Bob", status=None, value=44.0, n_rounds=1
    )
    assert len(board.records()) == board.n_eligible == 3


SINCE_METRICS = [
    LeaderboardMetric.BEST_SCORE,
    LeaderboardMetric.WINS,
    LeaderboardMetric.PODIUMS,
    LeaderboardMetric.EVENTS,
    LeaderboardMetric.ROUNDS,
    LeaderboardMetric.SEASON_POINTS,
]


def _two_years(fb: FrameBuilder) -> tuple[date, date]:
    """Weekly Sundays from 2025-06-01 to 2026-03-01 for three shooters."""
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob").shooter(3, "Cy, Cal")
    first = date(2025, 6, 1)
    for week in range(40):
        day = first + timedelta(weeks=week)
        for sid in (1, 2, 3):
            fb.round(day, sid, 30 + (sid * 5 + week * 7) % 20)
    return first, first + timedelta(weeks=39)


@pytest.mark.parametrize("metric", SINCE_METRICS)
def test_since_jan_1_equals_ytd_and_first_sunday_equals_all_time(
    fb: FrameBuilder, metric: LeaderboardMetric
) -> None:
    first, as_of = _two_years(fb)
    frames = fb.frames()
    ytd = leaderboard(frames, LeaderboardPeriod.YTD, metric, as_of)
    custom = leaderboard(frames, SEASON, metric, as_of, since=date(as_of.year, 1, 1))
    pd.testing.assert_frame_equal(custom.rows, ytd.rows)
    everything = leaderboard(frames, ALL, metric, as_of)
    from_start = leaderboard(frames, SEASON, metric, as_of, since=first)
    pd.testing.assert_frame_equal(from_start.rows, everything.rows)


@pytest.mark.parametrize("metric", [LeaderboardMetric.ROUNDS, LeaderboardMetric.AVG_SCORE])
def test_since_boundary_is_inclusive(fb: FrameBuilder, metric: LeaderboardMetric) -> None:
    fb.shooter(1, "Ace, Amy")
    since = date(2026, 1, 11)
    fb.round(since - timedelta(weeks=1), 1, 10)  # the Sunday before: never counts
    fb.round(since, 1, 40)
    fb.round(since + timedelta(weeks=1), 1, 30)
    board = leaderboard(fb.frames(), SEASON, metric, since + timedelta(weeks=1), since=since)
    expected = {LeaderboardMetric.ROUNDS: 2.0, LeaderboardMetric.AVG_SCORE: 35.0}[metric]
    assert values(board) == {1: expected}
    assert board.rows["n_rounds"].tolist() == [2]


def test_avg_score_custom_threshold_excludes_short_attendance(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    since = date(2026, 1, 4)
    for week in range(10):
        day = since + timedelta(weeks=week)
        fb.round(day, 1, 40)
        if week < 3:
            fb.round(day, 2, 45)  # 3 rounds < 4
    as_of = since + timedelta(weeks=9)
    board = leaderboard(fb.frames(), SEASON, LeaderboardMetric.AVG_SCORE, as_of, since=since)
    assert board.min_rounds_applied == 4
    assert values(board) == {1: 40.0}


def test_leaderboard_echoes_since(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").round(D1, 1, 40)
    frames = fb.frames()
    assert leaderboard(frames, SEASON, LeaderboardMetric.ROUNDS, D1).since is None
    assert leaderboard(frames, SEASON, LeaderboardMetric.ROUNDS, D1, since=D1).since == D1
