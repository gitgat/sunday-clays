"""Shooter score kinds leave thrown-out Sundays out (T5b)."""

from __future__ import annotations

import pytest

from sunday_clays.analytics.insights import (  # noqa: F401 - registers the kinds
    attendance,
    club,
    community,
    conditions,
    form,
    journeys,
    milestones,
    peaks,
    race,
    recap,
    records,
    registry,
    season,
    stations,
    streaks,
    tiers,
)
from sunday_clays.analytics.insights.club import _difficulty_split
from sunday_clays.analytics.insights.milestones import is_pb
from sunday_clays.analytics.insights.stations import entries_to
from sunday_clays.analytics.insights.sunday import first_rounds_before
from sunday_clays.analytics.insights.templates import (
    THROWN_OUT_RECAP_HOW,
    THROWN_OUT_ROUNDS_HOW,
    THROWN_OUT_STATION_HOW,
    plain,
    render,
)

ROUNDS_HOW: dict[str, tuple[str, ...]] = {
    "pf.pb": ("", "profile", "rollup"),
    "pf.tied-best": ("", "rollup"),
    "pf.first-tier": ("",),
    "pf.first-since": ("score",),
    "pf.back-strong": ("score",),
    "pf.best-stretch": ("", "rollup"),
    "pf.average-milestone": ("", "rollup"),
    "pf.season-best": ("",),
    "pf.best-day-vs-field": ("",),
    "pf.rating-high": ("",),
    "pf.learning-curve": ("",),
    "pf.hot-form": ("",),
    "pf.beat-own-usual": ("", "rollup"),
    "pf.up-on-usual": ("",),
    "pf.year-up": ("",),
    "pf.years-up-run": ("",),
    "pf.gaining-on-field": ("two_years", "career"),
    "pf.wet-strength": ("",),
    "pf.weather-steady": ("",),
    "pf.best-temp": ("",),
    "pf.tough-days": ("",),
    "pf.beat-field-streak": ("", "rollup"),
    "pf.above-own-avg-streak": ("", "rollup"),
    "pf.tier-run": ("", "rollup"),
    "pf.three-rising": ("", "rollup"),
    "pf.high-round-count": ("", "rollup"),
    "pf.more-high-rounds": ("", "rollup"),
    "pf.low-end-rising": ("",),
    "pf.year-wrapped": ("",),
    "lb.most-improved": ("",),
    "pf.rank-climb": ("",),
    "pf.top-of-club": ("",),
    "cl.rain-scores": ("",),
    "cl.weather-scoreboard": ("",),
    "cl.club-one-shooter": ("",),
    "rec.drought-clock": ("",),
    "ev.drought-ended": ("",),
    "rec.perfect-rarity": ("",),
    "ev.spotlight": ("",),
    "ev.rain-day": ("",),
    "ev.how-it-played": ("",),
    "ev.toughest-since": ("",),
    "ev.week-jump": ("",),
    "ev.record-watch": ("",),
    "ev.top-score": ("",),
    "ev.new-faces": ("strong",),
}
STATION_HOW: dict[str, tuple[str, ...]] = {"st.hardest-easiest": ("",), "pf.station-best": ("",)}


@pytest.mark.parametrize(("kind_id", "variants"), sorted(ROUNDS_HOW.items()))
def test_score_kinds_say_thrown_out_sundays_are_left_out(kind_id, variants):
    for v in variants:
        assert registry.get(kind_id).how[v][-1] is THROWN_OUT_ROUNDS_HOW


def test_count_variants_do_not_claim_the_rounds_line():
    assert THROWN_OUT_ROUNDS_HOW not in registry.get("pf.first-since").how[""]
    assert THROWN_OUT_ROUNDS_HOW not in registry.get("pf.back-strong").how[""]
    assert (
        registry.get("pf.first-since").how["score"][:-1] == registry.get("pf.first-since").how[""]
    )


