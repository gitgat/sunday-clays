"""Streak and kudos-run kinds (spec §2.2.2): consecutive Sundays shot that keep a good thing going.

"In a row" counts the Sundays the shooter shot: a Sunday they missed neither extends nor breaks
a run. Each kind has an anchored row at the crossing Sunday (Sunday and home pages) and an
evergreen profile row for a run still going (spec §3.1, separate page guards).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from datetime import timedelta

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    FINISH_FIELD,
    Day,
    InsightFrames,
    add_months,
    anchor_days,
    evergreen_days,
    finish_at,
    own_tier,
    run_back,
    run_start,
    shot_recently,
)
from sunday_clays.analytics.insights.form import VS_FIELD_LABEL, vs_field_chart
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
    Int,
    NameList,
    Ordinal,
    Shooter,
    T,
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
    count_rows,
    na,
    p_date,
    p_ids,
    p_int,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric

RunTest = Callable[[Day], bool | None]
ROLLUP_LABEL = T(named("Results for the Sunday"))


def run_facts(
    fr: InsightFrames,
    scope: Scope,
    ok: RunTest,
    *,
    crossings: Sequence[int],
    profile_min: int,
    strength_unit: float,
    min_prior_rounds: int = 0,
) -> Iterator[Fact]:
    """Anchored Facts when a run reaches one of `crossings`; a profile Fact while >= profile_min."""

    def fact(days: Sequence[Day], k: int, *, variant: str, pages: frozenset[P]) -> Fact | None:
        start = run_start(days, ok, k)
        if start.prior_rounds < min_prior_rounds:
            return None
        last = days[-1]
        return Fact(
            subject_id=str(last.shooter_id),
            anchor_date=last.date if variant != PROFILE else None,
            variant=variant,
            pages=pages,
            params={"s": last.shooter_id, "k": k, "start": start.date, "day": last.date},
            strength=k / strength_unit,
            named_shooter_ids=(last.shooter_id,),
        )

    for i, days in anchor_days(fr, scope):
        upto = days[: i + 1]
        if ok(upto[-1]) is not True:
            continue
        k = run_back(upto, ok)
        if k in crossings and (f := fact(upto, k, variant="", pages=frozenset({P.SUNDAY, P.HOME}))):
            yield f
    for _sid, days in evergreen_days(fr, scope):
        k = run_back(days, ok)
        if k >= profile_min and shot_recently(days, scope.as_of):
            f = fact(days, k, variant=PROFILE, pages=frozenset({P.PROFILE}))
            if f is not None:
                yield f


def run_window(fact: Fact, before: timedelta) -> tuple[Window, Highlight]:
    start, day = p_date(fact.params, "start"), p_date(fact.params, "day")
    return Window(start - before, day), Highlight(span=(start, day))


def rollup_chart(fact: Fact) -> ChartLink:
    return charts.results_chart(
        p_date(fact.params, "day"), p_ids(fact.params, "names"), label=ROLLUP_LABEL
    )


# --- pf.beat-field-streak ------------------------------------------------------------------------


def above_field(day: Day) -> bool | None:
    """Held Sundays only (the field's middle score exists only there)."""
    return None if day.adjusted is None or not day.held else day.adjusted > 0


def _beat_field(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    yield from run_facts(
        fr, scope, above_field, crossings=(6, 10, 15, 20), profile_min=5, strength_unit=5
    )


def _beat_field_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return rollup_chart(fact)
    window, hl = run_window(fact, timedelta(weeks=2))
    return vs_field_chart(fact, window, hl)


register(
    Kind(
        id="pf.beat-field-streak",
        family=Family.STREAK,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        guard={"profile_run": 5, "crossings": 6},
        params=frozenset({"s", "k", "start", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        "Above the field's middle score ",
                        Count("k", "Sunday"),
                        " in a row for ",
                        Shooter("s"),
                        ".",
                    ),
                    you=named(
                        "You have been above the field's middle score ",
                        Count("k", "Sunday"),
                        " in a row.",
                    ),
                ),
            ),
            PROFILE: (
                T(
                    named(
                        Shooter("s"),
                        " has beaten the field's middle score ",
                        Count("k", "Sunday"),
                        " running.",
                    ),
                    you=named(
                        "You have beaten the field's middle score ",
                        Count("k", "Sunday"),
                        " running.",
                    ),
                ),
            ),
            ROLLUP: (
                T(named("Long runs above the field's middle score: ", NameList("names"), ".")),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Each Sunday shot: the best round against the middle score of everyone "
                        "who shot that day. Sundays missed neither add to nor end the run."
                    ),
                    you=named(
                        "Each Sunday you shot: your best round against the middle score of "
                        "everyone who shot. Sundays you missed do not end the run."
                    ),
                ),
                T(
                    named(
                        "Shown on the Sunday a run reaches 6, 10, 15 or 20, and on the profile "
                        "from 5 while it lasts. All round types count."
                    ),
                    you=named(
                        "Shown on the Sunday your run reaches 6, 10, 15 or 20, and on "
                        "your profile from 5. All round types count."
                    ),
                ),
            ),
            ROLLUP: (
                T(
                    named(
                        "Runs of Sundays above the field's middle score reaching 6, 10, 15 "
                        "or 20 today."
                    )
                ),
            ),
        },
        labels=(VS_FIELD_LABEL, ROLLUP_LABEL),
        chart=_beat_field_chart,
        proof=(count_rows("k"),),
        evaluate=_beat_field,
    )
)


