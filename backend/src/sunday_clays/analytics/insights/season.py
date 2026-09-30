"""Points-race and club-standing kinds (spec §2.2.4, §2.2.8): this year's race, the rating board.

Only the leader or the climber is named; nobody is named as trailing (D9).
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterator, Mapping
from datetime import date, timedelta
from itertools import pairwise

import pandas as pd

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    ACTIVE_WINDOW,
    InsightFrames,
    anchor_days,
    evergreen_days,
    mean,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
    Dec1,
    NameList,
    Ordinal,
    Shooter,
    T,
    named,
)
from sunday_clays.analytics.insights.types import (
    ROLLUP,
    ChartLink,
    Fact,
    Family,
    Highlight,
    HomeSlot,
    P,
    Polarity,
    Scope,
    SubjectType,
    Window,
    cell,
    lead,
    na,
    p_date,
    p_ids,
    p_int,
)
from sunday_clays.analytics.leaderboards import (
    LeaderboardMetric,
    LeaderboardPeriod,
    leaderboard,
    make_leaderboard_frames,
    period_bounds,
)
from sunday_clays.analytics.points import event_points
from sunday_clays.explorer.spec import Agg, Dim, Metric

SEASON_MIN_SUNDAYS = 6  # the race kinds start on the year's 7th held Sunday (skip while <= 6)
RACE_LABEL = T(named("This year's points race"))


def season_standings(fr: InsightFrames) -> dict[date, dict[int, int]]:
    """Points (C7) after each held Sunday, running within each calendar year."""
    points = event_points(fr.rounds)
    by_day: dict[date, list[tuple[int, int]]] = {}
    for day, sid, value in zip(
        points["event_date"], points["shooter_id"], points["points"], strict=True
    ):
        by_day.setdefault(day, []).append((int(sid), int(value)))
    out: dict[date, dict[int, int]] = {}
    totals: dict[int, int] = {}
    year = None
    for sunday in fr.sundays:
        if sunday.date.year != year:
            totals, year = {}, sunday.date.year
        for sid, value in by_day.get(sunday.date, ()):
            totals[sid] = totals.get(sid, 0) + value
        out[sunday.date] = dict(totals)
    return out


def season_points_at(fr: InsightFrames, day: date) -> dict[int, int]:
    """Points after the last held Sunday on or before `day`, in `day`'s calendar year."""
    held = [s.date for s in fr.sundays if s.date.year == day.year and s.date <= day]
    return season_standings(fr)[held[-1]] if held else {}


def ranks(totals: Mapping[int, float]) -> dict[int, int]:
    """Rank 1 = most; ties share the better rank (the race chart's rank)."""
    ordered = sorted(totals.values())
    return {sid: 1 + len(ordered) - bisect_right(ordered, value) for sid, value in totals.items()}


def leader(totals: Mapping[int, int]) -> tuple[int, int] | None:
    """(the sole leader, their lead over 2nd), or None when nobody leads alone."""
    if len(totals) < 2:
        return None
    ordered = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    lead = ordered[0][1] - ordered[1][1]
    return (ordered[0][0], lead) if lead >= 1 else None


def year_sundays(fr: InsightFrames, day: date) -> list[date]:
    return [s.date for s in fr.sundays if s.date.year == day.year and s.date <= day]


def race_chart(fact: Fact, ids: tuple[int, ...]) -> ChartLink:
    day = p_date(fact.params, "day")
    return charts.page(
        "/race",
        "race-bars",
        label=RACE_LABEL,
        window=Window(date(day.year, 1, 1), day),
        hl=Highlight(shooter_ids=ids),
        params={"at": day.isoformat(), "period": "ytd"},
    )


# --- lb.new-leader -------------------------------------------------------------------------------


