from collections.abc import Callable
from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import club_insights as ci

AS_OF = date(2026, 9, 27)
WEEKS = [AS_OF - timedelta(days=7 * k) for k in range(60)]  # WEEKS[0] = AS_OF


def test_regulars_core_needs_half_of_held_window(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    window = WEEKS[:10]  # 10 held events inside (as_of - 364d, as_of]
    specs = [(d, 1, 30) for d in window[:6]]  # 6/10 -> core
    specs += [(d, 2, 30) for d in window[:5]]  # 5/10 -> core (exactly 50%)
    specs += [(d, 3, 30) for d in window[:4]]  # 4/10 -> not core
    specs += [
        {"event_date": d, "shooter_id": 4, "score": 30, "shooter_status": "deceased"}
        for d in window
    ]
    specs += [(AS_OF - timedelta(days=364), 3, 30)]  # outside the window

    result = ci.regulars(make_rounds(specs), make_events(window), AS_OF)

    assert result.n_held_window == 10
    assert [(c.shooter_id, c.events_attended, c.share) for c in result.core] == [
        (1, 6, 0.6),
        (2, 5, 0.5),
    ]


def test_lapsed_regulars(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    # 8 held events in (as_of - 544d, as_of - 364d]: inside the as_of - 180d window only
    early = [AS_OF - timedelta(days=364 + 7 * k) for k in range(8)]
    events = make_events([*early, WEEKS[2]])
    specs = [(d, 5, 30) for d in early]  # regular then, silent since -> lapsed
    specs += [(d, 6, 30) for d in early] + [(WEEKS[2], 6, 30)]  # came back 14 days ago
    specs += [
        {"event_date": d, "shooter_id": 7, "score": 30, "shooter_status": "deceased"} for d in early
    ]

    result = ci.regulars(make_rounds(specs), events, AS_OF)

    assert [(x.shooter_id, x.last_event) for x in result.lapsed] == [(5, early[0])]
    assert [c.shooter_id for c in result.core] == [6]
    assert result.n_held_window == 1


EARLY = [AS_OF - timedelta(days=364 + 7 * k) for k in range(8)]  # core at as_of - 180d only


def test_a_shooter_can_be_core_and_lapsed(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    # D20: the two lists are independent. Shooter 1 shot every held event from 280 to
    # 105 days back (core now and at as_of - 180d) and has not been seen for 105 days.
    shot = [AS_OF - timedelta(days=7 * k) for k in range(15, 41)]
    events = make_events([*shot, WEEKS[1]])
    specs = [(d, 1, 30) for d in shot] + [(WEEKS[1], 2, 30)]

    result = ci.regulars(make_rounds(specs), events, AS_OF)

    assert [(c.shooter_id, c.events_attended) for c in result.core] == [(1, 26)]
    assert [(x.shooter_id, x.last_event) for x in result.lapsed] == [(1, shot[0])]


def test_lapsed_quiet_window_includes_its_first_day(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    # Lapsed = no round in (as_of - 90d, as_of]: a last round exactly 90 days back still
    # lapses, one 89 days back does not.
    edge, inside = AS_OF - timedelta(days=90), AS_OF - timedelta(days=89)
    specs = [(d, s, 30) for d in EARLY for s in (1, 2)] + [(edge, 1, 30), (inside, 2, 30)]

    result = ci.regulars(make_rounds(specs), make_events([*EARLY, edge, inside]), AS_OF)

    assert [(x.shooter_id, x.last_event) for x in result.lapsed] == [(1, edge)]


def test_a_round_at_a_non_held_event_keeps_a_regular_from_lapsing(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    # "No round at all" in the quiet window: a non-held event counts for last_seen even
    # though it never counts toward the held window.
    recent = AS_OF - timedelta(days=30)
    events = make_events([*EARLY, {"event_date": recent, "results_complete": False}])
    specs: list[object] = [(d, s, 30) for d in EARLY for s in (1, 2)]
    specs.append({"event_date": recent, "shooter_id": 2, "score": 30, "held": False})

    result = ci.regulars(make_rounds(specs), events, AS_OF)

    assert result.n_held_window == 0
    assert [(x.shooter_id, x.last_event) for x in result.lapsed] == [(1, EARLY[0])]


def test_regulars_no_leak(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    dates = WEEKS[:30]
    rounds = make_rounds([(d, s, 30) for d in dates for s in (1, 2) if (d.day + s) % 3])
    events = make_events(dates)
    future = [AS_OF + timedelta(days=7 * k) for k in range(1, 5)]
    more = pd.concat([rounds, make_rounds([(d, s, 30) for d in future for s in (1, 3)])])
    assert ci.regulars(rounds, events, AS_OF) == ci.regulars(
        more, make_events(dates + future), AS_OF
    )


def test_guest_conversion_by_year(make_rounds: Callable[..., pd.DataFrame]) -> None:
    def r(d: date, sid: int, status: str) -> dict[str, object]:
        return {"event_date": d, "shooter_id": sid, "score": 30, "status": status}

    rounds = make_rounds(
        [
            r(date(2024, 5, 5), 1, "guest"),
            r(date(2024, 6, 2), 1, "guest"),
            r(date(2025, 1, 5), 1, "member"),
            r(date(2025, 2, 2), 1, "member"),
            r(date(2024, 8, 4), 2, "guest"),
            r(date(2023, 3, 5), 3, "member"),
            r(date(2025, 3, 2), 3, "guest"),
            r(date(2025, 3, 30), 3, "member"),
        ]
    )

    assert ci.guest_conversion(rounds) == [
        # Cohorts by the year of the first guest round: shooter 1 joined 245 days later (in
        # 2025), shooter 2 never did; shooter 3 joined 28 days after their guest round.
        ci.ConversionYear(2024, new_guests=2, converted=1, median_days_to_convert=245.0),
        ci.ConversionYear(2025, new_guests=1, converted=1, median_days_to_convert=28.0),
    ]


def test_guest_conversion_never_exceeds_its_cohort(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    """Joiners count in their guest year, so a year's converted is at most its new guests."""

    def r(d: date, sid: int, status: str) -> dict[str, object]:
        return {"event_date": d, "shooter_id": sid, "score": 30, "status": status}

    rounds = make_rounds(
        [
            r(date(2023, 5, 7), 1, "guest"),
            r(date(2024, 5, 5), 1, "member"),
            r(date(2024, 5, 5), 2, "guest"),
            r(date(2024, 6, 2), 2, "member"),
            r(date(2025, 6, 1), 3, "guest"),
            r(date(2025, 7, 6), 3, "member"),
            r(date(2025, 6, 1), 4, "guest"),
            r(date(2025, 7, 6), 4, "member"),
            r(date(2025, 7, 6), 5, "member"),
        ]
    )

    years = ci.guest_conversion(rounds)

    assert [(y.year, y.new_guests, y.converted) for y in years] == [
        (2023, 1, 1),
        (2024, 1, 1),
        (2025, 2, 2),
    ]
    assert all(y.converted <= y.new_guests for y in years)


def test_parity_winners_top3_share_and_favorites(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d = [date(2026, 1, 4) + timedelta(days=7 * k) for k in range(4)]

    def best(day: date, sid: int, rank: float, mu: float) -> dict[str, object]:
        return {
            "event_date": day,
            "shooter_id": sid,
            "score": 30,
            "is_best_round": True,
            "event_rank": rank,
            "mu_before": mu,
        }

    rounds = make_rounds(
        [
            best(d[0], 1, 1, 40),
            best(d[0], 2, 2, 30),
            best(d[1], 1, 1, 40),
            best(d[1], 2, 1, 30),
            best(d[2], 3, 1, 30),
            best(d[2], 1, 2, 41),
            best(d[3], 4, 1, float("nan")),
            best(d[3], 1, 2, float("nan")),
            {
                "event_date": date(2025, 6, 1),
                "shooter_id": 1,
                "score": 30,
                "is_best_round": True,
                "event_rank": 1.0,
                "mu_before": 35.0,
            },
        ]
    )

    by_year = {p.year: p for p in ci.parity(rounds)}

    assert by_year[2025] == ci.ParityYear(2025, 1, 1, 1.0, 1.0)
    p = by_year[2026]
    # wins: shooter 1 x2, 2 x1 (tie), 3 x1, 4 x1 -> total 5, top-3 = 2+1+1
    assert (p.n_events, p.distinct_winners) == (4, 4)
    assert p.top3_share == pytest.approx(4 / 5)
    assert p.favorite_win_rate == pytest.approx(2 / 3)  # event 4 has no ratings


def test_parity_favorite_ties_are_left_out_of_the_rate(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d = [date(2026, 1, 4) + timedelta(days=7 * k) for k in range(5)]

    def best(day: date, sid: int, rank: float, mu: float) -> dict[str, object]:
        return {
            "event_date": day,
            "shooter_id": sid,
            "score": 30,
            "is_best_round": True,
            "event_rank": rank,
            "mu_before": mu,
        }

    first_event = date(2025, 6, 1)  # everyone still shares the prior: no favorite
    rounds = make_rounds(
        [
            best(first_event, 1, 1, 30.0),
            best(first_event, 2, 2, 30.0),
            best(first_event, 3, 3, 30.0),
            best(d[0], 1, 1, 40),  # 1 and 2 share the top rating; a tied one wins
            best(d[0], 2, 2, 40),
            best(d[0], 3, 3, 35),
            best(d[1], 1, 2, 40),  # 2 and 3 share the top rating; neither wins
            best(d[1], 2, 3, 42),
            best(d[1], 3, 4, 42),
            best(d[1], 4, 1, 30),
            best(d[2], 1, 2, 42),  # a lone favorite loses
            best(d[2], 3, 1, 36),
            best(d[3], 2, 1, 45),  # a lone favorite wins
            best(d[3], 1, 2, 43),
            best(d[4], 3, 1, 44),  # a lone favorite wins
            best(d[4], 1, 2, 40),
        ]
    )

    by_year = {p.year: p for p in ci.parity(rounds)}

    assert by_year[2025] == ci.ParityYear(2025, 1, 1, 1.0, None)
    assert (by_year[2026].n_events, by_year[2026].distinct_winners) == (5, 4)
    assert by_year[2026].favorite_win_rate == pytest.approx(2 / 3)  # d[0], d[1] left out


def test_parity_skips_years_without_ranked_winners(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            {
                "event_date": date(2026, 1, 4),
                "shooter_id": 1,
                "score": 30,
                "is_best_round": True,
                "event_rank": float("nan"),
            }
        ]
    )
    assert ci.parity(rounds) == []


def test_yearly_trends_ytd_and_yoy(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    as_of = date(2026, 3, 1)
    specs = [
        (date(2025, 1, 5), 1, 30),
        (date(2025, 2, 2), 2, 30),
        (date(2025, 6, 1), 1, 30),
        (date(2026, 1, 4), 1, 30),
        (date(2026, 2, 1), 1, 30),
        (date(2026, 3, 1), 3, 30),
        (date(2026, 3, 8), 1, 30),
    ]
    events = make_events(
        [{"event_date": d, "head_count": 10.0 + i} for i, (d, _, _) in enumerate(specs)]
    )

    years = ci.yearly_trends(make_rounds(specs), events, as_of)

    assert [(y.year, y.events_held, y.unique_shooters) for y in years] == [
        (2025, 3, 2),
        (2026, 3, 2),
    ]
    assert [(y.ytd_events, y.ytd_rounds, y.ytd_unique_shooters) for y in years] == [
        (2, 2, 2),
        (3, 3, 2),
    ]
    assert years[0].ytd_events_yoy is None
    assert years[1].ytd_events_yoy == pytest.approx(0.5)
    assert years[1].mean_head_count == pytest.approx(14.0)


def test_leap_day_cutoff_clamps_to_feb_28(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    specs = [(date(2023, 2, 26), 1, 30), (date(2024, 2, 25), 1, 30)]
    years = ci.yearly_trends(
        make_rounds(specs), make_events([d for d, _, _ in specs]), date(2024, 2, 29)
    )
    assert [y.ytd_events for y in years] == [1, 1]


def test_event_trends_rolling_eight_and_seasonality(
    make_events: Callable[..., pd.DataFrame],
) -> None:
    dates = [date(2026, 1, 4) + timedelta(days=7 * k) for k in range(10)]
    events = make_events(
        [
            {
                "event_date": d,
                "top_score": 40 + k,
                "median": 30.0,
                "difficulty": float(k),
                "head_count": 20.0,
            }
            for k, d in enumerate(dates)
        ]
        + [
            {
                "event_date": date(2026, 3, 22),
                "results_complete": False,
                "top_score": 50,
                "median": 10.0,
                "difficulty": float("nan"),
                "head_count": 40.0,
            }
        ]
    )

    trend = ci.event_trends(events, date(2026, 12, 31))
    assert len(trend) == 10
    assert trend[0].top_score_rolling8 == 40.0
    assert trend[9].top_score_rolling8 == pytest.approx(sum(range(42, 50)) / 8)
    assert trend[9].difficulty_rolling8 == pytest.approx(sum(range(2, 10)) / 8)
    months = {m.month: m for m in ci.seasonality(events, date(2026, 12, 31))}
    assert (months[1].n_events, months[3].n_events, months[7].n_events) == (4, 2, 0)
    assert months[3].mean_head_count == 20.0  # the non-held March event is ignored
    assert months[7].mean_median is None


def test_trends_no_leak(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    dates = WEEKS[:20]
    rounds = make_rounds([(d, s, 30 + s) for d in dates for s in (1, 2)])
    events = make_events(
        [
            {
                "event_date": d,
                "top_score": 40,
                "median": 30.0,
                "difficulty": 0.5,
                "head_count": 12.0,
            }
            for d in dates
        ]
    )
    future = [AS_OF + timedelta(days=7 * k) for k in range(1, 4)]
    more_rounds = pd.concat([rounds, make_rounds([(d, 9, 50) for d in future])])
    more_events = make_events(
        [
            {
                "event_date": d,
                "top_score": 50,
                "median": 45.0,
                "difficulty": -3.0,
                "head_count": 30.0,
            }
            for d in dates + future
        ]
    )
    more_events.loc[
        more_events["event_date"] <= AS_OF,
        ["top_score", "median", "difficulty", "head_count"],
    ] = [40, 30.0, 0.5, 12.0]
    assert ci.yearly_trends(rounds, events, AS_OF) == ci.yearly_trends(
        more_rounds, more_events, AS_OF
    )
    assert ci.event_trends(events, AS_OF) == ci.event_trends(more_events, AS_OF)
    assert ci.seasonality(events, AS_OF) == ci.seasonality(more_events, AS_OF)


def test_ytd_yoy_compares_with_the_previous_calendar_year(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    # No events at all in 2024: 2025 has no prior-year window to compare with.
    specs = [(date(2023, 1, 8), 1, 30), (date(2025, 1, 5), 1, 30), (date(2025, 1, 12), 1, 30)]
    specs += [(date(2026, 1, 4), 1, 30)]
    years = ci.yearly_trends(
        make_rounds(specs), make_events([d for d, _, _ in specs]), date(2026, 3, 1)
    )
    assert [(y.year, y.ytd_events, y.ytd_events_yoy) for y in years] == [
        (2023, 1, None),
        (2025, 2, None),
        (2026, 1, -0.5),
    ]


def test_ytd_keeps_feb_29_in_leap_years(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    specs = [(date(2028, 2, 29), 1, 30), (date(2031, 2, 28), 1, 30), (date(2032, 2, 29), 1, 30)]
    years = ci.yearly_trends(
        make_rounds(specs), make_events([d for d, _, _ in specs]), date(2032, 2, 29)
    )
    assert [(y.year, y.ytd_events, y.ytd_rounds) for y in years] == [
        (2028, 1, 1),
        (2031, 1, 1),
        (2032, 1, 1),
    ]


def test_event_trends_skip_held_events_without_metrics(
    make_events: Callable[..., pd.DataFrame],
) -> None:
    # A held event whose event_metrics row is missing (s10 not run yet) is left out,
    # never an int(NaN) error; the rolling means run over the events listed.
    events = make_events(
        [
            {"event_date": date(2026, 1, 4), "top_score": 40, "median": 30.0},
            {"event_date": date(2026, 1, 11)},
            {"event_date": date(2026, 1, 18), "top_score": 44, "median": 32.0},
        ]
    )
    trend = ci.event_trends(events, date(2026, 12, 31))
    assert [(t.event_date, t.top_score_rolling8, t.difficulty) for t in trend] == [
        (date(2026, 1, 4), 40.0, None),
        (date(2026, 1, 18), 42.0, None),
    ]


def test_yearly_trends_count_special_sundays_as_held_sundays_and_shooters(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    from sunday_clays.analytics import frames

    d1, d2, d3 = date(2026, 3, 1), date(2026, 3, 8), date(2026, 3, 15)
    rounds = make_rounds([(d1, 1, 30), (d3, 1, 31), (d1, 2, 30)])
    calendar = frames.calendar_from_events(make_events([d1, d2, d3]))
    calendar.loc[calendar["event_date"] == d2, "kind"] = "special"
    special = frames.appearances_from_rounds(make_rounds([(d2, 3, 40)])).assign(kind="special")
    seen = pd.concat([frames.appearances_from_rounds(rounds), special], ignore_index=True)

    (year,) = ci.yearly_trends(rounds, calendar, d3, seen)
    (base,) = ci.yearly_trends(rounds, make_events([d1, d3]), d3)

    assert (year.events_held, year.unique_shooters, year.ytd_unique_shooters) == (3, 3, 3)
    assert (base.events_held, base.unique_shooters, base.ytd_unique_shooters) == (2, 2, 2)
    assert year.ytd_rounds == base.ytd_rounds == 3