def test_pb_skips_a_thrown_out_sunday_and_beats_only_scored_rounds(make_world, sun, run):
    fr = (
        make_world()
        .series(1, 0, [30, 31, 32, 33, 34, 50, 40])
        .sunday(sun(5), stats_excluded=True)
        .frames()
    )
    facts = [f for f in run("pf.pb", fr) if f.variant == ""]
    assert [
        (f.anchor_date, f.params["new"], f.params["old"], f.params["old_date"]) for f in facts
    ] == [(sun(6), 40, 34, sun(4))]
    assert is_pb(fr.histories[1][5]) is False


def test_first_tier_compares_with_the_best_scored_round(make_world, sun, run):
    fr = (
        make_world()
        .series(1, 0, [30] * 10 + [45, 41])
        .sunday(sun(10), stats_excluded=True)
        .frames()
    )
    assert [(f.anchor_date, f.params["level"]) for f in run("pf.first-tier", fr)] == [(sun(11), 40)]


def test_three_rising_skips_the_thrown_out_sunday_without_breaking(make_world, sun, run):
    fr = (
        make_world()
        .series(1, 0, [30] * 20 + [31, 20, 33, 36])
        .sunday(sun(21), stats_excluded=True)
        .frames()
    )
    facts = [f for f in run("pf.three-rising", fr) if f.variant == ""]
    assert [
        (f.anchor_date, f.params["a"], f.params["b"], f.params["c"], f.params["d2"]) for f in facts
    ] == [(sun(23), 31, 33, 36, sun(22))]


def test_year_wrapped_counts_every_sunday_but_best_is_scored_only(make_world, sun, run):
    scores = [30] * 49
    scores[20] = 49
    (fact,) = run(
        "pf.year-wrapped",
        make_world().series(1, 0, scores).sunday(sun(20), stats_excluded=True).frames(),
    )
    assert (fact.params["sundays"], fact.params["targets"], fact.params["best"]) == (49, 1489, 30)


@pytest.mark.parametrize(("kind_id", "variants"), sorted(STATION_HOW.items()))
def test_station_kinds_say_a_thrown_out_station_is_left_out(kind_id, variants):
    for v in variants:
        assert registry.get(kind_id).how[v][-1] is THROWN_OUT_STATION_HOW


def test_new_faces_welcome_keeps_no_rounds_line():
    assert THROWN_OUT_ROUNDS_HOW not in registry.get("ev.new-faces").how[""]


def test_record_watch_skips_a_thrown_out_top(make_world, sun, run):
    fr = (
        make_world()
        .crowd(sun(0), [46, 40])
        .crowd(sun(1), [50, 40])
        .crowd(sun(2), [48, 40])
        .sunday(sun(1), stats_excluded=True)
        .frames()
    )
    assert [(f.anchor_date, f.variant, f.params["record"]) for f in run("ev.record-watch", fr)] == [
        (sun(2), "new", 46)
    ]


def test_drought_wait_runs_through_a_thrown_out_49(make_world, sun, run):
    w = make_world()
    for i in range(21):
        w.crowd(sun(i), [{0: 49, 10: 50, 20: 49}.get(i, 40), 35])
    fr = w.sunday(sun(10), stats_excluded=True).frames()
    assert [(f.anchor_date, f.params["last"]) for f in run("ev.drought-ended", fr)] == [
        (sun(20), sun(0))
    ]


def test_how_it_played_says_nothing_on_a_thrown_out_sunday(make_world, sun, run):
    fr = (
        make_world()
        .crowd(sun(0), [40, 30])
        .sunday(sun(0), difficulty=4.0, stats_excluded=True)
        .frames()
    )
    assert run("ev.how-it-played", fr) == []


def test_first_rounds_pool_leaves_out_a_thrown_out_first_sunday(make_world, sun):
    w = (
        make_world()
        .round(1, sun(0), 30)
        .round(2, sun(9), 45)
        .round(3, sun(10), 20)
        .round(1, sun(11), 30)
    )
    assert first_rounds_before(w.sunday(sun(9), stats_excluded=True).frames(), sun(11)) == [20]