def _new_leader(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    standings = season_standings(fr)
    for sunday in fr.sundays:
        day = sunday.date
        held = year_sundays(fr, day)
        if day not in scope.sundays or len(held) <= SEASON_MIN_SUNDAYS:
            continue
        now = leader(standings[day])
        before = leader(standings[held[-2]])
        if now is None or (before is not None and before[0] == now[0]):
            continue
        if fr.profiles[now[0]].deceased:
            continue
        yield Fact(
            subject_id=str(day.year),
            anchor_date=day,
            variant="",
            pages=frozenset({P.LEADERBOARDS, P.HOME}),
            params={"day": day, "s": now[0], "lead": now[1]},
            strength=1.5,
            named_shooter_ids=(now[0],),
        )


register(
    Kind(
        id="lb.new-leader",
        family=Family.RACE,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SEASON,
        pages=frozenset({P.LEADERBOARDS, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        guard={"season_sundays": SEASON_MIN_SUNDAYS},
        params=frozenset({"day", "s", "lead"}),
        templates={
            "": (T(named("New points leader this year: ", Shooter("s"), " moved into 1st.")),)
        },
        how={
            "": (
                T(
                    named(
                        "Points this year: 10-8-6-5-4-3-2-1 for the top 8 by best round each "
                        "Sunday, plus 1 for shooting. From the year's 7th Sunday."
                    )
                ),
            )
        },
        labels=(RACE_LABEL,),
        chart=lambda fact: race_chart(fact, (p_int(fact.params, "s"),)),
        proof=(),
        evaluate=_new_leader,
    )
)


# --- lb.title-race -------------------------------------------------------------------------------

RACE_GAP = 11  # the most points one Sunday can swing between two shooters


def sundays_left(day: date) -> int:
    """Calendar Sundays after `day` up to Dec 31 of its year (the clinch bound)."""
    return max(0, (date(day.year, 12, 31) - day).days // 7)


def _title_race(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    day = scope.as_of
    if len(year_sundays(fr, day)) <= SEASON_MIN_SUNDAYS:
        return
    top = leader(season_points_at(fr, day))
    if top is None or fr.profiles[top[0]].deceased:
        return
    sid, lead = top
    if lead > RACE_GAP * sundays_left(day):
        variant, strength = "clinched", 2.0
    elif lead <= RACE_GAP:
        variant, strength = "race", min(2.0, RACE_GAP / max(lead, 1))
    else:
        return
    yield Fact(
        subject_id=str(day.year),
        anchor_date=None,
        variant=variant,
        pages=frozenset({P.LEADERBOARDS, P.HOME}),
        params={"day": day, "s": sid, "lead": lead, "year": day.year},
        strength=strength,
        named_shooter_ids=(sid,),
    )


register(
    Kind(
        id="lb.title-race",
        family=Family.RACE,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SEASON,
        pages=frozenset({P.LEADERBOARDS, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"gap": RACE_GAP, "season_sundays": SEASON_MIN_SUNDAYS},
        params=frozenset({"day", "s", "lead", "year"}),
        templates={
            "race": (
                T(
                    named(
                        "This year's points race: ",
                        Shooter("s"),
                        " leads by ",
                        Count("lead", "point"),
                        ".",
                    )
                ),
            ),
            "clinched": (T(named(Shooter("s"), " has this year's points title in hand.")),),
        },
        how={
            "": (
                T(
                    named(
                        "A race while the leader is 11 points or fewer clear (one Sunday can "
                        "swing 11). In hand once the lead is more than 11 for every Sunday "
                        "left this year."
                    )
                ),
                T(named("Only the leader is named.")),
            )
        },
        labels=(RACE_LABEL,),
        chart=lambda fact: race_chart(fact, (p_int(fact.params, "s"),)),
        proof=(lead("lead"),),
        evaluate=_title_race,
    )
)


# --- lb.biggest-climb ----------------------------------------------------------------------------

CLIMB_PLACES = 3
CLIMB_TOP = 10


def _biggest_climb(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    standings = season_standings(fr)
    cache: dict[date, dict[int, int]] = {}

    def rank_at(day: date) -> dict[int, int]:
        if day not in cache:
            cache[day] = ranks(standings[day])
        return cache[day]

    for i, days in anchor_days(fr, scope):
        d = days[i]
        held = year_sundays(fr, d.date)
        if len(held) <= SEASON_MIN_SUNDAYS:
            continue
        before, now = rank_at(held[-2]).get(d.shooter_id), rank_at(d.date).get(d.shooter_id)
        if before is None or now is None or now > CLIMB_TOP or before - now < CLIMB_PLACES:
            continue
        yield Fact(
            subject_id=str(d.shooter_id),
            anchor_date=d.date,
            variant="",
            pages=frozenset({P.LEADERBOARDS, P.HOME}),
            params={"s": d.shooter_id, "up": before - now, "rank": now, "day": d.date},
            strength=(before - now) / CLIMB_PLACES,
            named_shooter_ids=(d.shooter_id,),
        )


register(
    Kind(
        id="lb.biggest-climb",
        family=Family.RACE,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.LEADERBOARDS, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        kudos=True,
        guard={"places": CLIMB_PLACES, "top": CLIMB_TOP, "season_sundays": SEASON_MIN_SUNDAYS},
        params=frozenset({"s", "up", "rank", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        "Up ",
                        Count("up", "place"),
                        " in points this year: ",
                        Shooter("s"),
                        " is now ",
                        Ordinal("rank"),
                        ".",
                    ),
                    you=named(
                        "Up ",
                        Count("up", "place"),
                        " in points this year: you are now ",
                        Ordinal("rank"),
                        ".",
                    ),
                ),
            ),
            ROLLUP: (T(named("Climbing this year's points race: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "Place in this year's points after this Sunday against the Sunday before: "
                        "up 3 or more, into the top 10, from the year's 7th Sunday."
                    ),
                    you=named(
                        "Your place in this year's points after this Sunday against the Sunday "
                        "before: up 3 or more, into the top 10."
                    ),
                ),
            ),
            ROLLUP: (T(named("Each climbed 3 or more places into the top 10 today.")),),
        },
        labels=(RACE_LABEL,),
        chart=lambda fact: race_chart(
            fact,
            p_ids(fact.params, "names") if fact.variant == ROLLUP else (p_int(fact.params, "s"),),
        ),
        proof=(cell("rank", "rank", key="s"), na("up", "the race replay's earlier frame")),
        evaluate=_biggest_climb,
    )
)


# --- lb.most-improved ----------------------------------------------------------------------------

IMPROVED_MIN = 1.0
IMPROVED_BOARD = 3
BOARD_LABEL = T(named("Most improved this year"))


def improved_board(fr: InsightFrames, as_of: date) -> pd.DataFrame:
    frames = make_leaderboard_frames(fr.rounds, fr.events, fr.rating)
    board = leaderboard(frames, LeaderboardPeriod.YTD, LeaderboardMetric.RATING_GAIN, as_of)
    return board.rows


def last_rise(fr: InsightFrames, sid: int, start: date, end: date) -> date | None:
    """The latest Sunday in [start, end] on which the shooter's rating went up."""
    points = [p for p in fr.ratings.get(sid, ()) if p[0] <= end]
    rises = [b[0] for a, b in pairwise(points) if b[1] > a[1] and b[0] >= start]
    return rises[-1] if rises else None


def _most_improved(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    rows = improved_board(fr, scope.as_of)
    top = rows[rows["value"] >= IMPROVED_MIN].head(IMPROVED_BOARD)
    for place, (sid, value) in enumerate(zip(top["shooter_id"], top["value"], strict=True)):
        sid = int(sid)
        if fr.profiles[sid].deceased:
            continue
        kudos = last_rise(fr, sid, date(scope.as_of.year, 1, 1), scope.as_of)
        first = place == 0
        params: dict[str, object] = {"s": sid, "delta": round(float(value), 1), "day": scope.as_of}
        if kudos is not None and first:
            params["kudos_sunday"] = kudos
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="" if first else "board",
            pages=frozenset({P.LEADERBOARDS, P.HOME, P.PROFILE} if first else {P.LEADERBOARDS}),
            params=params,
            strength=float(value) / IMPROVED_MIN,
            named_shooter_ids=(sid,),
        )


def _improved_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    return charts.page(
        "/leaderboards",
        "lb-board",
        label=BOARD_LABEL,
        window=Window(date(day.year, 1, 1), day),
        hl=Highlight(shooter_ids=(p_int(fact.params, "s"),)),
        params={"metric": "rating_gain"},
    )


register(
    Kind(
        id="lb.most-improved",
        family=Family.RACE,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.LEADERBOARDS, P.HOME, P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=False,
        kudos=True,
        guard={"delta": IMPROVED_MIN, "board": IMPROVED_BOARD},
        params=frozenset({"s", "delta", "day", "kudos_sunday"}),
        templates={
            "": (
                T(
                    named(
                        "Most improved this year: ",
                        Shooter("s"),
                        ", skill rating up ",
                        Dec1("delta"),
                        " since January.",
                    ),
                    you=named(
                        "Most improved this year: your skill rating is up ",
                        Dec1("delta"),
                        " since January.",
                    ),
                ),
            ),
            "board": (
                T(
                    named(
                        "Among the most improved this year: ",
                        Shooter("s"),
                        ", skill rating up ",
                        Dec1("delta"),
                        " since January.",
                    ),
                    you=named(
                        "Among the most improved this year: your skill rating is up ",
                        Dec1("delta"),
                        " since January.",
                    ),
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "The rise in skill rating from before Jan 1 to now, for shooters with "
                        "10 rounds before this year and 5 in it (the leaderboard's rule)."
                    ),
                    you=named(
                        "The rise in your skill rating from before Jan 1 to now, with 10 "
                        "rounds before this year and 5 in it (the leaderboard's rule)."
                    ),
                ),
                T(
                    named(
                        "Shown at a rise of 1.0 or more; the kudos strip marks the Sunday the "
                        "rating last went up."
                    ),
                    you=named(
                        "Shown at a rise of 1.0 or more; the kudos strip marks the Sunday "
                        "your rating last went up."
                    ),
                ),
            )
        },
        labels=(BOARD_LABEL,),
        chart=_improved_chart,
        proof=(cell("delta", key="s"),),
        evaluate=_most_improved,
        expires={},
    )
)


# --- pf.rank-climb -------------------------------------------------------------------------------
# The id is kept; the fact is a rating GAIN (owner rule: no rating places, call out improvement).

GAIN_MIN = 2.0  # rating points gained over the last 12 months
MOVERS_LABEL = T(named("Biggest rating gains, last 12 months"))


def _rank_climb(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    frames = make_leaderboard_frames(fr.rounds, fr.events, fr.rating)
    board = leaderboard(
        frames, LeaderboardPeriod.ROLLING_12, LeaderboardMetric.RATING_GAIN, scope.as_of
    )
    gains = {
        int(sid): float(v)
        for sid, v in zip(board.rows["shooter_id"], board.rows["value"], strict=True)
    }
    for sid, _days in evergreen_days(fr, scope):
        gain = gains.get(sid)
        if gain is None or round(gain, 1) < GAIN_MIN:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE, P.LEADERBOARDS, P.HOME}),
            params={"s": sid, "gain": round(gain, 1), "day": scope.as_of},
            strength=gain / GAIN_MIN,
            named_shooter_ids=(sid,),
        )


def _rank_climb_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    start, _ = period_bounds(LeaderboardPeriod.ROLLING_12, day)
    return charts.page(
        "/leaderboards",
        "lb-movers",
        label=MOVERS_LABEL,
        window=Window(start or day, day),
        hl=Highlight(shooter_ids=(p_int(fact.params, "s"),)),
        params={"metric": "rating_gain"},
    )


register(
    Kind(
        id="pf.rank-climb",
        family=Family.RACE,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.LEADERBOARDS, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"gain": GAIN_MIN},
        params=frozenset({"s", "gain", "day"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        " gained ",
                        Dec1("gain"),
                        " rating points in the last 12 months.",
                    ),
                    you=named("You gained ", Dec1("gain"), " rating points in the last 12 months."),
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "The rise in skill rating over the last 12 months, for shooters with 10 "
                        "rounds before then and 5 in it (the leaderboard's rule)."
                    ),
                    you=named(
                        "The rise in your skill rating over the last 12 months, with 10 rounds "
                        "before then and 5 in it (the leaderboard's rule)."
                    ),
                ),
                T(
                    named("Shown at a gain of 2.0 rating points or more."),
                    you=named("Shown at a gain of 2.0 rating points or more."),
                ),
            )
        },
        labels=(MOVERS_LABEL,),
        chart=_rank_climb_chart,
        proof=(cell("gain", key="s"),),
        evaluate=_rank_climb,
    )
)


