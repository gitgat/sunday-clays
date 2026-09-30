"""Peak kinds (spec §2.2.1): stretches, averages, rating highs, learning curve, bests."""

from datetime import date, timedelta
from statistics import mean, median

import pytest

from sunday_clays.analytics.insights import peaks  # noqa: F401 - registers the kinds

FIELD = [30, 30]


def scored(make_world, sun, scores, *, sid=1, start=0):
    world = make_world()
    for j, score in enumerate(scores):
        day = sun(start + j)
        world.round(sid, day, score).crowd(day, FIELD)
    return world


# --- pf.best-stretch ------------------------------------------------------------------------


def test_best_stretch_fires_when_last_ten_beat_every_earlier_ten(make_world, sun, run, headline):
    scores = [34] * 25 + [38] * 5 + [40] * 5
    fr = scored(make_world, sun, scores).frames()
    facts = run("pf.best-stretch", fr, [sun(len(scores) - 1)])
    (fact,) = facts
    now = mean(scores[-10:])
    assert fact.params["avg"] == round(now, 1)
    assert fact.params["start"] == sun(len(scores) - 10)
    assert fact.strength == pytest.approx((now - mean(scores)) / 2)
    assert headline("pf.best-stretch", fact, fr).endswith(f"{now:.1f} a round.")


@pytest.mark.parametrize(
    "scores",
    [
        [30] * 19 + [40] * 10,  # 29 rounds: only the minimum-rounds guard trips
        [30] * 20 + [40] * 11,  # now == earlier best: only the over-best guard trips
        [36] * 29 + [40],  # 36.4 vs earlier 36.0, career 36.13: only over-career trips
    ],
    ids=["under 30 rounds", "not above the earlier best by 0.3", "under 2 over the career mean"],
)
def test_best_stretch_is_silent_outside_its_guard(make_world, sun, run, scores):
    fr = scored(make_world, sun, scores).frames()
    assert run("pf.best-stretch", fr, [sun(len(scores) - 1)]) == []


def test_best_stretch_fires_at_exactly_thirty_rounds(make_world, sun, run):
    scores = [30] * 20 + [40] * 10  # the firing twin of the 29-round case above
    fr = scored(make_world, sun, scores).frames()
    assert len(run("pf.best-stretch", fr, [sun(len(scores) - 1)])) == 1


# --- pf.average-milestone -------------------------------------------------------------------


def test_average_milestone_fires_on_the_first_crossing(make_world, sun, run, headline):
    scores = [34] * 20 + [36] * 10
    fr = scored(make_world, sun, scores).frames()
    facts = run("pf.average-milestone", fr)
    rolling = [mean(scores[j - 19 : j + 1]) for j in range(19, len(scores))]
    first = next(j for j, r in enumerate(rolling) if r >= 35) + 19
    (fact,) = facts
    assert fact.anchor_date == sun(first)
    assert fact.params["level"] == 35
    assert fact.params["avg"] == round(rolling[first - 19], 1)
    assert fact.strength == 1.25
    assert "went over 35 for the first time" in headline("pf.average-milestone", fact, fr)


def test_average_milestone_needs_a_gain_on_a_year_ago(make_world, sun, run):
    # rolling 20 sits at 34.95 for a year, crosses to 35.0 at week 80: a gain of 0.05, under 1
    scores = ([34] + [35] * 19) * 4 + [35]
    fr = scored(make_world, sun, scores).frames()
    assert run("pf.average-milestone", fr) == []


# --- pf.rating-high -------------------------------------------------------------------------


def rated(make_world, sun, mus):
    world = scored(make_world, sun, [35] * len(mus))
    for i, mu in enumerate(mus):
        world.rating(1, sun(i), mu)
    return world.frames()


def test_rating_high_quotes_the_rise_over_eight_sundays(make_world, sun, run):
    mus = [30.0] * 10 + [30.0 + 0.1 * k for k in range(1, 9)]
    (fact,) = run("pf.rating-high", rated(make_world, sun, mus))
    assert fact.params["rise"] == round(mus[-1] - mus[-9], 1)
    assert fact.params["day"] == sun(len(mus) - 1)


@pytest.mark.parametrize(
    "mus",
    [
        [30.0] * 10 + [30.0 + 0.05 * k for k in range(1, 9)],
        [31.0] + [30.0] * 9 + [30.0 + 0.1 * k for k in range(1, 9)],
        [30.0] * 5 + [30.0 + 0.1 * k for k in range(1, 9)],
    ],
    ids=["rise under 0.5", "not the highest ever", "under 15 rated Sundays"],
)
def test_rating_high_is_silent_outside_its_guard(make_world, sun, run, mus):
    assert run("pf.rating-high", rated(make_world, sun, mus)) == []


def test_rating_high_is_silent_when_they_have_not_shot_in_eight_weeks(make_world, sun, run):
    mus = [30.0] * 10 + [30.0 + 0.1 * k for k in range(1, 9)]
    world = scored(make_world, sun, [35] * len(mus))
    for i, mu in enumerate(mus):
        world.rating(1, sun(i), mu)
    for k in range(len(mus), len(mus) + 9):  # someone else keeps the club going
        world.round(2, sun(k), 30).crowd(sun(k), FIELD)
    assert run("pf.rating-high", world.frames()) == []