# --- pf.above-own-avg-streak ---------------------------------------------------------------------

OWN_AVG_PRIOR = 10


def above_own_average(day: Day) -> bool | None:
    """Above the mean of every round on earlier dates (all Sundays shot count)."""
    return None if day.prior_mean is None else day.score > day.prior_mean


def _own_avg(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    yield from run_facts(
        fr,
        scope,
        above_own_average,
        crossings=(6, 10, 15, 20),
        profile_min=4,
        strength_unit=4,
        min_prior_rounds=OWN_AVG_PRIOR,
    )


OWN_AVG_LABEL = T(
    named(Shooter("s"), "'s scores and average so far"),
    you=named("Your scores and your average so far"),
)


def _own_avg_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return rollup_chart(fact)
    window, hl = run_window(fact, timedelta(weeks=3))
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "trend",
        label=OWN_AVG_LABEL,
        window=window,
        hl=hl,
        params={"line": "so_far"},
    )


register(
    Kind(
        id="pf.above-own-avg-streak",
        family=Family.STREAK,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        guard={"min_prior_rounds": OWN_AVG_PRIOR, "profile_run": 4},
        params=frozenset({"s", "k", "start", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        Count("k", "Sunday"), " in a row above ", Shooter("s"), "'s own average."
                    ),
                    you=named(Count("k", "Sunday"), " in a row above your own average."),
                ),
            ),
            PROFILE: (
                T(
                    named(
                        Shooter("s"),
                        " is ",
                        Count("k", "Sunday"),
                        " running above their own average.",
                    ),
                    you=named("You are ", Count("k", "Sunday"), " running above your own average."),
                ),
            ),
            ROLLUP: (T(named("On a run above their own average: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "Own average = the average of every round before that Sunday. Each "
                        "Sunday in the run beat the average as it stood then."
                    ),
                    you=named(
                        "Your own average = the average of every round you shot before "
                        "that Sunday. Each Sunday in the run beat it."
                    ),
                ),
                T(
                    named(
                        "Needs 10 rounds before the run. Shown on the Sunday it reaches 6, 10, "
                        "15 or 20, and on the profile from 4. All round types count."
                    ),
                    you=named(
                        "Needs 10 of your rounds before the run. Shown on the Sunday it "
                        "reaches 6, 10, 15 or 20, and on your profile from 4."
                    ),
                ),
            ),
            ROLLUP: (T(named("Runs above their own average reaching 6, 10, 15 or 20 today.")),),
        },
        labels=(OWN_AVG_LABEL, ROLLUP_LABEL),
        chart=_own_avg_chart,
        proof=(count_rows("k", "score"),),
        evaluate=_own_avg,
    )
)


# --- pf.tier-run ---------------------------------------------------------------------------------

TIER_PROFILE_RUN = {45: 4, 40: 6, 35: 8}  # the qualifying length (measured: see Decisions)


def at_least(tier: int) -> RunTest:
    def ok(day: Day) -> bool:
        return day.score >= tier

    return ok


def _tier_run_fact(
    days: Sequence[Day], tier: int, k: int, *, variant: str, pages: frozenset[P]
) -> Fact:
    last = days[-1]
    return Fact(
        subject_id=str(last.shooter_id),
        anchor_date=last.date if variant != PROFILE else None,
        variant=variant,
        pages=pages,
        params={
            "s": last.shooter_id,
            "k": k,
            "tier": tier,
            "start": run_start(days, at_least(tier), k).date,
            "day": last.date,
        },
        strength=k / TIER_PROFILE_RUN[tier],
        named_shooter_ids=(last.shooter_id,),
    )


