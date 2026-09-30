"""Own-tier kinds (spec §2.2.1): round counts at the own mark and the low end."""

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.insights import tiers
from sunday_clays.analytics.insights.context import own_tier, quantile
from sunday_clays.analytics.insights.types import PROFILE, ROLLUP, Fact, Highlight, Page, Window

CYCLE = [36, 41, 37, 42, 38]  # 40 on 40% of Sundays: own tier 40


def test_high_round_count_counts_every_round_at_the_mark(make_world, sun, run, headline):
    world = make_world().series(1, 0, CYCLE * 4)  # 8 rounds of 40+
    world.round(1, sun(20), 41).round(1, sun(20), 43)  # two more in one day: 10
    fr = world.frames()
    assert own_tier(fr.histories[1]) == 40
    (fact,) = run("pf.high-round-count", fr)
    assert (fact.anchor_date, fact.params["count"], fact.params["tier"]) == (sun(20), 10, 40)
    assert fact.strength == 1.0
    assert fact.pages == frozenset({Page.PROFILE, Page.SUNDAY})
    assert fact.params["first"] == sun(0)
    assert headline("pf.high-round-count", fact, fr) == (
        "That was Pat Shooter1's 10th round of 40 or better."
    )


def year_rounds(world, year, scores):
    first = next(d for d in (date(year, 1, k) for k in range(1, 8)) if d.weekday() == 6)
    for j, score in enumerate(scores):
        world.round(1, first + timedelta(weeks=j), score)
    return world


def test_more_high_rounds_on_the_crossing_sunday_and_on_the_profile(make_world, run, headline):
    world = year_rounds(make_world(), 2024, CYCLE * 4)  # 8 at 40+
    world = year_rounds(world, 2025, CYCLE * 5)  # 10 at 40+, passing 8 on the 9th
    fr = world.frames()
    facts = run("pf.more-high-rounds", fr)
    anchored = [f for f in facts if f.variant == ""]
    ninth = [d.date for d in fr.histories[1] if d.date.year == 2025 and d.score >= 40][8]
    assert [(f.anchor_date, f.params["this"], f.params["last"]) for f in anchored] == [
        (ninth, 9, 8)
    ]
    assert anchored[0].pages == frozenset({Page.SUNDAY, Page.HOME})
    (profile,) = [f for f in facts if f.variant == PROFILE]
    assert (profile.params["this"], profile.params["last"]) == (10, 8)
    assert headline("pf.more-high-rounds", profile, fr).endswith(": 10 vs 8.")


def test_more_high_rounds_needs_eight_last_year(make_world, run):
    world = year_rounds(make_world(), 2024, CYCLE * 3)  # 6 at 40+
    world = year_rounds(world, 2025, CYCLE * 5)
    assert run("pf.more-high-rounds", world.frames()) == []


def test_low_end_rising_compares_the_quarter_mark_year_on_year(make_world, run, headline):
    last = [30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41]
    this = [s + 4 for s in last]
    world = year_rounds(year_rounds(make_world(), 2024, last), 2025, this)
    (fact,) = run("pf.low-end-rising", world.frames())
    assert fact.params["low"] == round(quantile([float(s) for s in this], 0.25), 1)
    assert fact.params["low_last"] == round(quantile([float(s) for s in last], 0.25), 1)
    assert headline("pf.low-end-rising", fact, world.frames()).startswith(
        "Off days are getting better for Pat Shooter1"
    )


@pytest.mark.parametrize(("shift", "n"), [(1, 12), (4, 11)], ids=["under 2", "under 12 Sundays"])
def test_low_end_rising_is_silent_outside_its_guard(make_world, run, shift, n):
    last = list(range(30, 30 + n))
    world = year_rounds(year_rounds(make_world(), 2024, last), 2025, [s + shift for s in last])
    assert run("pf.low-end-rising", world.frames()) == []


@pytest.mark.parametrize("chart", [tiers._high_count_chart, tiers._more_chart])
def test_rollup_variant_links_to_the_sunday_results(chart, sun):
    day = sun(3)
    fact = Fact(
        subject_id="sunday",
        anchor_date=day,
        variant=ROLLUP,
        pages=frozenset({Page.SUNDAY, Page.HOME}),
        params={"day": day, "names": (1, 2)},
        strength=1.0,
        named_shooter_ids=(1, 2),
    )
    link = chart(fact)
    assert link.type == "page"
    assert (link.route, link.anchor) == (f"/events/{day.isoformat()}", "results")
    assert link.window == Window(day, day)
    assert link.highlight == Highlight(shooter_ids=(1, 2))
    assert link.label is tiers.RESULTS_LABEL
