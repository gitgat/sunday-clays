"""The recap-only fact generator ("This week" candidates, 2026-10-11): one test group per type.

Every world is synthetic with invented names. Each type has: it emits when notable (with its exact
wording), it is silent when not, and (generic tests at the bottom) nothing it says leaks data from
after the Sunday, the same call always gives the same facts, and every sentence passes the
outsider lint.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pytest

from sunday_clays.analytics import club_milestones as cm
from sunday_clays.analytics.insights.context import InsightFrames
from sunday_clays.analytics.recap_facts import FACT_TYPES, RecapFact, week_facts
from sunday_clays.analytics.recap_insights import recap_text_problems

PRONOUNS = re.compile(r"\b(he|she|his|her|hers|him)\b|\bclass(es)?\b", re.IGNORECASE)
FIRST = date(2024, 1, 7)  # a Sunday


def wk(start: date, i: int) -> date:
    return start + timedelta(weeks=i)


def by_type(fr: InsightFrames, day: date, *, club_next: bool = True) -> dict[str, list[RecapFact]]:
    out: dict[str, list[RecapFact]] = {}
    for fact in week_facts(fr, day, club_next=club_next):
        out.setdefault(fact.type, []).append(fact)
    return out


def texts(fr: InsightFrames, day: date, kind: str, *, club_next: bool = True) -> list[str]:
    return [f.text for f in by_type(fr, day, club_next=club_next).get(kind, [])]


def weekly(
    make_world: Any,
    n: int,
    *,
    start: date = FIRST,
    event: Callable[[int], dict[str, Any]] | None = None,
    score: Callable[[int], int] | None = None,
    crowd: Callable[[int], int] | None = None,
    skip: frozenset[int] = frozenset(),
) -> Any:
    """`n` weekly Sundays from `start`; a crowd of filler shooters each (new ids every week)."""
    world = make_world()
    for i in range(n):
        if i in skip:
            continue
        day = wk(start, i)
        world.crowd(day, [score(i) if score else 40] * (crowd(i) if crowd else 3))
        world.sunday(day, **(event(i) if event else {}))
    return world


# --- turnout -------------------------------------------------------------------------------------


def heads(**by_week: int) -> Callable[[int], dict[str, Any]]:
    values = {int(k[1:]): v for k, v in by_week.items()}
    return lambda i: {"head_count": values.get(i, 20)}


def test_turnout_biggest_crowd_in_at_least_eight_weeks_names_the_last_bigger_month(
    make_world: Any,
) -> None:
    fr = weekly(make_world, 12, event=heads(w0=40, w11=35)).frames()
    assert texts(fr, wk(FIRST, 11), "turnout") == [
        "35 came out, the biggest crowd since January 2024."
    ]


def test_turnout_is_silent_when_a_bigger_crowd_came_inside_eight_weeks(make_world: Any) -> None:
    fr = weekly(make_world, 13, event=heads(w5=40, w12=35)).frames()  # 7 weeks back
    assert texts(fr, wk(FIRST, 12), "turnout") == []


def test_turnout_boundary_is_exactly_eight_weeks(make_world: Any) -> None:
    fr = weekly(make_world, 13, event=heads(w4=40, w12=35)).frames()  # 8 weeks back
    assert texts(fr, wk(FIRST, 12), "turnout") == [
        "35 came out, the biggest crowd since February 2024."
    ]


def test_turnout_an_equal_crowd_counts_as_not_beaten(make_world: Any) -> None:
    fr = weekly(make_world, 13, event=heads(w0=35, w12=35)).frames()
    assert texts(fr, wk(FIRST, 12), "turnout") == [
        "35 came out, the biggest crowd since January 2024."
    ]


def test_turnout_never_says_a_small_crowd(make_world: Any) -> None:
    fr = weekly(make_world, 12, event=heads(w0=40, w11=5)).frames()
    assert texts(fr, wk(FIRST, 11), "turnout") == []


def test_turnout_needs_a_history_to_call_a_record(make_world: Any) -> None:
    fr = weekly(make_world, 5, event=heads(w4=35)).frames()  # "the biggest ever" of 5 Sundays
    assert texts(fr, wk(FIRST, 4), "turnout") == []


def test_turnout_biggest_ever_says_on_record(make_world: Any) -> None:
    fr = weekly(make_world, 30, event=heads(w29=50)).frames()
    assert texts(fr, wk(FIRST, 29), "turnout") == ["50 came out, the biggest crowd on record."]


def test_turnout_falls_back_to_shooters_without_a_head_count(make_world: Any) -> None:
    fr = weekly(make_world, 30, crowd=lambda i: 10 if i == 0 else 8 if i == 29 else 3).frames()
    assert texts(fr, wk(FIRST, 29), "turnout") == [
        "8 came out, the biggest crowd since January 2024."
    ]


OCT_START = date(2022, 10, 2)
OCT_D = date(2025, 10, 5)
OCT_N = (OCT_D - OCT_START).days // 7 + 1


def october_world(make_world: Any, *, prior: int, big: int = 60) -> Any:
    """Weekly crowds of 20 from Oct 2022; Octobers of 2022-24 at `prior`; a crowd of `big` three
    weeks before D (so no 'since' claim is available); D's crowd is 45."""

    def event(i: int) -> dict[str, Any]:
        day = wk(OCT_START, i)
        if day == OCT_D:
            return {"head_count": 45}
        if day == OCT_D - timedelta(weeks=3):
            return {"head_count": big}
        return {"head_count": prior if day.month == 10 else 20}

    return weekly(make_world, OCT_N, start=OCT_START, event=event)


