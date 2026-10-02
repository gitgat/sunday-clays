"""Milestone kinds (spec §2.2.1, §2.2.3)."""

from datetime import timedelta

import pytest

from sunday_clays.analytics.insights import milestones  # noqa: F401 - registers the kinds
from sunday_clays.analytics.insights.templates import fmt_month_year
from sunday_clays.analytics.insights.types import PROFILE, Page


def test_pb_needs_five_earlier_rounds_and_a_strictly_higher_score(make_world, sun, run, headline):
    world = make_world().series(1, 0, [30, 31, 32, 33, 34, 40])  # 6th round beats 5 earlier
    world.series(2, 0, [30, 31, 32, 33, 40])  # only 4 earlier rounds: no PB (C12)
    world.series(3, 0, [30, 31, 32, 33, 34, 34])  # a tie is not a PB
    fr = world.frames()
    facts = [f for f in run("pf.pb", fr) if f.variant == ""]
    assert [(f.subject_id, f.anchor_date) for f in facts] == [("1", sun(5))]
    fact = facts[0]
    old = max([30, 31, 32, 33, 34])
    assert fact.params["new"] == 40
    assert fact.params["old"] == old
    assert fact.params["old_date"] == sun(4)
    assert fact.strength == 1 + (40 - old) / 2
    assert fact.pages == frozenset({Page.SUNDAY, Page.HOME})
    assert headline("pf.pb", fact, fr) == (
        f"New personal best for Pat Shooter1: 40, beating the {old} from {fmt_month_year(sun(4))}."
    )
    assert headline("pf.pb", fact, fr, you=True).startswith("New personal best: 40, beating your")


def test_pb_profile_row_is_the_latest_pb_within_52_sundays(make_world, sun, run):
    world = make_world().series(1, 0, [30, 31, 32, 33, 34, 40, 41, 35])
    fr = world.frames()
    profile = [f for f in run("pf.pb", fr) if f.variant == PROFILE]
    assert len(profile) == 1
    assert profile[0].anchor_date is None
    assert profile[0].params["new"] == 41
    assert profile[0].pages == frozenset({Page.PROFILE})


def test_pb_profile_row_expires_after_52_held_sundays(make_world, sun, run):
    world = make_world().series(1, 0, [30, 31, 32, 33, 34, 40])
    world.series(1, 6, [35] * 52)  # stays active; the PB is 52 held Sundays old
    fr = world.frames()
    assert [f for f in run("pf.pb", fr) if f.variant == PROFILE] == []


def test_tied_best_needs_twelve_earlier_rounds_and_a_best_three_over_the_average(
    make_world, sun, run, headline
):
    scores = [30] * 11 + [40] + [44]  # 44 is the best so far after 12 rounds
    world = make_world().series(1, 0, scores).round(1, sun(13), 44)
    fr = world.frames()
    (fact,) = [f for f in run("pf.tied-best", fr) if f.variant == ""]
    usual = sum(scores) / len(scores)
    assert fact.anchor_date == sun(13)
    assert fact.params["first"] == sun(12)
    assert fact.strength == pytest.approx((44 - usual) / 3)
    assert headline("pf.tied-best", fact, fr) == (
        f"Pat Shooter1 matched a personal best of 44, first set in {fmt_month_year(sun(12))}."
    )
    early = make_world().series(1, 0, [30] * 10 + [44, 44]).frames()
    assert run("pf.tied-best", early) == []


