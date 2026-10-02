"""Sunday-subject kinds (spec §2.2.5)."""

import dataclasses
from datetime import date, timedelta

import pytest

from sunday_clays.analytics.insights import sunday as sunday_kinds  # noqa: F401 - registers
from sunday_clays.analytics.insights.sunday import TOP_MIN_SUNDAYS
from sunday_clays.analytics.insights.types import Page


def test_spotlight_names_up_to_three_biggest_gaps(make_world, sun, run, headline):
    world = make_world()
    for sid in (1, 2, 3, 4):
        world.series(sid, 0, [30] * 20)
    day = sun(20)
    for sid, residual in ((1, 9.0), (2, 7.0), (3, 12.0), (4, 6.9)):
        world.round(sid, day, 40, residual=residual)
    fr = world.frames()
    (fact,) = run("ev.spotlight", fr, [day])
    assert fact.params["names"] == [3, 1, 2]
    assert fact.params["over"] == 12
    assert fact.strength == pytest.approx(12 / 7)
    text = headline("ev.spotlight", fact, fr)
    assert text.startswith("Well above their usual for a day like this: Pat Shooter3,")


def test_spotlight_needs_twenty_earlier_rounds(make_world, sun, run):
    world = make_world().series(1, 0, [30] * 19).round(1, sun(19), 45, residual=10.0)
    assert run("ev.spotlight", world.frames()) == []


def rain_sunday_world(make_world, sun, *, difficulty):
    world = make_world()
    for i in range(12):  # 4 wet then 8 dry earlier Sundays
        day = sun(i)
        world.sunday(day, precip_in=0.3 if i < 4 else 0.0, head_count=25)
        world.round(1, day, 35 if i < 4 else 31).round(2, day, 31).crowd(day, [30, 30, 30])
    today = sun(12)
    world.sunday(today, precip_in=0.5, head_count=19, difficulty=difficulty)
    world.round(1, today, 36).round(2, today, 30).crowd(today, [30, 30])
    return world.frames(), today


def test_rain_day_field_line_and_better_in_the_rain(make_world, sun, run, headline):
    fr, today = rain_sunday_world(make_world, sun, difficulty=0.4)
    (fact,) = run("ev.rain-day", fr, [today])
    assert fact.variant == "better"
    assert fact.params["better"] == [1]
    assert (fact.params["played"], fact.params["crowd"], fact.params["heads"]) == (
        "same",
        "fewer",
        19,
    )
    assert headline("ev.rain-day", fact, fr) == (
        "Rain Sunday. The field shot about the same as on a typical Sunday, and fewer shooters "
        "turned out than on a dry Sunday (19 shooters). Better in the rain: Pat Shooter1."
    )
    assert fact.pages == frozenset({Page.SUNDAY, Page.HOME})


def test_rain_day_shows_on_every_wet_sunday_even_without_names(make_world, sun, run):
    world = make_world().sunday(sun(0), precip_in=0.4).round(1, sun(0), 30)
    (fact,) = run("ev.rain-day", world.frames())
    assert fact.variant == "field"
    assert fact.named_shooter_ids == ()
    assert run("ev.rain-day", make_world().round(1, sun(0), 30).frames()) == []


@pytest.mark.parametrize(("difficulty", "variant"), [(2.5, "tough"), (-3.4, "easy")])
def test_how_it_played_at_two_and_a_half_targets(make_world, sun, run, difficulty, variant):
    world = make_world().sunday(sun(0), difficulty=difficulty).crowd(sun(0), [30, 32, 40])
    (fact,) = run("ev.how-it-played", world.frames())
    assert fact.variant == variant
    assert fact.params == {"day": sun(0), "by": round(abs(difficulty)), "median": 32.0}
    assert fact.strength == pytest.approx(abs(difficulty) / 2.5)
    calm = make_world().sunday(sun(0), difficulty=2.4).crowd(sun(0), [30])
    assert run("ev.how-it-played", calm.frames()) == []


def test_rain_day_ignores_earlier_sundays_without_weather(make_world, sun, run):
    world = make_world().sunday(sun(0)).round(1, sun(0), 30).crowd(sun(0), [30])
    world.sunday(sun(1), precip_in=0.4).round(1, sun(1), 30)
    (fact,) = run("ev.rain-day", world.frames(), [sun(1)])
    assert fact.variant == "field"


