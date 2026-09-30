"""Streak kinds (spec §2.2.2)."""

import pytest

from sunday_clays.analytics.insights import (
    charts,
    registry,
    streaks,  # noqa: F401 - registers the kinds
)
from sunday_clays.analytics.insights.context import own_tier
from sunday_clays.analytics.insights.streaks import rollup_chart
from sunday_clays.analytics.insights.types import PROFILE, ROLLUP, Fact, Page

FIELD = [30, 30]


def field_world(make_world, sun, scores, *, sid=1):
    world = make_world()
    for i, score in enumerate(scores):
        world.round(sid, sun(i), score).crowd(sun(i), FIELD)
    return world


def test_beat_field_streak_fires_when_the_run_reaches_six(make_world, sun, run, headline):
    fr = field_world(make_world, sun, [29, 31, 32, 33, 31, 32, 34, 29]).frames()
    anchored = [f for f in run("pf.beat-field-streak", fr) if f.variant == ""]
    assert [(f.anchor_date, f.params["k"]) for f in anchored] == [(sun(6), 6)]
    assert anchored[0].params["start"] == sun(1)
    assert anchored[0].strength == 6 / 5
    assert anchored[0].pages == frozenset({Page.SUNDAY, Page.HOME})
    text = headline("pf.beat-field-streak", anchored[0], fr)
    assert text == "Above the field's middle score 6 Sundays in a row for Pat Shooter1."


def test_a_missed_sunday_neither_extends_nor_breaks_the_run(make_world, sun, run):
    world = make_world()
    for i, score in enumerate([31, 32, 33, 34, 35, 36]):
        day = sun(i * 2)  # every other week; the club shoots in between without them
        world.round(1, day, score).crowd(day, FIELD).crowd(sun(i * 2 + 1), [30, 31, 32])
    facts = [f for f in run("pf.beat-field-streak", world.frames()) if f.variant == ""]
    assert [f.params["k"] for f in facts] == [6]


def test_beat_field_profile_row_while_the_run_is_five_or_more(make_world, sun, run):
    fr = field_world(make_world, sun, [29] + [31] * 5).frames()
    (profile,) = [f for f in run("pf.beat-field-streak", fr) if f.variant == PROFILE]
    assert profile.params["k"] == 5
    assert profile.strength == 1.0
    assert profile.anchor_date is None


def test_own_average_streak_needs_ten_earlier_rounds(make_world, sun, run, headline):
    scores = [30] * 10 + [31, 32, 33, 34, 35, 36]
    fr = field_world(make_world, sun, scores).frames()
    anchored = [f for f in run("pf.above-own-avg-streak", fr) if f.variant == ""]
    assert [(f.anchor_date, f.params["k"]) for f in anchored] == [(sun(15), 6)]
    assert anchored[0].strength == 6 / 4
    assert headline("pf.above-own-avg-streak", anchored[0], fr, you=True) == (
        "6 Sundays in a row above your own average."
    )
    short = field_world(make_world, sun, [30] * 9 + [31, 32, 33, 34, 35, 36]).frames()
    assert [f for f in run("pf.above-own-avg-streak", short) if f.variant == ""] == []


def test_own_average_is_the_mean_of_every_earlier_round(make_world, sun, run):
    # 38 is above the earlier average of 30 even though it is below an earlier 45
    scores = [30] * 10 + [45, 38, 38, 38]
    fr = field_world(make_world, sun, scores).frames()
    days = fr.histories[1]
    assert days[11].prior_mean == sum(scores[:11]) / 11
    (profile,) = [f for f in run("pf.above-own-avg-streak", fr) if f.variant == PROFILE]
    assert profile.params["k"] == 4


# --- pf.tier-run ----------------------------------------------------------------------------


def test_tier_run_fires_at_the_qualifying_length_for_the_own_tier(make_world, sun, run, headline):
    # 40 on 40% of the last 52 rounds makes 40 the own tier (45 is never reached)
    scores = [36, 41, 37, 42, 38] * 6 + [40] * 6
    fr = field_world(make_world, sun, scores).frames()
    days = fr.histories[1]
    assert own_tier(days) == 40
    anchored = [f for f in run("pf.tier-run", fr) if f.variant == ""]
    assert [(f.anchor_date, f.params["k"], f.params["tier"]) for f in anchored] == [
        (sun(len(scores) - 1), 6, 40)
    ]
    assert anchored[0].params["start"] == sun(len(scores) - 6)
    assert headline("pf.tier-run", anchored[0], fr) == (
        "6 Sundays in a row at 40 or better for Pat Shooter1."
    )
    (profile,) = [f for f in run("pf.tier-run", fr) if f.variant == PROFILE]
    assert profile.params["k"] == 6
    assert profile.strength == 1.0