def test_sunday_milestone_counts_every_sunday_shot_and_the_club(make_world, sun, run, headline):
    world = make_world().series(1, 0, [30] * 25).series(2, 0, [30] * 24)
    world.round(2, sun(30), 30)  # shooter 2 reaches 25 later
    fr = world.frames()
    facts = [f for f in run("pf.sunday-milestone", fr) if f.variant in ("", "first")]
    assert [(f.subject_id, f.anchor_date, f.params["club"], f.variant) for f in facts] == [
        ("1", sun(24), 1, "first"),
        ("2", sun(30), 2, ""),
    ]
    assert headline("pf.sunday-milestone", facts[0], fr) == (
        "25th Sunday for Pat Shooter1, the first shooter to get there."
    )
    assert headline("pf.sunday-milestone", facts[0], fr, you=True) == (
        "Your 25th Sunday: you are the first shooter to get there."
    )
    assert headline("pf.sunday-milestone", facts[1], fr) == (
        "25th Sunday for Pat Shooter2, one of 2 shooters to get there."
    )


def test_sunday_milestone_to_go_is_home_only(make_world, sun, run, headline):
    fr = make_world().series(1, 0, [30] * 23).frames()
    (to_go,) = [f for f in run("pf.sunday-milestone", fr) if f.variant == "to_go"]
    assert to_go.pages == frozenset({Page.HOME})
    assert to_go.params["to_go"] == 2
    assert headline("pf.sunday-milestone", to_go, fr) == "Pat Shooter1 is 2 Sundays from a 25th."


def test_first_career_win_needs_eight_earlier_rounds_and_fifteen_shooters(make_world, sun, run):
    world = make_world().series(1, 0, [30] * 8).round(1, sun(8), 49)
    for i in range(8):
        world.crowd(sun(i), [35, 36])  # somebody else wins the first 8 Sundays
    world.crowd(sun(8), range(30, 44))  # 15 shooters that day
    fr = world.frames()
    (fact,) = [f for f in run("pf.wins", fr) if f.subject_id == "1"]
    assert (fact.variant, fact.strength, fact.params["n"]) == ("career", 2.0, 15)


def test_first_win_of_the_year_and_the_profile_count(make_world, sun, run, headline):
    world = make_world()
    for i in range(60):
        world.round(1, sun(i), 45 if i in (10, 52, 55) else 30).crowd(sun(i), [35, 36])
    fr = world.frames()
    facts = run("pf.wins", fr)
    anchored = [(f.variant, f.anchor_date) for f in facts if f.anchor_date is not None]
    assert ("year", sun(52)) in anchored
    assert ("year", sun(55)) not in anchored  # a second win that year is not a "first"
    (count,) = [f for f in facts if f.variant == PROFILE]
    assert count.params["wins"] == 2
    assert headline("pf.wins", count, fr) == f"Pat Shooter1 has 2 wins in {sun(55).year} so far."


def test_back_strong_shows_the_score_only_at_or_above_the_average(make_world, sun, run, headline):
    world = make_world().series(1, 0, [30] * 5).round(1, sun(40), 31)
    world.series(2, 0, [30] * 5).round(2, sun(40), 25)
    fr = world.frames()
    facts = {f.subject_id: f for f in run("pf.back-strong", fr)}
    months = round((sun(40) - sun(4)).days / 30.44)
    assert facts["1"].variant == "score"
    assert headline("pf.back-strong", facts["1"], fr) == (
        f"Welcome back, Pat Shooter1, after {months} months, with a 31."
    )
    assert facts["2"].variant == ""
    assert "score" not in facts["2"].params


def test_tied_best_needs_a_best_three_over_the_average(make_world, sun, run):
    scores = [40] * 6 + [41] * 5 + [42] + [42]  # 12 earlier rounds, best 42 < mean + 3
    fr = make_world().series(1, 0, scores).round(1, sun(13), 42).frames()
    assert run("pf.tied-best", fr) == []


def test_wins_profile_needs_two_wins_and_the_career_first_needs_a_field_of_fifteen(
    make_world, sun, run
):
    world = make_world()
    for i in range(10):
        world.round(1, sun(i), 45 if i == 9 else 30).crowd(sun(i), [35, 36])
    fr = world.frames()
    assert [f for f in run("pf.wins", fr) if f.variant == PROFILE] == []
    small = make_world().series(1, 0, [30] * 8).round(1, sun(8), 49)
    small.crowd(sun(8), [20, 21])  # field of 3
    anchored = [f for f in run("pf.wins", small.frames()) if f.anchor_date is not None]
    assert [f for f in anchored if f.subject_id == "1"] == []