def test_turnout_biggest_october_on_record_over_at_least_two_years(make_world: Any) -> None:
    fr = october_world(make_world, prior=30).frames()
    assert texts(fr, OCT_D, "turnout") == ["45 came out, the biggest October Sunday on record."]


def test_turnout_not_a_month_record_when_an_earlier_october_was_bigger(make_world: Any) -> None:
    fr = october_world(make_world, prior=50).frames()
    assert texts(fr, OCT_D, "turnout") == []


# --- course: round type and stations -------------------------------------------------------------


def types(**by_week: str) -> Callable[[int], dict[str, Any]]:
    values = {int(k[1:]): v for k, v in by_week.items()}
    return lambda i: {
        "round_type": values.get(i, "sporting"),
        "round_type_source": "none" if values.get(i) == "unknown" else "stations",
    }


def test_course_type_first_of_its_kind_since_a_month(make_world: Any) -> None:
    fr = weekly(make_world, 11, event=types(w2="super_sporting", w10="super_sporting")).frames()
    assert texts(fr, wk(FIRST, 10), "course_type") == [
        "The first super sporting course since January 2024."
    ]


def test_course_type_silent_when_the_type_changed_back_inside_eight_weeks(make_world: Any) -> None:
    # super sporting at week 3, sporting at 4-9, super sporting again at 10: seven weeks apart
    fr = weekly(make_world, 11, event=types(w3="super_sporting", w10="super_sporting")).frames()
    assert texts(fr, wk(FIRST, 10), "course_type") == []
    fr = weekly(make_world, 11, event=types(w2="super_sporting", w10="super_sporting")).frames()
    assert len(texts(fr, wk(FIRST, 10), "course_type")) == 1  # eight weeks apart is enough


def test_course_type_first_ever_says_on_record(make_world: Any) -> None:
    fr = weekly(make_world, 27, event=types(w26="super_sporting")).frames()
    assert texts(fr, wk(FIRST, 26), "course_type") == ["The first super sporting course on record."]
    short = weekly(make_world, 11, event=types(w10="super_sporting")).frames()
    assert texts(short, wk(FIRST, 10), "course_type") == []  # too little history for 'on record'


def test_course_type_going_back_to_sporting(make_world: Any) -> None:
    ev = types(**{f"w{i}": "super_sporting" for i in range(2, 10)})
    fr = weekly(make_world, 11, event=ev).frames()
    assert texts(fr, wk(FIRST, 10), "course_type") == [
        "The first sporting course since January 2024."
    ]


def test_course_type_silent_when_the_type_did_not_change(make_world: Any) -> None:
    fr = weekly(make_world, 11, event=types(w9="super_sporting", w10="super_sporting")).frames()
    assert texts(fr, wk(FIRST, 10), "course_type") == []


def test_course_type_compares_with_the_last_known_type_and_skips_an_unknown_day(
    make_world: Any,
) -> None:
    ev = types(w25="unknown", w26="super_sporting")
    fr = weekly(make_world, 27, event=ev).frames()
    # week 25 has no known type, so week 24 (sporting) is the one compared with
    assert texts(fr, wk(FIRST, 26), "course_type") == ["The first super sporting course on record."]


def test_course_type_silent_when_today_has_no_known_type(make_world: Any) -> None:
    fr = weekly(make_world, 11, event=types(w10="unknown")).frames()
    assert texts(fr, wk(FIRST, 10), "course_type") == []


def test_course_type_silent_without_enough_history(make_world: Any) -> None:
    fr = weekly(make_world, 4, event=types(w3="super_sporting")).frames()
    assert texts(fr, wk(FIRST, 3), "course_type") == []


def add_entry(world: Any, day: date, sid: int, row: int, hits: list[int], target: int = 16) -> None:
    for station, h in enumerate(hits, start=1):
        world.station(sid, day, station, h, entry_row=row, target_count=target)


def stations_world(make_world: Any, per_station: dict[int, list[int]], n_entries: int = 10) -> Any:
    """One Sunday; `per_station[no]` is the hits of each of `n_entries` shooters at station `no`."""
    world = weekly(make_world, 1)
    for no, hits in per_station.items():
        for entry, h in enumerate(hits[:n_entries], start=1):
            world.station(entry, FIRST, no, h, entry_row=entry, target_count=16)
    return world


def test_course_stations_toughest_and_easiest(make_world: Any) -> None:
    # station 3: nine entries of 10 and one of 8 = 98/160 = 61%; station 7: 150/160 = 94%
    fr = stations_world(make_world, {3: [10] * 9 + [8], 5: [13] * 10, 7: [15] * 10}).frames()
    assert texts(fr, FIRST, "course_stations") == [
        "Toughest station: Station 3, 61% of targets broken. Easiest: Station 7, 94%."
    ]


def test_course_stations_silent_without_station_sheets(make_world: Any) -> None:
    assert texts(weekly(make_world, 1).frames(), FIRST, "course_stations") == []