def test_rain_day_drops_comparisons_it_has_no_data_for(make_world, sun, run, headline):
    world = make_world().sunday(sun(0), precip_in=0.4, head_count=1).round(1, sun(0), 30)
    fr = world.frames()
    (fact,) = run("ev.rain-day", fr)
    assert (fact.params["played"], fact.params["crowd"]) == ("unknown", "unknown")
    assert headline("ev.rain-day", fact, fr) == "Rain Sunday (1 shooter)."
    world = make_world().sunday(sun(0), precip_in=0.4, head_count=4, difficulty=2.0)
    fr = world.round(1, sun(0), 30).frames()
    (fact,) = run("ev.rain-day", fr)
    assert headline("ev.rain-day", fact, fr) == (
        "Rain Sunday. Scores ran tougher than a typical Sunday (4 shooters)."
    )


def test_how_it_played_needs_a_middle_score(make_world, sun, run):
    world = make_world().sunday(sun(0), difficulty=3.0).crowd(sun(0), [30, 32, 40])
    fr = world.frames()
    assert len(run("ev.how-it-played", fr)) == 1
    unknown = dataclasses.replace(fr.sundays[0], median=None)
    assert run("ev.how-it-played", dataclasses.replace(fr, sundays=(unknown,))) == []


# --- ev.toughest-since ----------------------------------------------------------------------


def difficulty_world(make_world, sun, difficulties):
    world = make_world()
    for i, d in enumerate(difficulties):
        world.sunday(sun(i), difficulty=d).crowd(sun(i), [30, 31, 32])
    return world.frames()