def test_sunday_milestone_to_go_needs_a_recent_shoot(make_world, sun, run):
    world = make_world().series(1, 0, [30] * 23)
    fr = world.frames()
    assert [f.subject_id for f in run("pf.sunday-milestone", fr) if f.variant == "to_go"] == ["1"]
    world.round(2, sun(200), 30)  # the field moves on; shooter 1 is long gone
    fr = world.frames()
    assert [f for f in run("pf.sunday-milestone", fr) if f.variant == "to_go"] == []


# --- pf.first-tier --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("new", "level", "strength"), [(41, 40, 1.0), (46, 45, 1.5), (48, 48, 2.0)], ids=str
)
def test_first_tier_names_the_highest_mark_passed(
    make_world, sun, run, headline, new, level, strength
):
    fr = make_world().series(1, 0, [36] * 10 + [new]).frames()
    (fact,) = run("pf.first-tier", fr)
    assert (fact.params["level"], fact.params["score"], fact.strength) == (level, new, strength)
    assert fact.pages == frozenset({Page.PROFILE})
    assert headline("pf.first-tier", fact, fr).startswith(
        f"Pat Shooter1 broke {level} for the first time: {new}"
    )


@pytest.mark.parametrize(
    "scores",
    [[36] * 9 + [41], [36] * 5 + [40] + [36] * 4 + [42]],
    ids=["under 10 rounds", "not a first"],
)
def test_first_tier_is_silent_outside_its_guard(make_world, sun, run, scores):
    assert run("pf.first-tier", make_world().series(1, 0, scores).frames()) == []


# --- pf.first-since -------------------------------------------------------------------------


def beaten(make_world, sun, scores):
    """Shooter 1's scores, with a 49 and three 30s every Sunday (no wins or podium runs)."""
    world = make_world().series(1, 0, scores)
    for i in range(len(scores)):
        world.crowd(sun(i), [49, 49, 49, 30, 30, 30])
    return world.frames()


def test_first_since_needs_a_year_and_fifteen_rounds_away(make_world, sun, run, headline):
    scores = [45, 36, 45] + [36] * 52 + [46]
    fr = beaten(make_world, sun, scores)
    (fact,) = [f for f in run("pf.first-since", fr) if f.anchor_date == sun(len(scores) - 1)]
    assert (fact.variant, fact.params["level"], fact.params["last"]) == ("score", 45, sun(2))
    assert fact.strength == (sun(len(scores) - 1) - sun(2)).days / 365
    assert headline("pf.first-since", fact, fr).startswith("First round of 45 or better since")


@pytest.mark.parametrize(
    "scores",
    [[36, 36, 45] + [36] * 52 + [46], [45, 36, 45] + [36] * 48 + [46]],
    ids=["reached only once before", "under a year away"],
)
def test_first_since_is_silent_outside_its_guard(make_world, sun, run, scores):
    fr = beaten(make_world, sun, scores)
    assert [f for f in run("pf.first-since", fr) if f.anchor_date == sun(len(scores) - 1)] == []


# --- pf.career-first ------------------------------------------------------------------------


def placed(world, day, place, field=15):
    world.round(1, day, 40).crowd(day, [45] * (place - 1) + [30] * (field - place))


@pytest.mark.parametrize(
    ("place", "variant"), [(3, "podium"), (5, "top_third"), (1, None), (6, None)], ids=str
)
def test_career_first_podium_or_top_third(make_world, sun, run, headline, place, variant):
    world = make_world()
    for i in range(8):
        placed(world, sun(i), 12)
    placed(world, sun(8), place)
    fr = world.frames()
    facts = [f for f in run("pf.career-first", fr) if f.subject_id == "1"]
    if variant is None:
        assert facts == []
        return
    (fact,) = facts
    assert (fact.variant, fact.params["rank"], fact.params["n"]) == (variant, place, 15)
    if variant == "podium":
        assert headline("pf.career-first", fact, fr) == (
            "First podium of Pat Shooter1's career: 3rd of 15."
        )


