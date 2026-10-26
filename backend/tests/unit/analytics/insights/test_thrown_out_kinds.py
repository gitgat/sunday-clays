"""Shooter score kinds leave thrown-out Sundays out (T5b)."""

from __future__ import annotations

import pytest

from sunday_clays.analytics.insights import (  # noqa: F401 - registers the kinds
    attendance,
    conditions,
    form,
    journeys,
    milestones,
    peaks,
    recap,
    registry,
    season,
    streaks,
    tiers,
)
from sunday_clays.analytics.insights.milestones import is_pb
from sunday_clays.analytics.insights.templates import THROWN_OUT_ROUNDS_HOW

ROUNDS_HOW: dict[str, tuple[str, ...]] = {
    "pf.pb": ("", "profile", "rollup"),
    "pf.tied-best": ("", "rollup"),
    "pf.first-tier": ("",),
    "pf.first-since": ("score",),
    "pf.back-strong": ("score",),
    "pf.best-stretch": ("", "rollup"),
    "pf.average-milestone": ("", "rollup"),
    "pf.season-best": ("",),
    "pf.best-day-vs-field": ("",),
    "pf.rating-high": ("",),
    "pf.learning-curve": ("",),
    "pf.hot-form": ("",),
    "pf.beat-own-usual": ("", "rollup"),
    "pf.up-on-usual": ("",),
    "pf.year-up": ("",),
    "pf.years-up-run": ("",),
    "pf.gaining-on-field": ("two_years", "career"),
    "pf.wet-strength": ("",),
    "pf.weather-steady": ("",),
    "pf.best-temp": ("",),
    "pf.tough-days": ("",),
    "pf.beat-field-streak": ("", "rollup"),
    "pf.above-own-avg-streak": ("", "rollup"),
    "pf.tier-run": ("", "rollup"),
    "pf.three-rising": ("", "rollup"),
    "pf.high-round-count": ("", "rollup"),
    "pf.more-high-rounds": ("", "rollup"),
    "pf.low-end-rising": ("",),
    "pf.year-wrapped": ("",),
    "lb.most-improved": ("",),
    "pf.rank-climb": ("",),
    "pf.top-of-club": ("",),
}
STATION_HOW: dict[str, tuple[str, ...]] = {}


@pytest.mark.parametrize(("kind_id", "variants"), sorted(ROUNDS_HOW.items()))
def test_score_kinds_say_thrown_out_sundays_are_left_out(kind_id, variants):
    for v in variants:
        assert registry.get(kind_id).how[v][-1] is THROWN_OUT_ROUNDS_HOW


def test_count_variants_do_not_claim_the_rounds_line():
    assert THROWN_OUT_ROUNDS_HOW not in registry.get("pf.first-since").how[""]
    assert THROWN_OUT_ROUNDS_HOW not in registry.get("pf.back-strong").how[""]
    assert (
        registry.get("pf.first-since").how["score"][:-1] == registry.get("pf.first-since").how[""]
    )


def test_pb_skips_a_thrown_out_sunday_and_beats_only_scored_rounds(make_world, sun, run):
    fr = (
        make_world()
        .series(1, 0, [30, 31, 32, 33, 34, 50, 40])
        .sunday(sun(5), stats_excluded=True)
        .frames()
    )
    facts = [f for f in run("pf.pb", fr) if f.variant == ""]
    assert [
        (f.anchor_date, f.params["new"], f.params["old"], f.params["old_date"]) for f in facts
    ] == [(sun(6), 40, 34, sun(4))]
    assert is_pb(fr.histories[1][5]) is False


def test_first_tier_compares_with_the_best_scored_round(make_world, sun, run):
    fr = (
        make_world()
        .series(1, 0, [30] * 10 + [45, 41])
        .sunday(sun(10), stats_excluded=True)
        .frames()
    )
    assert [(f.anchor_date, f.params["level"]) for f in run("pf.first-tier", fr)] == [(sun(11), 40)]


def test_three_rising_skips_the_thrown_out_sunday_without_breaking(make_world, sun, run):
    fr = (
        make_world()
        .series(1, 0, [30] * 20 + [31, 20, 33, 36])
        .sunday(sun(21), stats_excluded=True)
        .frames()
    )
    facts = [f for f in run("pf.three-rising", fr) if f.variant == ""]
    assert [
        (f.anchor_date, f.params["a"], f.params["b"], f.params["c"], f.params["d2"]) for f in facts
    ] == [(sun(23), 31, 33, 36, sun(22))]


def test_year_wrapped_counts_every_sunday_but_best_is_scored_only(make_world, sun, run):
    scores = [30] * 49
    scores[20] = 49
    (fact,) = run(
        "pf.year-wrapped",
        make_world().series(1, 0, scores).sunday(sun(20), stats_excluded=True).frames(),
    )
    assert (fact.params["sundays"], fact.params["targets"], fact.params["best"]) == (49, 1489, 30)
