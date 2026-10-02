"""Community kinds (spec §2.2.7): newcomers, originals, the year in numbers, the club as one."""

from datetime import date, timedelta
from statistics import mean

from sunday_clays.analytics.insights import community, registry  # noqa: F401 - registers the kinds
from sunday_clays.analytics.insights.types import P, Scope


def sundays_of(year, n):
    first = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
    return [first + timedelta(weeks=j) for j in range(n)]


def test_newcomers_counts_this_years_first_rounds_and_returns(make_world, run, headline):
    world = make_world()
    days = sundays_of(2025, 3)
    for sid in range(1, 13):
        world.round(sid, days[0], 30)
    for sid in range(1, 5):
        world.round(sid, days[1], 30)
    fr = world.frames()
    (fact,) = run("cl.newcomers", fr)
    assert (fact.params["n"], fact.params["back"], fact.params["year"]) == (12, 4, 2025)
    assert headline("cl.newcomers", fact, fr) == (
        "12 new shooters in 2025; 4 have come back for more."
    )


def test_originals_counts_first_sunday_shooters_still_active(make_world, sun, run, headline):
    world = make_world()
    for sid in (1, 2, 3, 4):
        world.round(sid, sun(0), 30)
    for sid in (1, 2, 3):
        world.series(sid, 1, [30] * 10)
    fr = world.frames()
    (fact,) = run("cl.originals", fr)
    assert (fact.params["still"], fact.params["n"]) == (3, 4)


def test_originals_drop_the_deceased(make_world, sun, run):
    world = make_world().shooter(1, status="deceased")
    for sid in (1, 2, 3, 4):
        world.round(sid, sun(0), 30)
        world.series(sid, 1, [30] * 10)
    (fact,) = run("cl.originals", world.frames())
    assert (fact.params["still"], fact.params["n"]) == (3, 4)
    assert 1 not in fact.params["ids"]


def test_year_wrap_totals_last_year(make_world, run, headline):
    world = make_world()
    days = sundays_of(2024, 30)
    for j, day in enumerate(days):
        world.sunday(day, head_count=10 + j).crowd(day, [30, 31])
    world.crowd(sundays_of(2025, 1)[0], [30])
    fr = world.frames()
    (fact,) = run("cl.year-wrap", fr)
    assert (fact.params["sundays"], fact.params["rounds"]) == (30, 60)
    assert (fact.params["busiest"], fact.params["busiest_n"]) == (days[-1], 39)
    assert fact.params["firsts"] == 60  # every filler shooter debuts in 2024


def test_year_wrap_firsts_skip_left_censored_and_home_pages_by_month(make_world, run):
    world = make_world().shooter(1, censored=True)
    days = sundays_of(2024, 30)
    for day in days:
        world.sunday(day, head_count=10).crowd(day, [30])
    world.round(1, days[0], 30).round(2, days[0], 30)  # 1 is left-censored: not a debut
    world.crowd(sundays_of(2025, 1)[0], [30])
    fr = world.frames()
    (fact,) = run("cl.year-wrap", fr)
    assert fact.params["firsts"] == 31
    assert P.HOME in fact.pages  # January as_of
    mid = Scope(sundays=frozenset(), as_of=date(2025, 6, 1))
    (mid_fact,) = registry.get("cl.year-wrap").evaluate(fr, mid)
    assert mid_fact.params["year"] == 2024  # the latest finished year, on the club page only
    assert mid_fact.pages == frozenset({P.CLUB})


def test_year_wrap_and_year_wrapped_carry_the_same_year_in_december(make_world, run):
    """The club and shooter wraps share one wrap_year rule (final review I-3)."""
    world = make_world()
    days = sundays_of(2025, 50)
    for day in days:
        world.sunday(day, head_count=10).crowd(day, [30] * 14)
        world.round(1, day, 35)
    fr = world.frames()
    december = Scope(sundays=frozenset(), as_of=date(2025, 12, 14))
    (club,) = list(registry.get("cl.year-wrap").evaluate(fr, december))
    (shooter,) = [
        f for f in registry.get("pf.year-wrapped").evaluate(fr, december) if f.subject_id == "1"
    ]
    assert club.params["year"] == shooter.params["year"] == 2025
    assert {P.CLUB, P.HOME} <= club.pages
    january = Scope(sundays=frozenset(), as_of=date(2026, 1, 4))
    (club_jan,) = list(registry.get("cl.year-wrap").evaluate(fr, january))
    (shooter_jan,) = [
        f for f in registry.get("pf.year-wrapped").evaluate(fr, january) if f.subject_id == "1"
    ]
    assert club_jan.params["year"] == shooter_jan.params["year"] == 2025