def test_club_one_shooter_average_leaves_out_thrown_out_rounds(make_world, sun, run):
    (fact,) = run(
        "cl.club-one-shooter",
        make_world()
        .series(1, 0, [40, 40, 40, 50, 40, 40])
        .sunday(sun(3), stats_excluded=True)
        .frames(),
    )
    assert (fact.params["avg"], fact.params["n"]) == (40.0, 1)


def test_perfect_rarity_counts_scored_rounds_only(make_world, sun, run):
    w = make_world().round(1, sun(0), 50).round(2, sun(1), 50).round(1, sun(2), 40)
    (fact,) = run("rec.perfect-rarity", w.sunday(sun(1), stats_excluded=True).frames())
    assert (fact.params["perfect"], fact.params["rounds"]) == (1, 2)


def test_rain_split_leaves_out_a_thrown_out_sunday(make_world, sun):
    w = make_world().crowd(sun(0), [40]).crowd(sun(1), [40])
    w.sunday(sun(0), difficulty=1.0, precip_in=0.3)
    w.sunday(sun(1), difficulty=5.0, precip_in=0.3, stats_excluded=True)
    assert _difficulty_split(w.frames().sundays, "precip_band", "wet") == ([1.0], [])


def test_station_entries_leave_out_a_dropped_station(make_world, sun):
    w = make_world().round(1, sun(0), 40)
    w.station(1, sun(0), 11, 7, target_count=7, dropped=True)
    w.station(1, sun(0), 3, 5, target_count=7)
    assert entries_to(w.frames(), sun(0))["station_label"].tolist() == ["3"]


def test_the_sunday_recap_discloses_a_thrown_out_sunday(make_world, sun, run):
    w = make_world().crowd(sun(0), [45, 40, 35, 30]).sunday(sun(0), temp_f=60.0, gust_mph=5.0)
    plain_fact = [f for f in run("home.sunday-recap", w.frames()) if f.anchor_date == sun(0)]
    assert plain_fact
    assert "x" not in plain_fact[0].variant
    (fact,) = [
        f
        for f in run("home.sunday-recap", w.sunday(sun(0), stats_excluded=True).frames())
        if f.anchor_date == sun(0)
    ]
    assert fact.variant == plain_fact[0].variant.replace("p", "") + "x"
    kind = registry.get("home.sunday-recap")
    assert kind.how[fact.variant][-1] is THROWN_OUT_RECAP_HOW
    assert THROWN_OUT_RECAP_HOW not in kind.how.get(plain_fact[0].variant, kind.how[""])
    assert "*" not in plain(render(kind.templates[fact.variant][0], fact.params, {}))


COUNT_KINDS = (
    "ev.close-finish",
    "ev.new-faces",
    "pf.targets-milestone",
    "pf.wins",
    "pf.podium-run",
)


@pytest.fixture
def count_world(make_world, sun):
    """sun(24) has a close finish (49, 48, 48), one first-timer, a shooter crossing 1,000
    clays broken, a first win for a shooter with 11 earlier rounds and a third podium in a row."""
    k = 24
    w = make_world()
    for i in range(k + 1):
        for sid in range(1, 18):
            score = 30
            if sid == 3:
                score = 40
            elif sid in (10, 11, 12):
                score = {10: 45, 11: 44, 12: 43}[sid]
            elif sid == 2 and i < 14:
                continue
            elif sid == 1 and i >= 22:
                score = 46
            if i == k and sid == 1:
                score = 48
            if i == k and sid == 10:
                score = 48
            if i == k and sid == 2:
                score = 49
            w.round(sid, sun(i), score)
    w.round(99, sun(k), 20)
    w.k = k
    return w


@pytest.mark.parametrize("kind_id", COUNT_KINDS)
def test_count_kinds_still_anchor_on_a_thrown_out_sunday(kind_id, count_world, sun, run):
    k = count_world.k
    assert sun(k) in {f.anchor_date for f in run(kind_id, count_world.frames())}
    facts = [
        f
        for f in run(kind_id, count_world.sunday(sun(k), stats_excluded=True).frames())
        if f.anchor_date == sun(k)
    ]
    assert facts
    if kind_id == "ev.new-faces":
        assert {f.variant for f in facts} == {"welcome"}