def test_course_stations_silent_when_the_spread_is_small(make_world: Any) -> None:
    fr = stations_world(make_world, {3: [12] * 10, 7: [13] * 10}).frames()
    assert texts(fr, FIRST, "course_stations") == []


def test_course_stations_silent_with_a_single_station_or_thin_entries(make_world: Any) -> None:
    assert texts(stations_world(make_world, {3: [5] * 10}).frames(), FIRST, "course_stations") == []
    thin = stations_world(make_world, {3: [4] * 3, 7: [16] * 10}).frames()  # station 3: 3 entries
    assert texts(thin, FIRST, "course_stations") == []


def test_course_stations_keep_a_lettered_station_label(make_world: Any) -> None:
    world = weekly(make_world, 1)
    for entry in range(1, 11):
        world.station(entry, FIRST, "7A", 4, entry_row=entry, target_count=16)
        world.station(entry, FIRST, 8, 15, entry_row=entry, target_count=16)
    assert texts(world.frames(), FIRST, "course_stations") == [
        "Toughest station: Station 7A, 25% of targets broken. Easiest: Station 8, 94%."
    ]


# --- scores_context ------------------------------------------------------------------------------


def medians(by_day: Callable[[date], int | None], start: date, n: int) -> Any:
    return lambda make_world: weekly(
        make_world, n, start=start, score=lambda i: by_day(wk(start, i)) or 30
    )


def test_scores_context_best_for_the_month_in_two_years(make_world: Any) -> None:
    def score(day: date) -> int | None:
        if day == OCT_D:
            return 37
        if day.month == 10:
            return {2022: 38, 2023: 36, 2024: 35}[day.year]
        return None

    fr = medians(score, OCT_START, OCT_N)(make_world).frames()
    assert texts(fr, OCT_D, "scores_context") == [
        "The middle score of 37 was the highest for an October Sunday since 2022."
    ]


def test_scores_context_best_in_twelve_weeks(make_world: Any) -> None:
    fr = medians(
        lambda d: 38 if d == wk(FIRST, 5) else 37 if d == wk(FIRST, 25) else None, FIRST, 26
    )(make_world).frames()
    assert texts(fr, wk(FIRST, 25), "scores_context") == [
        "The middle score of 37 was the highest since February 2024."
    ]


def test_scores_context_silent_when_a_better_day_is_inside_twelve_weeks(make_world: Any) -> None:
    fr = medians(
        lambda d: 38 if d == wk(FIRST, 15) else 37 if d == wk(FIRST, 25) else None, FIRST, 26
    )(make_world).frames()
    assert texts(fr, wk(FIRST, 25), "scores_context") == []


def test_scores_context_boundary_is_exactly_twelve_weeks(make_world: Any) -> None:
    fr = medians(
        lambda d: 38 if d == wk(FIRST, 13) else 37 if d == wk(FIRST, 25) else None, FIRST, 26
    )(make_world).frames()
    assert len(texts(fr, wk(FIRST, 25), "scores_context")) == 1


def test_scores_context_silent_when_not_the_best_even_for_the_month(make_world: Any) -> None:
    def score(day: date) -> int | None:
        if day == OCT_D:
            return 37
        # last October was better (inside two years) and so was a Sunday three weeks ago
        return 38 if day in (date(2024, 10, 6), date(2025, 9, 14)) else None

    fr = medians(score, OCT_START, OCT_N)(make_world).frames()
    assert texts(fr, OCT_D, "scores_context") == []


def test_scores_context_month_claim_needs_two_years_of_that_month(make_world: Any) -> None:
    start, day = date(2024, 10, 6), date(2025, 10, 5)  # only one year of Octobers behind it
    n = (day - start).days // 7 + 1
    fr = medians(lambda d: 37 if d == day else 36 if d.month == 10 else None, start, n)(
        make_world
    ).frames()
    # the month claim is unavailable; the 12-week claim is the only one left
    assert all("October" not in t for t in texts(fr, day, "scores_context"))


# --- weather -------------------------------------------------------------------------------------


def weather(**by_week: dict[str, float]) -> Callable[[int], dict[str, Any]]:
    values = {int(k[1:]): v for k, v in by_week.items()}
    return lambda i: {"temp_f": 70.0, "gust_mph": 5.0, "precip_in": 0.0, **values.get(i, {})}


def test_weather_coldest_since(make_world: Any) -> None:
    ev = weather(w3={"temp_f": 45.0}, w14={"temp_f": 49.0})
    fr = weekly(make_world, 15, event=ev).frames()
    assert texts(fr, wk(FIRST, 14), "weather") == ["The coldest Sunday since January 2024: 49 °F."]


def test_weather_hottest_since(make_world: Any) -> None:
    ev = weather(w3={"temp_f": 95.0}, w14={"temp_f": 91.0})
    fr = weekly(make_world, 15, event=ev).frames()
    assert texts(fr, wk(FIRST, 14), "weather") == ["The hottest Sunday since January 2024: 91 °F."]


def test_weather_windiest_since(make_world: Any) -> None:
    ev = weather(w3={"gust_mph": 30.0}, w14={"gust_mph": 24.0})
    fr = weekly(make_world, 15, event=ev).frames()
    assert texts(fr, wk(FIRST, 14), "weather") == [
        "The windiest Sunday since January 2024: gusts up to 24 mph."
    ]


