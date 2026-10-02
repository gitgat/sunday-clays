"""Plan 11 Task 4: pure Year in Review and On this day rules (no database)."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from sunday_clays.analytics.yir import (
    EventStat,
    MonthStat,
    PbDay,
    ShooterMonth,
    ShooterTotals,
    TopRound,
    Winner,
    YearTotals,
    YirFrames,
    club_year,
    filter_round_types,
    on_this_day,
    pb_days,
    scored_years,
    shooter_year,
)
from sunday_clays.domain.round_type import RoundType

A1, A2 = date(2024, 11, 3), date(2024, 12, 1)
B1, B2, B3, B4, B5 = (
    date(2025, 1, 5),
    date(2025, 1, 19),
    date(2025, 2, 2),
    date(2025, 3, 2),
    date(2025, 9, 28),
)
NAMES = {1: "Able, Al", 2: "Baker, Bo", 3: "Slocum, Cy", 4: "Dunn, Di"}
NAN = math.nan


def _world(
    rounds: list[tuple[date, int, int, bool, float]],
    events: list[tuple[date, bool, bool, float, float, float]],
    *,
    censored: frozenset[int] = frozenset(),
    trophies: tuple[tuple[int, str, date], ...] = (),
    history: tuple[tuple[int, date, float], ...] = (),
    super_days: frozenset[date] = frozenset(),
) -> YirFrames:
    """rounds: (date, shooter, score, is_best, rank).

    events: (date, has_scores, held, head_count, median, difficulty).
    """
    r = pd.DataFrame(
        rounds, columns=["event_date", "shooter_id", "score", "is_best_round", "event_rank"]
    )
    r["display_name"] = r["shooter_id"].map(NAMES)
    r["round_type"] = ["super_sporting" if d in super_days else "sporting" for d in r["event_date"]]
    counts = r.groupby("event_date")["shooter_id"].nunique()
    tops = r.groupby("event_date")["score"].max()
    e = pd.DataFrame(
        events,
        columns=[
            "event_date",
            "has_scores",
            "results_complete",
            "head_count",
            "median",
            "difficulty",
        ],
    )
    e["round_type"] = ["super_sporting" if d in super_days else "sporting" for d in e["event_date"]]
    e["n_shooters"] = [float(counts.get(d, 0)) for d in e["event_date"]]
    e["top_score"] = [float(tops.get(d, NAN)) for d in e["event_date"]]
    profiles = pd.DataFrame(
        [(s, n, s in censored) for s, n in NAMES.items()],
        columns=["shooter_id", "display_name", "left_censored"],
    )
    return YirFrames(
        rounds=r,
        events=e,
        profiles=profiles,
        trophies=pd.DataFrame(list(trophies), columns=["shooter_id", "code", "event_date"]),
        history=pd.DataFrame(list(history), columns=["shooter_id", "event_date", "mu"]),
    )


ROUNDS = [
    (A1, 1, 40, True, 1.0),
    (A1, 4, 35, True, 2.0),
    (A2, 1, 42, True, 1.0),
    (A2, 4, 30, True, 2.0),
    (B1, 1, 44, True, 2.0),
    (B1, 2, 45, True, 1.0),
    (B2, 1, 46, True, 1.0),
    (B2, 1, 41, False, NAN),  # shooter 1's second round that day
    (B2, 2, 46, True, 1.0),
    (B2, 3, 30, True, 3.0),
    (B4, 1, 50, True, 1.0),
    (B5, 2, 39, True, 1.0),
    (B5, 3, 39, True, 1.0),
]
EVENTS = [
    (A1, True, True, 12.0, 37.5, 0.2),
    (A2, True, True, 10.0, 36.0, 0.1),
    (B1, True, True, 20.0, 44.5, 1.5),
    (B2, True, True, 25.0, 43.5, -0.5),
    (B3, False, False, 9.0, NAN, NAN),  # attendance only
    (B4, True, False, 30.0, 50.0, 9.9),  # 1 shooter vs head count 30: not held
    (B5, True, True, NAN, 39.0, 1.5),
]
TROPHIES = (
    (1, "events:1", A1),
    (2, "events:1", B1),
    (2, "first_win", B1),
    (3, "events:1", B2),
    (1, "doubleheader", B2),
)
HISTORY = (
    (1, A1, 31.0),
    (1, A2, 32.0),
    (1, B1, 33.5),
    (1, B2, 34.0),
    (1, B4, 34.0),
    (4, A1, 29.0),
    (4, A2, 28.5),
)
WORLD = _world(ROUNDS, EVENTS, censored=frozenset({3}), trophies=TROPHIES, history=HISTORY)


def test_club_year_totals_and_highlights() -> None:
    year = club_year(WORLD, 2025)
    # 9 rounds: 44+45 + 46+41+46+30 + 50 + 39+39 = 380
    assert year.totals == YearTotals(2025, 4, 3, 9, 3, 450, 380, pytest.approx(380 / 9))
    assert (year.events, year.perfect_rounds, year.trophies) == (5, 1, 4)
    assert year.top_rounds == (TopRound(1, "Able, Al", B4, 50),)
    assert year.mean_head_count == 21.0  # (20 + 25 + 9 + 30) / 4
    assert year.busiest == EventStat(B4, 30.0)
    # B4 (9.9) is not held; B1 and B5 tie at 1.5 -> the earlier date
    assert (year.hardest, year.easiest) == (EventStat(B1, 1.5), EventStat(B2, -0.5))
    assert year.months[0] == MonthStat(1, 2, 6, 42.0)
    assert year.months[1] == MonthStat(2, 0, 0, None)
    assert (year.months[2], year.months[8]) == (MonthStat(3, 1, 1, 50.0), MonthStat(9, 1, 2, 39.0))
    assert year.previous == YearTotals(2024, 2, 2, 4, 2, 200, 147, 36.75)


def test_club_year_counts_newcomers_but_not_left_censored() -> None:
    assert club_year(WORLD, 2025).newcomers == 1  # Baker; Slocum is left-censored
    uncensored = replace(WORLD, profiles=WORLD.profiles.assign(left_censored=False))
    assert club_year(uncensored, 2025).newcomers == 2


def test_club_year_without_data_before_it_has_no_previous() -> None:
    year = club_year(WORLD, 2024)
    assert year.previous is None
    assert year.totals.scored_events == 2


def test_club_year_without_events_is_empty() -> None:
    year = club_year(WORLD, 2023)
    assert year.totals == YearTotals(2023, 0, 0, 0, 0, 0, 0, None)
    assert (year.events, year.newcomers, year.perfect_rounds, year.top_rounds) == (0, 0, 0, ())
    assert (year.mean_head_count, year.busiest, year.hardest, year.easiest) == (
        None,
        None,
        None,
        None,
    )
    assert year.months[0] == MonthStat(1, 0, 0, None)


def test_club_year_no_leak() -> None:
    later_rounds = [
        *ROUNDS,
        (date(2026, 1, 4), 2, 50, True, 1.0),
        (date(2026, 1, 4), 9, 20, True, 2.0),
    ]
    later_events = [*EVENTS, (date(2026, 1, 4), True, True, 40.0, 35.0, -3.0)]
    names = {**NAMES, 9: "Zed, Zo"}
    grown = _world(
        later_rounds, later_events, censored=frozenset({3}), trophies=TROPHIES, history=HISTORY
    )
    grown = replace(
        grown, rounds=grown.rounds.assign(display_name=grown.rounds["shooter_id"].map(names))
    )
    assert club_year(grown, 2025) == club_year(WORLD, 2025)


def test_pb_days_once_per_day_after_five_rounds() -> None:
    rounds = pd.DataFrame(
        {
            "event_date": [A1, A2, B1, B2, B2, B4, B5, B5],
            "score": [40, 42, 44, 46, 41, 50, 49, 50],
        }
    )
    # B2 (46) has only 3 earlier rounds; B4 (50) has 5; B5 ties the 50 and is not a PB.
    assert pb_days(rounds) == (PbDay(B4, 50),)


def test_shooter_year_summary() -> None:
    year = shooter_year(WORLD, 1, 2025)
    assert year.totals == ShooterTotals(2025, 3, 4, 200, 181, 45.25)
    assert year.best == TopRound(1, "Able, Al", B4, 50)
    assert (year.wins, year.podiums, year.best_finish) == (2, 3, 1)
    assert year.pbs == (PbDay(B4, 50),)
    assert year.trophies == 1
    assert (year.rating_start, year.rating_end) == (32.0, 34.0)
    assert (year.attendance_rank, year.n_shooters) == (1, 3)  # 3 events, tied with Baker
    assert year.months[0] == ShooterMonth(1, 3, pytest.approx(131 / 3), 42.0)
    assert year.months[8] == ShooterMonth(9, 0, None, 39.0)
    assert year.previous == ShooterTotals(2024, 2, 2, 100, 82, 41.0)


def test_shooter_year_attendance_rank_is_min_rank() -> None:
    assert shooter_year(WORLD, 3, 2025).attendance_rank == 3  # 2 events; Able and Baker have 3


def test_shooter_year_without_rounds_that_year() -> None:
    year = shooter_year(WORLD, 4, 2025)
    assert year.totals == ShooterTotals(2025, 0, 0, 0, 0, None)
    assert (year.best, year.wins, year.podiums, year.best_finish, year.pbs, year.trophies) == (
        None,
        0,
        0,
        None,
        (),
        0,
    )
    assert (year.rating_start, year.rating_end, year.attendance_rank) == (28.5, 28.5, None)
    assert year.months[0] == ShooterMonth(1, 0, None, 42.0)
    assert year.previous == ShooterTotals(2024, 2, 2, 100, 65, 32.5)


def test_shooter_year_no_leak() -> None:
    later = [*ROUNDS, (date(2026, 1, 4), 1, 50, True, 1.0)]
    grown = _world(
        later,
        [*EVENTS, (date(2026, 1, 4), True, True, 10.0, 50.0, 0.0)],
        censored=frozenset({3}),
        trophies=(*TROPHIES, (1, "events:10", date(2026, 1, 4))),
        history=(*HISTORY, (1, date(2026, 1, 4), 36.0)),
    )
    assert shooter_year(grown, 1, 2025) == shooter_year(WORLD, 1, 2025)


OTD_ROUNDS = [
    (date(2025, 9, 28), 2, 45, True, 1.0),
    (date(2025, 9, 28), 1, 41, True, 2.0),
    (date(2024, 9, 29), 3, 40, True, 1.0),
    (date(2024, 9, 29), 1, 40, True, 1.0),
    (date(2024, 9, 29), 2, 40, True, 1.0),
    (date(2024, 9, 29), 4, 31, True, 4.0),
    (date(2023, 9, 24), 4, 47, True, 1.0),
    (date(2023, 9, 30), 1, 49, True, 1.0),
]
OTD_EVENTS = [
    (date(2025, 9, 28), True, True, 23.0, 43.0, 0.0),
    (date(2024, 9, 29), True, True, 25.0, 40.0, 0.0),
    (date(2023, 9, 24), True, True, 30.0, 47.0, 0.0),
    (date(2023, 9, 30), True, True, 12.0, 49.0, 0.0),
    (date(2025, 3, 2), False, False, 9.0, NAN, NAN),
    (date(2027, 2, 28), True, True, 18.0, 35.0, 0.0),
]
OTD = _world(OTD_ROUNDS, OTD_EVENTS)


def test_on_this_day_lists_all_tied_winners() -> None:
    items = on_this_day(OTD, date(2026, 9, 27))
    assert [(i.years_ago, i.event_date) for i in items] == [
        (1, date(2025, 9, 28)),
        (2, date(2024, 9, 29)),
        (
            3,
            date(2023, 9, 24),
        ),  # 2023-09-27 is 3 days from both the 24th and the 30th: earlier wins
    ]
    assert items[0].winners == (Winner(2, "Baker, Bo", 45),)
    assert items[1].winners == (
        Winner(1, "Able, Al", 40),
        Winner(2, "Baker, Bo", 40),
        Winner(3, "Slocum, Cy", 40),
    )
    assert (items[1].head_count, items[1].n_shooters, items[1].top_score, items[1].median) == (
        25,
        4,
        40,
        40.0,
    )


def test_on_this_day_keeps_attendance_only_and_skips_empty_years() -> None:
    (item,) = on_this_day(OTD, date(2026, 3, 1))
    assert (item.years_ago, item.event_date, item.has_scores) == (1, date(2025, 3, 2), False)
    assert (item.head_count, item.n_shooters, item.top_score, item.median, item.winners) == (
        9,
        0,
        None,
        None,
        (),
    )


def test_on_this_day_maps_feb_29_to_feb_28() -> None:
    items = on_this_day(OTD, date(2028, 2, 29))
    # 1 year back: 2027-02-28; 2 years: nothing near 2026-02-28; 3 years: 2025-03-02 is 2 days away
    assert [(i.years_ago, i.event_date) for i in items] == [
        (1, date(2027, 2, 28)),
        (3, date(2025, 3, 2)),
    ]


def test_on_this_day_no_leak() -> None:
    grown = _world(
        [*OTD_ROUNDS, (date(2026, 9, 27), 1, 50, True, 1.0)],
        [*OTD_EVENTS, (date(2026, 9, 27), True, True, 5.0, 50.0, 0.0)],
    )
    assert on_this_day(grown, date(2026, 9, 27)) == on_this_day(OTD, date(2026, 9, 27))


def test_scored_years_ignore_attendance_only_years() -> None:
    only_attendance = _world(ROUNDS, [*EVENTS, (date(2018, 12, 30), False, False, 7.0, NAN, NAN)])
    assert scored_years(only_attendance) == [2024, 2025]


def test_filter_round_types_keeps_only_matching_rounds_events_and_trophies() -> None:
    world = _world(ROUNDS, EVENTS, trophies=TROPHIES, history=HISTORY, super_days=frozenset({B1}))
    only = filter_round_types(world, [RoundType.SUPER_SPORTING])
    assert set(only.rounds["event_date"]) == {B1}
    assert list(only.events["event_date"]) == [B1]
    assert list(only.trophies["event_date"]) == [B1, B1]
    assert only.profiles is world.profiles
    club = club_year(only, 2025)
    assert (club.events, club.totals.rounds, club.perfect_rounds) == (1, 2, 0)
    assert [m.rounds for m in club.months][:2] == [2, 0]
    assert club.trophies == 2
    assert shooter_year(only, 1, 2025).totals.rounds == 1
    # the year picker is taken from the unfiltered world
    assert scored_years(world) == [2024, 2025]


def test_filter_round_types_empty_selection_is_no_filter() -> None:
    world = _world(ROUNDS, EVENTS, super_days=frozenset({B1}))
    assert filter_round_types(world, []) is world


def test_special_sundays_count_as_sundays_but_never_as_rounds_in_the_year() -> None:
    special_day = date(2025, 2, 9)
    events = pd.concat(
        [
            WORLD.events.assign(kind="regular"),
            pd.DataFrame(
                [
                    {
                        "event_date": special_day,
                        "has_scores": True,
                        "results_complete": True,
                        "head_count": NAN,
                        "median": NAN,
                        "difficulty": NAN,
                        "round_type": "sporting",
                        "n_shooters": 2.0,
                        "top_score": NAN,
                        "kind": "special",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    regular = WORLD.rounds[["event_date", "shooter_id", "round_type"]].drop_duplicates()
    extra = pd.DataFrame(
        [(special_day, 1, "sporting"), (special_day, 4, "sporting")],
        columns=["event_date", "shooter_id", "round_type"],
    )
    data = replace(WORLD, events=events, appearances=pd.concat([regular, extra], ignore_index=True))

    base, club = club_year(WORLD, 2025), club_year(data, 2025)
    assert club.totals.held_events == base.totals.held_events + 1
    assert club.totals.scored_events == base.totals.scored_events
    assert club.totals.shooters == base.totals.shooters + 1  # shooter 4's only 2025 Sunday
    assert (club.totals.rounds, club.totals.clays_thrown, club.totals.avg_score) == (
        base.totals.rounds,
        base.totals.clays_thrown,
        base.totals.avg_score,
    )
    assert club.events == base.events + 1
    assert club.months[1].events == base.months[1].events + 1
    assert club.months[1].rounds == base.months[1].rounds
    assert club.newcomers == base.newcomers
    mine, before = shooter_year(data, 1, 2025), shooter_year(WORLD, 1, 2025)
    assert mine.totals.events == before.totals.events + 1
    assert (mine.totals.rounds, mine.totals.clays_broken) == (
        before.totals.rounds,
        before.totals.clays_broken,
    )
    assert on_this_day(data, date(2026, 2, 9)) == on_this_day(WORLD, date(2026, 2, 9))
    assert scored_years(data) == scored_years(WORLD)


def test_a_year_with_only_a_special_sunday_is_not_a_scored_year() -> None:
    special_day = date(2031, 3, 2)
    special = pd.DataFrame(
        [
            {
                "event_date": special_day,
                "has_scores": True,
                "results_complete": True,
                "head_count": NAN,
                "median": NAN,
                "difficulty": NAN,
                "round_type": "sporting",
                "n_shooters": 2.0,
                "top_score": NAN,
                "kind": "special",
            }
        ]
    )
    data = replace(WORLD, events=pd.concat([WORLD.events.assign(kind="regular"), special]))

    assert scored_years(data) == scored_years(WORLD)
    assert 2031 not in scored_years(data)
