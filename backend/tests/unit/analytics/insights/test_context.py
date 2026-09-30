"""InsightFrames views and helpers (spec §2.1, §4.4)."""

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.insights.context import (
    add_months,
    evergreen_days,
    is_active,
    own_tier,
    quantile,
    shuffle_share,
    stable_seed,
    stderr_diff,
)
from sunday_clays.analytics.insights.types import Scope


def test_days_carry_prefix_values_over_earlier_dates_only(make_world, sun):
    world = make_world().series(1, 0, [30, 40, 35]).round(1, sun(1), 20)  # 2 rounds, sun(1)
    world.crowd(sun(0), [20, 30]).crowd(sun(1), [25]).crowd(sun(2), [30, 40])
    days = world.frames().histories[1]
    assert [d.score for d in days] == [30, 40, 35]
    assert [d.n_rounds for d in days] == [1, 2, 1]
    assert [d.prior_rounds for d in days] == [0, 1, 3]
    assert [d.prior_best for d in days] == [None, 30, 40]
    assert [d.prior_sum for d in days] == [0, 30, 90]
    assert [d.targets for d in days] == [30, 90, 125]
    assert [d.k for d in days] == [1, 2, 3]
    assert days[2].prev_date == sun(1)


def test_adjusted_is_score_minus_the_median_of_every_round_that_day(make_world, sun):
    world = make_world().round(1, sun(0), 40).crowd(sun(0), [20, 30, 50])
    day = world.frames().histories[1][0]
    assert day.adjusted == 40 - 35  # median of 40, 20, 30, 50
    assert day.rank == 2
    assert day.field_n == 4


def test_sundays_list_held_dates_with_ranked_results(make_world, sun):
    world = make_world().round(1, sun(0), 40).round(2, sun(0), 44).sunday(sun(1), held=False)
    world.round(1, sun(1), 30)
    fr = world.frames()
    assert fr.held_dates() == [sun(0)]
    assert [(r.shooter_id, r.rank) for r in fr.sundays[0].results] == [(2, 1), (1, 2)]
    assert fr.as_of == sun(0)
    assert fr.histories[1][1].held is False


def test_until_forgets_everything_after_the_cut(make_world, sun):
    world = make_world().series(1, 0, [30, 31, 32, 50]).rating(1, sun(3), 44.0)
    fr = world.frames()
    cut = fr.until(sun(2))
    assert cut.as_of == sun(2)
    assert [d.score for d in cut.histories[1]] == [30, 31, 32]
    assert cut.rating_at(1, sun(3)) is None
    assert fr.rating_at(1, sun(3)) == 44.0


def test_active_needs_five_rounds_and_one_in_the_last_364_days(make_world, sun):
    days = make_world().series(1, 0, [30] * 5).frames().histories[1]
    assert is_active(days, sun(4))
    assert not is_active(days[:4], sun(3))
    assert not is_active(days, sun(4) + timedelta(days=364))
    assert is_active(days, sun(4) + timedelta(days=363))


def test_evergreen_subjects_skip_new_guests_and_deceased(make_world, sun):
    world = make_world().shooter(2, status="guest").shooter(3, status="deceased")
    world.series(1, 0, [30] * 5).series(2, 0, [30] * 5).series(3, 0, [30] * 5)
    world.series(4, 0, [30] * 6).shooter(4, status="guest")
    fr = world.frames()
    scope = Scope(sundays=frozenset(), as_of=sun(5))
    assert [sid for sid, _ in evergreen_days(fr, scope)] == [1, 4]


@pytest.mark.parametrize(
    ("scores", "tier"),
    [
        ([46] * 3 + [38] * 17, 45),
        ([41] * 5 + [36] * 15, 40),
        ([36] * 4 + [30] * 16, 35),
        ([30] * 20, None),
        ([46] * 20, None),
    ],
)
def test_own_tier_is_reached_on_10_to_60_percent_of_rounds(make_world, scores, tier):
    days = make_world().series(1, 0, scores).frames().histories[1]
    assert own_tier(days) == tier


def test_statistics_helpers():
    assert quantile([1, 2, 3, 4], 0.25) == 1.75  # numpy's linear rule
    assert stderr_diff([1, 3], [2, 4]) == pytest.approx(((2 / 2) + (2 / 2)) ** 0.5)
    assert stable_seed("pf.wet-strength", 7) == stable_seed("pf.wet-strength", 7)
    assert stable_seed("a", 1) != stable_seed("a", 2)


def test_shuffle_share_is_reproducible_and_high_for_a_real_gap():
    wet, dry = [5.0, 6.0, 7.0, 6.5], [0.0, 1.0, -1.0, 0.5, 0.2, -0.3]
    first = shuffle_share(wet, dry, seed=1)
    assert first == shuffle_share(wet, dry, seed=1)
    assert first > 0.95
    assert shuffle_share([0.0, 1.0], [0.0, 1.0], seed=1) < 0.9


@pytest.mark.parametrize(
    ("day", "months", "out"),
    [
        (date(2026, 9, 27), -3, date(2026, 6, 27)),
        (date(2026, 5, 31), -3, date(2026, 2, 28)),
        (date(2025, 12, 7), 1, date(2026, 1, 7)),
    ],
)
def test_add_months_clamps_the_day(day, months, out):
    assert add_months(day, months) == out