def _tier_run(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        upto = days[: i + 1]
        tier = own_tier(upto)
        if tier is None:
            continue
        k = run_back(upto, at_least(tier))
        if k == TIER_PROFILE_RUN[tier]:
            yield _tier_run_fact(upto, tier, k, variant="", pages=frozenset({P.SUNDAY, P.HOME}))
    for _sid, days in evergreen_days(fr, scope):
        tier = own_tier(days)
        if tier is None or not shot_recently(days, scope.as_of):
            continue
        k = run_back(days, at_least(tier))
        if k >= TIER_PROFILE_RUN[tier]:
            yield _tier_run_fact(days, tier, k, variant=PROFILE, pages=frozenset({P.PROFILE}))


def _tier_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return rollup_chart(fact)
    window, hl = run_window(fact, timedelta(weeks=2))
    query = charts.spec(
        Metric.SCORE, Agg.MAX, Dim.EVENT, window=window, shooters=(p_int(fact.params, "s"),)
    )
    return charts.explorer(
        query,
        label=charts.BEST_EACH_LABEL,
        chart_type="line",
        hl=hl,
        ref=p_int(fact.params, "tier"),
    )


_TIER_TEXT = T(
    named(Count("k", "Sunday"), " in a row at ", Int("tier"), " or better for ", Shooter("s"), "."),
    you=named(Count("k", "Sunday"), " in a row at ", Int("tier"), " or better for you."),
)

register(
    Kind(
        id="pf.tier-run",
        family=Family.STREAK,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        guard={"run_45": 4, "run_40": 6, "run_35": 8},
        params=frozenset({"s", "k", "tier", "start", "day", "names"}),
        templates={
            "": (_TIER_TEXT,),
            PROFILE: (_TIER_TEXT,),
            ROLLUP: (T(named("Long runs at their own high mark: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "The mark is the highest of 45, 40 or 35 reached on 10% to 60% of their "
                        "last 52 rounds. Each Sunday shot counts once, by its best round. Sundays "
                        "missed do not end the run."
                    ),
                    you=named(
                        "Your mark is the highest of 45, 40 or 35 you reached on 10% to 60% of "
                        "your last 52 rounds. Each Sunday counts once, by its best round. Sundays "
                        "missed do not end the run."
                    ),
                ),
                T(
                    named(
                        "Shown when a run reaches 4 in a row at 45, 6 at 40 or 8 at 35, and on "
                        "the profile while it lasts."
                    ),
                    you=named(
                        "Shown when your run reaches 4 in a row at 45, 6 at 40 or 8 at 35, and "
                        "on your profile while it lasts."
                    ),
                ),
            ),
            ROLLUP: (T(named("Each reached a long run at their own mark today.")),),
        },
        labels=(charts.BEST_EACH_LABEL, ROLLUP_LABEL),
        chart=_tier_chart,
        proof=(count_rows("k"), na("tier", "the dashed reference line")),
        evaluate=_tier_run,
        supersedes=frozenset({"pf.beat-field-streak"}),
    )
)


# --- pf.three-rising -----------------------------------------------------------------------------

RISING_BEST_OF = 20  # the last score beats every one of the 20 Sundays before it
RISING_TOTAL = 4


def _three_rising(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        if i < RISING_BEST_OF:
            continue
        d1, d2, d3 = days[i - 2 : i + 1]
        if not d1.score < d2.score < d3.score:
            continue
        rise = d3.score - d1.score
        if rise < RISING_TOTAL or d3.score <= max(d.score for d in days[i - RISING_BEST_OF : i]):
            continue
        yield Fact(
            subject_id=str(d3.shooter_id),
            anchor_date=d3.date,
            variant="",
            pages=frozenset({P.PROFILE, P.SUNDAY}),
            params={
                "s": d3.shooter_id,
                "a": d1.score,
                "b": d2.score,
                "c": d3.score,
                "d1": d1.date,
                "d2": d2.date,
                "day": d3.date,
            },
            strength=rise / RISING_TOTAL,
            named_shooter_ids=(d3.shooter_id,),
        )


def _rising_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return rollup_chart(fact)
    d1, d2, day = (p_date(fact.params, k) for k in ("d1", "d2", "day"))
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "trend",
        label=charts.BEST_EACH_LABEL,
        window=Window(min(d1, add_months(day, -3)), day),
        hl=Highlight(dates=(d1, d2, day)),
    )


register(
    Kind(
        id="pf.three-rising",
        family=Family.STREAK,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        kudos=True,
        guard={"best_of": RISING_BEST_OF, "total_rise": RISING_TOTAL},
        params=frozenset({"s", "a", "b", "c", "d1", "d2", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        "Scores up 3 Sundays straight for ",
                        Shooter("s"),
                        ": ",
                        Int("a"),
                        ", ",
                        Int("b"),
                        ", then ",
                        Int("c"),
                        ".",
                    ),
                    you=named(
                        "Your scores are up 3 Sundays straight: ",
                        Int("a"),
                        ", ",
                        Int("b"),
                        ", then ",
                        Int("c"),
                        ".",
                    ),
                ),
            ),
            ROLLUP: (T(named("Up 3 Sundays straight: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "The best round on each of the last 3 Sundays shot, each higher than "
                        "the one before, up 4 or more in all."
                    ),
                    you=named(
                        "Your best round on each of your last 3 Sundays, each higher than the "
                        "one before, up 4 or more in all."
                    ),
                ),
                T(
                    named("The last must beat every one of the 20 Sundays before it."),
                    you=named("Your last must beat every one of your 20 Sundays before it."),
                ),
            ),
            ROLLUP: (T(named("Each has 3 rising Sundays in a row.")),),
        },
        labels=(charts.BEST_EACH_LABEL, ROLLUP_LABEL),
        chart=_rising_chart,
        proof=(
            cell("a", "score", key="d1"),
            cell("b", "score", key="d2"),
            cell("c", "score", key="day"),
        ),
        evaluate=_three_rising,
    )
)


