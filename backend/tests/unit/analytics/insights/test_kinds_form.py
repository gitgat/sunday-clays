"""Form kinds (spec §2.2.1)."""

from dataclasses import replace
from datetime import date, timedelta
from statistics import mean

import pytest

from sunday_clays.analytics.insights import form  # noqa: F401 - registers the kinds
from sunday_clays.analytics.insights.types import P

FIELD = [30, 30]  # with the shooter's round, the field's middle score is 30 when they shoot >= 30


def hot_world(make_world, sun, last5, *, n=15, gap_weeks=0):
    world = make_world()
    scores = [32] * (n - 5) + list(last5)
    for i, score in enumerate(scores):
        day = sun(i if i < n - 5 else i + gap_weeks)
        world.round(1, day, score).crowd(day, FIELD)
    return world.frames()


def test_hot_form_quotes_the_average_gap_over_the_last_five_sundays(make_world, sun, run, headline):
    last5 = [34, 35, 36, 33, 36]
    fr = hot_world(make_world, sun, last5)
    (fact,) = run("pf.hot-form", fr)
    expected = round(mean(s - 30 for s in last5), 1)
    assert fact.params["avg"] == expected
    assert fact.strength == pytest.approx(expected / 4, abs=0.02)
    assert headline("pf.hot-form", fact, fr) == (
        f"Last 5 Sundays: Pat Shooter1 averaged {expected} above the field's middle score."
    )
    assert "you averaged" in headline("pf.hot-form", fact, fr, you=True)


def test_hot_form_guard_edge_fires_at_exactly_four_with_strength_one(make_world, sun, run):
    (fact,) = run("pf.hot-form", hot_world(make_world, sun, [34] * 5))
    assert fact.strength == 1.0


@pytest.mark.parametrize(
    ("last5", "kwargs"),
    [([33] * 5, {}), ([36] * 5, {"n": 14})],
    ids=["below 4", "under 15 rounds"],
)
def test_hot_form_is_silent_outside_its_guard(make_world, sun, run, last5, kwargs):
    assert run("pf.hot-form", hot_world(make_world, sun, last5, **kwargs)) == []


def test_hot_form_round_guard_is_the_only_thing_that_silences_fourteen_rounds(make_world, sun, run):
    """A field of ten (so adjusted scores are real): 15 rounds fire, 14 are silent."""
    big = [30] * 9

    def world_of(n):
        world = make_world()
        for i, score in enumerate([32] * (n - 5) + [36] * 5):
            world.round(1, sun(i), score).crowd(sun(i), big)
        return world.frames()

    assert len(run("pf.hot-form", world_of(15))) == 1
    assert run("pf.hot-form", world_of(14)) == []


def test_hot_form_is_silent_when_not_shot_in_eight_weeks(make_world, sun, run):
    world = make_world()
    for i in range(10):
        world.round(1, sun(i), 32).crowd(sun(i), FIELD)
    for i in range(10, 15):
        world.round(1, sun(i), 36).crowd(sun(i), FIELD)
    fr = world.frames()
    assert len(run("pf.hot-form", fr)) == 1  # sanity: fires while they are still shooting
    world.crowd(sun(24), [30, 31, 32, 33, 34])  # a later Sunday they missed
    assert run("pf.hot-form", world.frames()) == []


def test_hot_form_needs_five_sundays_even_with_many_rounds(make_world, sun, run):
    world = make_world()
    for i in range(4):
        for _ in range(4):  # 16 rounds on only 4 Sundays
            world.round(1, sun(i), 36)
        world.crowd(sun(i), FIELD)
    assert run("pf.hot-form", world.frames()) == []


# --- pf.beat-own-usual ----------------------------------------------------------------------


def usual_world(make_world, sun, *, prior=20, residual=6.0, expected=38.0):
    world = make_world()
    for i in range(prior):
        world.round(1, sun(i), 36, residual=0.0, expected=36.0).crowd(sun(i), FIELD)
    day = sun(prior)
    score = round(expected + residual)
    world.round(1, day, score, residual=residual, expected=expected).crowd(day, FIELD)
    return world.frames(), day, score