# --- pf.top-of-club ------------------------------------------------------------------------------

TOP_MIN_ROUNDS = 10
TOP_QUARTER, TOP_TENTH = 0.25, 0.10
TOP_LABEL = T(named("Average against the field's middle score, last 12 months"))


def _top_of_club(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    start = scope.as_of - ACTIVE_WINDOW + timedelta(days=1)
    values: dict[int, list[float]] = {}
    for sid, day, adjusted in zip(
        fr.rounds["shooter_id"], fr.rounds["event_date"], fr.rounds["adjusted"], strict=True
    ):
        if start <= day <= scope.as_of and not pd.isna(adjusted):
            values.setdefault(int(sid), []).append(float(adjusted))
    field = {sid: mean(v) for sid, v in values.items() if len(v) >= TOP_MIN_ROUNDS}
    if not field:
        return
    placed = {sid: 1 + sum(o > v for o in field.values()) for sid, v in field.items()}
    n = len(placed)
    for sid, _days in evergreen_days(fr, scope):
        rank = placed.get(sid)
        if rank is None:
            continue
        if rank <= TOP_TENTH * n:
            variant, strength = "tenth", 1.5
        elif rank <= TOP_QUARTER * n:
            variant, strength = "quarter", 1.0
        else:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant=variant,
            pages=frozenset({P.PROFILE}),
            params={"s": sid, "start": start, "day": scope.as_of},
            strength=strength,
            named_shooter_ids=(sid,),
        )


