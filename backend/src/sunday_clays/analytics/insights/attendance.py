"""Attendance kinds (spec §2.2.2, §2.2.3): showing up, told as stats about the shooter only.

These are on the worse-at-everything allowlist (§5): the streak kinds never quote a score, a
finish or a residual, so they can name anyone who keeps coming. `pf.year-wrapped` quotes only
the shooter's own best round, and a finish only when it was in the top third.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterator, Sequence
from datetime import date

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    SHOOTER_WRAP_MIN,
    Day,
    InsightFrames,
    anchor_days,
    evergreen_days,
    held_only,
    jan1,
    top_third,
    wrap_year,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
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
    count_rows,
    distinct,
    na,
    p_date,
    p_int,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric

RESULTS_LABEL = charts.RESULTS_LABEL


def _cal(
    fact: Fact, window: Window, hl: Highlight, params: dict[str, str] | None = None
) -> ChartLink:
    return charts.profile_chart(
        p_int(fact.params, "s"), "cal", label=charts.CAL_LABEL, window=window, hl=hl, params=params
    )


# --- pf.attendance-year --------------------------------------------------------------------------

YEAR_SHARE = 0.85
YEAR_MIN_HELD = 8


def _attendance_year(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    year = scope.as_of.year
    held = [s.date for s in fr.sundays if s.date.year == year and s.date <= scope.as_of]
    if len(held) < YEAR_MIN_HELD:
        return
    for sid, days in evergreen_days(fr, scope):
        shot = sum(d.held and d.date.year == year for d in days)
        share = shot / len(held)
        if share < YEAR_SHARE:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="every" if shot == len(held) else "",
            pages=frozenset({P.PROFILE, P.HOME}),
            params={"s": sid, "shot": shot, "held": len(held), "year": year, "day": scope.as_of},
            strength=share / YEAR_SHARE,
            named_shooter_ids=(sid,),
        )


register(
    Kind(
        id="pf.attendance-year",
        family=Family.STREAK,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.HOME}),
        polarity=Polarity.NEUTRAL,
        care=3,
        anchored=False,
        guard={"share": YEAR_SHARE, "min_held": YEAR_MIN_HELD},
        params=frozenset({"s", "shot", "held", "year", "day"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        " has shot ",
                        Int("shot"),
                        " of ",
                        Count("held", "Sunday"),
                        " this year.",
                    ),
                    you=named(
                        "You have shot ",
                        Int("shot"),
                        " of ",
                        Count("held", "Sunday"),
                        " this year.",
                    ),
                ),
            ),
            "every": (
                T(
                    named(
                        Shooter("s"),
                        " has shot every one of the ",
                        Count("held", "Sunday"),
                        " this year.",
                    ),
                    you=named(
                        "You have shot every one of the ", Count("held", "Sunday"), " this year."
                    ),
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Sundays with full results this calendar year; shown at 85% or more "
                        "once 8 have been held."
                    ),
                    you=named(
                        "Sundays with full results this calendar year; shown at 85% or "
                        "more once 8 have been held."
                    ),
                ),
            )
        },
        labels=(charts.CAL_LABEL,),
        chart=lambda fact: _cal(
            fact, Window(jan1(p_date(fact.params, "day")), p_date(fact.params, "day")), Highlight()
        ),
        proof=(count_rows("shot", "held_value"), na("held", "the Sundays held this year")),
        evaluate=_attendance_year,
    )
)


# --- pf.attendance-streak ------------------------------------------------------------------------

STREAK_PROFILE = 5
STREAK_HOME_STEP = 10


def held_run(fr: InsightFrames, days: Sequence[Day]) -> tuple[int, date | None]:
    """(held Sundays in a row ending at the last day, the run's first Sunday); C7 `streaks`."""
    positions = [fr.sunday_index[d.date] for d in held_only(days)]
    if not positions or positions[-1] != fr.sunday_index.get(days[-1].date):
        return 0, None
    k = 1
    while k < len(positions) and positions[-k - 1] == positions[-k] - 1:
        k += 1
    return k, fr.sundays[positions[-k]].date


def longest_before(fr: InsightFrames, days: Sequence[Day]) -> int:
    positions = [fr.sunday_index[d.date] for d in held_only(days)]
    longest = run = 0
    for j, pos in enumerate(positions):
        run = run + 1 if j and pos == positions[j - 1] + 1 else 1
        longest = max(longest, run)
    return longest


def _streak_fact(
    fr: InsightFrames, days: Sequence[Day], *, variant: str, pages: frozenset[P]
) -> Fact | None:
    k, start = held_run(fr, days)
    if start is None:
        return None
    last = days[-1]
    longest = longest_before(fr, days[:-1]) < k
    return Fact(
        subject_id=str(last.shooter_id),
        anchor_date=last.date if variant != PROFILE else None,
        variant=(f"{variant}_longest" if variant else "longest") if longest else variant,
        pages=pages,
        params={"s": last.shooter_id, "k": k, "start": start, "day": last.date},
        strength=k / STREAK_PROFILE,
        named_shooter_ids=(last.shooter_id,),
    )


def _attendance_streak(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        upto = days[: i + 1]
        k, _start = held_run(fr, upto)
        if k >= STREAK_HOME_STEP and k % STREAK_HOME_STEP == 0:
            fact = _streak_fact(fr, upto, variant="", pages=frozenset({P.HOME}))
            if fact is not None:
                yield fact
    for _sid, days in evergreen_days(fr, scope):
        if days[-1].date != scope.as_of:
            continue
        k, _start = held_run(fr, days)
        if k >= STREAK_PROFILE:
            fact = _streak_fact(fr, days, variant=PROFILE, pages=frozenset({P.PROFILE}))
            if fact is not None:
                yield fact


def _streak_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    start, day = p_date(fact.params, "start"), p_date(fact.params, "day")
    return _cal(fact, Window(start, day), Highlight(span=(start, day)))


_STREAK = T(
    named(Shooter("s"), " has shot ", Count("k", "Sunday"), " in a row."),
    you=named("You have shot ", Count("k", "Sunday"), " in a row."),
)
_STREAK_LONGEST = T(
    named(Shooter("s"), " has shot ", Count("k", "Sunday"), " in a row, their longest run yet."),
    you=named("You have shot ", Count("k", "Sunday"), " in a row, your longest run yet."),
)

register(
    Kind(
        id="pf.attendance-streak",
        family=Family.STREAK,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.HOME}),
        polarity=Polarity.NEUTRAL,
        care=3,
        anchored=True,
        guard={"profile_run": STREAK_PROFILE, "home_step": STREAK_HOME_STEP},
        params=frozenset({"s", "k", "start", "day", "names"}),
        templates={
            "": (_STREAK,),
            "longest": (_STREAK_LONGEST,),
            PROFILE: (_STREAK,),
            f"{PROFILE}_longest": (_STREAK_LONGEST,),
            ROLLUP: (T(named("Long runs of Sundays in a row: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "Every Sunday with full results in a row, with no gaps. Sundays "
                        "without full results neither add to nor end the run."
                    ),
                    you=named(
                        "Every Sunday with full results in a row, with no gaps. Sundays "
                        "without full results neither add to nor end your run."
                    ),
                ),
                T(
                    named("On the profile from 5 in a row; on home at 10, 20, 30 and so on."),
                    you=named("On your profile from 5 in a row; on home at 10, 20, 30 and so on."),
                ),
            ),
            ROLLUP: (T(named("Each reached 10, 20, 30 or more Sundays in a row today.")),),
        },
        labels=(charts.CAL_LABEL, RESULTS_LABEL),
        chart=_streak_chart,
        proof=(count_rows("k", "held_value"),),
        evaluate=_attendance_streak,
    )
)