def test_beat_own_usual_quotes_score_usual_and_gap(make_world, sun, run, headline):
    fr, day, score = usual_world(make_world, sun, residual=6.0, expected=38.0)
    (fact,) = run("pf.beat-own-usual", fr)
    assert fact.anchor_date == day
    assert (fact.params["score"], fact.params["usual"], fact.params["over"]) == (score, 38, 6)
    assert fact.strength == pytest.approx(6.0 / 5)
    assert f"{score}, 6 over a usual of 38" in headline("pf.beat-own-usual", fact, fr)


@pytest.mark.parametrize(
    "kwargs", [{"residual": 4.9}, {"prior": 19}], ids=["under +5", "under 20 prior rounds"]
)
def test_beat_own_usual_is_silent_outside_its_guard(make_world, sun, run, kwargs):
    fr, _day, _score = usual_world(make_world, sun, **kwargs)
    assert run("pf.beat-own-usual", fr) == []


# --- pf.up-on-usual -------------------------------------------------------------------------


def up_world(make_world, sun, before, recent):
    world = make_world()
    for i, score in enumerate([*before, *recent]):
        world.round(1, sun(i), score).crowd(sun(i), FIELD)
    return world.frames()


def test_up_on_usual_compares_last_ten_with_the_twenty_before(make_world, sun, run):
    before = [33, 35] * 10
    recent = [37, 38] * 5
    (fact,) = run("pf.up-on-usual", up_world(make_world, sun, before, recent))
    assert fact.params["gap"] == round(mean(recent) - mean(before), 1)
    assert fact.params["recent"] == round(mean(recent), 1)
    assert fact.params["start"] == sun(len(before))


@pytest.mark.parametrize(
    ("before", "recent"),
    [([33, 35] * 10, [35, 36] * 5), ([25, 45] * 10, [30, 50] * 5), ([34] * 19, [37] * 10)],
    ids=["gap under 2", "gap within noise", "under 30 Sundays"],
)
def test_up_on_usual_is_silent_outside_its_guard(make_world, sun, run, before, recent):
    assert run("pf.up-on-usual", up_world(make_world, sun, before, recent)) == []


# --- pf.year-up and pf.years-up-run ---------------------------------------------------------


def years_world(make_world, per_year):
    """per_year: {year: scores}; one round each Sunday from the first Sunday of the year."""
    world = make_world()
    for year, scores in per_year.items():
        first = next(d for d in (date(year, 1, k) for k in range(1, 8)) if d.weekday() == 6)
        for j, score in enumerate(scores):
            day = first + timedelta(weeks=j)
            world.round(1, day, score).crowd(day, FIELD)
    return world.frames()


def test_year_up_quotes_both_years(make_world, run, headline):
    last, this = [34] * 12, [37] * 12
    fr = years_world(make_world, {2024: last, 2025: this})
    (fact,) = run("pf.year-up", fr)
    assert (fact.params["this"], fact.params["last"]) == (mean(this), mean(last))
    assert fact.params["year"] == 2025
    assert "2025" in headline("pf.year-up", fact, fr)


@pytest.mark.parametrize(
    "per_year",
    [{2024: [34] * 12, 2025: [35] * 12}, {2024: [34] * 9, 2025: [38] * 12}],
    ids=["under 1.5", "under 10 rounds last year"],
)
def test_year_up_is_silent_outside_its_guard(make_world, run, per_year):
    assert run("pf.year-up", years_world(make_world, per_year)) == []


def test_years_up_run_needs_two_rises_and_a_total_of_one_and_a_half(make_world, run):
    fr = years_world(make_world, {2023: [33] * 10, 2024: [34] * 10, 2025: [35] * 10})
    (fact,) = run("pf.years-up-run", fr)
    assert (fact.params["a"], fact.params["b"], fact.params["c"]) == (33, 34, 35)
    assert fact.params["y3"] == 2025
    flat = years_world(make_world, {2023: [33] * 10, 2024: [35] * 10, 2025: [35] * 10})
    assert run("pf.years-up-run", flat) == []