def _top_chart(fact: Fact) -> ChartLink:
    query = charts.spec(
        Metric.ADJUSTED,
        Agg.AVG,
        Dim.SHOOTER,
        window=Window(p_date(fact.params, "start"), p_date(fact.params, "day")),
        min_rounds=TOP_MIN_ROUNDS,
        sort="value_desc",
    )
    return charts.explorer(
        query, label=TOP_LABEL, hl=Highlight(shooter_ids=(p_int(fact.params, "s"),)), ref=0
    )


register(
    Kind(
        id="pf.top-of-club",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"min_rounds": TOP_MIN_ROUNDS, "quarter": TOP_QUARTER, "tenth": TOP_TENTH},
        params=frozenset({"s", "start", "day"}),
        templates={
            "quarter": (
                T(
                    named(
                        Shooter("s"), " is in the top quarter of the club over the last 12 months."
                    ),
                    you=named("You are in the top quarter of the club over the last 12 months."),
                ),
            ),
            "tenth": (
                T(
                    named(Shooter("s"), " is in the top 10% of the club over the last 12 months."),
                    you=named("You are in the top 10% of the club over the last 12 months."),
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Average of every round against the field's middle score over the last "
                        "12 months, placed among shooters with 10 or more such rounds."
                    ),
                    you=named(
                        "Your average against the field's middle score over the last 12 "
                        "months, placed among shooters with 10 or more such rounds."
                    ),
                ),
            )
        },
        labels=(TOP_LABEL,),
        chart=_top_chart,
        proof=(),
        evaluate=_top_of_club,
    )
)
