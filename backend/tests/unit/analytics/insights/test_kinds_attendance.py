"""Attendance kinds (spec §2.2.2, §2.2.3): stats about showing up, never a score."""

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.insights import (
    attendance,  # noqa: F401 - registers the kinds
    charts,
    registry,
)
from sunday_clays.analytics.insights.context import wrap_year
from sunday_clays.analytics.insights.types import PROFILE, ROLLUP, Fact, Page


def club_sundays(world, sun, n):
    for i in range(n):
        world.crowd(sun(i), [30, 31])
    return world


def test_attendance_year_share_of_held_sundays(make_world, sun, run, headline):
    world = club_sundays(make_world(), sun, 10)
    for i in range(10):
        if i != 4:
            world.round(1, sun(i), 30)
    fr = world.frames()
    (fact,) = [f for f in run("pf.attendance-year", fr) if f.subject_id == "1"]
    assert (fact.params["shot"], fact.params["held"]) == (9, 10)
    assert fact.strength == pytest.approx(0.9 / 0.85)
    assert (
        headline("pf.attendance-year", fact, fr)
        == "Pat Shooter1 has shot 9 of 10 Sundays this year."
    )


def test_attendance_year_needs_eight_held_and_eighty_five_percent(make_world, sun, run):
    world = club_sundays(make_world(), sun, 7).series(1, 0, [30] * 7)
    assert [f for f in run("pf.attendance-year", world.frames()) if f.subject_id == "1"] == []
    world = club_sundays(make_world(), sun, 10).series(1, 0, [30] * 8)
    assert [f for f in run("pf.attendance-year", world.frames()) if f.subject_id == "1"] == []


def test_attendance_streak_profile_from_five_and_home_at_ten(make_world, sun, run, headline):
    world = club_sundays(make_world(), sun, 12)
    world.round(1, sun(0), 30)
    for i in range(2, 12):
        world.round(1, sun(i), 30)
    fr = world.frames()
    facts = [f for f in run("pf.attendance-streak", fr) if f.subject_id == "1"]
    anchored = [(f.anchor_date, f.params["k"]) for f in facts if f.anchor_date is not None]
    assert anchored == [(sun(11), 10)]
    (profile,) = [f for f in facts if f.anchor_date is None]
    assert (profile.variant, profile.params["k"], profile.params["start"]) == (
        f"{PROFILE}_longest",
        10,
        sun(2),
    )
    assert headline("pf.attendance-streak", profile, fr).endswith("their longest run yet.")