def test_years_up_run_uses_last_year_until_this_year_has_ten_rounds(make_world, run):
    fr = years_world(
        make_world, {2022: [33] * 10, 2023: [34] * 10, 2024: [35] * 10, 2025: [30] * 3}
    )
    (fact,) = run("pf.years-up-run", fr)
    assert fact.params["y3"] == 2024
    assert P.HOME in fact.pages  # as_of is in January


# --- pf.gaining-on-field --------------------------------------------------------------------


def test_gaining_on_field_two_year_window_measures_the_gain(make_world, sun, run):
    world = make_world()
    scores = [31] * 52 + [34] * 52  # field middle is 30 when they shoot >= 30
    for i, score in enumerate(scores):
        world.round(1, sun(i), score).crowd(sun(i), FIELD)
    fr = world.frames()
    (fact,) = run("pf.gaining-on-field", fr)
    days = fr.histories[1]
    recent = [d.adjusted for d in days if d.date > fr.as_of - timedelta(weeks=52)]
    before = [
        d.adjusted
        for d in days
        if fr.as_of - timedelta(weeks=104) < d.date <= fr.as_of - timedelta(weeks=52)
    ]
    assert fact.variant == "two_years"
    assert fact.params["gain"] == round(mean(recent) - mean(before), 1)
    assert fact.params["first"] == fr.as_of - timedelta(weeks=104)


def test_gaining_on_field_falls_back_to_first_and_last_ten(make_world, sun, run):
    world = make_world()
    scores = [31] * 10 + [32] * 10 + [34] * 10
    for i, score in enumerate(scores):
        day = sun(i * 6)  # sparse: fewer than 10 rounds in each 52-week window
        world.round(1, day, score).crowd(day, FIELD)
    fr = world.frames()
    (fact,) = run("pf.gaining-on-field", fr)
    adjusted = [d.adjusted for d in fr.histories[1]]
    assert fact.variant == "career"
    assert fact.params["gain"] == round(mean(adjusted[-10:]) - mean(adjusted[:10]), 1)


def test_gaining_on_field_career_chart_starts_at_first_held_sunday(make_world, sun, run):
    world = make_world()
    scores = [31] * 10 + [32] * 10 + [34] * 10
    for i, score in enumerate(scores):
        day = sun(i * 6)
        world.round(1, day, score).crowd(day, FIELD)
    fr = world.frames()
    (fact,) = run("pf.gaining-on-field", fr)
    assert fact.params["first"] == sun(0)


@pytest.mark.parametrize(
    "scores",
    [[34] * 52 + [35] * 52, [34] * 25],
    ids=["gain under 2", "neither window qualifies"],
)
def test_gaining_on_field_is_silent_outside_its_guard(make_world, sun, run, scores):
    world = make_world()
    for i, score in enumerate(scores):
        world.round(1, sun(i), score).crowd(sun(i), FIELD)
    assert run("pf.gaining-on-field", world.frames()) == []


def test_years_up_run_is_silent_when_a_year_has_under_ten_rounds(make_world, run):
    fr = years_world(make_world, {2023: [33] * 9, 2024: [34] * 10, 2025: [36] * 10})
    assert run("pf.years-up-run", fr) == []


def test_up_on_usual_is_silent_when_not_shot_recently(make_world, sun, run):
    before, recent = [33, 35] * 10, [37, 38] * 5
    world = make_world()
    for i, score in enumerate(before + recent):
        world.round(1, sun(i), score).crowd(sun(i), FIELD)
    fr = world.frames()
    assert run("pf.up-on-usual", fr)  # sanity: fires when recent
    stale = replace(fr, as_of=fr.as_of + timedelta(weeks=30))
    assert run("pf.up-on-usual", stale) == []
