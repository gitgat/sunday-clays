"""Record kinds (spec §2.2.6): the wait for a 49 and the Sunday it ends."""

import pytest

from sunday_clays.analytics.insights import records  # noqa: F401 - registers the kinds


def tops_world(make_world, sun, tops):
    world = make_world()
    for i, top in enumerate(tops):
        world.round(1 + i % 3, sun(i), top).crowd(sun(i), [30, 31])
    return world.frames()


def test_drought_clock_counts_held_sundays_since_the_last_49(make_world, sun, run, headline):
    tops = [49] + [45] * 16
    fr = tops_world(make_world, sun, tops)
    facts = run("rec.drought-clock", fr)
    assert [(f.anchor_date, f.params["wait"]) for f in facts] == [(sun(16), 16)]
    assert facts[0].params["last"] == sun(0)
    assert facts[0].named_shooter_ids == ()
    assert headline("rec.drought-clock", facts[0], fr) == (
        "16 Sundays since the last round of 49 or better."
    )


def test_drought_clock_is_silent_under_sixteen_and_before_any_49(make_world, sun, run):
    assert run("rec.drought-clock", tops_world(make_world, sun, [49] + [45] * 15)) == []
    assert run("rec.drought-clock", tops_world(make_world, sun, [45] * 30)) == []


@pytest.mark.parametrize(("wait", "fires"), [(16, True), (15, False)])
def test_drought_ended_names_the_shooter(make_world, sun, run, headline, wait, fires):
    fr = tops_world(make_world, sun, [49] + [45] * (wait - 1) + [49])
    facts = run("ev.drought-ended", fr, [sun(wait)])
    if not fires:
        assert facts == []
        return
    (fact,) = facts
    assert (fact.variant, fact.params["wait"], fact.params["score"]) == ("one", wait, 49)
    assert headline("ev.drought-ended", fact, fr).endswith(
        f"'s 49 ends a {wait}-Sunday wait for a round that high."
    )


def test_perfect_rarity_counts_every_round(make_world, sun, run, headline):
    world = make_world().round(1, sun(0), 50).round(2, sun(0), 49).round(3, sun(1), 50)
    world.crowd(sun(1), [30, 31, 32])
    fr = world.frames()
    (fact,) = run("rec.perfect-rarity", fr)
    assert (fact.params["perfect"], fact.params["rounds"], fact.params["high"]) == (2, 6, 3)
    assert headline("rec.perfect-rarity", fact, fr) == (
        "2 perfect 50s in 6 rounds; 3 rounds of 49 or better."
    )


def test_streak_chase_attendance_and_wins(make_world, sun, run, headline):
    world = make_world()
    for i in range(16):
        world.round(1, sun(i), 45).round(2, sun(i), 30)
    fr = world.frames()
    facts = {f.variant: f for f in run("rec.streak-chase", fr)}
    assert facts["attendance"].params["n"] == 2
    assert facts["attendance"].params["record"] == 16
    assert (facts["wins"].params["s"], facts["wins"].params["run"]) == (1, 16)
    assert headline("rec.streak-chase", facts["attendance"], fr).startswith(
        "2 shooters are on runs of 15 or more Sundays in a row"
    )


def test_drought_ended_with_two_49s_names_them_all(make_world, sun, run, headline):
    world = make_world()
    for i in range(16):
        world.round(1, sun(i), 49 if i == 0 else 45).crowd(sun(i), [30, 31])
    world.round(1, sun(16), 49).round(2, sun(16), 49).crowd(sun(16), [30, 31])
    fr = world.frames()
    (fact,) = run("ev.drought-ended", fr, [sun(16)])
    assert (fact.variant, fact.params["wait"]) == ("many", 16)
    assert fact.named_shooter_ids == (1, 2)
    assert headline("ev.drought-ended", fact, fr) == (
        "Pat Shooter1 and Pat Shooter2 ended a 16-Sunday wait for a round of 49 or better."
    )


def test_drought_ended_skips_deceased_shooters(make_world, sun, run):
    world = make_world().shooter(1, status="deceased")
    for i in range(16):
        world.round(2, sun(i), 49 if i == 0 else 45).crowd(sun(i), [30, 31])
    world.round(1, sun(16), 49).crowd(sun(16), [30, 31])
    assert run("ev.drought-ended", world.frames(), [sun(16)]) == []


def test_streak_chase_names_the_longest_current_win_run(make_world, sun, run):
    world = make_world().round(1, sun(0), 30).round(2, sun(0), 45)
    for i in range(1, 5):
        world.round(1, sun(i), 45).round(2, sun(i), 45)
    facts = {f.variant: f for f in run("rec.streak-chase", world.frames())}
    assert (facts["wins"].params["s"], facts["wins"].params["run"]) == (2, 5)
