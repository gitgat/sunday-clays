"""Points-race and club-standing kinds (spec §2.2.4, §2.2.8)."""

from datetime import date, timedelta

from sunday_clays.analytics.insights import season
from sunday_clays.analytics.insights.season import leader, ranks, season_standings, sundays_left

FIRST = date(2025, 1, 5)


def day(j: int) -> date:
    return FIRST + timedelta(weeks=j)


def race_world(make_world, winners, deceased=()):
    """winners[j]: who wins Sunday j (10 points + 1); shooters 1-3 always shoot."""
    world = make_world()
    for sid in deceased:
        world.shooter(sid, status="deceased")
    for j, winner in enumerate(winners):
        for sid in (1, 2, 3):
            world.round(sid, day(j), 45 if sid == winner else 30 + sid)
    return world.frames()


def test_new_leader_after_the_sixth_sunday(make_world, run, headline):
    fr = race_world(make_world, [1] * 5 + [2] * 7)
    facts = run("lb.new-leader", fr)
    standings = season_standings(fr)
    assert standings[day(9)][2] == standings[day(9)][1]  # level after 10 Sundays: no sole leader
    assert [f.anchor_date for f in facts] == [day(10)]
    assert headline("lb.new-leader", facts[0], fr) == (
        "New points leader this year: Pat Shooter2 moved into 1st."
    )


def test_title_race_names_only_the_leader(make_world, run, headline):
    fr = race_world(make_world, [1, 2, 1, 2, 1, 2, 1])
    (fact,) = run("lb.title-race", fr)
    totals = season_standings(fr)[day(6)]
    ordered = sorted(totals.values(), reverse=True)
    assert (fact.variant, fact.params["s"], fact.params["lead"]) == (
        "race",
        1,
        ordered[0] - ordered[1],
    )
    assert fact.named_shooter_ids == (1,)
    assert "Pat Shooter2" not in headline("lb.title-race", fact, fr)


def test_sundays_left_counts_to_new_year():
    assert sundays_left(date(2025, 12, 21)) == 1
    assert sundays_left(date(2025, 12, 28)) == 0


def test_biggest_climb_three_places_into_the_top_ten(make_world, run, headline, monkeypatch):
    monkeypatch.setattr(season, "SEASON_MIN_SUNDAYS", 1)  # a two-Sunday year keeps it small
    world = make_world()
    for sid, score in ((2, 45), (3, 44), (4, 43), (5, 42), (6, 41), (1, 40)):
        world.round(sid, day(0), score)
    world.round(1, day(1), 45).round(2, day(1), 44)
    fr = world.frames()
    before, after = ranks(season_standings(fr)[day(0)]), ranks(season_standings(fr)[day(1)])
    (fact,) = [f for f in run("lb.biggest-climb", fr) if f.subject_id == "1"]
    assert (before[1], after[1]) == (6, 2)
    assert (fact.params["up"], fact.params["rank"]) == (4, 2)
    assert headline("lb.biggest-climb", fact, fr) == (
        "Up 4 places in points this year: Pat Shooter1 is now 2nd."
    )


def test_most_improved_uses_the_leaderboard_rule(make_world, run, headline):
    world = make_world()
    start = date(2024, 1, 7)
    for j in range(12):  # 12 rounds before the year
        world.round(1, start + timedelta(weeks=j), 30).rating(1, start + timedelta(weeks=j), 30.0)
    for j in range(6):
        world.round(1, day(j), 36).rating(1, day(j), 30.0 + j)
    fr = world.frames()
    (fact,) = run("lb.most-improved", fr)
    assert (fact.params["s"], fact.params["delta"]) == (1, 5.0)
    assert fact.params["kudos_sunday"] == day(5)
    assert headline("lb.most-improved", fact, fr) == (
        "Most improved this year: Pat Shooter1, skill rating up 5.0 since January."
    )


def test_top_of_club_quarter_and_tenth(make_world, run):
    world = make_world()
    for sid in range(1, 21):
        world.series(sid, 0, [30 + sid] * 10)
    fr = world.frames()
    variants = {int(f.subject_id): f.variant for f in run("pf.top-of-club", fr)}
    assert variants == {20: "tenth", 19: "tenth", 18: "quarter", 17: "quarter", 16: "quarter"}


def _gain_world(make_world, top: float):
    """12 rounds long before the last year, then 6 inside it with the rating rising to `top`."""
    world = make_world()
    start = date(2023, 1, 1)
    for j in range(12):
        world.round(1, start + timedelta(weeks=j), 30).rating(1, start + timedelta(weeks=j), 30.0)
    for j in range(6):
        rating = 30.0 + (top - 30.0) * j / 5
        world.round(1, day(j), 36).rating(1, day(j), rating)
    return world.frames()


def test_rank_climb_is_a_rating_gain_over_twelve_months(make_world, run, headline):
    fr = _gain_world(make_world, 35.0)
    (fact,) = run("pf.rank-climb", fr)
    assert (fact.variant, fact.params["s"], fact.params["gain"]) == ("", 1, 5.0)
    assert set(fact.params) == {"s", "gain", "day"}
    text = headline("pf.rank-climb", fact, fr)
    assert text == "Pat Shooter1 gained 5.0 rating points in the last 12 months."
    assert "place" not in text


def test_rank_climb_needs_a_real_gain(make_world, run):
    assert run("pf.rank-climb", _gain_world(make_world, 31.0)) == []


def test_title_race_clinched_late_in_the_year(make_world, run):
    fr = race_world(make_world, [1] * 52)
    (fact,) = run("lb.title-race", fr)
    assert (fact.variant, fact.named_shooter_ids) == ("clinched", (1,))


def test_a_lone_shooter_leads_nobody():
    assert leader({1: 5}) is None


def test_deceased_leader_is_not_named(make_world, run):
    fr = race_world(make_world, [1] * 5 + [2] * 7, deceased=(2,))
    assert run("lb.new-leader", fr) == []
    fr = race_world(make_world, [1, 2, 1, 2, 1, 2, 1], deceased=(1,))
    assert run("lb.title-race", fr) == []


def test_deceased_most_improved_is_not_named(make_world, run):
    world = make_world().shooter(1, status="deceased")
    start = date(2024, 1, 7)
    for j in range(12):
        world.round(1, start + timedelta(weeks=j), 30).rating(1, start + timedelta(weeks=j), 30.0)
    for j in range(6):
        world.round(1, day(j), 36).rating(1, day(j), 30.0 + j)
    assert run("lb.most-improved", world.frames()) == []
