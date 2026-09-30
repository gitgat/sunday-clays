"""Club kinds (spec §2.2.7): weather, turnout and pace, about everyone at once."""

from datetime import date, timedelta
from statistics import mean

import pytest

from sunday_clays.analytics.insights import club, registry
from sunday_clays.analytics.insights.types import Scope
from sunday_clays.explorer.spec import Dim


def weather_world(make_world, sun, *, wet_heads, dry_heads, wet_diff=0.0, dry_diff=0.0, n_wet=20):
    world = make_world()
    for i in range(n_wet + 20):
        wet = i < n_wet
        heads = wet_heads[i % len(wet_heads)] if wet else dry_heads[i % len(dry_heads)]
        world.sunday(
            sun(i),
            precip_in=0.3 if wet else 0.0,
            head_count=heads,
            difficulty=wet_diff if wet else dry_diff,
            temp_f=60.0,
            gust_mph=12.0,
        ).crowd(sun(i), [30, 31])
    return world.frames()


def test_rain_turnout_quotes_both_averages(make_world, sun, run, headline):
    wet, dry = [18, 19, 20], [24, 25, 26]
    fr = weather_world(make_world, sun, wet_heads=wet, dry_heads=dry)
    (fact,) = run("cl.rain-turnout", fr)
    wet_all = [wet[i % 3] for i in range(20)]
    dry_all = [dry[i % 3] for i in range(20, 40)]
    assert (fact.params["wet"], fact.params["dry"]) == (
        round(mean(wet_all), 1),
        round(mean(dry_all), 1),
    )
    assert fact.named_shooter_ids == ()
    assert headline("cl.rain-turnout", fact, fr).startswith("Rain keeps about ")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"wet_heads": [23, 24, 25], "dry_heads": [24, 25, 26]},
        {"wet_heads": [18, 19, 20], "dry_heads": [24, 25, 26], "n_wet": 19},
        {"wet_heads": [5, 35], "dry_heads": [24, 25, 26]},
    ],
    ids=["gap under 3", "under 20 wet Sundays", "inside the noise"],
)
def test_rain_turnout_is_silent_outside_its_guard(make_world, sun, run, kwargs):
    assert run("cl.rain-turnout", weather_world(make_world, sun, **kwargs)) == []


def test_rain_scores_neutral_twin_and_moving_twin(make_world, sun, run, headline):
    steady = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20])
    (fact,) = run("cl.rain-scores", steady)
    assert fact.variant == "same"  # a gap that rounds to 0.0 has its own number-free line
    moving = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20], wet_diff=2.0)
    (fact,) = run("cl.rain-scores", moving)
    assert (fact.variant, fact.params["gap"], fact.params["way"]) == ("moves", 2.0, "tough")
    assert "wet Sundays play about 2.0 targets tougher" in headline("cl.rain-scores", fact, moving)


def test_weather_scoreboard_names_the_band_that_moves_scores(make_world, sun, run, headline):
    steady = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20])
    assert [f.variant for f in run("cl.weather-scoreboard", steady)] == ["steady"]
    moving = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20], wet_diff=2.0)
    (fact,) = run("cl.weather-scoreboard", moving)
    assert (fact.variant, fact.params["band"]) == ("moves", "wet")


def test_turnout_trend_three_rising_years(make_world, run, headline):
    world = make_world()
    for year, heads in ((2023, 20), (2024, 22), (2025, 25)):
        first = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
        for j in range(20):
            day = first + timedelta(weeks=j)
            world.sunday(day, head_count=heads).crowd(day, [30])
    fr = world.frames()
    (fact,) = run("cl.turnout-trend", fr)
    assert (fact.variant, fact.params["a"], fact.params["c"]) == ("years", 20, 25)


def test_year_pace_ahead_and_passed(make_world, run, headline):
    world = make_world()
    for year, per_sunday in ((2024, 10), (2025, 12)):
        first = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
        for j in range(20):
            day = first + timedelta(weeks=j)
            world.crowd(day, [30] * per_sunday)
    fr = world.frames()
    facts = run("cl.year-pace", fr)
    evergreen = [f for f in facts if f.anchor_date is None]
    assert [(f.variant, f.params["this"], f.params["last"]) for f in evergreen] == [
        ("passed", 240, 200)
    ]
    anchored = [f.variant for f in facts if f.anchor_date is not None]
    assert "passed" in anchored


def test_every_club_kind_is_silent_on_an_empty_club(make_world):
    fr = make_world().frames()
    scope = Scope(sundays=frozenset(), as_of=date(2025, 6, 1))
    for kind_id in (
        "cl.rain-turnout",
        "cl.rain-scores",
        "cl.weather-scoreboard",
        "cl.turnout-trend",
        "cl.year-pace",
    ):
        assert list(registry.get(kind_id).evaluate(fr, scope)) == []


