"""Dormant kinds (spec §2.2.9, §2.2.10): stations and trophies."""

from dataclasses import replace

from sunday_clays.analytics.insights import stations, trophies  # noqa: F401 - registers
from sunday_clays.analytics.insights.engine import evaluate_all
from sunday_clays.analytics.insights.proof import proof_problems
from sunday_clays.analytics.insights.registry import get


def station_world(make_world, sun, *, sundays=8, mine=8, others=6):
    world = make_world()
    for i in range(sundays):
        day = sun(i)
        world.round(1, day, 40, round_id=None)
        for station in (1, 2):
            hits = mine if station == 1 else 6
            world.station(1, day, station, hits, round_id=i * 10 + 1, entry_row=1)
            for sid in range(2, 6):
                world.station(sid, day, station, others, round_id=i * 10 + sid, entry_row=sid)
            world.round(99, day, 30)
    return world.frames()


def test_station_kinds_are_dormant_under_eight_station_sundays(make_world, sun):
    fr = station_world(make_world, sun, sundays=7)
    kinds = [get("st.hardest-easiest"), get("pf.station-best")]
    assert evaluate_all(fr, kinds=kinds) == []
    assert get("pf.station-best").requires.station_sundays == 8


def test_trophy_kinds_wait_for_the_first_award():
    assert get("pf.trophy-rare").requires.trophy_awards == 1
    assert get("pf.next-trophy").requires.trophy_awards == 1


def test_trophy_rare_one_fact_per_shooter_and_sunday(make_world, sun, run, headline):
    world = make_world().series(1, 0, [30] * 30).series(2, 0, [30] * 30)
    world.award(1, "sunday_milestone:1", sun(27))
    world.award(1, "round_score:1", sun(27))
    world.award(2, "round_score:1", sun(28))
    fr = world.frames()
    facts = run("pf.trophy-rare", fr)
    assert [(f.subject_id, f.anchor_date, f.params["holders"]) for f in facts] == [
        ("1", sun(27), 1),
        ("2", sun(28), 2),
    ]
    assert facts[0].variant == "first"


def test_trophy_rare_skips_the_first_26_sundays(make_world, sun, run):
    world = make_world().series(1, 0, [30] * 30).award(1, "round_score:1", sun(3))
    assert run("pf.trophy-rare", world.frames()) == []


def test_hardest_station_and_personal_best(make_world, sun, run, headline):
    fr = station_world(make_world, sun)
    (hardest,) = run("st.hardest-easiest", fr)
    assert hardest.subject_id == "2"
    assert hardest.params["station"] == "2"
    assert hardest.params["pct"] == 75
    best = {f.subject_id: f for f in run("pf.station-best", fr)}
    assert best["1"].params["station"] == "1"
    assert (best["1"].params["mine"], best["1"].params["field"]) == (100, 80)
    assert get("pf.station-best").chart(best["1"]).compare is not None
    assert get("st.hardest-easiest").chart(hardest).highlight.keys == ("2",)


def test_station_kinds_need_two_stations_with_enough_entries(make_world, sun, run):
    fr = station_world(make_world, sun)
    thin = fr.stations[fr.stations["station_no"] == 1]
    assert run("st.hardest-easiest", replace(fr, stations=thin)) == []


def test_station_kinds_emit_nothing_under_eight_station_sundays(make_world, sun, run):
    fr = station_world(make_world, sun, sundays=7)
    assert run("st.hardest-easiest", fr) == []
    assert run("pf.station-best", fr) == []


def test_trophy_rare_same_sunday_ties_share_the_first(make_world, sun, run):
    world = make_world().series(1, 0, [30] * 30).series(2, 0, [30] * 30)
    world.award(2, "round_score:1", sun(27)).award(1, "round_score:1", sun(27))
    facts = run("pf.trophy-rare", world.frames())
    assert [(f.subject_id, f.variant, f.params["holders"]) for f in facts] == [
        ("1", "", 2),
        ("2", "", 2),
    ]


def test_next_trophy_names_an_effort_tier_and_skips_scoring(make_world, sun, run, headline):
    fr = make_world().series(1, 0, [44] * 8).frames()
    (fact,) = run("pf.next-trophy", fr)
    assert (fact.subject_id, fact.params["code"], fact.params["left"]) == ("1", "events:2", 2)
    assert headline("pf.next-trophy", fact, fr) == (
        "Pat Shooter1 is 2 short of Events Attended (10 events)."
    )


def test_next_trophy_accepts_a_tier_within_ten_percent(make_world, sun, run):
    fr = make_world().series(1, 0, [44] * 9).frames()
    (fact,) = run("pf.next-trophy", fr)
    assert (fact.params["code"], fact.params["left"]) == ("clays_thrown:1", 50)


def lettered_world(make_world, sun):
    """Stations 7, 7A and 8 over 8 Sundays: 7A is the hardest stand and shooter 1 shines on 7."""
    world = make_world()
    for i in range(8):
        day = sun(i)
        for station, mine, others in (("7", 8, 6), ("7A", 4, 4), ("8", 7, 7)):
            world.station(1, day, station, mine, round_id=i * 10 + 1, entry_row=1)
            for sid in range(2, 6):
                world.station(sid, day, station, others, round_id=i * 10 + sid, entry_row=sid)
        world.round(1, day, 40)
        world.round(99, day, 30)
    return world.frames()


def test_a_lettered_station_can_be_the_toughest_and_a_personal_best(make_world, sun, run, headline):
    fr = lettered_world(make_world, sun)
    (hardest,) = run("st.hardest-easiest", fr)
    assert (hardest.subject_id, hardest.params["station"]) == ("7A", "7A")
    assert headline("st.hardest-easiest", hardest, fr).startswith(
        "Station 7A is the toughest stand"
    )
    assert get("st.hardest-easiest").chart(hardest).highlight.keys == ("7A",)
    assert proof_problems(get("st.hardest-easiest"), hardest, fr, None) == []
    best = {f.subject_id: f for f in run("pf.station-best", fr)}
    assert best["1"].params["station"] == "7"
    assert get("pf.station-best").chart(best["1"]).highlight.keys == ("7",)


def test_station_best_can_be_a_lettered_station(make_world, sun, run, headline):
    world = make_world()
    for i in range(8):
        day = sun(i)
        for station, mine, others in (("7", 6, 6), ("7A", 7, 5), ("8", 6, 6)):
            world.station(1, day, station, mine, round_id=i * 10 + 1, entry_row=1)
            for sid in range(2, 6):
                world.station(sid, day, station, others, round_id=i * 10 + sid, entry_row=sid)
        world.round(1, day, 40)
        world.round(99, day, 30)
    fr = world.frames()
    best = {f.subject_id: f for f in run("pf.station-best", fr)}
    assert best["1"].params["station"] == "7A"
    assert headline("pf.station-best", best["1"], fr).startswith(
        "Station 7A is Pat Shooter1's station"
    )
    assert get("pf.station-best").chart(best["1"]).highlight.keys == ("7A",)


def test_next_trophy_counts_a_special_sunday_toward_events(make_world, sun, run):
    world = make_world()
    for i in [*range(7), 8]:
        world.round(1, sun(i), 44)
    fr = world.frames()
    (fact,) = run("pf.next-trophy", fr)
    assert (fact.params["code"], fact.params["left"]) == ("events:2", 2)

    (fact,) = run("pf.next-trophy", world.special(1, sun(7)).frames())
    assert (fact.params["code"], fact.params["left"]) == ("events:2", 1)