# --- pf.podium-run -------------------------------------------------------------------------------

PODIUM_RUN = 3
PODIUM_CROSSINGS = (3, 5, 10, 20)


def on_podium(day: Day) -> bool | None:
    """Held Sundays only; a Sunday with a field under 15 ends the run."""
    return finish_at(day, PODIUM_RUN)


def _podium_run(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        upto = days[: i + 1]
        if on_podium(upto[-1]) is not True:
            continue
        k = run_back(upto, on_podium)
        if k not in PODIUM_CROSSINGS:
            continue
        yield Fact(
            subject_id=str(upto[-1].shooter_id),
            anchor_date=upto[-1].date,
            variant="",
            pages=frozenset({P.PROFILE, P.SUNDAY}),
            params={
                "s": upto[-1].shooter_id,
                "k": k,
                "start": run_start(upto, on_podium, k).date,
                "day": upto[-1].date,
            },
            strength=k / PODIUM_RUN,
            named_shooter_ids=(upto[-1].shooter_id,),
        )


def _podium_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return rollup_chart(fact)
    window, hl = run_window(fact, timedelta(weeks=4))
    return charts.profile_chart(
        p_int(fact.params, "s"), "finishes", label=charts.FINISH_LABEL, window=window, hl=hl
    )


register(
    Kind(
        id="pf.podium-run",
        family=Family.STREAK,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        guard={"field": FINISH_FIELD, "crossings": len(PODIUM_CROSSINGS)},
        params=frozenset({"s", "k", "start", "day", "names"}),
        templates={
            "": (
                T(
                    named(Ordinal("k"), " podium in a row for ", Shooter("s"), "."),
                    you=named("Your ", Ordinal("k"), " podium in a row."),
                ),
            ),
            ROLLUP: (T(named("Podium runs going on: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "Podium = 1st, 2nd or 3rd by best round, ties sharing the place. Each "
                        "Sunday in the run had 15 or more shooters."
                    ),
                    you=named(
                        "Podium = 1st, 2nd or 3rd by your best round, ties sharing the place. "
                        "Each Sunday in the run had 15 or more shooters."
                    ),
                ),
                T(
                    named(
                        "Shown when a run reaches 3, 5, 10 or 20. Sundays missed do not end "
                        "the run; a smaller field does."
                    ),
                    you=named(
                        "Shown when your run reaches 3, 5, 10 or 20. Sundays you missed do "
                        "not end the run; a smaller field does."
                    ),
                ),
            ),
            ROLLUP: (T(named("Each has reached 3, 5, 10 or 20 podiums in a row.")),),
        },
        labels=(charts.FINISH_LABEL, ROLLUP_LABEL),
        chart=_podium_chart,
        proof=(count_rows("k"),),
        evaluate=_podium_run,
    )
)
