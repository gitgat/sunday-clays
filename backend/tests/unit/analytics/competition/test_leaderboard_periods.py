from __future__ import annotations

import math
from datetime import date, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from sunday_clays.analytics.leaderboards import (
    LeaderboardMetric,
    LeaderboardPeriod,
    custom_min_rounds,
    make_leaderboard_frames,
    min_rounds_for,
    period_bounds,
    scaled_min_rounds,
    scored_event_dates,
)

if TYPE_CHECKING:
    from conftest import FrameBuilder


def test_rolling12_has_52_sundays() -> None:
    as_of = date(2026, 9, 27)
    start, end = period_bounds(LeaderboardPeriod.ROLLING_12, as_of)
    assert (start, end) == (date(2025, 9, 29), as_of)
    days = [date(2025, 9, 29) + timedelta(days=i) for i in range(364)]
    assert sum(1 for d in days if d.weekday() == 6) == 52


def test_ytd_starts_jan_1_and_all_time_has_no_start() -> None:
    assert period_bounds(LeaderboardPeriod.YTD, date(2026, 3, 1)) == (
        date(2026, 1, 1),
        date(2026, 3, 1),
    )
    assert period_bounds(LeaderboardPeriod.ALL_TIME, date(2026, 3, 1)) == (None, date(2026, 3, 1))


@pytest.mark.parametrize(
    ("n_events", "expected"),
    [(0, 1), (1, 1), (2, 1), (3, 2), (5, 2), (6, 3), (8, 4), (10, 4), (11, 5), (13, 5), (40, 5)],
)
def test_ytd_threshold_formula(fb: FrameBuilder, n_events: int, expected: int) -> None:
    for week in range(n_events):
        fb.event(date(2026, 1, 4) + timedelta(weeks=week))
    assert scaled_min_rounds(fb.events(), LeaderboardPeriod.YTD, date(2026, 12, 31)) == expected


def test_ytd_threshold_scales_early_year_unit(fb: FrameBuilder) -> None:
    fb.event(date(2023, 12, 31))  # previous season: ignored
    fb.event(date(2024, 1, 7))
    fb.event(date(2024, 1, 14), has_scores=False)  # attendance only: ignored
    fb.event(date(2024, 1, 28))
    fb.event(date(2024, 2, 4))  # after as_of: ignored
    fb.event(date(2024, 2, 11))
    assert scaled_min_rounds(fb.events(), LeaderboardPeriod.YTD, date(2024, 1, 28)) == 1
    assert scaled_min_rounds(fb.events(), LeaderboardPeriod.YTD, date(2024, 2, 11)) == 2


def test_season_is_the_rolling_last_8_sundays() -> None:
    as_of = date(2026, 9, 27)  # a Sunday
    start, end = period_bounds(LeaderboardPeriod.SEASON, as_of)
    assert (start, end) == (date(2026, 8, 3), as_of)  # (as_of - 56 days, as_of]
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    assert next(d for d in days if d.weekday() == 6) == date(2026, 8, 9)
    assert sum(1 for d in days if d.weekday() == 6) == 8


def test_season_never_resets_on_jan_1() -> None:
    assert period_bounds(LeaderboardPeriod.SEASON, date(2026, 1, 4)) == (
        date(2025, 11, 10),
        date(2026, 1, 4),
    )


def test_season_threshold_counts_only_the_last_8_sundays(fb: FrameBuilder) -> None:
    for week in range(20):
        fb.event(date(2026, 1, 4) + timedelta(weeks=week))
    as_of = date(2026, 1, 4) + timedelta(weeks=19)
    # 8 Sundays in the window: ceil(0.4 * 8) = 4 (a calendar-year count would cap at 5)
    assert scaled_min_rounds(fb.events(), LeaderboardPeriod.SEASON, as_of) == 4
    assert scaled_min_rounds(fb.events(), LeaderboardPeriod.YTD, as_of) == 5


@pytest.mark.parametrize(
    ("metric", "period", "expected"),
    [
        (LeaderboardMetric.AVG_SCORE, LeaderboardPeriod.ROLLING_12, 8),
        (LeaderboardMetric.AVG_SCORE, LeaderboardPeriod.ALL_TIME, 15),
        (LeaderboardMetric.AVG_ADJUSTED, LeaderboardPeriod.ROLLING_12, 8),
        (LeaderboardMetric.AVG_ADJUSTED, LeaderboardPeriod.ALL_TIME, 15),
        (LeaderboardMetric.BEST_SCORE, LeaderboardPeriod.ALL_TIME, 1),
        (LeaderboardMetric.WINS, LeaderboardPeriod.SEASON, 1),
        (LeaderboardMetric.RATING_GAIN, LeaderboardPeriod.SEASON, 3),
        (LeaderboardMetric.RATING_GAIN, LeaderboardPeriod.YTD, 5),
        (LeaderboardMetric.WINS, LeaderboardPeriod.YTD, 1),
        (LeaderboardMetric.RATING_GAIN, LeaderboardPeriod.ROLLING_12, 5),
        (LeaderboardMetric.RATING_GAIN, LeaderboardPeriod.ALL_TIME, 15),
    ],
)
def test_min_rounds_per_metric_and_period(
    fb: FrameBuilder, metric: LeaderboardMetric, period: LeaderboardPeriod, expected: int
) -> None:
    assert min_rounds_for(metric, period, fb.events(), date(2026, 6, 7)) == expected