def test_toughest_since_names_the_last_tougher_sunday(make_world, sun, run, headline):
    fr = difficulty_world(make_world, sun, [3.0] + [0.5] * 30 + [2.5])
    (fact,) = run("ev.toughest-since", fr, [sun(31)])
    assert (fact.variant, fact.params["prev"]) == ("tough", sun(0))
    assert fact.strength == pytest.approx(((sun(31) - sun(0)).days // 7) / 26)
    assert headline("ev.toughest-since", fact, fr).startswith("Toughest Sunday since ")


@pytest.mark.parametrize(
    "difficulties",
    [[3.0] + [0.5] * 30 + [1.9], [3.0] + [0.5] * 20 + [2.5], [0.5] * 31 + [2.5]],
    ids=["under 2", "tougher one within 26 weeks", "no tougher one on record"],
)
def test_toughest_since_is_silent_outside_its_guard(make_world, sun, run, difficulties):
    fr = difficulty_world(make_world, sun, difficulties)
    assert run("ev.toughest-since", fr, [sun(len(difficulties) - 1)]) == []


# --- ev.week-jump ---------------------------------------------------------------------------


def jump_world(make_world, sun, *, last=30, now=42, expected=38.0, gap_weeks=1, spotlit=False):
    world = make_world()
    for i in range(20):
        world.round(1, sun(i), 34, expected=34.0).crowd(sun(i), [30, 31, 32])
    world.round(1, sun(20), last, expected=34.0).crowd(sun(20), [30, 31, 32])
    day = sun(20 + gap_weeks)
    residual = 8.0 if spotlit else 1.0
    world.round(1, day, now, expected=expected, residual=residual).crowd(day, [30, 31, 32])
    return world.frames(), day


def test_week_jump_names_the_biggest_jump_without_the_earlier_score(make_world, sun, run, headline):
    fr, day = jump_world(make_world, sun)
    (fact,) = run("ev.week-jump", fr, [day])
    assert (fact.variant, fact.params["score"], fact.params["prev"]) == ("one", 42, sun(20))
    assert fact.strength == pytest.approx((42 - 30) / 10)
    text = headline("ev.week-jump", fact, fr)
    assert text == "Biggest jump from the Sunday before: Pat Shooter1, with a 42."
    assert "30" not in text


@pytest.mark.parametrize(
    "kwargs",
    [{"now": 39}, {"expected": 43.0}, {"gap_weeks": 7}, {"spotlit": True}],
    ids=["jump under 10", "under their usual", "over 6 weeks", "already in the spotlight"],
)
def test_week_jump_is_silent_outside_its_guard(make_world, sun, run, kwargs):
    fr, day = jump_world(make_world, sun, **kwargs)
    assert run("ev.week-jump", fr, [day]) == []


# --- ev.record-watch and ev.top-score -------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "variant", "gap"), [(49, "near", 1), (50, "tie", 0), (48, "near", 2)], ids=str
)
def test_record_watch_against_the_earlier_record(
    make_world, sun, run, headline, score, variant, gap
):
    world = make_world().round(2, sun(0), 50).crowd(sun(0), [30])
    world.round(1, sun(1), score).crowd(sun(1), [30])
    fr = world.frames()
    (fact,) = run("ev.record-watch", fr, [sun(1)])
    assert (fact.variant, fact.params["record"], fact.params["gap"]) == (variant, 50, gap)
    if variant == "near":
        assert headline("ev.record-watch", fact, fr).endswith("off the club record of 50.")


def test_record_watch_new_record_and_under_48_is_silent(make_world, sun, run):
    world = make_world().round(2, sun(0), 48).crowd(sun(0), [30])
    world.round(1, sun(1), 49).crowd(sun(1), [30]).round(1, sun(2), 47).crowd(sun(2), [30])
    facts = run("ev.record-watch", world.frames(), [sun(1), sun(2)])
    assert [(f.anchor_date, f.variant) for f in facts] == [(sun(1), "new")]


def test_record_watch_skips_a_sunday_without_results(make_world, sun, run):
    world = make_world().round(2, sun(0), 50).crowd(sun(0), [30])
    world.round(1, sun(1), 50).crowd(sun(1), [30]).round(1, sun(2), 50).crowd(sun(2), [30])
    fr = world.frames()
    empty = dataclasses.replace(fr.sundays[1], results=())
    fr = dataclasses.replace(fr, sundays=(fr.sundays[0], empty, fr.sundays[2]))
    facts = run("ev.record-watch", fr, [sun(1), sun(2)])
    assert [(f.anchor_date, f.variant) for f in facts] == [(sun(2), "tie")]


def test_top_score_is_in_the_top_tenth_of_three_years(make_world, sun, run):
    world = make_world()
    tops = [40 + (i % 5) for i in range(40)] + [45, 41]
    for i, top in enumerate(tops):
        world.round(1, sun(i), top).crowd(sun(i), [30])
    fr = world.frames()
    (fact,) = run("ev.top-score", fr, [sun(40)])
    assert fact.params["top"] == 45
    assert run("ev.top-score", fr, [sun(41)]) == []  # most earlier tops beat a 41


# --- ev.new-faces ---------------------------------------------------------------------------


def firsts_world(make_world, sun, *, newcomer_score):
    world = make_world().round(200, sun(0), 30)  # the club's first Sunday: nobody is new yet
    for i in range(20):  # 20 earlier first rounds: 30, 31, ... 49
        world.round(100 + i, sun(8 + i), 30 + i)
    day = sun(28)
    world.round(1, day, newcomer_score).round(2, day, 30).crowd(day, [35, 36, 37])
    return world.frames(), day


def test_new_faces_welcome_and_strong_start(make_world, sun, run, headline):
    fr, day = firsts_world(make_world, sun, newcomer_score=45)
    (fact,) = run("ev.new-faces", fr, [day])
    earlier = list(range(30, 50))
    pct = 100 * sum(e < 45 for e in earlier) // len(earlier)
    assert (fact.variant, fact.params["n"], fact.params["s"], fact.params["pct"]) == (
        "strong",
        2 + 3,
        1,
        pct,
    )
    assert headline("ev.new-faces", fact, fr).startswith("Welcome to 5 first-timers. Pat Shooter1")


def test_new_faces_welcome_only_below_seventy_percent(make_world, sun, run, headline):
    fr, day = firsts_world(make_world, sun, newcomer_score=40)
    (fact,) = run("ev.new-faces", fr, [day])
    assert fact.variant == "welcome"
    assert fact.named_shooter_ids == ()
    assert headline("ev.new-faces", fact, fr) == "Welcome to 5 first-timers."


# --- ev.second-visit ------------------------------------------------------------------------


def test_second_visit_within_ten_weeks_shows_no_scores(make_world, sun, run, headline):
    world = make_world().round(9, sun(0), 30).round(1, sun(8), 20).round(1, sun(11), 22)
    world.round(2, sun(8), 20).round(2, sun(20), 22)  # 12 weeks later: not counted
    world.crowd(sun(11), [30]).crowd(sun(20), [30])
    fr = world.frames()
    (fact,) = run("ev.second-visit", fr, [sun(11), sun(20)])
    assert (fact.anchor_date, fact.params["names"]) == (sun(11), [1])
    text = headline("ev.second-visit", fact, fr)
    assert text == "Second visit for Pat Shooter1. Welcome back."
    assert "22" not in text


def test_new_faces_is_silent_in_the_first_eight_weeks_of_records(make_world, sun, run):
    world = make_world().round(1, sun(0), 30).round(2, sun(0), 31).round(3, sun(7), 32)
    assert run("ev.new-faces", world.frames()) == []
    world.round(4, sun(8), 33)
    assert [f.anchor_date for f in run("ev.new-faces", world.frames())] == [sun(8)]


def test_second_visit_is_silent_when_the_first_visit_is_in_the_first_eight_weeks(
    make_world, sun, run
):
    world = make_world().round(1, sun(0), 20).round(1, sun(3), 22)
    world.round(2, sun(7), 20).round(2, sun(9), 22).round(9, sun(8), 30)
    world.crowd(sun(3), [30]).crowd(sun(9), [30])
    assert run("ev.second-visit", world.frames()) == []


def test_top_score_survives_a_29_february_sunday(make_world, sun, run):
    world = make_world()
    leap = date(2032, 2, 29)
    world.round(1, leap, 45).crowd(leap, [30])
    for i in range(1, TOP_MIN_SUNDAYS + 2):
        earlier = leap - timedelta(weeks=i)
        world.round(1, earlier, 40).crowd(earlier, [30])
    (fact,) = run("ev.top-score", world.frames(), [leap])
    assert fact.params["start"] == date(2029, 2, 28)


def test_week_jump_two_variant_names_both(make_world, sun, run, headline):
    fr, day = jump_world(make_world, sun)
    (fact,) = run("ev.week-jump", fr, [day])
    two = dataclasses.replace(fact, variant="two", params={**fact.params, "names": [1, 2]})
    assert headline("ev.week-jump", two, fr).startswith("Big jumps from the Sunday before:")


def test_second_visit_many_variant_counts_without_names(make_world, sun, run, headline):
    fr, day = jump_world(make_world, sun)
    (fact,) = run("ev.week-jump", fr, [day])
    many = dataclasses.replace(
        fact, variant="many", params={"day": day, "names": [1, 2, 3, 4, 5, 6], "n": 6}
    )
    text = headline("ev.second-visit", many, fr)
    assert text == "6 shooters came back for a second visit. Welcome back."


@pytest.mark.parametrize(
    ("variant", "phrase"), [("new", "set a new club record"), ("tie", "level with the club record")]
)
def test_record_watch_new_and_tie_headlines(make_world, sun, run, headline, variant, phrase):
    world = make_world().round(2, sun(0), 50).crowd(sun(0), [30])
    world.round(1, sun(1), 50 if variant == "tie" else 51).crowd(sun(1), [30])
    fr = world.frames()
    (fact,) = run("ev.record-watch", fr, [sun(1)])
    assert fact.variant == variant
    assert phrase in headline("ev.record-watch", fact, fr)


# --- special-shoot debuts (Plan 17 final review) ---------------------------------------------


def test_new_faces_ignores_a_shooter_whose_debut_was_a_special_shoot(make_world, sun, run):
    world = make_world().round(200, sun(0), 30)
    for i in range(1, 10):
        world.round(200, sun(i), 30)
    world.special(1, sun(20))
    world.round(1, sun(21), 30).round(2, sun(21), 30).crowd(sun(21), [31])
    (fact,) = run("ev.new-faces", world.frames(), [sun(21)])
    assert fact.params["n"] == 2  # shooter 2 and the filler; shooter 1 debuted a week earlier


def test_new_faces_is_silent_on_the_regular_sunday_after_a_special_debut(make_world, sun, run):
    world = make_world().series(200, 0, [30] * 12)
    world.special(1, sun(10)).round(1, sun(11), 30)
    assert run("ev.new-faces", world.frames(), [sun(11)]) == []


def test_second_visit_counts_the_special_shoot_as_the_first_visit(make_world, sun, run):
    world = make_world().series(200, 0, [30] * 12)
    world.special(1, sun(8)).round(1, sun(9), 30).round(1, sun(10), 30)
    fr = world.frames()
    (fact,) = run("ev.second-visit", fr, [sun(9), sun(10)])
    assert (fact.anchor_date, fact.params["names"]) == (sun(9), [1])
