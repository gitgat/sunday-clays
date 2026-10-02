"""Journey kinds (spec §2.2.3): charter shooters, anniversaries and lifetime targets."""

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights.journeys import anniversary  # importing registers the kinds
from sunday_clays.analytics.insights.types import Scope


def test_charter_shooter_is_active_and_shot_the_first_sunday(make_world, sun, run, headline):
    world = make_world().series(1, 0, [30] * 60).series(2, 0, [30] * 3).series(3, 1, [30] * 59)
    fr = world.frames()
    facts = run("pf.charter-shooter", fr)
    assert [f.subject_id for f in facts] == ["1"]
    assert headline("pf.charter-shooter", facts[0], fr).startswith(
        "Pat Shooter1 was here on the first Sunday on record, "
    )


def test_anniversary_on_the_first_sunday_on_or_after_the_date(make_world, sun, run, headline):
    world = make_world().series(9, 0, [30] * 60)  # the club's first Sunday is someone else's
    first = sun(3)
    days = [first + timedelta(weeks=j) for j in range(0, 57)]
    for day in days:
        world.round(1, day, 30)
    fr = world.frames()
    due = anniversary(first, 1)
    held = fr.held_dates()
    expected = next(d for d in held if d >= due)
    (fact,) = [f for f in run("pf.shooter-anniversary", fr) if f.subject_id == "1"]
    assert (fact.anchor_date, fact.params["years"]) == (expected, 1)
    assert fact.params["k"] == sum(d <= expected for d in days)
    assert headline("pf.shooter-anniversary", fact, fr).startswith(
        "1 year since Pat Shooter1's first Sunday: "
    )


def test_anniversary_skips_left_censored_shooters(make_world, sun, run):
    world = make_world().shooter(1, censored=True).series(1, 0, [30] * 60)
    assert run("pf.shooter-anniversary", world.frames()) == []


def test_anniversary_handles_feb_29():
    assert anniversary(date(2024, 2, 29), 1) == date(2025, 2, 28)


def test_targets_milestone_on_the_sunday_each_thousand_is_passed(make_world, sun, run, headline):
    world = make_world().series(1, 0, [40] * 26)  # 40 a Sunday: 1,000 on the 25th
    fr = world.frames()
    facts = run("pf.targets-milestone", fr)
    assert [(f.anchor_date, f.params["level"], f.params["total"]) for f in facts] == [
        (sun(24), 1000, 1000)
    ]
    assert facts[0].strength == pytest.approx(1.1)
    assert headline("pf.targets-milestone", facts[0], fr) == (
        "Pat Shooter1 has now broken 1,000 targets on Sundays: 1,000 in all."
    )


def test_charter_shooter_is_silent_without_any_sundays(make_world, sun):
    # Calls evaluate directly: the `run` fixture always sets as_of, so it cannot pass empty Sundays.
    scope = Scope(sundays=frozenset(), as_of=sun(0))
    assert list(registry.get("pf.charter-shooter").evaluate(make_world().frames(), scope)) == []


def test_anniversary_is_silent_when_the_shooter_misses_that_sunday(make_world, sun, run):
    world = make_world().series(9, 0, [30] * 60)
    first = sun(3)
    fr0 = make_world().series(9, 0, [30] * 60).frames()
    expected = next(d for d in fr0.held_dates() if d >= anniversary(first, 1))
    for j in range(0, 57):
        day = first + timedelta(weeks=j)
        if day != expected:
            world.round(1, day, 30)
    facts = [f for f in run("pf.shooter-anniversary", world.frames()) if f.subject_id == "1"]
    assert all(f.params["years"] != 1 for f in facts)


def test_anniversary_dates_from_a_special_shoot_debut(make_world, sun, run):
    world = make_world().series(9, 0, [30] * 70)
    world.special(1, sun(3))
    for j in range(4, 62):
        world.round(1, sun(j), 30)
    fr = world.frames()
    (fact,) = [f for f in run("pf.shooter-anniversary", fr) if f.subject_id == "1"]
    expected = next(d for d in fr.held_dates() if d >= anniversary(sun(3), 1))
    assert (fact.anchor_date, fact.params["first"]) == (expected, sun(3))