def test_weather_scoreboard_is_silent_when_no_band_has_enough_sundays(make_world, sun, run):
    world = make_world()
    for i in range(4):
        world.sunday(
            sun(i), precip_in=0.0, head_count=20, difficulty=0.0, temp_f=60.0, gust_mph=12.0
        ).crowd(sun(i), [30, 31])
    assert run("cl.weather-scoreboard", world.frames()) == []


def test_rain_scores_easy_and_in_between(make_world, sun, run):
    easy = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20], wet_diff=-2.0)
    (fact,) = run("cl.rain-scores", easy)
    assert (fact.variant, fact.params["way"]) == ("moves", "easy")
    between = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20], wet_diff=1.0)
    assert run("cl.rain-scores", between) == []


def gusty_world(make_world, sun, *, gust_diff):
    world = make_world()
    for i in range(24):
        gusty = i % 2 == 0
        world.sunday(
            sun(i),
            precip_in=0.0,
            head_count=20,
            difficulty=gust_diff if gusty else 0.0,
            temp_f=60.0,
            gust_mph=25.0 if gusty else 5.0,
        ).crowd(sun(i), [30, 31])
    return world.frames()


def test_weather_scoreboard_finds_a_gust_band_and_links_every_cut(make_world, sun, run):
    fr = gusty_world(make_world, sun, gust_diff=-3.0)
    (fact,) = run("cl.weather-scoreboard", fr)
    assert (fact.variant, fact.params["band"], fact.params["way"]) == ("moves", "<10", "tough")
    link = registry.get("cl.weather-scoreboard").chart(fact)
    assert link.also
    steady = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20])
    (quiet,) = run("cl.weather-scoreboard", steady)
    assert registry.get("cl.weather-scoreboard").chart(quiet).also


def test_turnout_trend_recent_eight_sundays(make_world, run, sun):
    world = make_world()
    for i in range(16):
        world.sunday(sun(i), head_count=20 if i < 8 else 26).crowd(sun(i), [30])
    fr = world.frames()
    (fact,) = run("cl.turnout-trend", fr)
    assert (fact.variant, fact.params["recent"], fact.params["before"]) == ("recent", 26, 20)
    assert registry.get("cl.turnout-trend").chart(fact).highlight.span is not None
    flat = make_world()
    for i in range(16):
        flat.sunday(sun(i), head_count=20).crowd(sun(i), [30])
    assert run("cl.turnout-trend", flat.frames()) == []
    short = make_world()
    for i in range(10):
        short.sunday(sun(i), head_count=20).crowd(sun(i), [30])
    assert run("cl.turnout-trend", short.frames()) == []


def test_year_pace_ahead_and_leap_day_pace(make_world, run):
    world = make_world()
    for year, per_sunday, sundays in ((2024, 10, 20), (2025, 11, 10)):
        first = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
        for j in range(sundays):
            world.crowd(first + timedelta(weeks=j), [30] * per_sunday)
    facts = run("cl.year-pace", world.frames())
    assert "ahead" in [f.variant for f in facts if f.anchor_date is None]
    ahead = next(f for f in facts if f.variant == "ahead")
    assert registry.get("cl.year-pace").chart(ahead).spec.filters.ytd is not None
    assert club.same_date(date(2024, 2, 29), 2025) == date(2025, 2, 28)


def test_year_pace_caught_up_on_a_sunday(make_world, run):
    world = make_world()
    for year, counts in ((2024, [10] * 20), (2025, [5, 5, 5] + [15] * 7)):
        first = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
        for j, per_sunday in enumerate(counts):
            world.crowd(first + timedelta(weeks=j), [30] * per_sunday)
    facts = run("cl.year-pace", world.frames())
    caught = [f for f in facts if f.variant == "caught"]
    assert len(caught) == 1
    assert caught[0].anchor_date is not None
    assert registry.get("cl.year-pace").chart(caught[0]).spec.filters.ytd is not None


def test_sundays_without_weather_or_difficulty_are_skipped(make_world, sun, run):
    world = make_world()
    for i in range(45):
        bare = i >= 40
        world.sunday(
            sun(i),
            precip_in=None if bare else (0.3 if i < 24 else 0.0),
            head_count=20,
            difficulty=None if i % 9 == 8 else 0.0,
            temp_f=60.0,
            gust_mph=12.0,
        ).crowd(sun(i), [30, 31])
    fr = world.frames()
    (fact,) = run("cl.rain-scores", fr)
    assert fact.variant == "same"
    link = registry.get("cl.rain-scores").chart(fact)
    assert (link.spec.group_by, link.ref) == ([Dim.PRECIP_BAND], 0)