def test_months_in_row_skips_months_without_a_held_sunday(make_world, run, headline):
    world = make_world()
    first = date(2024, 1, 7)
    for m in range(14):
        day = date(2024 + (m // 12), m % 12 + 1, 1) + timedelta(days=6)
        if m == 5:
            continue  # no Sunday held in June 2024
        world.round(1, day, 30).crowd(day, [30])
    fr = world.frames()
    (profile,) = [f for f in run("pf.months-in-row", fr) if f.variant == PROFILE]
    assert profile.params["months"] == 13
    assert profile.params["start"] == date(first.year, 1, 1)
    assert Page.PROFILE in profile.pages


def test_year_wrapped_only_in_december_and_january():
    assert wrap_year(date(2025, 12, 7)) == 2025
    assert wrap_year(date(2026, 1, 4)) == 2025
    assert wrap_year(date(2026, 2, 1)) is None


def test_year_wrapped_counts_and_finish(make_world, run, headline):
    world = make_world()
    first = date(2025, 1, 5)
    for j in range(12):
        day = first + timedelta(weeks=j)
        world.round(1, day, 40 if j == 3 else 35).crowd(day, [30, 31, 32, 33, 34, 36] + [30] * 8)
    world.crowd(date(2025, 12, 7), [30])
    fr = world.frames()
    (fact,) = [f for f in run("pf.year-wrapped", fr) if f.subject_id == "1"]
    assert (fact.params["sundays"], fact.params["targets"], fact.params["best"]) == (
        12,
        11 * 35 + 40,
        40,
    )
    assert fact.params["finish"] == 1
    assert headline("pf.year-wrapped", fact, fr) == (
        "Pat Shooter1's 2025: 12 Sundays, 425 targets, best 40, best finish 1st."
    )


# --- fix round 1 ---------------------------------------------------------------------------------


def monthly_world(make_world, months, *, miss_last=False):
    """One Sunday on the 7th (a Sunday-agnostic date) per month from 2024-01; the shooter shoots
    each one except, optionally, the last."""
    world = make_world()
    for m in range(months):
        day = date(2024 + m // 12, m % 12 + 1, 7)
        world.crowd(day, [30])
        if not (miss_last and m == months - 1):
            world.round(1, day, 30)
    return world


def test_months_in_row_does_not_break_on_the_month_in_progress(make_world, run):
    fr = monthly_world(make_world, 13, miss_last=True).frames()
    (profile,) = [f for f in run("pf.months-in-row", fr) if f.variant == PROFILE]
    assert profile.params["months"] == 12


def test_months_in_row_home_fact_at_twenty_four_months(make_world, run):
    fr = monthly_world(make_world, 24).frames()
    home = [f for f in run("pf.months-in-row", fr) if f.subject_id == "1" and f.anchor_date]
    assert [f.params["months"] for f in home] == [24]
    assert Page.HOME in home[0].pages


def test_months_in_row_rollup_copy_and_chart(sun):
    kind = registry.get("pf.months-in-row")
    fact = Fact(
        subject_id="club",
        anchor_date=sun(0),
        variant=ROLLUP,
        pages=frozenset({Page.SUNDAY}),
        params={"names": [1, 2], "day": sun(0)},
        strength=1.0,
    )
    assert kind.templates[ROLLUP]
    assert kind.how[ROLLUP]
    assert vars(kind.chart(fact)) == vars(charts.rollup_results(fact))


def test_attendance_streak_rollup_chart(sun):
    kind = registry.get("pf.attendance-streak")
    fact = Fact(
        subject_id="club",
        anchor_date=sun(0),
        variant=ROLLUP,
        pages=frozenset({Page.SUNDAY}),
        params={"names": [1, 2], "day": sun(0)},
        strength=1.0,
    )
    assert kind.templates[ROLLUP]
    assert kind.how[ROLLUP]
    assert kind.chart(fact).type


def wrapped_world(make_world, shooter_scores, field, *, n=12):
    world = make_world()
    for j in range(n):
        day = date(2025, 1, 5) + timedelta(weeks=j)
        world.round(1, day, shooter_scores).crowd(day, field)
    world.crowd(date(2025, 12, 7), [30])
    return world


def test_year_wrapped_without_a_top_third_finish_has_no_finish(make_world, run, headline):
    fr = wrapped_world(make_world, 20, [30, 31, 32, 33, 34, 36]).frames()
    (fact,) = [f for f in run("pf.year-wrapped", fr) if f.subject_id == "1"]
    assert fact.variant == ""
    assert "finish" not in fact.params
    assert "finish" not in headline("pf.year-wrapped", fact, fr)


def test_year_wrapped_needs_twelve_sundays(make_world, run):
    fr = wrapped_world(make_world, 35, [30, 31], n=11).frames()
    assert [f for f in run("pf.year-wrapped", fr) if f.subject_id == "1"] == []


def test_year_wrapped_chart_covers_the_calendar_year(make_world, run):
    fr = wrapped_world(make_world, 35, [30, 31]).frames()
    (fact,) = [f for f in run("pf.year-wrapped", fr) if f.subject_id == "1"]
    link = registry.get("pf.year-wrapped").chart(fact)
    assert (link.window.start, link.window.end) == (date(2025, 1, 1), date(2025, 12, 31))


def test_year_wrapped_finish_needs_a_field_of_fifteen(make_world, run):
    """A top-third finish in a 7-shooter field is not a "best finish" (spec 4.3, I-2)."""
    small = wrapped_world(make_world, 40, [30, 31, 32, 33, 34, 36]).frames()
    (fact,) = [f for f in run("pf.year-wrapped", small) if f.subject_id == "1"]
    assert fact.variant == ""
    full = wrapped_world(make_world, 40, [30] * 14).frames()
    (fact,) = [f for f in run("pf.year-wrapped", full) if f.subject_id == "1"]
    assert (fact.variant, fact.params["finish"]) == ("finish", 1)


def test_attendance_streak_runs_through_a_special_sunday_and_never_breaks_on_it(
    make_world, sun, run
):
    world = make_world()
    for i in (0, 1, 3, 4, 5):
        world.crowd(sun(i), [30, 31]).round(1, sun(i), 30).round(2, sun(i), 30)
    world.special(1, sun(2))
    fr = world.frames()

    facts = {f.subject_id: f for f in run("pf.attendance-streak", fr) if f.anchor_date is None}
    assert (facts["1"].params["k"], facts["1"].params["start"]) == (6, sun(0))
    assert (facts["2"].params["k"], facts["2"].params["start"]) == (5, sun(0))