# --- pf.months-in-row ----------------------------------------------------------------------------

MONTHS_PROFILE = 12
MONTHS_HOME_STEP = 12
MONTHS_HOME_MIN = 24


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def months_in_row(fr: InsightFrames, days: Sequence[Day], until: date) -> list[str]:
    """Months (newest last) in the run ending at `until`'s month: a month with a held Sunday
    must have a round; a month without one is skipped."""
    shot = {(d.date.year, d.date.month) for d in days if d.date <= until}
    starts = fr.held_month_starts
    held_months = [key for _, key in starts[: bisect_right(fr.held_month_first_dates, until)]]
    if held_months and held_months[-1] == month_key(until) and _ym(held_months[-1]) not in shot:
        held_months.pop()  # the month in progress is not missed yet
    run: list[str] = []
    for month in reversed(held_months):
        if _ym(month) not in shot:
            break
        run.append(month)
    return run[::-1]


def _ym(key: str) -> tuple[int, int]:
    return int(key[:4]), int(key[5:])


def _months_fact(
    fr: InsightFrames, days: Sequence[Day], months: list[str], *, variant: str, pages: frozenset[P]
) -> Fact:
    last = days[-1]
    return Fact(
        subject_id=str(last.shooter_id),
        anchor_date=last.date if variant != PROFILE else None,
        variant=variant,
        pages=pages,
        params={
            "s": last.shooter_id,
            "months": len(months),
            "start": date.fromisoformat(f"{months[0]}-01"),
            "day": last.date,
        },
        strength=len(months) / MONTHS_PROFILE,
        named_shooter_ids=(last.shooter_id,),
    )


