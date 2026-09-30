"""Conditions kinds (spec §2.2.4)."""

from statistics import mean

import pytest

from sunday_clays.analytics.insights import conditions  # noqa: F401 - registers the kinds

FIELD = [30, 30]


def rain_world(make_world, sun, wet_scores, dry_scores):
    """Wet Sundays first (0.3 in), then dry; the field's middle score is 30 each Sunday."""
    world = make_world()
    for i, score in enumerate([*wet_scores, *dry_scores]):
        day = sun(i)
        world.sunday(day, precip_in=0.3 if i < len(wet_scores) else 0.0)
        world.round(1, day, score).crowd(day, FIELD)
    return world.frames()


def test_wet_strength_quotes_both_averages(make_world, sun, run, headline):
    wet, dry = [34, 33, 35, 34, 33, 35], [30, 31, 30, 31, 30, 31, 30, 31, 30, 31, 30, 31]
    fr = rain_world(make_world, sun, wet, dry)
    (fact,) = run("pf.wet-strength", fr)
    wet_avg, dry_avg = mean(s - 30 for s in wet), mean(s - 30 for s in dry)
    assert fact.params["wet"] == round(wet_avg, 1)
    assert fact.params["dry"] == round(dry_avg, 1)
    assert fact.strength == pytest.approx((wet_avg - dry_avg) / 1.5)
    assert headline("pf.wet-strength", fact, fr) == (
        f"Rain suits Pat Shooter1: +{wet_avg:.1f} against the field's middle score on wet "
        f"Sundays, +{dry_avg:.1f} on dry."
    )
    assert run("pf.weather-steady", fr) == []


def test_wet_strength_needs_six_wet_sundays(make_world, sun, run):
    fr = rain_world(make_world, sun, [34] * 5, [30, 31] * 6)
    assert run("pf.wet-strength", fr) == []


def test_wet_strength_skips_a_gap_that_reshuffling_matches(make_world, sun, run):
    wet = [30, 38, 30, 38, 30, 38]
    dry = [30] * 9 + [38] * 3
    fr = rain_world(make_world, sun, wet, dry)
    assert run("pf.wet-strength", fr) == []


def test_wet_strength_never_quotes_a_below_the_field_average(make_world, sun, run):
    fr = rain_world(make_world, sun, [29] * 6, [26] * 12)  # wet beats dry by 3, both under 30
    assert run("pf.wet-strength", fr) == []


def test_weather_steady_never_quotes_a_below_the_field_average(make_world, sun, run):
    fr = rain_world(make_world, sun, [29, 28] * 3, [29, 28] * 6)  # steady, but under the field
    assert run("pf.weather-steady", fr) == []


def test_weather_steady_when_wet_and_dry_are_within_three_quarters(make_world, sun, run):
    fr = rain_world(make_world, sun, [31, 32] * 3, [31, 32] * 6)
    (fact,) = run("pf.weather-steady", fr)
    assert fact.params["wet"] == fact.params["dry"]
    assert fact.strength == 2.0  # 0.75 / max(0, 0.25) capped at 2
    assert run("pf.wet-strength", fr) == []


# --- pf.best-temp ---------------------------------------------------------------------------


def temp_world(make_world, sun, cold_scores, mild_scores):
    """Cold Sundays (35°F) first, then mild (60°F); the field's middle score is 30."""
    world = make_world()
    for i, score in enumerate([*cold_scores, *mild_scores]):
        day = sun(i)
        world.sunday(day, temp_f=35.0 if i < len(cold_scores) else 60.0)
        world.round(1, day, score).crowd(day, FIELD)
    return world.frames()


def test_best_temp_names_the_band_and_its_average(make_world, sun, run, headline):
    cold, mild = [34, 35, 33, 34, 35, 33, 34], [30, 31] * 7
    fr = temp_world(make_world, sun, cold, mild)
    (fact,) = run("pf.best-temp", fr)
    assert (fact.params["band"], fact.params["avg"]) == (
        "<40",
        round(mean(s - 30 for s in cold), 1),
    )
    gap = mean(s - 30 for s in cold) - mean(s - 30 for s in mild)
    assert fact.strength == pytest.approx(gap / 2)
    assert headline("pf.best-temp", fact, fr).startswith("Cold suits Pat Shooter1: +")
    assert headline("pf.best-temp", fact, fr, you=True).startswith("Cold suits you: +")


@pytest.mark.parametrize(
    ("cold", "mild"),
    [([32, 32] * 4, [30, 31] * 7), ([34] * 5, [30, 31] * 7), ([25, 45] * 4, [30, 31] * 7)],
    ids=["gap under 2", "under 6 Sundays in the band", "chance"],
)
def test_best_temp_is_silent_outside_its_guard(make_world, sun, run, cold, mild):
    assert run("pf.best-temp", temp_world(make_world, sun, cold, mild)) == []


# --- pf.tough-days --------------------------------------------------------------------------


def tough_world(make_world, sun, hard_scores, easy_scores):
    world = make_world()
    for i, score in enumerate([*hard_scores, *easy_scores]):
        day = sun(i)
        world.sunday(day, difficulty=2.0 if i < len(hard_scores) else 0.0)
        world.round(1, day, score).crowd(day, FIELD)
    return world.frames()


def test_tough_days_quotes_the_hard_day_average(make_world, sun, run, headline):
    hard, easy = [33, 34, 33, 34, 33, 34], [30, 31] * 6
    fr = tough_world(make_world, sun, hard, easy)
    (fact,) = run("pf.tough-days", fr)
    assert fact.params["hard"] == round(mean(s - 30 for s in hard), 1)
    assert fact.params["hard_days"] == [sun(i) for i in range(6)]
    assert headline("pf.tough-days", fact, fr).startswith(
        "The tougher the Sunday, the better Pat Shooter1 does: +"
    )


def test_tough_days_needs_six_hard_sundays(make_world, sun, run):
    fr = tough_world(make_world, sun, [33, 34, 33, 34, 33], [30, 31] * 6)
    assert run("pf.tough-days", fr) == []


def test_best_temp_is_silent_when_the_average_rounds_to_zero(make_world, sun, run):
    cold = [30] * 24 + [31]  # band mean 0.04 against a middle of 30
    assert run("pf.best-temp", temp_world(make_world, sun, cold, [26, 27] * 7)) == []


def test_tough_days_is_silent_when_the_hard_average_rounds_to_zero(make_world, sun, run):
    fr = tough_world(make_world, sun, [30] * 24 + [31], [25, 26] * 6)
    assert run("pf.tough-days", fr) == []
