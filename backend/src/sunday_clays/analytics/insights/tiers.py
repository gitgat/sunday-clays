"""Own-tier kinds (spec §2.2.1): counts of rounds at the shooter's own mark, and the low end.

Own tier T (context.own_tier) is the highest of 45/40/35 reached on 10-60% of the last 52
rounds, so each shooter is measured against a mark that is hard but reachable for them.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    Day,
    InsightFrames,
    anchor_days,
    evergreen_days,
    jan1,
    own_tier,
    quantile,
    stderr_diff,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Dec1,
    Int,
    NameList,
    Ordinal,
    Shooter,
    T,
    Year,
    named,
)
from sunday_clays.analytics.insights.types import (
    PROFILE,
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
    na,
    p_date,
    p_int,
    total,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric

RESULTS_LABEL = charts.RESULTS_LABEL
HIGH_LABEL = T(
    named(Shooter("s"), "'s rounds at their mark, by year"),
    you=named("Your rounds at your mark, by year"),
)


def high_rounds(days: Sequence[Day], tier: int, year: int | None = None) -> int:
    """Rounds (not Sundays) at `tier` or better, optionally in one calendar year."""
    return sum(
        sum(s >= tier for s in d.scores) for d in days if year is None or d.date.year == year
    )


def _running_high_rounds(days: Sequence[Day], tier: int, year: int | None = None) -> list[int]:
    """`high_rounds(days[:k], tier, year)` for every k, so each anchor reads two entries."""
    out = [0]
    for d in days:
        out.append(
            out[-1] + (sum(s >= tier for s in d.scores) if year in (None, d.date.year) else 0)
        )
    return out


def _count_chart(fact: Fact, start: date, hl: Highlight) -> ChartLink:
    query = charts.spec(
        Metric.SCORE,
        Agg.COUNT,
        Dim.YEAR,
        window=Window(start, p_date(fact.params, "day")),
        shooters=(p_int(fact.params, "s"),),
        min_score=p_int(fact.params, "tier"),
    )
    return charts.explorer(query, label=HIGH_LABEL, hl=hl)


# --- pf.high-round-count -------------------------------------------------------------------------

COUNT_STEPS = (10, 25, 50, 100, 150, 200)
COUNT_STRENGTH = {10: 1.0, 25: 1.25, 50: 1.5, 100: 2.0, 150: 2.0, 200: 2.0}


def _high_round_count(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    running: dict[tuple[int, int], list[int]] = {}
    for i, days in anchor_days(fr, scope):
        upto = days[: i + 1]
        tier = own_tier(upto)
        if tier is None:
            continue
        counts = running.setdefault((id(days), tier), _running_high_rounds(days, tier))
        before, now = counts[i], counts[i + 1]
        step = max((s for s in COUNT_STEPS if before < s <= now), default=None)
        if step is None:
            continue
        yield Fact(
            subject_id=str(upto[-1].shooter_id),
            anchor_date=upto[-1].date,
            variant="",
            pages=frozenset({P.PROFILE, P.SUNDAY}),
            params={
                "s": upto[-1].shooter_id,
                "count": now,
                "tier": tier,
                "first": upto[0].date,
                "day": upto[-1].date,
            },
            strength=COUNT_STRENGTH[step],
            named_shooter_ids=(upto[-1].shooter_id,),
        )


def _high_count_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    return _count_chart(fact, p_date(fact.params, "first"), Highlight())


register(
    Kind(
        id="pf.high-round-count",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        kudos=True,
        guard={"steps": 6},
        params=frozenset({"s", "count", "tier", "first", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        "That was ",
                        Shooter("s"),
                        "'s ",
                        Ordinal("count"),
                        " round of ",
                        Int("tier"),
                        " or better.",
                    ),
                    you=named(
                        "That was your ", Ordinal("count"), " round of ", Int("tier"), " or better."
                    ),
                ),
            ),
            ROLLUP: (
                T(named("Round-count milestones at their own mark: ", NameList("names"), ".")),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "The mark is the highest of 45, 40 or 35 reached on 10% to 60% of their "
                        "last 52 rounds. Every round counts, not just the best each Sunday."
                    ),
                    you=named(
                        "Your mark is the highest of 45, 40 or 35 you reached on 10% to 60% of "
                        "your last 52 rounds. Every round counts."
                    ),
                ),
                T(
                    named("Shown when the count reaches 10, 25, 50, 100, 150 or 200."),
                    you=named("Shown when your count reaches 10, 25, 50, 100, 150 or 200."),
                ),
            ),
            ROLLUP: (T(named("Each reached 10, 25, 50, 100, 150 or 200 rounds at their mark.")),),
        },
        labels=(HIGH_LABEL, RESULTS_LABEL),
        chart=_high_count_chart,
        proof=(total("count"), na("tier", "the mark named in the chart's filter")),
        evaluate=_high_round_count,
    )
)


# --- pf.more-high-rounds -------------------------------------------------------------------------

MORE_LAST_MIN = 8


def _more_fact(days: Sequence[Day], tier: int, *, variant: str, pages: frozenset[P]) -> Fact | None:
    last_day = days[-1]
    year = last_day.date.year
    this, last = high_rounds(days, tier, year), high_rounds(days, tier, year - 1)
    if last < MORE_LAST_MIN or this <= last:
        return None
    return Fact(
        subject_id=str(last_day.shooter_id),
        anchor_date=last_day.date if variant != PROFILE else None,
        variant=variant,
        pages=pages,
        params={
            "s": last_day.shooter_id,
            "this": this,
            "last": last,
            "tier": tier,
            "year": year,
            "last_year": year - 1,
            "day": last_day.date,
        },
        strength=this / last,
        named_shooter_ids=(last_day.shooter_id,),
    )


def _more_high_rounds(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    running: dict[tuple[int, int, int], list[int]] = {}

    def through(days: tuple[Day, ...], tier: int, year: int) -> list[int]:
        return running.setdefault((id(days), tier, year), _running_high_rounds(days, tier, year))

    for i, days in anchor_days(fr, scope):
        upto = days[: i + 1]
        tier = own_tier(upto)
        if tier is None:
            continue
        year = upto[-1].date.year
        if through(days, tier, year)[i] > through(days, tier, year - 1)[i + 1]:
            continue  # crossed on an earlier Sunday
        fact = _more_fact(upto, tier, variant="", pages=frozenset({P.SUNDAY, P.HOME}))
        if fact is not None:
            yield fact
    for _sid, days in evergreen_days(fr, scope):
        tier = own_tier(days)
        if tier is None or days[-1].date.year != scope.as_of.year:
            continue
        fact = _more_fact(days, tier, variant=PROFILE, pages=frozenset({P.PROFILE}))
        if fact is not None:
            yield fact


def _more_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    year = p_int(fact.params, "year")
    return _count_chart(fact, date(year - 1, 1, 1), Highlight(keys=(str(year),)))


_MORE_TEXT = T(
    named(
        "More rounds of ",
        Int("tier"),
        " or better this year than in all of last year for ",
        Shooter("s"),
        ": ",
        Int("this"),
        " vs ",
        Int("last"),
        ".",
    ),
    you=named(
        "You have more rounds of ",
        Int("tier"),
        " or better this year than in all of last year: ",
        Int("this"),
        " vs ",
        Int("last"),
        ".",
    ),
)

register(
    Kind(
        id="pf.more-high-rounds",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        kudos=True,
        guard={"last_year_min": MORE_LAST_MIN},
        params=frozenset({"s", "this", "last", "tier", "year", "last_year", "day", "names"}),
        templates={
            "": (_MORE_TEXT,),
            PROFILE: (_MORE_TEXT,),
            ROLLUP: (
                T(named("Already past last year's count at their mark: ", NameList("names"), ".")),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Every round at their own mark (the highest of 45, 40 or 35 reached on "
                        "10% to 60% of their last 52 rounds), this calendar year vs last."
                    ),
                    you=named(
                        "Every round at your own mark (the highest of 45, 40 or 35 you reached "
                        "on 10% to 60% of your last 52 rounds), this calendar year vs last."
                    ),
                ),
                T(
                    named(
                        "Needs 8 such rounds last year; the Sunday page shows the day it passes."
                    ),
                    you=named("Needs 8 such rounds last year; the Sunday page shows the day."),
                ),
            ),
            ROLLUP: (T(named("Each passed last year's full count today.")),),
        },
        labels=(HIGH_LABEL, RESULTS_LABEL),
        chart=_more_chart,
        proof=(
            cell("this", key="year"),
            cell("last", key="last_year"),
            na("tier", "the mark named in the chart's filter"),
        ),
        evaluate=_more_high_rounds,
    )
)


# --- pf.low-end-rising ---------------------------------------------------------------------------

LOW_MIN_ROUNDS = 12
LOW_GAIN = 2.0
LOW_LABEL = T(
    named("Low end of ", Shooter("s"), "'s Sundays, by year"),
    you=named("Low end of your Sundays, by year"),
)


def _low_end_rising(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    year = scope.as_of.year
    for sid, days in evergreen_days(fr, scope):
        this = [float(d.score) for d in days if d.date.year == year]
        last = [float(d.score) for d in days if d.date.year == year - 1]
        if min(len(this), len(last)) < LOW_MIN_ROUNDS:
            continue
        low, low_last = quantile(this, 0.25), quantile(last, 0.25)
        gain = low - low_last
        if gain < LOW_GAIN or gain < 2 * stderr_diff(this, last):
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={
                "s": sid,
                "low": round(low, 1),
                "low_last": round(low_last, 1),
                "year": year,
                "last_year": year - 1,
                "day": days[-1].date,
            },
            strength=gain / LOW_GAIN,
            named_shooter_ids=(sid,),
        )


def _low_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    query = charts.spec(
        Metric.SCORE,
        Agg.P25,
        Dim.YEAR,
        window=Window(jan1(day).replace(year=day.year - 1), day),
        shooters=(p_int(fact.params, "s"),),
        best=True,
    )
    return charts.explorer(query, label=LOW_LABEL, hl=Highlight(keys=(str(day.year),)))


register(
    Kind(
        id="pf.low-end-rising",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"min_rounds": LOW_MIN_ROUNDS, "gain": LOW_GAIN, "noise_multiple": 2},
        params=frozenset({"s", "low", "low_last", "year", "last_year", "day"}),
        templates={
            "": (
                T(
                    named(
                        "Off days are getting better for ",
                        Shooter("s"),
                        ": the low end of their Sundays is up from ",
                        Dec1("low_last"),
                        " in ",
                        Year("last_year"),
                        " to ",
                        Dec1("low"),
                        ".",
                    ),
                    you=named(
                        "Your off days are getting better: the low end of your Sundays is up from ",
                        Dec1("low_last"),
                        " in ",
                        Year("last_year"),
                        " to ",
                        Dec1("low"),
                        ".",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Low end = the score a quarter of their Sundays fall at or under (best "
                        "round each Sunday), this calendar year vs last."
                    ),
                    you=named(
                        "Low end = the score a quarter of your Sundays fall at or under (your "
                        "best round each Sunday), this calendar year vs last."
                    ),
                ),
                T(
                    named(
                        "Needs 12 Sundays in each year and a rise of 2 or more that is well "
                        "clear of chance."
                    ),
                    you=named(
                        "Needs 12 of your Sundays in each year and a rise of 2 or more that is "
                        "well clear of chance."
                    ),
                ),
            )
        },
        labels=(LOW_LABEL,),
        chart=_low_chart,
        proof=(cell("low", key="year"), cell("low_last", key="last_year")),
        evaluate=_low_end_rising,
    )
)
