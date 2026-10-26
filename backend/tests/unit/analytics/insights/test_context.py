"""InsightFrames views and helpers (spec §2.1, §4.4)."""

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.insights.context import (
    add_months,
    anchor_days,
    evergreen_days,
    is_active,
    own_tier,
    quantile,
    scored_only,
    shuffle_share,
    stable_seed,
    stderr_diff,
)
from sunday_clays.analytics.insights.lints import lint_clauses
from sunday_clays.analytics.insights.templates import (
    THROWN_OUT_RECAP_HOW,
    THROWN_OUT_ROUNDS_HOW,
    THROWN_OUT_STATION_HOW,
    plain,
    render,
)
from sunday_clays.analytics.insights.types import Scope


def test_days_carry_prefix_values_over_earlier_dates_only(make_world, sun):
    world = make_world().series(1, 0, [30, 40, 35]).round(1, sun(1), 20)  # 2 rounds, sun(1)
    world.crowd(sun(0), [20, 30]).crowd(sun(1), [25]).crowd(sun(2), [30, 40])
    days = world.frames().histories[1]
    assert [d.score for d in days] == [30, 40, 35]
    assert [d.n_rounds for d in days] == [1, 2, 1]
    assert [d.prior_rounds for d in days] == [0, 1, 3]
    assert [d.prior_best_s for d in days] == [None, 30, 40]
    assert [d.prior_sum_s for d in days] == [0, 30, 90]
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


def test_score_prefixes_skip_a_thrown_out_sunday_but_gates_count_it(make_world, sun):
    world = make_world().series(1, 0, [30, 48, 35, 36]).crowd(sun(1), [40, 40, 40])
    days = world.sunday(sun(1), stats_excluded=True).frames().histories[1]
    assert [d.stats_excluded for d in days] == [False, True, False, False]
    assert [d.prior_rounds for d in days] == [0, 1, 2, 3]
    assert [d.prior_n_s for d in days] == [0, 1, 1, 2]
    assert [d.prior_sum_s for d in days] == [0, 30, 30, 65]
    assert [d.prior_best_s for d in days] == [None, 30, 30, 35]
    assert [d.prior_mean_s for d in days] == [None, 30.0, 30.0, 32.5]
    assert [d.targets for d in days] == [30, 78, 113, 149]
    assert [d.k for d in days] == [1, 2, 3, 4]
    assert days[1].adjusted is None
    assert not any(hasattr(days[0], f) for f in ("prior_best", "prior_sum", "prior_mean"))


def test_sundays_carry_the_flag_and_scored_views_leave_them_out(make_world, sun):
    fr = make_world().series(1, 0, [30, 48, 35]).sunday(sun(1), stats_excluded=True).frames()
    assert [s.stats_excluded for s in fr.sundays] == [False, True, False]
    assert [s.date for s in fr.scored_sundays] == [sun(0), sun(2)]
    assert [d.date for d in fr.scored_histories[1]] == [sun(0), sun(2)]
    assert [d.date for d in scored_only(fr.histories[1])] == [sun(0), sun(2)]
    scope = Scope(sundays=frozenset(fr.held_dates()), as_of=sun(2))
    assert [ds[i].date for i, ds in anchor_days(fr, scope)] == [sun(0), sun(1), sun(2)]
    assert [ds[i].date for i, ds in anchor_days(fr, scope, scored=True)] == [sun(0), sun(2)]


def test_evergreen_scored_days_keep_the_activity_gate_on_every_round(make_world, sun):
    world = make_world().series(1, 0, [30, 31, 48, 33, 34])
    fr = world.sunday(sun(2), stats_excluded=True).frames()
    [(sid, days)] = list(evergreen_days(fr, Scope(sundays=frozenset(), as_of=sun(4)), scored=True))
    assert sid == 1
    assert [d.score for d in days] == [30, 31, 33, 34]
    assert days[-1].rounds_through == 5


def test_own_tier_reads_scored_rounds_only(make_world, sun):
    assert own_tier(make_world().series(1, 0, [38] * 9 + [45]).frames().histories[1]) == 45
    out = make_world().series(1, 0, [38] * 9 + [45]).sunday(sun(9), stats_excluded=True)
    assert own_tier(out.frames().histories[1]) is None


def test_world_marks_a_thrown_out_sunday(make_world, sun):
    fr = make_world().round(1, sun(0), 40).sunday(sun(0), stats_excluded=True).frames()
    assert fr.events["stats_excluded"].tolist() == [True]
    assert fr.rounds["stats_excluded"].tolist() == [True]


def test_thrown_out_how_lines_pass_the_insight_lints():
    for t in (THROWN_OUT_ROUNDS_HOW, THROWN_OUT_STATION_HOW, THROWN_OUT_RECAP_HOW):
        assert lint_clauses(t.third, force_named=True) == []
        assert t.you is not None
        assert lint_clauses(t.you, force_named=True) == []
    assert (
        plain(render(THROWN_OUT_ROUNDS_HOW, {}, {}))
        == "Sundays with a station thrown out (marked *) are left out."
    )
    assert (
        plain(render(THROWN_OUT_STATION_HOW, {}, {}))
        == "A station thrown out on the day is left out."
    )
    assert plain(render(THROWN_OUT_RECAP_HOW, {}, {})) == (
        "A station was thrown out this Sunday. Its results count; its scores stay out of "
        "averages and PBs."
    )
