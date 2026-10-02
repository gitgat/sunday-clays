"""Recap kinds (spec §2.2.3, §2.2.5): the profile digest line and the home Sunday recap."""

from sunday_clays.analytics.insights import recap, registry
from sunday_clays.analytics.insights.recap import played_word
from sunday_clays.analytics.insights.templates import fmt_sunday, plain, render


def _digest_world(make_world, sun):
    """Four shooters on one Sunday, ranked 1 to 4, with chosen residuals (gap to their usual)."""
    world = make_world()
    for sid, score, residual in [(1, 50, 0.6), (2, 40, 0.4), (3, 30, 2.0), (4, 20, 0.4)]:
        world.series(sid, 0, [score] * 4)  # 4 earlier rounds: 5 in all makes them active (C7)
        world.round(sid, sun(4), score, residual=residual)
    return world.frames()


def test_digest_variants_follow_rank_and_residual(make_world, sun, run):
    fr = _digest_world(make_world, sun)
    variants = {f.subject_id: f.variant for f in run("pf.digest-line", fr)}
    # 1: rank 1 (top half), residual 0.6 rounds to 1 -> full
    # 2: rank 2 = field_n / 2 exactly (top half), residual 0.4 rounds to 0 -> finish only
    # 3: rank 3 (bottom half), residual 2 -> usual only
    # 4: rank 4 (bottom half), residual 0.4 -> plain
    assert variants == {"1": "full", "2": "finish", "3": "usual", "4": "plain"}


def test_digest_params_carry_only_what_the_variant_shows(make_world, sun, run):
    facts = {f.subject_id: f for f in run("pf.digest-line", _digest_world(make_world, sun))}
    shown = {sid: {k: f.params.get(k) for k in ("rank", "n", "over")} for sid, f in facts.items()}
    assert shown == {
        "1": {"rank": 1, "n": 4, "over": 1},
        "2": {"rank": 2, "n": 4, "over": None},
        "3": {"rank": None, "n": None, "over": 2},
        "4": {"rank": None, "n": None, "over": None},
    }
    assert all(f.anchor_date is None for f in facts.values())


def test_digest_skips_shooters_who_missed_the_latest_sunday(make_world, sun, run):
    world = make_world()
    world.series(1, 0, [40] * 6)
    world.series(2, 0, [30] * 5)  # shooter 2 is not on the latest Sunday
    facts = run("pf.digest-line", world.frames())
    assert [f.subject_id for f in facts] == ["1"]


def test_digest_headline_in_third_and_second_person(make_world, sun, run, headline):
    fr = _digest_world(make_world, sun)
    fact = next(f for f in run("pf.digest-line", fr) if f.subject_id == "1")
    day = fmt_sunday(sun(4))
    assert headline("pf.digest-line", fact, fr) == (
        f"{day}: Pat Shooter1 shot 50, 1st of 4, 1 over their usual for a day like this."
    )
    assert headline("pf.digest-line", fact, fr, you=True) == (
        f"{day}: you shot 50, 1st of 4, 1 over your usual for a day like this."
    )


def test_sunday_recap_joins_every_slot_that_passes(make_world, sun, run, headline):
    world = make_world()
    world.series(1, 0, [30, 31, 32, 33, 34, 40])  # a PB on the last Sunday
    for i in range(6):
        world.crowd(sun(i), [35, 36])
    world.sunday(sun(5), temp_f=50.0, gust_mph=15.0, difficulty=-1.5)
    world.round(50, sun(5), 20)  # a first-timer
    fr = world.frames()
    (fact,) = run("home.sunday-recap", fr, [sun(5)])
    assert fact.variant == "wpbf"
    assert headline("home.sunday-recap", fact, fr) == (
        f"Sunday {sun(5).month}/{sun(5).day}: 4 shooters on a cool, breezy morning. "
        "Scores ran a little easier. Pat Shooter1 topped the board with a 40. "
        "1 shooter set a personal best and 3 first-timers joined us."
    )


def test_every_recap_variant_renders(make_world, sun):
    world = make_world()
    world.series(1, 0, [30, 31, 32, 33, 34, 40])
    world.series(2, 0, [30, 31, 32, 33, 34, 40])
    fr = world.frames()
    params = {
        "day": sun(5),
        "n": 2,
        "top": 40,
        "s": 1,
        "names": [1, 2],
        "temp": "40-55",
        "wind": "10-20",
        "played": "same",
        "pbs": 2,
        "firsts": 1,
    }
    variants = recap._all_flags()
    assert len(variants) == 32
    templates = registry.get("home.sunday-recap").templates
    for flags in variants:
        text = plain(render(templates[flags][0], params, fr.names))
        assert text
        assert ("shared the top" in text) == ("t" in flags)
        assert ("personal best" in text) == ("b" in flags)
        assert ("joined us" in text) == ("f" in flags)
        assert ("cool, breezy" in text) == ("w" in flags)
        assert ("as usual" in text) == ("p" in flags)


def test_played_word_bands():
    assert played_word(0.5) == "same"
    assert played_word(2.0) == "bit_tough"
    assert played_word(-3.0) == "easy"


def test_sunday_recap_needs_three_slots_and_names_a_tie(make_world, sun, run, headline):
    world = make_world()
    for sid in (1, 2):
        world.series(sid, 0, [30] * 5)  # level scores: no PB, and neither is a first-timer
    assert run("home.sunday-recap", world.frames(), [sun(4)]) == []  # crowd and top score only
    world.sunday(sun(4), temp_f=50.0, gust_mph=15.0)  # weather makes the third slot
    fr = world.frames()
    (fact,) = run("home.sunday-recap", fr, [sun(4)])
    assert fact.variant == "wt"
    assert "shared the top of the board with 30" in headline("home.sunday-recap", fact, fr)


def test_sunday_recap_does_not_count_a_special_debut_as_a_first_timer(make_world, sun, run):
    world = make_world()
    world.series(1, 0, [30, 31, 32, 33, 34, 35])
    world.special(60, sun(4))
    world.round(60, sun(5), 20)  # second Sunday, first regular round
    world.round(50, sun(5), 20)  # a true first-timer
    for i in range(5):
        world.crowd(sun(i), [35, 36])
    fr = world.frames()
    (fact,) = run("home.sunday-recap", fr, [sun(5)])
    assert fact.params["firsts"] == 1