def test_rain_turnout_chart_and_years_chart(make_world, sun, run):
    fr = weather_world(make_world, sun, wet_heads=[18, 19, 20], dry_heads=[24, 25, 26])
    (fact,) = run("cl.rain-turnout", fr)
    assert registry.get("cl.rain-turnout").chart(fact).highlight.keys == ("wet",)
    moving = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20], wet_diff=2.0)
    (moves,) = run("cl.rain-scores", moving)
    assert registry.get("cl.rain-scores").chart(moves).ref == 0
    world = make_world()
    for year, heads in ((2023, 20), (2024, 22), (2025, 25)):
        first = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
        for j in range(20):
            day = first + timedelta(weeks=j)
            world.sunday(day, head_count=heads).crowd(day, [30])
    (years,) = run("cl.turnout-trend", world.frames())
    assert registry.get("cl.turnout-trend").chart(years).highlight.keys == ("2023", "2024", "2025")


def test_turnout_trend_needs_every_year_to_beat_the_last(make_world, run):
    world = make_world()
    for year, heads in ((2023, 20), (2024, 25), (2025, 22)):
        first = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
        for j in range(20):
            day = first + timedelta(weeks=j)
            world.sunday(day, head_count=heads).crowd(day, [30])
    assert run("cl.turnout-trend", world.frames()) == []


def test_year_pace_passed_chart_and_level_year_is_silent(make_world, run):
    world = make_world()
    for year, per_sunday, sundays in ((2024, 10, 20), (2025, 9, 10)):
        first = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
        for j in range(sundays):
            world.crowd(first + timedelta(weeks=j), [30] * per_sunday)
    assert [f for f in run("cl.year-pace", world.frames()) if f.anchor_date is None] == []
    passed = passed_pace_fact(make_world, run)
    assert registry.get("cl.year-pace").chart(passed).spec.filters.ytd is None


def passed_pace_fact(make_world, run):
    world = make_world()
    for year, per_sunday in ((2024, 10), (2025, 12)):
        first = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
        for j in range(20):
            world.crowd(first + timedelta(weeks=j), [30] * per_sunday)
    return next(f for f in run("cl.year-pace", world.frames()) if f.variant == "passed")


def test_rain_kinds_ignore_sundays_without_weather_and_need_enough_wet_ones(make_world, sun, run):
    world = make_world()
    for i in range(45):
        world.sunday(
            sun(i),
            precip_in=None if i >= 40 else (0.3 if i < 20 else 0.0),
            head_count=18 if i < 20 else 25,
            difficulty=0.0,
        ).crowd(sun(i), [30, 31])
    (fact,) = run("cl.rain-turnout", world.frames())
    assert (fact.params["wet"], fact.params["dry"]) == (18, 25)
    few = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20], n_wet=5)
    assert run("cl.rain-scores", few) == []


def test_rain_scores_steady_copy_never_says_within_zero(make_world, sun, run, headline):
    same = weather_world(make_world, sun, wet_heads=[20], dry_heads=[20])
    (fact,) = run("cl.rain-scores", same)
    assert (fact.variant, fact.params["gap"]) == ("same", 0.0)
    text = headline("cl.rain-scores", fact, same)
    assert "within" not in text
    assert "0.0" not in text


def test_rain_turnout_gap_agrees_with_the_quoted_averages(make_world, sun, run):
    world = make_world()
    for i in range(45):
        world.sunday(
            sun(i),
            precip_in=0.3 if i < 20 else 0.0,
            head_count=19 if i < 20 and i % 5 else (20 if i < 20 else 25),
            difficulty=0.0,
        ).crowd(sun(i), [30, 31])
    (fact,) = run("cl.rain-turnout", world.frames())
    assert fact.params["gap"] == round(fact.params["dry"] - fact.params["wet"])


def test_rain_scores_steady_quotes_a_small_gap_inside_the_noise(make_world, sun, run, headline):
    world = make_world()
    for i in range(40):
        wet = i < 20
        swing = 2.0 if i % 2 else -2.0
        world.sunday(
            sun(i),
            precip_in=0.3 if wet else 0.0,
            head_count=20,
            difficulty=swing + (0.2 if wet else 0.0),
            temp_f=60.0,
            gust_mph=12.0,
        ).crowd(sun(i), [30, 31])
    fr = world.frames()
    (fact,) = run("cl.rain-scores", fr)
    assert (fact.variant, fact.params["gap"]) == ("steady", 0.2)
    assert "within 0.2 targets" in headline("cl.rain-scores", fact, fr)
