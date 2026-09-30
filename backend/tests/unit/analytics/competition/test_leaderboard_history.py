from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from sunday_clays.analytics.leaderboard_history import history_dates, leaderboard_history
from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    leaderboard,
)

if TYPE_CHECKING:
    from conftest import FrameBuilder

SEASON = LeaderboardPeriod.SEASON
YTD = LeaderboardPeriod.YTD
POINTS = LeaderboardMetric.SEASON_POINTS


def _three_shooters(fb: FrameBuilder) -> FrameBuilder:
    return fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob").shooter(3, "Cy, Cal", status="guest")


def test_history_frames_match_leaderboard_as_of(fb: FrameBuilder) -> None:
    _three_shooters(fb)
    days = [date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18)]
    fb.day(days[0], {1: 45, 2: 40, 3: 30}).day(days[1], {2: 44, 3: 43}).day(days[2], {3: 49, 1: 20})
    frames = fb.frames()
    history = leaderboard_history(frames, SEASON, POINTS, top=2, date_from=days[0], date_to=days[2])
    assert [f.event_date for f in history] == days
    assert [[(r.shooter_id, r.value, r.rank) for r in f.rows] for f in history] == [
        [(1, 11.0, 1), (2, 9.0, 2)],
        [(2, 20.0, 1), (3, 16.0, 2)],
        [(3, 27.0, 1), (1, 20.0, 2)],
    ]
    filters = LeaderboardFilters(status="member")
    filtered = leaderboard_history(
        frames, SEASON, POINTS, top=2, date_from=days[0], date_to=days[2], filters=filters
    )
    for frame in filtered:
        expected = leaderboard(frames, SEASON, POINTS, frame.event_date, filters).records(2)
        assert list(frame.rows) == expected


def test_history_ytd_points_reset_jan1(fb: FrameBuilder) -> None:
    _three_shooters(fb)
    fb.day(date(2025, 12, 21), {1: 45, 2: 40}).day(date(2025, 12, 28), {1: 45, 2: 40})
    fb.day(date(2026, 1, 4), {2: 44, 1: 43})
    history = leaderboard_history(
        fb.frames(), YTD, POINTS, top=5, date_from=date(2025, 12, 28), date_to=date(2026, 1, 4)
    )
    assert [(f.event_date, [(r.shooter_id, r.value) for r in f.rows]) for f in history] == [
        (date(2025, 12, 28), [(1, 22.0), (2, 18.0)]),
        (date(2026, 1, 4), [(2, 11.0), (1, 9.0)]),
    ]


def test_history_season_points_roll_across_jan1_and_drop_old_sundays(fb: FrameBuilder) -> None:
    _three_shooters(fb)
    fb.day(date(2025, 12, 21), {1: 45, 2: 40}).day(date(2025, 12, 28), {1: 45, 2: 40})
    fb.day(date(2026, 1, 4), {2: 44, 1: 43})
    for week in range(1, 9):  # eight later Sundays push 2025-12-21 .. 2026-01-04 out of the window
        fb.day(date(2026, 1, 4) + timedelta(weeks=week), {3: 40})
    history = leaderboard_history(
        fb.frames(), SEASON, POINTS, top=5, date_from=date(2026, 1, 4), date_to=date(2026, 3, 1)
    )
    by_day = {f.event_date: {r.shooter_id: r.value for r in f.rows} for f in history}
    assert by_day[date(2026, 1, 4)] == {1: 31.0, 2: 29.0}  # Dec 21 + Dec 28 + Jan 4: no reset
    assert set(by_day[date(2026, 3, 1)]) == {3}  # the first three Sundays have aged out


def test_history_has_one_frame_per_scored_event_in_range(fb: FrameBuilder) -> None:
    _three_shooters(fb)
    fb.day(date(2026, 1, 4), {1: 40})
    fb.event(date(2026, 1, 11), has_scores=False)  # attendance only: no frame
    fb.day(date(2026, 1, 18), {1: 41}).day(date(2026, 1, 25), {1: 42})
    assert history_dates(fb.events(), date(2026, 1, 5), date(2026, 1, 25)) == [
        date(2026, 1, 18),
        date(2026, 1, 25),
    ]


def test_history_no_leak(make_builder: type[FrameBuilder]) -> None:
    def build(extra_weeks: int) -> FrameBuilder:
        fb = _three_shooters(make_builder())
        for week in range(6 + extra_weeks):
            fb.day(date(2026, 1, 4) + timedelta(weeks=week), {1: 40 + week % 3, 2: 41, 3: 39})
        return fb

    kwargs = {"top": 3, "date_from": date(2026, 1, 1), "date_to": date(2026, 2, 8)}
    past = leaderboard_history(build(0).frames(), SEASON, POINTS, **kwargs)
    full = leaderboard_history(build(4).frames(), SEASON, POINTS, **kwargs)
    assert past == full
    assert len(past) == 6


def test_history_since_jan_1_equals_the_ytd_frames(fb: FrameBuilder) -> None:
    _three_shooters(fb)
    days = [date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18)]
    fb.day(date(2025, 12, 28), {1: 45, 2: 40}).day(days[0], {1: 45, 2: 40, 3: 30})
    fb.day(days[1], {2: 44, 3: 43}).day(days[2], {3: 49, 1: 20})
    frames = fb.frames()
    kw = {"top": 3, "date_from": days[0], "date_to": days[2]}
    season = leaderboard_history(frames, YTD, POINTS, **kw)
    custom = leaderboard_history(frames, YTD, POINTS, since=date(2026, 1, 1), **kw)
    assert custom == season


def test_history_since_mid_year_frames_match_the_custom_boards(fb: FrameBuilder) -> None:
    _three_shooters(fb)
    days = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(5)]
    for i, day in enumerate(days):
        fb.day(day, {1: 40 + i, 2: 45 - i, 3: 30 + 2 * i})
    since = days[2]
    frames = fb.frames()
    history = leaderboard_history(
        frames, SEASON, POINTS, top=2, date_from=since, date_to=days[4], since=since
    )
    assert [f.event_date for f in history] == days[2:]
    for frame in history:
        expected = leaderboard(frames, SEASON, POINTS, frame.event_date, since=since).records(2)
        assert list(frame.rows) == expected
    assert [r.value for r in history[0].rows] == [
        r.value for r in leaderboard(frames, SEASON, POINTS, since, since=since).records(2)
    ]