@pytest.mark.parametrize("period", [LeaderboardPeriod.SEASON, LeaderboardPeriod.YTD])
def test_season_and_ytd_average_threshold_use_the_scaled_formula(
    fb: FrameBuilder, period: LeaderboardPeriod
) -> None:
    for week in range(3):
        fb.event(date(2026, 1, 4) + timedelta(weeks=week))
    assert min_rounds_for(LeaderboardMetric.AVG_SCORE, period, fb.events(), date(2026, 1, 18)) == 2


def test_scored_event_dates_lists_has_scores_events_ascending(fb: FrameBuilder) -> None:
    fb.event(date(2026, 1, 18)).event(date(2026, 1, 4)).event(date(2026, 1, 11), has_scores=False)
    assert scored_event_dates(fb.events()) == [date(2026, 1, 4), date(2026, 1, 18)]


def test_make_frames_normalizes_loader_dtypes(fb: FrameBuilder) -> None:
    day = date(2026, 1, 4)
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob").day(day, {1: 45, 2: 40})
    fb.round(day, 2, 30, ordinal=2)
    rounds = fb.rounds().convert_dtypes()  # nullable Int64/boolean/<NA>, as a DB loader may return
    rounds["event_date"] = pd.to_datetime(rounds["event_date"])  # datetime64, not date objects
    frames = make_leaderboard_frames(rounds, fb.events(), fb.history())
    assert frames.rounds["event_date"].tolist() == [day, day, day]
    assert frames.rounds["is_best_round"].tolist() == [True, True, False]
    assert frames.rounds["event_rank"].tolist()[:2] == [1.0, 2.0]
    assert math.isnan(frames.rounds["event_rank"].iloc[2])
    assert frames.rounds["adjusted"].tolist() == [5.0, 0.0, -10.0]


@pytest.mark.parametrize("period", list(LeaderboardPeriod))
def test_since_replaces_the_period_start(period: LeaderboardPeriod) -> None:
    as_of = date(2026, 9, 27)
    assert period_bounds(period, as_of, since=date(2026, 3, 1)) == (date(2026, 3, 1), as_of)


def _sundays_in_range(fb: FrameBuilder, n: int, since: date) -> date:
    """``n`` scored Sundays from ``since``, plus an unscored one and one after ``as_of``."""
    for week in range(n):
        fb.event(since + timedelta(weeks=week))
    as_of = since + timedelta(weeks=n)
    fb.event(as_of, has_scores=False)  # attendance only: not counted
    fb.event(as_of + timedelta(weeks=1))  # after as_of: not counted
    return as_of


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, 1),
        (1, 1),
        (3, 2),
        (10, 4),
        (12, 5),
        (33, 5),
        (34, 6),
        (52, 8),
        (99, 15),
        (100, 15),
        (300, 15),
    ],
)
def test_custom_min_rounds_formula(fb: FrameBuilder, n: int, expected: int) -> None:
    since = date(2020, 1, 5)
    as_of = _sundays_in_range(fb, n, since)
    fb.event(since - timedelta(weeks=1))  # before since: not counted
    assert custom_min_rounds(fb.events(), since, as_of) == expected


def test_custom_min_rounds_never_decreases(fb: FrameBuilder) -> None:
    since = date(2020, 1, 5)
    for week in range(300):
        fb.event(since + timedelta(weeks=week))
    events = fb.events()
    values = [
        custom_min_rounds(events, since, since + timedelta(weeks=max(week - 1, 0))) if week else 1
        for week in range(301)
    ]
    assert all(a <= b for a, b in pairwise(values))
    assert values[-1] == 15


@pytest.mark.parametrize(
    ("metric", "expected"),
    [
        (LeaderboardMetric.RATING_GAIN, 5),
        (LeaderboardMetric.WINS, 1),
        (LeaderboardMetric.BEST_SCORE, 1),
        (LeaderboardMetric.SEASON_POINTS, 1),
    ],
)
@pytest.mark.parametrize("period", list(LeaderboardPeriod))
def test_min_rounds_with_since_ignores_the_period(
    fb: FrameBuilder, metric: LeaderboardMetric, period: LeaderboardPeriod, expected: int
) -> None:
    fb.event(date(2026, 3, 1))
    got = min_rounds_for(metric, period, fb.events(), date(2026, 6, 7), since=date(2026, 3, 1))
    assert got == expected


@pytest.mark.parametrize("metric", [LeaderboardMetric.AVG_SCORE, LeaderboardMetric.AVG_ADJUSTED])
@pytest.mark.parametrize("period", list(LeaderboardPeriod))
def test_average_min_rounds_with_since_is_the_custom_rule(
    fb: FrameBuilder, metric: LeaderboardMetric, period: LeaderboardPeriod
) -> None:
    since = date(2026, 1, 4)
    as_of = _sundays_in_range(fb, 10, since)
    assert min_rounds_for(metric, period, fb.events(), as_of, since=since) == 4
