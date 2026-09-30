"""Journey kinds (spec §2.2.3): charter shooters, anniversaries and lifetime targets."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    InsightFrames,
    anchor_days,
    evergreen_days,
    is_active,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
    FullDate,
    Int,
    NameList,
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
    na,
    p_date,
    p_int,
    rows_total,
    total,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric

RESULTS_LABEL = charts.RESULTS_LABEL


# --- pf.charter-shooter --------------------------------------------------------------------------


def _charter(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    if not fr.sundays:
        return
    first = fr.sundays[0].date
    for sid, days in evergreen_days(fr, scope):
        if days[0].date != first or not is_active(days, scope.as_of):
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={"s": sid, "first": first},
            strength=1.0,
            named_shooter_ids=(sid,),
        )


register(
    Kind(
        id="pf.charter-shooter",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=2,
        anchored=False,
        guard={},
        params=frozenset({"s", "first"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        " was here on the first Sunday on record, ",
                        FullDate("first"),
                        ", and is still going.",
                    ),
                    you=named(
                        "You were here on the first Sunday on record, ",
                        FullDate("first"),
                        ", and are still going.",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Shot the first Sunday in our records and still active: 5 or more "
                        "rounds in the last 12 months."
                    ),
                    you=named(
                        "You shot the first Sunday in our records and are still active: 5 or "
                        "more rounds in the last 12 months."
                    ),
                ),
            )
        },
        labels=(charts.CAL_LABEL,),
        chart=lambda fact: charts.profile_chart(
            p_int(fact.params, "s"),
            "cal",
            label=charts.CAL_LABEL,
            window=Window(p_date(fact.params, "first"), p_date(fact.params, "first")),
            hl=Highlight(dates=(p_date(fact.params, "first"),)),
        ),
        proof=(),
        evaluate=_charter,
    )
)


# --- pf.shooter-anniversary ----------------------------------------------------------------------

ANNIVERSARY_YEARS = (1, 2, 3, 5, 7, 10)
ANNIVERSARY_STRENGTH = {1: 1.0, 2: 1.25, 3: 1.25, 5: 1.5, 7: 2.0, 10: 2.0}
ANNIVERSARY_ROUNDS = 12


def anniversary(first: date, years: int) -> date:
    """The years-th anniversary of `first` (Feb 29 falls back to Feb 28)."""
    try:
        return first.replace(year=first.year + years)
    except ValueError:
        return first.replace(year=first.year + years, day=28)


def _shooter_anniversary(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    held = fr.held_dates()
    for i, days in anchor_days(fr, scope):
        d = days[i]
        sid = d.shooter_id
        if fr.profiles[sid].left_censored or d.rounds_through < ANNIVERSARY_ROUNDS:
            continue
        for years in ANNIVERSARY_YEARS:
            due = anniversary(days[0].date, years)
            first_on_or_after = next((h for h in held if h >= due), None)
            if first_on_or_after != d.date:
                continue
            yield Fact(
                subject_id=str(sid),
                anchor_date=d.date,
                variant="",
                pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
                params={"s": sid, "years": years, "k": d.k, "first": days[0].date, "day": d.date},
                strength=ANNIVERSARY_STRENGTH[years],
                named_shooter_ids=(sid,),
            )


def _anniversary_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    first, day = p_date(fact.params, "first"), p_date(fact.params, "day")
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "cal",
        label=charts.CAL_LABEL,
        window=Window(first, day),
        hl=Highlight(dates=(first, day)),
    )


register(
    Kind(
        id="pf.shooter-anniversary",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        guard={"min_rounds": ANNIVERSARY_ROUNDS},
        params=frozenset({"s", "years", "k", "first", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        Count("years", "year"),
                        " since ",
                        Shooter("s"),
                        "'s first Sunday: ",
                        Count("k", "Sunday"),
                        " so far.",
                    ),
                    you=named(
                        Count("years", "year"),
                        " since your first Sunday: ",
                        Count("k", "Sunday"),
                        " so far.",
                    ),
                ),
            ),
            ROLLUP: (T(named("Club anniversaries today: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "The first Sunday on or after 1, 2, 3, 5, 7 or 10 years from the first "
                        "round on record, when the shooter is there."
                    ),
                    you=named(
                        "The first Sunday on or after 1, 2, 3, 5, 7 or 10 years from your first "
                        "round on record, when you are there."
                    ),
                ),
                T(
                    named(
                        "Needs 12 rounds, and a first Sunday that is not the first Sunday of "
                        "our records (their real start may be earlier)."
                    ),
                    you=named(
                        "Needs 12 rounds, and a first Sunday after the start of our records "
                        "(your real start may be earlier)."
                    ),
                ),
            ),
            ROLLUP: (T(named("Each marks 1, 2, 3, 5, 7 or 10 years since their first Sunday.")),),
        },
        labels=(charts.CAL_LABEL, RESULTS_LABEL),
        chart=_anniversary_chart,
        proof=(rows_total("k"), na("years", "the span between the two highlighted Sundays")),
        evaluate=_shooter_anniversary,
    )
)


# --- pf.targets-milestone ------------------------------------------------------------------------

TARGETS_STEP = 1000


def _targets_milestone(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        d = days[i]
        level = d.targets // TARGETS_STEP * TARGETS_STEP
        if level == 0 or d.prior_sum >= level:
            continue
        thousands = level // TARGETS_STEP
        yield Fact(
            subject_id=str(d.shooter_id),
            anchor_date=d.date,
            variant="",
            pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
            params={
                "s": d.shooter_id,
                "level": level,
                "total": d.targets,
                "first": days[0].date,
                "day": d.date,
            },
            strength=min(2.0, 1 + thousands / 10),
            named_shooter_ids=(d.shooter_id,),
        )


TARGETS_LABEL = T(named(Shooter("s"), "'s targets by year"), you=named("Your targets by year"))


def _targets_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    query = charts.spec(
        Metric.SCORE,
        Agg.SUM,
        Dim.YEAR,
        window=Window(p_date(fact.params, "first"), p_date(fact.params, "day")),
        shooters=(p_int(fact.params, "s"),),
    )
    return charts.explorer(query, label=TARGETS_LABEL)


register(
    Kind(
        id="pf.targets-milestone",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        kudos=True,
        expires={P.HOME: 3, P.PROFILE: 4},
        guard={"step": TARGETS_STEP},
        params=frozenset({"s", "level", "total", "first", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        " has now broken ",
                        Int("level"),
                        " targets on Sundays: ",
                        Int("total"),
                        " in all.",
                    ),
                    you=named(
                        "You have now broken ",
                        Int("level"),
                        " targets on Sundays: ",
                        Int("total"),
                        " in all.",
                    ),
                ),
            ),
            ROLLUP: (T(named("New thousand-target marks: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named("Every target broken in every round on record, all round types."),
                    you=named("Every target you broke in every round on record, all round types."),
                ),
                T(
                    named("Shown for 4 Sundays after the total passes each 1,000."),
                    you=named("Shown for 4 Sundays after your total passes each 1,000."),
                ),
            ),
            ROLLUP: (T(named("Each passed another 1,000 targets today.")),),
        },
        labels=(TARGETS_LABEL, RESULTS_LABEL),
        chart=_targets_chart,
        proof=(total("total"), na("level", "the total has passed this mark")),
        evaluate=_targets_milestone,
    )
)