def test_weather_first_wet_sunday_since(make_world: Any) -> None:
    ev = weather(w3={"precip_in": 0.3}, w14={"precip_in": 0.25})
    fr = weekly(make_world, 15, event=ev).frames()
    assert texts(fr, wk(FIRST, 14), "weather") == ["The first wet Sunday since January 2024."]


def test_weather_silent_when_the_extreme_was_matched_inside_eight_weeks(make_world: Any) -> None:
    ev = weather(w9={"temp_f": 45.0}, w14={"temp_f": 49.0})
    assert texts(weekly(make_world, 15, event=ev).frames(), wk(FIRST, 14), "weather") == []


def test_weather_silent_for_an_ordinary_cool_day(make_world: Any) -> None:
    ev = weather(w3={"temp_f": 40.0}, w14={"temp_f": 60.0})  # coldest in months, but not cold
    assert texts(weekly(make_world, 15, event=ev).frames(), wk(FIRST, 14), "weather") == []


def test_weather_skips_silently_without_a_weather_row(make_world: Any) -> None:
    fr = weekly(make_world, 15, event=lambda i: {}).frames()
    assert texts(fr, wk(FIRST, 14), "weather") == []


def test_weather_wet_boundary_is_the_site_wet_threshold(make_world: Any) -> None:
    ev = weather(w3={"precip_in": 0.02}, w14={"precip_in": 0.019})
    assert texts(weekly(make_world, 15, event=ev).frames(), wk(FIRST, 14), "weather") == []


# --- on_this_day ---------------------------------------------------------------------------------


def a_year_back(make_world: Any, skip: frozenset[int] = frozenset()) -> Any:
    def event(i: int) -> dict[str, Any]:
        return {"head_count": 28 if i == 8 else 30 if i in (7, 9) else 20}

    return weekly(
        make_world, 61, event=event, score=lambda i: 46 if i == 8 else 40, skip=skip
    ).frames()


def test_on_this_day_names_the_sunday_a_year_earlier(make_world: Any) -> None:
    assert texts(a_year_back(make_world), wk(FIRST, 60), "on_this_day") == [
        "A year ago this week: 28 shooters, top score 46."
    ]


def test_on_this_day_uses_the_nearest_sunday_within_a_week(make_world: Any) -> None:
    fr = a_year_back(make_world, skip=frozenset({7, 8}))
    assert texts(fr, wk(FIRST, 60), "on_this_day") == [
        "A year ago this week: 30 shooters, top score 40."
    ]


def test_on_this_day_silent_when_nothing_was_held_around_then(make_world: Any) -> None:
    fr = a_year_back(make_world, skip=frozenset({7, 8, 9}))
    assert texts(fr, wk(FIRST, 60), "on_this_day") == []
    assert texts(a_year_back(make_world), wk(FIRST, 20), "on_this_day") == []


# --- year_so_far ---------------------------------------------------------------------------------


Y_START = date(2023, 1, 1)  # a Sunday, and 2023 has 53 of them


def year_world(make_world: Any, per_2024: int) -> Any:
    last = date(2024, 12, 29)
    n = (last - Y_START).days // 7 + 1
    return weekly(
        make_world, n, start=Y_START, crowd=lambda i: 3 if wk(Y_START, i).year == 2023 else per_2024
    ).frames()


def test_year_so_far_passed_all_of_last_year(make_world: Any) -> None:
    # 2023: 53 Sundays x 3 = 159 rounds. 2024 at 4 a Sunday passes it on the 40th (160).
    fr = year_world(make_world, 4)
    assert texts(fr, date(2024, 10, 6), "year_so_far") == [
        "2024 so far: 160 rounds over 40 Sundays, already more than all of 2023 (159 rounds)."
    ]
    assert texts(fr, date(2024, 10, 13), "year_so_far") == []  # the crossing is a one-day story
    assert texts(fr, date(2024, 9, 29), "year_so_far") == []


def test_year_so_far_round_number_crossed_today(make_world: Any) -> None:
    # at 7 a Sunday, 2024 reaches 252 rounds on the 36th Sunday (245 the week before)
    fr = year_world(make_world, 7)
    assert texts(fr, date(2024, 9, 8), "year_so_far") == [
        "2024 so far: 252 rounds over 36 Sundays, past the 250-round mark."
    ]
    assert texts(fr, date(2024, 9, 15), "year_so_far") == []
    assert texts(fr, date(2024, 7, 21), "year_so_far") == []  # 203: a hundred is not news


def test_year_so_far_passing_last_year_comes_before_the_round_number(make_world: Any) -> None:
    # 7 a Sunday passes 2023's 159 rounds on the 23rd Sunday (161)
    fr = year_world(make_world, 7)
    assert texts(fr, date(2024, 6, 9), "year_so_far") == [
        "2024 so far: 161 rounds over 23 Sundays, already more than all of 2023 (159 rounds)."
    ]


def test_year_so_far_comparison_needs_a_full_earlier_year(make_world: Any) -> None:
    # 2024 starts the data: 40 a Sunday passes 2023's (empty) total on the first Sunday, but a
    # year the club did not play is no comparison
    fr = weekly(make_world, 20, crowd=lambda i: 40).frames()
    assert all("all of" not in t for i in range(20) for t in texts(fr, wk(FIRST, i), "year_so_far"))