# --- pf.learning-curve ----------------------------------------------------------------------


def test_learning_curve_compares_first_ten_with_the_club_line(make_world, sun, run):
    world = make_world()
    for i in range(10):
        day = sun(i)
        world.round(1, day, 38).round(2, day, 30).round(3, day, 32).crowd(day, FIELD)
    fr = world.frames()
    facts = {f.subject_id: f for f in run("pf.learning-curve", fr)}
    own = mean(d.adjusted for d in fr.histories[1][:10])
    at_k = [[h[k].adjusted for h in fr.histories.values() if len(h) > k] for k in range(10)]
    club = mean(median(values) for values in at_k)
    assert set(facts) == {"1"}
    assert facts["1"].params["own"] == round(own, 1)
    assert facts["1"].params["club"] == round(club, 1)


def test_learning_curve_skips_shooters_whose_start_predates_our_records(make_world, sun, run):
    world = make_world().shooter(1, censored=True)
    for i in range(10):
        world.round(1, sun(i), 38).round(2, sun(i), 30).crowd(sun(i), FIELD)
    assert run("pf.learning-curve", world.frames()) == []


def test_learning_curve_is_silent_after_forty_sundays(make_world, sun, run):
    world = make_world()
    for i in range(41):
        day = sun(i)
        world.round(1, day, 38 if i < 10 else 30).round(2, day, 30).crowd(day, FIELD)
    assert run("pf.learning-curve", world.frames()) == []


def test_learning_curve_is_silent_before_ten_sundays(make_world, sun, run):
    world = make_world()
    for i in range(9):
        world.round(1, sun(i), 38).round(2, sun(i), 30).crowd(sun(i), FIELD)
    assert run("pf.learning-curve", world.frames()) == []


# --- pf.season-best -------------------------------------------------------------------------


def year_world(make_world, scores, first=date(2025, 1, 5)):
    world = make_world()
    for j, score in enumerate(scores):
        day = first + timedelta(weeks=j)
        world.round(1, day, score).crowd(day, FIELD)
    return world.frames()


def test_season_best_names_this_years_best_when_it_is_not_a_pb(make_world, run, headline):
    world = make_world()  # a 45 in 2024 keeps this year's 40 from being a PB
    for j, score in enumerate([45] * 6):
        world.round(1, date(2024, 1, 7) + timedelta(weeks=j), score)
    for j, score in enumerate([34] * 6 + [40, 34]):
        world.round(1, date(2025, 1, 5) + timedelta(weeks=j), score)
    fr = world.frames()
    (fact,) = run("pf.season-best", fr)
    assert (fact.params["best"], fact.params["year"]) == (40, 2025)
    assert fact.params["day"] == date(2025, 1, 5) + timedelta(weeks=6)
    assert headline("pf.season-best", fact, fr).startswith("Best round of 2025 so far")


def test_season_best_stays_silent_when_the_best_is_a_pb(make_world, run):
    fr = year_world(make_world, [34] * 6 + [40, 34])
    assert run("pf.season-best", fr) == []


def season_world(make_world, scores):
    world = make_world()  # a 2024 run of 45s keeps every 2025 best from being a PB
    for j in range(6):
        world.round(1, date(2024, 1, 7) + timedelta(weeks=j), 45)
    for j, score in enumerate(scores):
        day = date(2025, 1, 5) + timedelta(weeks=j)
        world.round(1, day, score).crowd(day, FIELD)
    return world.frames()


@pytest.mark.parametrize(
    "scores",
    [
        [34] * 3 + [40],  # 4 rounds this year
        [40] + [34] * 11,  # the best was 11 Sundays ago
        [34] * 7 + [36, 34],  # best 36 is under the average (34.2) + 3
        [40] + [34] * 10 + [40],  # tied best: the earlier date counts, and that is not recent
    ],
    ids=["under 5 rounds", "not recent", "under 3 over the average", "tie keeps earliest date"],
)
def test_season_best_is_silent_outside_its_guard(make_world, run, scores):
    assert run("pf.season-best", season_world(make_world, scores)) == []


def test_season_best_fires_at_five_rounds(make_world, run):
    assert len(run("pf.season-best", season_world(make_world, [34] * 4 + [40]))) == 1


# --- pf.best-day-vs-field -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("best", "variant"), [(41, ""), (37, "fallback"), (35, None)], ids=["main", "fallback", "none"]
)
def test_best_day_vs_field_main_and_fallback(make_world, sun, run, best, variant):
    fr = scored(make_world, sun, [32] * 5 + [best] + [32] * 3).frames()
    facts = run("pf.best-day-vs-field", fr)
    if variant is None:
        assert facts == []
        return
    (fact,) = facts
    gap = max(d.adjusted for d in fr.histories[1])
    assert fact.variant == variant
    assert fact.params["best"] == round(gap, 1)
    assert fact.params["day"] == sun(5)


def test_best_day_vs_field_is_silent_without_field_days(make_world, sun, run):
    world = make_world()
    for j in range(6):  # rained out: no held Sunday, so no field median to compare with
        world.sunday(sun(j), held=False).round(1, sun(j), 40).crowd(sun(j), FIELD)
    world.crowd(sun(6), [30] * 12)  # a later full Sunday keeps the club (and as_of) moving
    assert run("pf.best-day-vs-field", world.frames()) == []