def test_career_first_needs_eight_earlier_rounds(make_world, sun, run):
    world = make_world()
    for i in range(7):
        placed(world, sun(i), 12)
    placed(world, sun(7), 3)
    assert [f for f in run("pf.career-first", world.frames()) if f.subject_id == "1"] == []


def test_first_since_needs_a_full_field_today_but_counts_any_field_in_history(make_world, sun, run):
    """The reported Sunday needs 15 shooters; earlier podiums count in fields of any size."""

    def result(weeks):
        """weeks: (place, field) per Sunday for shooter 1; returns the podium facts on the last."""
        world = make_world()
        for i, (place, field) in enumerate(weeks):
            day = sun(0) + timedelta(weeks=i)
            world.round(1, day, 40).crowd(day, [45] * (place - 1) + [30] * (field - place))
        last = sun(0) + timedelta(weeks=len(weeks) - 1)
        return [
            f
            for f in run("pf.first-since", world.frames())
            if f.anchor_date == last and f.variant == "podium"
        ]

    away = [(8, 15)] * 52
    (fact,) = result([(2, 15), (2, 15), *away, (2, 15)])  # control: a real first since
    assert fact.params["last"] == sun(1)
    assert result([(2, 15), (2, 15), *away, (2, 6)]) == []  # today's field is too small
    mid = [(8, 15)] * 26 + [(2, 6)] + [(8, 15)] * 25
    assert result([(2, 15), (2, 15), *mid, (2, 15)]) == []  # a 6-shooter podium in between counts


def test_sunday_counts_include_special_sundays(make_world, sun, run):
    world = make_world()
    for i in range(24):
        world.crowd(sun(i), [30]).round(1, sun(i), 30)
    world.special(1, sun(24))  # Sunday 25 is special: no anchored milestone (Decision 11)
    world.crowd(sun(25), [30]).round(1, sun(25), 30)
    fr = world.frames()

    assert fr.histories[1][-1].k == 26
    assert fr.appearances_through(1, sun(25)) == 26
    assert fr.specials_through(1, sun(25)) == (sun(24),)
    assert not [f for f in run("pf.sunday-milestone", fr) if f.subject_id == "1" and f.anchor_date]


def test_the_sundays_to_go_count_a_special_sunday_after_the_last_round(make_world, sun, run):
    world = make_world()
    for i in range(22):
        world.crowd(sun(i), [30]).round(1, sun(i), 30)
    world.special(1, sun(22))
    world.crowd(sun(23), [30])  # the latest Sunday; shooter 1 missed it
    fr = world.frames()

    (fact,) = [
        f for f in run("pf.sunday-milestone", fr) if f.subject_id == "1" and f.variant == "to_go"
    ]
    assert (fact.params["next"], fact.params["to_go"]) == (25, 2)


def test_the_sunday_milestone_club_count_includes_a_milestone_reached_on_a_special_sunday(
    make_world, sun, run
):
    world = make_world()
    for i in range(24):
        world.crowd(sun(i), [30]).round(2, sun(i), 30).round(1, sun(i), 30)
    world.special(2, sun(24))  # shooter 2's 25th Sunday is the special one
    world.crowd(sun(25), [30]).round(1, sun(25), 30)  # shooter 1's 25th is a week later
    fr = world.frames()

    (fact,) = [
        f
        for f in run("pf.sunday-milestone", fr)
        if f.subject_id == "1" and f.anchor_date == sun(25)
    ]
    assert fact.params["club"] == 2
    assert fact.variant != "first"