def test_tier_run_is_silent_without_an_own_tier(make_world, sun, run):
    fr = field_world(make_world, sun, [30] * 20).frames()
    assert run("pf.tier-run", fr) == []


# --- pf.three-rising ------------------------------------------------------------------------


def test_three_rising_needs_a_rise_of_four_and_the_best_in_twenty(make_world, sun, run, headline):
    scores = [36] * 20 + [34, 36, 38]
    fr = field_world(make_world, sun, scores).frames()
    (fact,) = run("pf.three-rising", fr)
    assert (fact.params["a"], fact.params["b"], fact.params["c"]) == (34, 36, 38)
    assert fact.params["d1"] == sun(20)
    assert fact.strength == (38 - 34) / 4
    assert headline("pf.three-rising", fact, fr) == (
        "Scores up 3 Sundays straight for Pat Shooter1: 34, 36, then 38."
    )


@pytest.mark.parametrize(
    "scores",
    [[36] * 20 + [35, 36, 38], [36] * 17 + [39, 36, 36] + [34, 36, 38], [36] * 17 + [34, 36, 38]],
    ids=["rise under 4", "not the best in 20", "under 20 earlier Sundays"],
)
def test_three_rising_is_silent_outside_its_guard(make_world, sun, run, scores):
    fr = field_world(make_world, sun, scores).frames()
    assert run("pf.three-rising", fr) == []


# --- pf.podium-run --------------------------------------------------------------------------


def podium_world(make_world, sun, places, *, field=15):
    """places[i]: shooter 1's rank on Sunday i (1-based) in a field of `field` shooters."""
    world = make_world()
    for i, place in enumerate(places):
        above, below = [45] * (place - 1), [30] * (field - place)
        world.round(1, sun(i), 40).crowd(sun(i), above + below)
    return world.frames()


def test_podium_run_fires_at_three_and_five(make_world, sun, run, headline):
    fr = podium_world(make_world, sun, [5, 2, 3, 1, 2, 3, 8])
    facts = run("pf.podium-run", fr)
    assert [(f.anchor_date, f.params["k"]) for f in facts] == [(sun(3), 3), (sun(5), 5)]
    ranks = [d.rank for d in fr.histories[1]]
    assert all(r <= 3 for r in ranks[1:6])
    assert headline("pf.podium-run", facts[0], fr) == "3rd podium in a row for Pat Shooter1."


def test_a_small_field_ends_a_podium_run(make_world, sun, run):
    def run_of(small):
        world = make_world()
        for i in range(3):
            field = 10 if i == 1 and small else 15
            world.round(1, sun(i), 45).crowd(sun(i), [30] * (field - 1))
        return run("pf.podium-run", world.frames())

    assert [f.params["k"] for f in run_of(small=False)] == [3]  # control: full fields fire
    assert run_of(small=True) == []


# --- review fix round: chart labels, rollup chart, copy -------------------------------------


def test_the_rising_chart_carries_the_shared_best_round_label(make_world, sun, run):
    fr = field_world(make_world, sun, [36] * 20 + [34, 36, 38]).frames()
    (fact,) = run("pf.three-rising", fr)
    assert registry.get("pf.three-rising").chart(fact).label is charts.BEST_EACH_LABEL


def test_the_tier_run_rollup_chart_is_the_results_chart(sun):
    fact = Fact(
        subject_id="club",
        anchor_date=sun(0),
        variant=ROLLUP,
        pages=frozenset({Page.SUNDAY}),
        params={"names": [1, 2], "day": sun(0)},
        strength=1.0,
    )
    a, b = registry.get("pf.tier-run").chart(fact), rollup_chart(fact)
    assert vars(a) == vars(b)


def test_the_tier_run_explainer_says_missed_sundays_do_not_end_the_run():
    t = registry.get("pf.tier-run").how[""][0]
    assert t.you is not None
    for clauses in (t.third, t.you):
        text = "".join(p for c in clauses for p in c.parts if isinstance(p, str))
        assert "missed do not end the run." in text