def _months(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        upto = days[: i + 1]
        if i and month_key(days[i - 1].date) == month_key(upto[-1].date):
            continue  # only the month's first Sunday shot can extend the run
        months = months_in_row(fr, upto, upto[-1].date)
        n = len(months)
        if n >= MONTHS_HOME_MIN and n % MONTHS_HOME_STEP == 0:
            yield _months_fact(fr, upto, months, variant="", pages=frozenset({P.HOME}))
    for _sid, days in evergreen_days(fr, scope):
        months = months_in_row(fr, days, scope.as_of)
        if len(months) >= MONTHS_PROFILE:
            yield _months_fact(fr, days, months, variant=PROFILE, pages=frozenset({P.PROFILE}))


def _months_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    start, day = p_date(fact.params, "start"), p_date(fact.params, "day")
    keys = tuple(month_key(m) for m in _month_starts(start, day))
    return _cal(fact, Window(start, day), Highlight(keys=keys), params={"view": "month"})


def _month_starts(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day = date(day.year + (day.month == 12), day.month % 12 + 1, 1)


_MONTHS = T(
    named(
        "At least one Sunday in each of the last ",
        Count("months", "month"),
        " for ",
        Shooter("s"),
        ".",
    ),
    you=named(
        "You have shot at least one Sunday in each of the last ", Count("months", "month"), "."
    ),
)

register(
    Kind(
        id="pf.months-in-row",
        family=Family.STREAK,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.HOME}),
        polarity=Polarity.NEUTRAL,
        care=2,
        anchored=True,
        guard={"profile_months": MONTHS_PROFILE, "home_months": MONTHS_HOME_MIN},
        params=frozenset({"s", "months", "start", "day", "names"}),
        templates={
            "": (_MONTHS,),
            PROFILE: (_MONTHS,),
            ROLLUP: (T(named("A Sunday every month for years now: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "Calendar months in a row with at least one round, up to this month. "
                        "A month with no Sunday held is skipped."
                    ),
                    you=named(
                        "Calendar months in a row with at least one round of yours, up to "
                        "this month. A month with no Sunday held is skipped."
                    ),
                ),
                T(
                    named("On the profile from 12 months; on home at 24, 36, 48 and so on."),
                    you=named("On your profile from 12 months; on home at 24, 36, 48 and so on."),
                ),
            ),
            ROLLUP: (T(named("Each reached 24, 36 or more months in a row today.")),),
        },
        labels=(charts.CAL_LABEL, RESULTS_LABEL),
        chart=_months_chart,
        proof=(distinct("months", "month"),),
        evaluate=_months,
    )
)


# --- pf.year-wrapped -----------------------------------------------------------------------------


def _year_wrapped(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    year = wrap_year(scope.as_of)
    if year is None:
        return
    for sid, days in evergreen_days(fr, scope):
        in_year = [d for d in days if d.date.year == year]
        if len(in_year) < SHOOTER_WRAP_MIN:
            continue
        targets = sum(sum(d.scores) for d in in_year)
        finishes = [d for d in in_year if top_third(d)]
        params: dict[str, object] = {
            "s": sid,
            "year": year,
            "sundays": len(in_year),
            "targets": targets,
            "best": max(d.score for d in in_year),
        }
        if finishes:
            params["finish"] = min(d.rank or 0 for d in finishes)
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="finish" if finishes else "",
            pages=frozenset({P.PROFILE, P.HOME}),
            params=params,
            strength=1.0,
            named_shooter_ids=(sid,),
        )


WRAPPED_LABEL = T(named(Shooter("s"), "'s average by month"), you=named("Your average by month"))


def _wrapped_chart(fact: Fact) -> ChartLink:
    year = p_int(fact.params, "year")
    query = charts.spec(
        Metric.SCORE,
        Agg.AVG,
        Dim.MONTH,
        window=Window(date(year, 1, 1), date(year, 12, 31)),
        shooters=(p_int(fact.params, "s"),),
    )
    return charts.explorer(query, label=WRAPPED_LABEL)


_WRAP_HEAD = (
    Year("year"),
    ": ",
    Count("sundays", "Sunday"),
    ", ",
    Int("targets"),
    " targets, best ",
    Int("best"),
)

register(
    Kind(
        id="pf.year-wrapped",
        family=Family.RECAP,
        home_slot=None,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.HOME}),
        polarity=Polarity.NEUTRAL,
        care=3,
        anchored=False,
        guard={"min_sundays": SHOOTER_WRAP_MIN},
        params=frozenset({"s", "year", "sundays", "targets", "best", "finish"}),
        templates={
            "": (
                T(
                    named(Shooter("s"), "'s ", *_WRAP_HEAD, "."),
                    you=named("Your ", *_WRAP_HEAD, "."),
                ),
            ),
            "finish": (
                T(
                    named(
                        Shooter("s"), "'s ", *_WRAP_HEAD, ", best finish ", Ordinal("finish"), "."
                    ),
                    you=named("Your ", *_WRAP_HEAD, ", best finish ", Ordinal("finish"), "."),
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "The calendar year in numbers: Sundays shot, targets broken in every "
                        "round, the best round. Shown in December and January."
                    ),
                    you=named(
                        "Your calendar year in numbers: Sundays shot, targets broken in "
                        "every round, your best round. Shown in December and January."
                    ),
                ),
                T(
                    named("The best finish shows only when it was in the top third of the field."),
                    you=named(
                        "Your best finish shows only when it was in the top third of the field."
                    ),
                ),
            )
        },
        labels=(WRAPPED_LABEL,),
        chart=_wrapped_chart,
        proof=(
            na("sundays", "the calendar on the profile"),
            na("targets", "the season summary on the profile"),
            na("best", "the highest monthly bar is an average; the best round is on the trend"),
            na("finish", "the finish strip on the profile"),
        ),
        evaluate=_year_wrapped,
        expires={},
    )
)