# --- club_next -----------------------------------------------------------------------------------


def only_rounds(monkeypatch: pytest.MonkeyPatch, *marks: int) -> None:
    monkeypatch.setattr(
        cm,
        "THRESHOLDS",
        {"clays_thrown": (), "sundays_held": (), "shooters": (), "rounds": marks},
    )


def test_club_next_within_reach(make_world: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    only_rounds(monkeypatch, 40)
    fr = weekly(make_world, 12).frames()  # 36 rounds, 3 a Sunday
    assert texts(fr, wk(FIRST, 10), "club_next") == [  # 33 rounds: first within 9 of 40
        "7 more rounds and the club reaches 40 rounds shot all time."
    ]
    assert by_type(fr, wk(FIRST, 10))["club_next"][0].key == "rounds:40"


def test_club_next_says_each_milestone_once_when_it_first_comes_within_reach(
    make_world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    only_rounds(monkeypatch, 40)
    fr = weekly(make_world, 13).frames()
    assert texts(fr, wk(FIRST, 9), "club_next") == []  # 30 rounds: 10 away
    assert len(texts(fr, wk(FIRST, 10), "club_next")) == 1
    assert texts(fr, wk(FIRST, 11), "club_next") == []  # already said
    assert texts(fr, wk(FIRST, 12), "club_next") == []


def test_club_next_silent_when_far_away(make_world: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    only_rounds(monkeypatch, 100)
    assert texts(weekly(make_world, 12).frames(), wk(FIRST, 11), "club_next") == []


def test_club_next_boundary_is_three_typical_sundays(
    make_world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    fr = weekly(make_world, 12).frames()  # 36 rounds; a typical Sunday is 3
    only_rounds(monkeypatch, 45)  # 9 away = 3 x 3
    assert len(texts(fr, wk(FIRST, 11), "club_next")) == 1
    only_rounds(monkeypatch, 46)
    assert texts(fr, wk(FIRST, 11), "club_next") == []


def test_club_next_can_be_switched_off(make_world: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    only_rounds(monkeypatch, 40)
    fr = weekly(make_world, 12).frames()
    assert texts(fr, wk(FIRST, 10), "club_next", club_next=False) == []


def test_club_next_says_sundays_held(make_world: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cm,
        "THRESHOLDS",
        {"clays_thrown": (), "sundays_held": (13,), "shooters": (), "rounds": ()},
    )
    fr = weekly(make_world, 12).frames()
    assert texts(fr, wk(FIRST, 9), "club_next") == [
        "3 more Sundays and the club reaches 13 Sundays held all time."
    ]


# --- attendance_streak ---------------------------------------------------------------------------


def streak_world(make_world: Any, attended: dict[int, range], n: int = 30) -> Any:
    world = weekly(make_world, n)
    for sid, weeks in attended.items():
        world.shooter(sid, f"Hadley{sid}, Ike" if sid == 1 else f"Kaplan{sid}, Noel")
        for i in weeks:
            world.round(sid, wk(FIRST, i), 40)
    return world.frames()


def test_attendance_streak_at_a_multiple_of_ten(make_world: Any) -> None:
    fr = streak_world(make_world, {1: range(20, 30)})
    (fact,) = by_type(fr, wk(FIRST, 29))["attendance_streak"]
    assert fact.text == "Ike Hadley1 has come out 10 Sundays in a row."
    assert fact.named_ids == (1,)


def test_attendance_streak_silent_below_ten_or_between_tiers(make_world: Any) -> None:
    for weeks in (range(21, 30), range(19, 30)):  # 9, then 11 (not >= 12)
        fr = streak_world(make_world, {1: weeks})
        assert texts(fr, wk(FIRST, 29), "attendance_streak") == []


def test_attendance_streak_only_at_multiples_of_ten_even_for_the_clubs_longest(
    make_world: Any,
) -> None:
    for first in (15, 17, 16, 14):  # 15, 13, 14 and 16 in a row, each the club's longest
        fr = streak_world(make_world, {1: range(first, 30)})
        assert texts(fr, wk(FIRST, 29), "attendance_streak") == []
    fr = streak_world(make_world, {1: range(10, 30), 2: range(20, 30)})  # 20 and 10
    assert sorted(texts(fr, wk(FIRST, 29), "attendance_streak")) == [
        "Ike Hadley1 has come out 20 Sundays in a row.",
        "Noel Kaplan2 has come out 10 Sundays in a row.",
    ]


def test_attendance_streak_resets_when_a_week_is_missed(make_world: Any) -> None:
    fr = streak_world(make_world, {1: [*range(10, 25), *range(26, 30)]})
    assert texts(fr, wk(FIRST, 29), "attendance_streak") == []


def test_attendance_streak_counts_only_those_who_came_today(make_world: Any) -> None:
    fr = streak_world(make_world, {1: range(10, 29)})  # 19 in a row, missed the 30th Sunday
    assert texts(fr, wk(FIRST, 29), "attendance_streak") == []


def test_attendance_streak_wording_uses_sundays_in_a_row(make_world: Any) -> None:
    fr = streak_world(make_world, {1: range(0, 30)})
    (text,) = texts(fr, wk(FIRST, 29), "attendance_streak")
    assert text.endswith("30 Sundays in a row.")


# --- station_feats -------------------------------------------------------------------------------


def feats_world(make_world: Any) -> Any:
    world = weekly(make_world, 1)
    for sid in (1, 2, 3, 4):
        world.round(sid, FIRST, 40)
    world.shooter(1, "Hadley, Ike")
    clean, miss = 16, 5
    add_entry(world, FIRST, 1, 1, [clean, clean, clean, clean, clean, miss, miss])
    for sid in (2, 3, 4):
        add_entry(world, FIRST, sid, sid, [miss, miss, clean, miss, miss, miss, miss])
    return world


def test_station_feats_named_and_club_level(make_world: Any) -> None:
    fr = feats_world(make_world).frames()
    facts = by_type(fr, FIRST)["station_feats"]
    named = [f for f in facts if f.named_ids]
    club = [f for f in facts if not f.named_ids]
    assert [f.text for f in named] == ["Ike Hadley broke every target at 5 of 7 stations."]
    assert named[0].named_ids == (1,)
    assert [f.text for f in club] == ["4 shooters broke every target at Station 3."]


def test_station_feats_silent_below_four_stations_and_three_shooters(make_world: Any) -> None:
    world = weekly(make_world, 1)
    world.round(1, FIRST, 40).shooter(1, "Hadley, Ike")
    add_entry(world, FIRST, 1, 1, [16, 16, 16, 5, 5, 5, 5])  # only three cleaned
    add_entry(world, FIRST, 2, 2, [16, 5, 5, 5, 5, 5, 5])  # two shooters clean station 1
    assert texts(world.frames(), FIRST, "station_feats") == []


def test_station_feats_use_the_best_entry_of_a_shooter_with_two_rounds(make_world: Any) -> None:
    world = weekly(make_world, 1)
    world.round(1, FIRST, 40).shooter(1, "Hadley, Ike")
    add_entry(world, FIRST, 1, 1, [16, 16, 5, 5, 5, 5])
    add_entry(world, FIRST, 1, 2, [16, 16, 16, 16, 5, 5])
    assert texts(world.frames(), FIRST, "station_feats") == [
        "Ike Hadley broke every target at 4 of 6 stations."
    ]


def test_station_feats_say_a_lettered_station_plainly(make_world: Any) -> None:
    world = weekly(make_world, 1)
    for sid in (1, 2, 3):
        add_entry(world, FIRST, sid, sid, [5])
        world.station(sid, FIRST, "7A", 16, entry_row=sid, target_count=16)
    assert texts(world.frames(), FIRST, "station_feats") == [
        "3 shooters broke every target at Station 7A."
    ]


def test_station_feats_one_shooter_cleaned_is_not_a_crowd_and_unknown_shooters_are_skipped(
    make_world: Any,
) -> None:
    world = weekly(make_world, 1)
    for no in range(1, 6):
        world.station(None, FIRST, no, 16, entry_row=1, target_count=16)  # no shooter id
    assert texts(world.frames(), FIRST, "station_feats") == []


# --- improvement ---------------------------------------------------------------------------------


def climber(make_world: Any, n: int, then: int, now: int, *, since: int = 50) -> Any:
    world = weekly(make_world, n)
    world.shooter(1, "Hadley, Ike")
    for i in range(n):
        world.round(1, wk(FIRST, i), then if i < since else now)
    return world.frames()


def test_improvement_up_on_a_year_ago(make_world: Any) -> None:
    fr = climber(make_world, 120, 36, 40, since=100)
    assert texts(fr, wk(FIRST, 119), "improvement") == [
        "Ike Hadley's average over the last 20 rounds is up 4.0 targets compared with a year ago."
    ]
    assert by_type(fr, wk(FIRST, 119))["improvement"][0].named_ids == (1,)


def test_improvement_fires_when_the_gain_first_reaches_two_and_at_each_whole_target_after(
    make_world: Any,
) -> None:
    fr = climber(make_world, 120, 36, 40, since=100)  # +0.2 a Sunday from the 101st round on
    said = [i for i in range(100, 120) if texts(fr, wk(FIRST, i), "improvement")]
    assert said == [109, 114, 119]  # 2.0, 3.0, then 4.0 (3.8 the week before)


def test_improvement_boundary_is_two_targets(make_world: Any) -> None:
    assert (
        len(texts(climber(make_world, 120, 36, 38, since=100), wk(FIRST, 119), "improvement")) == 1
    )
    assert texts(climber(make_world, 120, 36, 37, since=100), wk(FIRST, 119), "improvement") == []


def test_improvement_needs_twenty_earlier_sundays(make_world: Any) -> None:
    fr = climber(make_world, 60, 36, 40, since=40)
    assert all(texts(fr, wk(FIRST, i), "improvement") == [] for i in range(60))


def test_improvement_needs_ten_sundays_in_the_last_year(make_world: Any) -> None:
    world = weekly(make_world, 80)
    world.shooter(1, "Hadley, Ike")
    for i in [*range(0, 20), *range(75, 80)]:
        world.round(1, wk(FIRST, i), 36 if i < 20 else 44)
    assert texts(world.frames(), wk(FIRST, 79), "improvement") == []


def test_improvement_never_says_a_drop(make_world: Any) -> None:
    assert texts(climber(make_world, 120, 40, 30, since=100), wk(FIRST, 119), "improvement") == []


def test_improvement_is_about_people_who_shot_today(make_world: Any) -> None:
    world = weekly(make_world, 120)
    world.shooter(1, "Hadley, Ike")
    for i in range(0, 119):
        world.round(1, wk(FIRST, i), 36 if i < 100 else 40)
    assert texts(world.frames(), wk(FIRST, 119), "improvement") == []


# --- coming_up -----------------------------------------------------------------------------------


def sunday_count_world(make_world: Any, k: int) -> Any:
    world = weekly(make_world, k)
    world.shooter(1, "Hadley, Ike")
    for i in range(k):
        world.round(1, wk(FIRST, i), 40)
    return world.frames()


def test_coming_up_names_the_next_round_number_when_one_away(make_world: Any) -> None:
    fr = sunday_count_world(make_world, 49)
    (fact,) = by_type(fr, wk(FIRST, 48))["coming_up"]
    assert fact.text == "Ike Hadley is 1 Sunday away from 50 Sundays at the club."
    assert fact.named_ids == (1,)


def test_coming_up_says_it_once_at_exactly_one_away(make_world: Any) -> None:
    for n in (46, 47, 48):  # 4, 3 and 2 away
        assert texts(sunday_count_world(make_world, n), wk(FIRST, n - 1), "coming_up") == []
    # the 50th is today: the Milestones section carries it
    assert texts(sunday_count_world(make_world, 50), wk(FIRST, 49), "coming_up") == []


def test_coming_up_has_no_article_to_get_wrong_for_800(make_world: Any) -> None:
    fr = sunday_count_world(make_world, 799)
    assert texts(fr, wk(FIRST, 798), "coming_up") == [
        "Ike Hadley is 1 Sunday away from 800 Sundays at the club."
    ]


def test_coming_up_counts_special_sundays_as_sundays(make_world: Any) -> None:
    world = weekly(make_world, 45)  # 45 regular Sundays, 4 specials among them: 49 shot
    world.shooter(1, "Hadley, Ike")
    for i in range(45):
        world.round(1, wk(FIRST, i), 40)
    for i in (5, 15, 25, 35):
        world.special(1, wk(FIRST, i) + timedelta(days=3), heads=30)
    fr = world.frames()
    assert texts(fr, wk(FIRST, 44), "coming_up") == [
        "Ike Hadley is 1 Sunday away from 50 Sundays at the club."
    ]


# --- generic: every type, no leak, determinism, lint ---------------------------------------------


@dataclass(frozen=True)
class Case:
    world: Any
    day: date
    type: str
    text: str


def case_turnout(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    fr = weekly(make_world, 12, event=heads(w0=40, w11=35)).frames()
    return Case(fr, wk(FIRST, 11), "turnout", "35 came out, the biggest crowd since January 2024.")


def case_course_type(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    fr = weekly(make_world, 27, event=types(w26="super_sporting")).frames()
    return Case(fr, wk(FIRST, 26), "course_type", "The first super sporting course on record.")


def case_course_stations(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    fr = stations_world(make_world, {3: [10] * 9 + [8], 5: [13] * 10, 7: [15] * 10}).frames()
    return Case(
        fr,
        FIRST,
        "course_stations",
        "Toughest station: Station 3, 61% of targets broken. Easiest: Station 7, 94%.",
    )


def case_scores(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    fr = medians(
        lambda d: 38 if d == wk(FIRST, 5) else 37 if d == wk(FIRST, 25) else None, FIRST, 26
    )(make_world).frames()
    return Case(
        fr,
        wk(FIRST, 25),
        "scores_context",
        "The middle score of 37 was the highest since February 2024.",
    )


def case_weather(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    ev = weather(w3={"temp_f": 45.0}, w14={"temp_f": 49.0})
    fr = weekly(make_world, 15, event=ev).frames()
    return Case(fr, wk(FIRST, 14), "weather", "The coldest Sunday since January 2024: 49 °F.")


def case_on_this_day(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    return Case(
        a_year_back(make_world),
        wk(FIRST, 60),
        "on_this_day",
        "A year ago this week: 28 shooters, top score 46.",
    )


def case_year(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    return Case(
        year_world(make_world, 7),
        date(2024, 9, 8),
        "year_so_far",
        "2024 so far: 252 rounds over 36 Sundays, past the 250-round mark.",
    )


def case_club_next(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    only_rounds(mp, 40)
    fr = weekly(make_world, 12).frames()
    return Case(
        fr,
        wk(FIRST, 10),
        "club_next",
        "7 more rounds and the club reaches 40 rounds shot all time.",
    )


def case_streak(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    fr = streak_world(make_world, {1: range(20, 30)})
    return Case(
        fr, wk(FIRST, 29), "attendance_streak", "Ike Hadley1 has come out 10 Sundays in a row."
    )


def case_feats(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    return Case(
        feats_world(make_world).frames(),
        FIRST,
        "station_feats",
        "Ike Hadley broke every target at 5 of 7 stations.",
    )


def case_improvement(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    return Case(
        climber(make_world, 120, 36, 40, since=100),
        wk(FIRST, 119),
        "improvement",
        "Ike Hadley's average over the last 20 rounds is up 4.0 targets compared with a year ago.",
    )


def case_coming_up(make_world: Any, mp: pytest.MonkeyPatch) -> Case:
    return Case(
        sunday_count_world(make_world, 49),
        wk(FIRST, 48),
        "coming_up",
        "Ike Hadley is 1 Sunday away from 50 Sundays at the club.",
    )


CASES = {
    "turnout": case_turnout,
    "course_type": case_course_type,
    "course_stations": case_course_stations,
    "scores_context": case_scores,
    "weather": case_weather,
    "on_this_day": case_on_this_day,
    "year_so_far": case_year,
    "club_next": case_club_next,
    "attendance_streak": case_streak,
    "station_feats": case_feats,
    "improvement": case_improvement,
    "coming_up": case_coming_up,
}


def test_the_case_list_covers_every_fact_type() -> None:
    assert set(CASES) == set(FACT_TYPES)
    assert len(FACT_TYPES) == 12  # the owner's 11, with `course` split into type and stations


@pytest.mark.parametrize("name", sorted(CASES))
def test_each_type_emits_its_fact_with_the_expected_sentence(
    name: str, make_world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = CASES[name](make_world, monkeypatch)
    found = by_type(case.world, case.day)
    assert case.text in [f.text for f in found.get(case.type, [])]
    assert all(f.strength > 0 for fs in found.values() for f in fs)


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_sentence_passes_the_outsider_lint_and_the_wording_rules(
    name: str, make_world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = CASES[name](make_world, monkeypatch)
    for fact in week_facts(case.world, case.day):
        # shooter names are not prose (a shooter surnamed Gold is not a banned word)
        prose = fact.text
        for sid in fact.named_ids:
            prose = prose.replace(case.world.names[sid], "")
        assert recap_text_problems(prose) == [], fact.text
        assert not PRONOUNS.search(fact.text), fact.text
        assert fact.type in FACT_TYPES


def with_extreme_later_sundays(world_cls: Any) -> Any:
    """A World that, when framed, first adds five record-setting Sundays after its last one: a huge
    crowd, top scores, a freezing gale, rain, a new course type and every station cleaned."""

    class Later(world_cls):  # type: ignore[misc]
        def frames(self) -> InsightFrames:
            last = max(r["event_date"] for r in self._rounds)
            for k in range(1, 6):
                day = last + timedelta(weeks=k)
                self.crowd(day, [49] * 12)
                self.round(1, day, 49).round(2, day, 49)
                self.sunday(
                    day,
                    head_count=99,
                    temp_f=5.0,
                    gust_mph=45.0,
                    precip_in=2.0,
                    round_type="super_sporting",
                    round_type_source="stations",
                )
                for entry in range(1, 13):
                    for no in range(1, 8):
                        self.station(entry, day, no, 16, entry_row=entry, target_count=16)
            return super().frames()  # type: ignore[no-any-return]

    return Later


@pytest.mark.parametrize("name", sorted(CASES))
def test_facts_are_deterministic_and_use_only_data_up_to_the_day(
    name: str, make_world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = CASES[name](make_world, monkeypatch)
    full = week_facts(case.world, case.day)
    assert case.text in [f.text for f in full]
    assert full == week_facts(case.world, case.day)
    assert full == week_facts(case.world.until(case.day), case.day)
    # and Sundays recorded afterwards, however extreme, change nothing about this one
    later = CASES[name](with_extreme_later_sundays(make_world), monkeypatch)
    assert later.world.as_of > case.day
    assert week_facts(later.world, case.day) == full


def test_appending_later_sundays_never_changes_an_earlier_days_facts(
    make_world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A property over a long busy world: every Sunday's facts equal the facts computed from the
    frames cut at that Sunday (all twelve types are in play somewhere along it)."""
    only_rounds(monkeypatch, 150, 300, 450)
    ev = {**{f"w{i}": 20 + (i * 7) % 15 for i in range(100)}, "w20": 44, "w60": 50}

    def event(i: int) -> dict[str, Any]:
        return {
            "head_count": ev.get(f"w{i}", 25),
            "temp_f": 90.0 if i % 23 == 5 else 40.0 if i % 31 == 9 else 65.0,
            "gust_mph": 25.0 if i % 17 == 3 else 6.0,
            "precip_in": 0.2 if i % 13 == 4 else 0.0,
            "round_type": "super_sporting" if i % 5 == 4 else "sporting",
            "round_type_source": "stations",
        }

    world = weekly(make_world, 110, event=event, score=lambda i: 35 + (i * 3) % 8)
    world.shooter(1, "Hadley, Ike")
    for i in range(110):
        world.round(1, wk(FIRST, i), 34 + i // 12)
        for no in range(1, 8):
            world.station(
                1, wk(FIRST, i), no, 16 if (i + no) % 3 else 9, entry_row=1, target_count=16
            )
    fr = world.frames()
    seen: set[str] = set()
    for i in range(60, 110):
        day = wk(FIRST, i)
        now = week_facts(fr, day)
        assert now == week_facts(fr.until(day), day), day
        seen.update(f.type for f in now)
    assert len(seen) >= 8, seen
