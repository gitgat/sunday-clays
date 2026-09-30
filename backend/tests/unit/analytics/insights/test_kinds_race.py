"""Finish kinds on a Sunday (spec §2.2.5)."""

from sunday_clays.analytics.insights import race  # noqa: F401 - registers the kinds


def test_a_tie_at_the_top_names_both_winners(make_world, sun, run, headline):
    world = make_world().round(1, sun(0), 47).round(2, sun(0), 47).crowd(sun(0), range(30, 43))
    fr = world.frames()
    (fact,) = run("ev.close-finish", fr)
    assert fact.variant == "tie2"
    assert fact.params["names"] == [1, 2]
    assert fact.strength == 1.5
    assert headline("ev.close-finish", fact, fr) == (
        "Tie at the top: Pat Shooter1 and Pat Shooter2 both shot 47."
    )


def test_top_three_within_one_needs_a_45(make_world, sun, run):
    world = make_world().round(1, sun(0), 46).round(2, sun(0), 45).round(3, sun(0), 45)
    world.crowd(sun(0), range(30, 42))
    (fact,) = run("ev.close-finish", world.frames())
    assert fact.variant == "close"
    assert fact.params["top"] == 46
    low = make_world().round(1, sun(0), 44).round(2, sun(0), 43).round(3, sun(0), 43)
    low.crowd(sun(0), range(20, 32))
    assert run("ev.close-finish", low.frames()) == []


def test_a_field_under_fifteen_is_silent(make_world, sun, run):
    world = make_world().round(1, sun(0), 47).round(2, sun(0), 47).crowd(sun(0), range(30, 42))
    assert world.frames().sundays[0].n == 14
    assert run("ev.close-finish", world.frames()) == []


def test_a_deceased_shooter_at_the_top_silences_the_sunday(make_world, sun, run):
    world = make_world().shooter(9, status="deceased")
    world.round(9, sun(0), 49).round(1, sun(0), 46).round(2, sun(0), 45).round(3, sun(0), 45)
    world.crowd(sun(0), range(30, 41))
    fr = world.frames()
    assert fr.sundays[0].n >= 15
    assert run("ev.close-finish", fr) == []


def test_a_deceased_tied_winner_silences_the_tie(make_world, sun, run):
    world = make_world().shooter(2, status="deceased")
    world.round(1, sun(0), 47).round(2, sun(0), 47).crowd(sun(0), range(30, 43))
    assert run("ev.close-finish", world.frames()) == []


def test_third_place_shared_beyond_three_names_is_silent(make_world, sun, run):
    world = make_world().round(1, sun(0), 46).round(2, sun(0), 45).round(3, sun(0), 45)
    world.round(4, sun(0), 45).crowd(sun(0), range(20, 31))
    assert run("ev.close-finish", world.frames()) == []


def test_a_tie_too_big_to_name_is_silent(make_world, sun, run):
    world = make_world()
    for sid in range(1, 7):
        world.round(sid, sun(0), 47)
    world.crowd(sun(0), range(20, 29))
    assert run("ev.close-finish", world.frames()) == []
