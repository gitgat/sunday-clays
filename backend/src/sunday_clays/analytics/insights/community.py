"""Community kinds (spec §2.2.7): newcomers, the originals, the year in numbers, the club as one.

All club subjects and field kinds (no names), evergreen as of the latest held Sunday in scope.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, timedelta

import pandas as pd

from sunday_clays.analytics.cohorts import cohort_returns
from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.club import CLUB, held_to, special_turnout
from sunday_clays.analytics.insights.context import (
    ACTIVE_WINDOW,
    InsightFrames,
    is_active,
    mean,
    wrap_year,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
    Dec1,
    Int,
    Ordinal,
    ShortDate,
    T,
    Year,
    field_,
    named,
)
from sunday_clays.analytics.insights.types import (
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
    na,
    p_date,
    p_ids,
    p_int,
    rows_total,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric


def _rounds_to(fr: InsightFrames, day: date) -> pd.DataFrame:
    return fr.rounds.loc[[d <= day for d in fr.rounds["event_date"]]]


def _appearances_to(fr: InsightFrames, day: date) -> pd.DataFrame:
    return fr.appearances.loc[[d <= day for d in fr.appearances["event_date"]]]


def _fact(scope: Scope, pages: frozenset[P], params: Mapping[str, object], strength: float) -> Fact:
    return Fact(
        subject_id=CLUB,
        anchor_date=None,
        variant="",
        pages=pages,
        params={"day": scope.as_of, **params},
        strength=strength,
    )


# --- cl.newcomers --------------------------------------------------------------------------------

NEWCOMERS_MIN = 10
NEWCOMERS_LABEL = T(named("New shooters by year, and how many came back"))


def _newcomers(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    # cohorts follow Sundays shot, like the /club "new" chart this links to (Plan 17)
    returns = cohort_returns(_appearances_to(fr, scope.as_of), fr.shooters)
    year = scope.as_of.year
    row = returns.loc[returns["cohort_year"] == year]
    if row.empty or int(row["n_cohort"].iloc[0]) < NEWCOMERS_MIN:
        return
    n, back = int(row["n_cohort"].iloc[0]), int(row["n_returned"].iloc[0])
    params = {"n": n, "back": back, "year": year}
    yield _fact(scope, frozenset({P.CLUB, P.HOME}), params, n / NEWCOMERS_MIN)


def _newcomers_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    return charts.page(
        "/club",
        "new",
        label=NEWCOMERS_LABEL,
        window=Window(date(day.year - 10, 1, 1), day),
        hl=Highlight(keys=(str(p_int(fact.params, "year")),)),
    )


register(
    Kind(
        id="cl.newcomers",
        family=Family.NEWCOMER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.CLUB, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"min_newcomers": NEWCOMERS_MIN},
        params=frozenset({"day", "n", "back", "year"}),
        templates={
            "": (
                T(
                    field_(
                        Count("n", "new shooter"),
                        " in ",
                        Year("year"),
                        "; ",
                        Int("back"),
                        " have come back for more.",
                    )
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "New = first round on record this calendar year. Came back = shot a "
                        "second Sunday. Shooters from before our records are left out."
                    )
                ),
            )
        },
        labels=(NEWCOMERS_LABEL,),
        chart=_newcomers_chart,
        proof=(cell("n", key="year"), cell("back", "returned", key="year")),
        evaluate=_newcomers,
    )
)


# --- cl.originals --------------------------------------------------------------------------------

ORIGINALS_MIN = 3
ORIGINALS_LABEL = T(named("Rounds by year from the first Sunday's shooters"))


def _originals(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    sundays = held_to(fr, scope.as_of)
    if not sundays:
        return
    first = sundays[0]
    there = sorted(r.shooter_id for r in first.results)
    still = [
        sid
        for sid in there
        if not fr.profiles[sid].deceased
        and is_active(fr.history_until(sid, scope.as_of), scope.as_of)
    ]
    if len(still) < ORIGINALS_MIN:
        return
    params = {"first": first.date, "still": len(still), "n": len(there), "ids": still}
    yield _fact(scope, frozenset({P.CLUB, P.HOME}), params, 1.0)


def _originals_chart(fact: Fact) -> ChartLink:
    window = Window(p_date(fact.params, "first"), p_date(fact.params, "day"))
    query = charts.spec(
        Metric.ROUNDS, Agg.COUNT, Dim.YEAR, window=window, shooters=p_ids(fact.params, "ids")
    )
    return charts.explorer(query, label=ORIGINALS_LABEL)


register(
    Kind(
        id="cl.originals",
        family=Family.NEWCOMER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.CLUB, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"min_still": ORIGINALS_MIN},
        params=frozenset({"day", "first", "still", "n", "ids"}),
        templates={
            "": (
                T(
                    field_(
                        Int("still"),
                        " of the ",
                        Int("n"),
                        " shooters from our first Sunday on record still shoot.",
                    )
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Shooters on the first Sunday in our records who are still active: 5 "
                        "or more rounds, one in the last 12 months."
                    )
                ),
            )
        },
        labels=(ORIGINALS_LABEL,),
        chart=_originals_chart,
        proof=(
            na("still", "the chart shows their rounds by year"),
            na("n", "the first Sunday's results"),
        ),
        evaluate=_originals,
    )
)


# --- cl.year-wrap --------------------------------------------------------------------------------

CLUB_WRAP_MIN = 30
WRAP_LABEL = T(named("Rounds by year"))


def _year_wrap(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    wrapping = wrap_year(scope.as_of)  # December/January: the year just wrapping, on home too
    year = scope.as_of.year - 1 if wrapping is None else wrapping
    held = held_to(fr, scope.as_of)
    sundays = [s for s in held if s.date.year == year]
    # special Sundays are Sundays held, can be the busiest, and bring first-timers (Plan 17);
    # the round count stays the scored rounds
    specials = special_turnout(fr, date(year, 1, 1), min(date(year, 12, 31), scope.as_of))
    if not held or len(sundays) + len(specials) < CLUB_WRAP_MIN:
        return
    rounds = _rounds_to(fr, scope.as_of)
    in_year = rounds.loc[[d.year == year for d in rounds["event_date"]]]
    firsts = sum(
        1
        for sid, dates in fr.appearance_dates.items()
        if dates and dates[0].year == year and not fr.profiles[sid].left_censored
    )
    busiest_n, busiest = max(
        [(float(s.head_count or s.n), s.date) for s in sundays]
        + [(turnout, day) for day, turnout in specials]
    )
    params = {
        "first": held[0].date,
        "year": year,
        "sundays": len(sundays) + len(specials),
        "rounds": len(in_year),
        "firsts": firsts,
        "busiest": busiest,
        "busiest_n": round(busiest_n),
    }
    pages = {P.CLUB} | ({P.HOME} if wrapping is not None else set())
    yield _fact(scope, frozenset(pages), params, 1.0)


def _wrap_chart(fact: Fact) -> ChartLink:
    window = Window(p_date(fact.params, "first"), p_date(fact.params, "day"))
    query = charts.spec(Metric.ROUNDS, Agg.COUNT, Dim.YEAR, window=window)
    hl = Highlight(keys=(str(p_int(fact.params, "year")),))
    return charts.explorer(query, label=WRAP_LABEL, hl=hl)


register(
    Kind(
        id="cl.year-wrap",
        family=Family.RECAP,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.CLUB, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"min_sundays": CLUB_WRAP_MIN},
        params=frozenset(
            {"day", "first", "year", "sundays", "rounds", "firsts", "busiest", "busiest_n"}
        ),
        templates={
            "": (
                T(
                    field_(
                        Year("year"),
                        " in numbers: ",
                        Count("sundays", "Sunday"),
                        ", ",
                        Count("rounds", "round"),
                        ", ",
                        Count("firsts", "first-timer"),
                        "; busiest Sunday ",
                        ShortDate("busiest"),
                        " with ",
                        Int("busiest_n"),
                        ".",
                    )
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "A calendar year. Rounds = every round shot; busiest = the highest head "
                        "count."
                    )
                ),
                T(
                    named(
                        "Needs 30 Sundays in that year. Home shows it in December and January "
                        "(that year); otherwise the club page shows the latest finished year."
                    )
                ),
            )
        },
        labels=(WRAP_LABEL,),
        chart=_wrap_chart,
        proof=(
            cell("rounds", key="year"),
            na("sundays", "the year's Sundays are on the calendar"),
            na("firsts", "the newcomers chart on the club page"),
            na("busiest_n", "the attendance chart on the club page"),
        ),
        evaluate=_year_wrap,
    )
)


# --- cl.club-one-shooter -------------------------------------------------------------------------

ONE_MIN_ROUNDS = 5
ONE_LABEL = T(named("Average best round, last 12 months, shooters with 5 or more"))


def _club_one_shooter(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    start = scope.as_of - ACTIVE_WINDOW + timedelta(days=1)
    scores: dict[int, list[float]] = {}
    for s in held_to(fr, scope.as_of):
        if s.date < start:
            continue
        for r in s.results:
            scores.setdefault(r.shooter_id, []).append(float(r.score))
    everyone = [x for xs in scores.values() for x in xs]
    field = {sid: mean(xs) for sid, xs in scores.items() if len(xs) >= ONE_MIN_ROUNDS}
    if not field:
        return
    club = round(mean(everyone), 1)
    rank = 1 + sum(v > club for v in field.values())
    params = {"start": start, "avg": club, "rank": rank, "n": len(field)}
    yield _fact(scope, frozenset({P.CLUB}), params, 1.0)


def _one_chart(fact: Fact) -> ChartLink:
    window = Window(p_date(fact.params, "start"), p_date(fact.params, "day"))
    query = charts.spec(
        Metric.SCORE,
        Agg.AVG,
        Dim.SHOOTER,
        window=window,
        best=True,
        min_rounds=ONE_MIN_ROUNDS,
        sort="value_desc",
    )
    avg = fact.params["avg"]
    return charts.explorer(
        query, label=ONE_LABEL, ref=float(avg) if isinstance(avg, int | float) else None
    )


register(
    Kind(
        id="cl.club-one-shooter",
        family=Family.TURNOUT,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.CLUB}),
        polarity=Polarity.NEUTRAL,
        care=2,
        anchored=False,
        guard={"min_rounds": ONE_MIN_ROUNDS},
        params=frozenset({"day", "start", "avg", "rank", "n"}),
        templates={
            "": (
                T(
                    field_(
                        "If the club were one shooter: a ",
                        Dec1("avg"),
                        " average, ",
                        Ordinal("rank"),
                        " of the ",
                        Int("n"),
                        " shooters with 5 or more rounds in the last 12 months.",
                    )
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "The average of every best round each Sunday in the last 12 months, "
                        "placed among the shooters with 5 or more of those rounds."
                    )
                ),
            )
        },
        labels=(ONE_LABEL,),
        chart=_one_chart,
        proof=(
            rows_total("n"),
            na("avg", "the dashed reference line"),
            na("rank", "count the bars above the reference line"),
        ),
        evaluate=_club_one_shooter,
    )
)
