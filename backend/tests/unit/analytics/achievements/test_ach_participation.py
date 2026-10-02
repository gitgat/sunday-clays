"""Participation trophies (Plan 10 T2): milestone families and calendar one-offs."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.achievements import registry
from sunday_clays.analytics.achievements.participation import last_sunday


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def awards(code, ctx):
    return sorted(
        (w.shooter_id, w.code, w.event_date) for w in registry.evaluate_one(registry.get(code), ctx)
    )


def value_series(code, ctx, shooter_id):
    frame = registry.get(code).value(ctx)
    return list(frame[frame["shooter_id"] == shooter_id]["value"])


# ---- scenarios (also reused by the no-leak tests) ----------------------------------------


def clays_broken_ctx(b):
    return (
        b()
        .round(1, sun(0), 40)
        .round(1, sun(0), 45)
        .round(1, sun(1), 20)
        .round(2, sun(1), 50)
        .build()
    )


def thrown_ctx(b):
    builder = b()
    for i in range(5):
        builder.round(1, sun(i), 30).round(1, sun(i), 31)
    builder.round(2, sun(0), 30)
    return builder.build()


def events_ctx(b):
    builder = b().round(1, sun(0), 30)  # a second round on the first date is still one event
    for i in range(10):
        builder.round(1, sun(i), 31)
    return builder.build()


def years_ctx(b):
    return (
        b()
        .round(1, date(2024, 12, 29), 30)
        .round(1, date(2025, 1, 5), 30)
        .round(1, date(2025, 6, 1), 30)
        .round(1, date(2026, 1, 4), 30)
        .build()
    )


def big_year_ctx(b):
    builder = b()
    for i in range(20):
        builder.round(1, date(2025, 1, 5) + timedelta(weeks=i), 30)
    for i in range(19):
        builder.round(2, date(2024, 1, 7) + timedelta(weeks=i), 30)
        builder.round(2, date(2025, 1, 5) + timedelta(weeks=i), 30)
    return builder.build()


NON_HELD = sun(2) + timedelta(days=3)


def streak_ctx(b):
    builder = b().event(NON_HELD, results_complete=False).round(1, NON_HELD, 30)
    for i in range(4):
        builder.round(1, sun(i), 30)  # also attends the non-held date
        builder.round(3, sun(i), 30)  # skips the non-held date: still 4 straight held events
    for i in (0, 1, 3, 4, 5):
        builder.round(2, sun(i), 30)  # misses sun(2): longest run is 3
    return builder.build()


def pb_ctx(b):
    builder = b()
    for i, score in enumerate([30, 31, 32, 33, 34]):
        builder.round(1, sun(i), score)
    builder.round(1, sun(5), 35).round(1, sun(6), 35).round(1, sun(7), 36).round(1, sun(7), 37)
    builder.round(2, sun(0), 40).round(2, sun(1), 45)
    return builder.build()


def doubleheader_ctx(b):
    return (
        b()
        .round(1, sun(0), 30)
        .round(1, sun(1), 30)
        .round(1, sun(1), 31)
        .round(1, sun(2), 30)
        .round(1, sun(2), 32)
        .round(2, sun(1), 30)
        .build()
    )


def new_year_ctx(b):
    return (
        b()
        .event(date(2025, 1, 5), results_complete=False)
        .round(2, date(2025, 1, 5), 30)
        .round(1, date(2025, 1, 12), 30)
        .round(1, date(2026, 1, 4), 30)
        .round(2, date(2026, 1, 4), 30)
        .build()
    )


FIRST = date(2024, 1, 7)


def anniversary_ctx(b):
    return (
        b()
        .round(1, FIRST, 30)
        .round(1, FIRST + timedelta(days=358), 30)
        .round(2, FIRST, 30)
        .round(2, FIRST + timedelta(days=357), 30)
        .round(2, FIRST + timedelta(days=373), 30)
        .round(3, FIRST, 30)
        .round(3, FIRST + timedelta(days=372), 30)
        .round(4, FIRST, 30)
        .round(4, FIRST + timedelta(days=365 * 5 + 7), 30)
        .build()
    )


W0 = sun(0)
W1 = W0 + timedelta(days=179)
W2 = W1 + timedelta(days=180)
W3 = W2 + timedelta(days=7)
W4 = W3 + timedelta(days=200)


def welcome_ctx(b):
    builder = b()
    for day in (W0, W1, W2, W3, W4):
        builder.round(1, day, 30)
    return builder.build()


def joined_ctx(b):
    return (
        b()
        .round(1, sun(0), 30, status="guest")  # round 1
        .round(1, sun(1), 30)  # round 2
        .round(2, sun(0), 30, status="guest")  # round 3
        .round(2, sun(0), 31)  # round 4: same day as the guest round, does not count
        .round(2, sun(1), 30)  # round 5
        .round(3, sun(0), 30)  # round 6
        .round(3, sun(1), 30, status="guest")  # round 7
        .round(3, sun(2), 30)  # round 8
        .round(4, sun(0), 30)
        .round(4, sun(1), 30)
        .build()
    )


def disciplines_ctx(b):
    return (
        b()
        .event(sun(0), round_type="sporting")
        .event(sun(1), round_type="sporting")
        .event(sun(2), round_type="super_sporting")
        .round(1, sun(0), 30)
        .round(1, sun(2), 30)
        .round(2, sun(0), 30)
        .round(2, sun(1), 30)
        .build()
    )


def seasons_ctx(b):
    return (
        b()
        .round(1, date(2024, 12, 29), 30)  # December counts toward 2025's winter
        .round(1, date(2025, 4, 6), 30)
        .round(1, date(2025, 7, 6), 30)
        .round(1, date(2025, 10, 5), 30)
        .round(2, date(2025, 4, 6), 30)
        .round(2, date(2025, 7, 6), 30)
        .round(2, date(2025, 10, 5), 30)
        .round(2, date(2025, 12, 7), 30)  # counts toward 2026's winter, not 2025's
        .build()
    )


MARCH = [date(2025, 3, d) for d in (2, 9, 16, 23)]
MARCH_30 = date(2025, 3, 30)
MARCH_31 = date(2025, 3, 31)  # a Monday: non-Sunday event dates do occur (C3 non_sunday_date)
APRIL_6 = date(2025, 4, 6)


def month_ctx(b, *, last_sunday_held, april_held):
    builder = b()
    for day in MARCH:
        builder.round(1, day, 30).round(2, day, 30)
    builder.round(3, MARCH[0], 30).round(3, MARCH[1], 30).round(3, MARCH[3], 30)  # misses 3/16
    if last_sunday_held:
        builder.round(1, MARCH_30, 30).round(2, MARCH_30, 30)
    else:
        builder.event(MARCH_30, results_complete=False).round(4, MARCH_30, 30)
    if april_held:
        builder.round(4, APRIL_6, 30)
    # February: only 2 held events
    builder.round(5, date(2025, 2, 2), 30).round(5, date(2025, 2, 9), 30)
    return builder.build()


def late_monday_ctx(b, *, last_sunday_held):
    builder = b()
    for day in MARCH:
        builder.round(1, day, 30).round(2, day, 30)
    if last_sunday_held:
        builder.round(1, MARCH_30, 30).round(2, MARCH_30, 30)
    return builder.round(2, MARCH_31, 30).build()  # only shooter 2 shoots the Monday


# ---- families ------------------------------------------------------------------------------


def test_clays_broken_crosses_at_first_event_over_threshold(ctx_builder):
    ctx = clays_broken_ctx(ctx_builder)
    assert awards("clays_broken", ctx) == [(1, "clays_broken:1", sun(1))]
    assert value_series("clays_broken", ctx, 1) == [85.0, 105.0]


def test_clays_thrown_counts_fifty_per_round(ctx_builder):
    assert awards("clays_thrown", thrown_ctx(ctx_builder)) == [(1, "clays_thrown:1", sun(4))]


def test_events_counts_dates_not_rounds(ctx_builder):
    assert awards("events", events_ctx(ctx_builder)) == [
        (1, "events:1", sun(0)),
        (1, "events:2", sun(9)),
    ]


def test_years_active_counts_distinct_calendar_years(ctx_builder):
    ctx = years_ctx(ctx_builder)
    assert awards("years_active", ctx) == [
        (1, "years_active:1", date(2025, 1, 5)),
        (1, "years_active:2", date(2026, 1, 4)),
    ]
    assert value_series("years_active", ctx, 1) == [1.0, 2.0, 2.0, 3.0]


def test_big_year_needs_twenty_events_in_one_calendar_year(ctx_builder):
    ctx = big_year_ctx(ctx_builder)
    assert awards("big_year", ctx) == [(1, "big_year:1", date(2025, 5, 18))]
    assert max(value_series("big_year", ctx, 2)) == 19.0


def test_iron_streak_counts_consecutive_held_events(ctx_builder):
    assert awards("iron_streak", streak_ctx(ctx_builder)) == [
        (1, "iron_streak:1", sun(3)),
        (3, "iron_streak:1", sun(3)),
    ]


def test_personal_best_counts_once_per_day(ctx_builder):
    ctx = pb_ctx(ctx_builder)
    assert value_series("personal_bests", ctx, 1) == [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 2.0]
    assert value_series("personal_bests", ctx, 2) == [0.0, 0.0]
    assert awards("personal_bests", ctx) == [(1, "personal_bests:1", sun(5))]


# ---- one-offs --------------------------------------------------------------------------------


def test_doubleheader_awarded_on_first_two_round_day(ctx_builder):
    assert awards("doubleheader", doubleheader_ctx(ctx_builder)) == [(1, "doubleheader", sun(1))]


def test_new_year_uses_first_held_event_of_the_year(ctx_builder):
    assert awards("new_year", new_year_ctx(ctx_builder)) == [
        (1, "new_year", date(2025, 1, 12)),
        (2, "new_year", date(2026, 1, 4)),
    ]


def test_anniversary_1_window_is_358_to_372_days(ctx_builder):
    assert awards("anniversary_1", anniversary_ctx(ctx_builder)) == [
        (1, "anniversary_1", FIRST + timedelta(days=358)),
        (3, "anniversary_1", FIRST + timedelta(days=372)),
    ]


def test_anniversary_5_window_is_a_week_either_side(ctx_builder):
    assert awards("anniversary_5", anniversary_ctx(ctx_builder)) == [
        (4, "anniversary_5", FIRST + timedelta(days=365 * 5 + 7))
    ]


def test_welcome_back_after_180_days_is_repeatable(ctx_builder):
    assert awards("welcome_back", welcome_ctx(ctx_builder)) == [
        (1, "welcome_back", W2),
        (1, "welcome_back", W4),
    ]


def test_joined_club_needs_a_guest_round_on_an_earlier_date(ctx_builder):
    got = {
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_one(registry.get("joined_club"), joined_ctx(ctx_builder))
    }
    assert got == {(1, sun(1), 2), (2, sun(1), 5), (3, sun(2), 8)}


def test_joined_club_without_any_guest_rounds_awards_nothing(ctx_builder):
    assert awards("joined_club", ctx_builder().round(1, sun(0), 30).build()) == []


def test_both_disciplines_dated_when_second_type_is_shot(ctx_builder):
    assert awards("both_disciplines", disciplines_ctx(ctx_builder)) == [
        (1, "both_disciplines", sun(2))
    ]


def test_both_disciplines_needs_known_round_types(ctx_builder):
    assert awards("both_disciplines", ctx_builder().round(1, sun(0), 30).build()) == []


def test_four_seasons_counts_december_toward_next_year(ctx_builder):
    assert awards("four_seasons", seasons_ctx(ctx_builder)) == [
        (1, "four_seasons", date(2025, 10, 5))
    ]


@pytest.mark.parametrize(
    ("year", "month", "expected"),
    [(2025, 3, date(2025, 3, 30)), (2025, 2, date(2025, 2, 23)), (2025, 8, date(2025, 8, 31))],
)
def test_last_sunday_of_month(year, month, expected):
    assert last_sunday(year, month) == expected


def test_perfect_month_closes_on_last_sunday_when_held(ctx_builder):
    ctx = month_ctx(ctx_builder, last_sunday_held=True, april_held=False)
    got = [
        (w.shooter_id, w.event_date, dict(w.details))
        for w in registry.evaluate_one(registry.get("perfect_month"), ctx)
    ]
    assert got == [(1, MARCH_30, {"month": "2025-03"}), (2, MARCH_30, {"month": "2025-03"})]


def test_perfect_month_closes_on_next_held_event_when_last_sunday_not_held(ctx_builder):
    ctx = month_ctx(ctx_builder, last_sunday_held=False, april_held=True)
    assert awards("perfect_month", ctx) == [
        (1, "perfect_month", APRIL_6),
        (2, "perfect_month", APRIL_6),
    ]


def test_perfect_month_not_awarded_while_month_is_open(ctx_builder):
    ctx = month_ctx(ctx_builder, last_sunday_held=False, april_held=False)
    assert awards("perfect_month", ctx) == []


def test_perfect_month_held_day_after_the_closing_sunday_cannot_change_it(ctx_builder, no_leak):
    # 3/30 closes March, so the award on 3/30 must not depend on who shoots the later Monday 3/31.
    ctx = late_monday_ctx(ctx_builder, last_sunday_held=True)
    assert awards("perfect_month", ctx) == [
        (1, "perfect_month", MARCH_30),
        (2, "perfect_month", MARCH_30),
    ]
    assert no_leak("perfect_month", ctx, MARCH_30) == (2, 0)


def test_perfect_month_held_monday_that_closes_the_month_counts(ctx_builder):
    # 3/30 is not an event, so the Monday 3/31 closes March and is one of its held events.
    ctx = late_monday_ctx(ctx_builder, last_sunday_held=False)
    assert awards("perfect_month", ctx) == [(2, "perfect_month", MARCH_31)]


def test_every_family_handles_a_shooter_with_no_rounds(ctx_builder):
    ctx = ctx_builder().round(1, sun(0), 30).build().for_shooter(99)
    for code in (
        "clays_broken",
        "clays_thrown",
        "events",
        "years_active",
        "big_year",
        "iron_streak",
        "personal_bests",
    ):
        assert registry.get(code).value(ctx).empty
    for code in (
        "doubleheader",
        "new_year",
        "anniversary_1",
        "welcome_back",
        "four_seasons",
        "perfect_month",
    ):
        assert awards(code, ctx) == []


# ---- no-leak (C12: each definition gets its own) ---------------------------------------------


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("clays_broken", clays_broken_ctx, sun(0)),
        ("clays_thrown", thrown_ctx, sun(3)),
        ("events", events_ctx, sun(5)),
        ("years_active", years_ctx, date(2025, 6, 1)),
        ("big_year", big_year_ctx, date(2025, 5, 11)),
        ("iron_streak", streak_ctx, sun(2)),
        ("personal_bests", pb_ctx, sun(4)),
        ("doubleheader", doubleheader_ctx, sun(0)),
        ("new_year", new_year_ctx, date(2025, 6, 1)),
        ("anniversary_1", anniversary_ctx, FIRST + timedelta(days=300)),
        ("anniversary_5", anniversary_ctx, FIRST + timedelta(days=400)),
        ("welcome_back", welcome_ctx, W2 - timedelta(days=1)),
        ("joined_club", joined_ctx, sun(0)),
        ("both_disciplines", disciplines_ctx, sun(1)),
        ("four_seasons", seasons_ctx, date(2025, 7, 6)),
        (
            "perfect_month",
            lambda b: month_ctx(b, last_sunday_held=False, april_held=True),
            MARCH_30,
        ),
        ("perfect_month", lambda b: late_monday_ctx(b, last_sunday_held=False), MARCH_30),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0  # the scenario has awards after the cut, so a leak would be visible


# ---- special Sundays (Plan 17): they count as Sundays shot, never as rounds ---------------


def special_ctx(b):
    """Shooter 1 shoots sun(0), the special sun(1) and sun(2); shooter 2 skips the special."""
    return (
        b()
        .round(1, sun(0), 30)
        .special(1, sun(1))
        .round(1, sun(2), 31)
        .round(2, sun(0), 40)
        .round(2, sun(2), 41)
        .build()
    )


def test_a_special_sunday_counts_toward_events_years_and_big_year(ctx_builder):
    ctx = special_ctx(ctx_builder)

    assert value_series("events", ctx, 1) == [1.0, 2.0, 3.0]
    assert value_series("events", ctx, 2) == [1.0, 2.0]
    assert value_series("big_year", ctx, 1) == [1.0, 2.0, 3.0]
    assert value_series("years_active", ctx, 1) == [1.0, 1.0, 1.0]


def test_iron_streak_runs_through_a_special_sunday_and_never_breaks_on_it(ctx_builder):
    ctx = special_ctx(ctx_builder)

    assert value_series("iron_streak", ctx, 1) == [1.0, 2.0, 3.0]
    assert value_series("iron_streak", ctx, 2) == [1.0, 2.0]


def test_score_trophies_ignore_the_special_sunday(ctx_builder):
    ctx = special_ctx(ctx_builder)

    assert value_series("clays_broken", ctx, 1) == [30.0, 61.0]
    assert value_series("clays_thrown", ctx, 1) == [50.0, 100.0]
    assert value_series("personal_bests", ctx, 1) == [0.0, 0.0]
    assert awards("doubleheader", ctx) == []


def test_new_year_goes_to_a_special_sunday_before_the_first_regular_one(ctx_builder):
    jan4, jan11, jan18 = date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18)
    ctx = (
        ctx_builder()
        .special(1, jan4)
        .special(2, jan4)
        .round(1, jan11, 30)
        .round(3, jan11, 30)
        .special(4, jan18)
        .build()
    )

    found = sorted(
        (w.shooter_id, w.event_date, w.round_id is None)
        for w in registry.evaluate_one(registry.get("new_year"), ctx)
    )
    assert found == [(1, jan4, True), (2, jan4, True), (3, jan11, False)]


def test_welcome_back_and_the_anniversary_count_a_special_sunday(ctx_builder):
    d0 = date(2025, 1, 5)
    back, year_on = d0 + timedelta(weeks=29), d0 + timedelta(weeks=52)
    ctx = ctx_builder().round(1, d0, 30).special(1, back).special(1, year_on).build()

    (welcome,) = registry.evaluate_one(registry.get("welcome_back"), ctx)
    assert (welcome.event_date, welcome.round_id, welcome.details) == (
        back,
        None,
        {"days_away": 203},
    )
    assert awards("anniversary_1", ctx) == [(1, "anniversary_1", year_on)]


def test_perfect_month_counts_a_special_sunday_toward_the_three(ctx_builder):
    mar1, mar8, mar15, apr5 = (
        date(2026, 3, 1),
        date(2026, 3, 8),
        date(2026, 3, 15),
        date(2026, 4, 5),
    )
    ctx = (
        ctx_builder()
        .round(1, mar1, 30)
        .round(2, mar1, 30)
        .special(1, mar8)
        .round(1, mar15, 30)
        .round(2, mar15, 30)
        .round(3, apr5, 30)
        .build()
    )

    assert awards("perfect_month", ctx) == [(1, "perfect_month", apr5)]


@pytest.mark.parametrize("code", ["events", "iron_streak", "new_year", "perfect_month"])
def test_appearance_trophies_with_a_special_sunday_never_leak(ctx_builder, no_leak, code):
    no_leak(code, special_ctx(ctx_builder), sun(1))  # the fixture asserts full == sliced


def test_four_seasons_counts_a_season_covered_only_by_a_special_sunday(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, date(2025, 4, 6), 30)
        .round(1, date(2025, 7, 6), 30)
        .special(1, date(2025, 10, 5))
        .round(1, date(2025, 12, 7), 30)  # winter 2026: not 2025's winter
        .round(1, date(2025, 2, 2), 30)
        .build()
    )

    (found,) = registry.evaluate_one(registry.get("four_seasons"), ctx)
    assert (found.shooter_id, found.event_date, found.round_id) == (1, date(2025, 10, 5), None)


# ---- the 3-Bird Shoot (Plan 17 T10) -------------------------------------------------------


def three_bird_awards(ctx):
    return [
        (w.shooter_id, w.event_date, w.round_id, w.details)
        for w in registry.evaluate_one(registry.get("three_bird_shoot"), ctx)
    ]


def test_the_three_bird_trophy_is_a_non_tiered_calendar_one_off(ctx_builder):
    from sunday_clays.analytics.achievements.registry import Category

    achievement = registry.get("three_bird_shoot")
    assert (achievement.name, achievement.description) == ("3-Bird Shoot", "Shot the 3-Bird Shoot.")
    assert (achievement.category, achievement.art_key) == (Category.CALENDAR, "three_bird_shoot")
    assert (achievement.tiers, achievement.repeatable) == ((), False)


def test_a_three_bird_special_sunday_awards_its_shooters(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 30)
        .special(1, sun(1), "3-Bird Shoot")
        .special(2, sun(1), "3-Bird Shoot")
        .build()
    )

    assert three_bird_awards(ctx) == [
        (1, sun(1), None, {"label": "3-Bird Shoot", "event_date": sun(1).isoformat()}),
        (2, sun(1), None, {"label": "3-Bird Shoot", "event_date": sun(1).isoformat()}),
    ]


@pytest.mark.parametrize("label", ["three bird shoot", " 3_BIRD  Shoot ", "THREE-Bird Shoot"])
def test_three_bird_labels_are_normalised(label, ctx_builder):
    ctx = ctx_builder().special(1, sun(1), label).build()

    assert three_bird_awards(ctx) == [
        (1, sun(1), None, {"label": label, "event_date": sun(1).isoformat()})
    ]


def test_another_special_shoot_or_a_regular_sunday_does_not_award(ctx_builder):
    ctx = ctx_builder().round(1, sun(0), 30).special(1, sun(1), "Fun Shoot").build()

    assert three_bird_awards(ctx) == []


def test_only_the_first_three_bird_shoot_awards(ctx_builder):
    ctx = (
        ctx_builder()
        .special(1, sun(1), "3-Bird Shoot")
        .special(1, sun(5), "Three Bird Shoot")
        .special(2, sun(5), "Three Bird Shoot")
        .build()
    )

    assert [(sid, day) for sid, day, _, _ in three_bird_awards(ctx)] == [
        (1, sun(1)),
        (2, sun(5)),
    ]


def test_three_bird_never_leaks(ctx_builder, no_leak):
    ctx = (
        ctx_builder().special(1, sun(1), "3-Bird Shoot").special(2, sun(5), "3-Bird Shoot").build()
    )

    assert no_leak("three_bird_shoot", ctx, sun(2)) == (1, 1)
    assert three_bird_awards(ctx.until(sun(0))) == []