def test_club_one_shooter_places_the_club_average(make_world, sun, run, headline):
    world = make_world()
    for sid, score in ((1, 40), (2, 35), (3, 30)):
        world.series(sid, 0, [score] * 5)
    world.series(4, 0, [45] * 4)  # under 5 rounds: in the average, not in the placing
    fr = world.frames()
    (fact,) = run("cl.club-one-shooter", fr)
    club = round(mean([40] * 5 + [35] * 5 + [30] * 5 + [45] * 4), 1)
    assert (fact.params["avg"], fact.params["n"]) == (club, 3)
    assert fact.params["rank"] == 1 + sum(v > club for v in (40, 35, 30))


def test_guards_stay_silent_on_thin_data(make_world, sun, run):
    world = make_world()
    world.round(1, sun(0), 30)
    thin = world.frames()
    for kind in ("cl.newcomers", "cl.year-wrap", "cl.club-one-shooter"):
        assert run(kind, thin) == []
    world = make_world()
    days = sundays_of(2025, 2)
    for sid in range(1, 10):
        world.round(sid, days[0], 30)
    assert run("cl.newcomers", world.frames()) == []
    world = make_world()
    world.round(1, sun(0), 30)
    assert run("cl.originals", world.frames()) == []
    world = make_world()
    for sid in range(1, 4):
        world.series(sid, 0, [30] * 4)
    assert run("cl.club-one-shooter", world.frames()) == []


def test_chart_links_point_at_the_evidence(make_world, sun, run):
    world = make_world()
    days = sundays_of(2025, 3)
    for sid in range(1, 13):
        world.round(sid, days[0], 30)
    for sid in range(1, 5):
        world.round(sid, days[1], 30)
    (fact,) = run("cl.newcomers", world.frames())
    assert registry.get("cl.newcomers").chart(fact).highlight.keys == ("2025",)

    world = make_world()
    for sid in (1, 2, 3, 4):
        world.round(sid, sun(0), 30)
    for sid in (1, 2, 3):
        world.series(sid, 1, [30] * 10)
    (fact,) = run("cl.originals", world.frames())
    link = registry.get("cl.originals").chart(fact)
    assert link.spec.filters.shooter_ids == [1, 2, 3]
    assert link.window.start == fact.params["first"]
    assert link.window.end == fact.params["day"]

    world = make_world()
    for j, day in enumerate(sundays_of(2024, 30)):
        world.sunday(day, head_count=10 + j).crowd(day, [30, 31])
    world.crowd(sundays_of(2025, 1)[0], [30])
    (fact,) = run("cl.year-wrap", world.frames())
    assert registry.get("cl.year-wrap").chart(fact).highlight.keys == ("2024",)

    world = make_world()
    for sid, score in ((1, 40), (2, 35), (3, 30)):
        world.series(sid, 0, [score] * 5)
    (fact,) = run("cl.club-one-shooter", world.frames())
    assert registry.get("cl.club-one-shooter").chart(fact).ref == 35.0


def test_old_sundays_and_pre_history_scopes(make_world, sun, run):
    world = make_world()
    for sid in (1, 2, 3):
        world.series(sid, 0, [30] * 5)
    world.round(9, sun(0) - timedelta(days=800), 20)  # older than 12 months: left out
    fr = world.frames()
    (fact,) = run("cl.club-one-shooter", fr)
    assert fact.params["avg"] == 30.0
    before = Scope(sundays=frozenset(), as_of=sun(0) - timedelta(days=2000))
    assert list(registry.get("cl.originals").evaluate(fr, before)) == []


def test_newcomers_count_a_first_sunday_at_a_special_shoot(make_world, run):
    """Plan 17: cohorts follow Sundays shot, like the /club "new" chart the fact links to."""
    days = sundays_of(2025, 3)
    world = make_world()
    for sid in range(1, 10):
        world.round(sid, days[0], 30)
    for sid in range(1, 4):
        world.round(sid, days[2], 30)
    assert run("cl.newcomers", world.frames()) == []  # 9 new: under NEWCOMERS_MIN
    world.special(10, days[1])  # shooter 10's only Sunday is the special shoot
    (fact,) = run("cl.newcomers", world.frames())
    assert (fact.params["n"], fact.params["back"], fact.params["year"]) == (10, 3, 2025)


def test_year_wrap_counts_a_special_sunday(make_world, run):
    """Plan 17: the special Sunday is one of the year's Sundays, can be the busiest, and its new
    shooters are first-timers; the round count stays the scored rounds."""
    days = sundays_of(2024, 30)
    world = make_world()
    for day in days[:15] + days[16:]:
        world.sunday(day, head_count=10).crowd(day, [30])
    world.crowd(sundays_of(2025, 1)[0], [30])
    assert run("cl.year-wrap", world.frames()) == []  # 29 regular Sundays: too few
    for sid in range(1, 13):
        world.special(sid, days[15])
    (fact,) = run("cl.year-wrap", world.frames())
    assert (fact.params["sundays"], fact.params["rounds"]) == (30, 29)
    assert (fact.params["busiest"], fact.params["busiest_n"]) == (days[15], 12)
    assert fact.params["firsts"] == 29 + 12
