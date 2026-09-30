"""Form and improvement kinds (spec §2.2.1): a shooter against their own history or the field."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    Day,
    InsightFrames,
    add_months,
    anchor_days,
    evergreen_days,
    held_only,
    mean,
    shot_recently,
    stderr_diff,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Dec1,
    Int,
    NameList,
    Shooter,
    T,
    Year,
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
    mean_of,
    na,
    p_date,
    p_ids,
    p_int,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric

VS_FIELD_LABEL = T(
    named(Shooter("s"), " vs the field's middle score"),
    you=named("You vs the field's middle score"),
)


def vs_field_chart(fact: Fact, window: Window, hl: Highlight) -> ChartLink:
    """Explorer: the shooter's best round each Sunday minus the field's middle score."""
    sid = p_int(fact.params, "s")
    query = charts.spec(
        Metric.ADJUSTED, Agg.AVG, Dim.EVENT, window=window, shooters=(sid,), best=True
    )
    return charts.explorer(query, label=VS_FIELD_LABEL, chart_type="line", hl=hl, ref=0)


# --- pf.hot-form ---------------------------------------------------------------------------------

HOT_SUNDAYS = 5
HOT_MIN = 4.0
HOT_MIN_ROUNDS = 15


def _hot_form(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        if days[-1].rounds_through < HOT_MIN_ROUNDS or not shot_recently(days, scope.as_of):
            continue
        last = [d for d in held_only(days) if d.adjusted is not None][-HOT_SUNDAYS:]
        if len(last) < HOT_SUNDAYS:
            continue
        avg = mean([d.adjusted or 0.0 for d in last])
        if avg >= HOT_MIN:
            yield Fact(
                subject_id=str(sid),
                anchor_date=None,
                variant="",
                pages=frozenset({P.PROFILE}),
                params={
                    "s": sid,
                    "avg": round(avg, 1),
                    "first": last[0].date,
                    "last": last[-1].date,
                },
                strength=avg / HOT_MIN,
                named_shooter_ids=(sid,),
            )


def _hot_form_chart(fact: Fact) -> ChartLink:
    first, last = p_date(fact.params, "first"), p_date(fact.params, "last")
    return vs_field_chart(fact, Window(add_months(first, -1), last), Highlight(span=(first, last)))


register(
    Kind(
        id="pf.hot-form",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"min_avg": HOT_MIN, "sundays": HOT_SUNDAYS, "min_rounds": HOT_MIN_ROUNDS},
        params=frozenset({"s", "avg", "first", "last"}),
        templates={
            "": (
                T(
                    named(
                        "Last 5 Sundays: ",
                        Shooter("s"),
                        " averaged ",
                        Dec1("avg"),
                        " above the field's middle score.",
                    ),
                    you=named(
                        "Last 5 Sundays: you averaged ",
                        Dec1("avg"),
                        " above the field's middle score.",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Each Sunday: the best round minus the middle score of everyone who "
                        "shot that day. This is the average of the last 5 Sundays shot."
                    ),
                    you=named(
                        "Each Sunday: your best round minus the middle score of everyone "
                        "who shot that day, averaged over your last 5 Sundays."
                    ),
                ),
                T(
                    named(
                        "Shows at 4 or more above, with 15 or more rounds and a round in the "
                        "last 8 weeks. All round types count."
                    ),
                    you=named(
                        "Shows at 4 or more above, once you have 15 rounds and a round in "
                        "the last 8 weeks. All round types count."
                    ),
                ),
            )
        },
        labels=(VS_FIELD_LABEL,),
        chart=_hot_form_chart,
        proof=(mean_of("avg"),),
        evaluate=_hot_form,
    )
)


# --- pf.beat-own-usual ---------------------------------------------------------------------------

OWN_USUAL_MIN = 5.0
OWN_USUAL_PRIOR = 20
USUAL_LABEL = T(
    named(Shooter("s"), " vs usual for a day like this"),
    you=named("You vs your usual"),
)
RESULTS_LABEL = T(named("Results for the Sunday"))


def _beat_own_usual(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        d = days[i]
        if d.residual is None or d.expected is None or d.prior_rounds < OWN_USUAL_PRIOR:
            continue
        if d.residual < OWN_USUAL_MIN:
            continue
        yield Fact(
            subject_id=str(d.shooter_id),
            anchor_date=d.date,
            variant="",
            pages=frozenset({P.PROFILE, P.SUNDAY}),
            params={
                "s": d.shooter_id,
                "score": d.score,
                "usual": round(d.expected),
                "over": round(d.residual),
                "day": d.date,
            },
            strength=d.residual / OWN_USUAL_MIN,
            named_shooter_ids=(d.shooter_id,),
        )


def _own_usual_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    if fact.variant == ROLLUP:
        return charts.results_chart(day, p_ids(fact.params, "names"), label=RESULTS_LABEL)
    sid = p_int(fact.params, "s")
    query = charts.spec(
        Metric.RESIDUAL, Agg.MAX, Dim.EVENT, window=charts.recent(day), shooters=(sid,), best=True
    )
    return charts.explorer(
        query, label=USUAL_LABEL, chart_type="line", hl=Highlight(dates=(day,)), ref=0
    )


register(
    Kind(
        id="pf.beat-own-usual",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        kudos=True,
        expires={P.PROFILE: 1},  # the profile shows only the latest Sunday's (spec §2.2.1)
        guard={"min_over": OWN_USUAL_MIN, "min_prior_rounds": OWN_USUAL_PRIOR},
        params=frozenset({"s", "score", "usual", "over", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        "Well above ",
                        Shooter("s"),
                        "'s usual for a day like that: ",
                        Int("score"),
                        ", ",
                        Int("over"),
                        " over a usual of ",
                        Int("usual"),
                        ".",
                    ),
                    you=named(
                        "Well above your usual for a day like that: ",
                        Int("score"),
                        ", ",
                        Int("over"),
                        " over a usual of ",
                        Int("usual"),
                        ".",
                    ),
                ),
            ),
            ROLLUP: (T(named("Well above their usual today: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "Usual for a day like this = the score the skill model predicted for "
                        "them that Sunday, before the round, from their history and how the "
                        "day played."
                    ),
                    you=named(
                        "Your usual for a day like this = the score the skill model "
                        "predicted for you that Sunday, before the round."
                    ),
                ),
                T(
                    named("Shown at 5 or more over, with 20 or more earlier rounds."),
                    you=named("Shown at 5 or more over, once you have 20 earlier rounds."),
                ),
            ),
            ROLLUP: (T(named("Each shot 5 or more over their usual for a day like this.")),),
        },
        labels=(USUAL_LABEL, RESULTS_LABEL),
        chart=_own_usual_chart,
        proof=(
            cell("over"),
            na("score", "the score is on the Sunday's results"),
            na("usual", "the usual is the score minus the charted gap"),
        ),
        evaluate=_beat_own_usual,
    )
)


# --- pf.up-on-usual ------------------------------------------------------------------------------

UP_RECENT, UP_BEFORE = 10, 20
UP_MIN = 2.0
TREND_LABEL = T(
    named(Shooter("s"), "'s scores with the 10-Sunday average line"),
    you=named("Your scores with the 10-Sunday average line"),
)


def _up_on_usual(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        if len(days) < UP_RECENT + UP_BEFORE or not shot_recently(days, scope.as_of):
            continue
        recent = [float(d.score) for d in days[-UP_RECENT:]]
        before = [float(d.score) for d in days[-(UP_RECENT + UP_BEFORE) : -UP_RECENT]]
        gap = mean(recent) - mean(before)
        if gap < UP_MIN or gap < 2 * stderr_diff(recent, before):
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={
                "s": sid,
                "recent": round(mean(recent), 1),
                "gap": round(gap, 1),
                "start": days[-UP_RECENT].date,
                "day": days[-1].date,
            },
            strength=gap / UP_MIN,
            named_shooter_ids=(sid,),
        )


def _up_chart(fact: Fact) -> ChartLink:
    start, day = p_date(fact.params, "start"), p_date(fact.params, "day")
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "trend",
        label=TREND_LABEL,
        window=Window(add_months(day, -12), day),
        hl=Highlight(span=(start, day)),
        params={"line": "roll10"},
    )


register(
    Kind(
        id="pf.up-on-usual",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"recent": UP_RECENT, "before": UP_BEFORE, "min_gap": UP_MIN},
        params=frozenset({"s", "recent", "gap", "start", "day"}),
        templates={
            "": (
                T(
                    named(
                        "Last 10 Sundays: ",
                        Shooter("s"),
                        " averaged ",
                        Dec1("recent"),
                        ", ",
                        Dec1("gap"),
                        " better than the 20 Sundays before.",
                    ),
                    you=named(
                        "Last 10 Sundays: you averaged ",
                        Dec1("recent"),
                        ", ",
                        Dec1("gap"),
                        " better than your 20 Sundays before.",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "The average of the best round of each of the last 10 Sundays shot, "
                        "against the 20 Sundays shot before those."
                    ),
                    you=named(
                        "The average of your best round on each of your last 10 Sundays, "
                        "against your 20 Sundays before those."
                    ),
                ),
                T(
                    named(
                        "Shown at 2 or more better, when the gap is also at least twice what "
                        "chance alone gives, with a round in the last 8 weeks."
                    ),
                    you=named(
                        "Shown at 2 or more better, when the gap is also at least twice "
                        "what chance alone gives, with a round in the last 8 weeks."
                    ),
                ),
            )
        },
        labels=(TREND_LABEL,),
        chart=_up_chart,
        proof=(
            mean_of("recent", "score"),
            na("gap", "the earlier 20 Sundays sit left of the band"),
        ),
        evaluate=_up_on_usual,
    )
)


# --- pf.year-up ----------------------------------------------------------------------------------

YEAR_MIN_ROUNDS = 10
YEAR_UP_RAW, YEAR_UP_FIELD = 1.5, 1.0
YEAR_LABEL = T(named(Shooter("s"), "'s average by year"), you=named("Your average by year"))


def _year_split(days: tuple[Day, ...], year: int) -> tuple[list[float], list[float]]:
    own = [d for d in days if d.date.year == year]
    return [float(d.score) for d in own], [float(d.adjusted) for d in own if d.adjusted is not None]


def _year_up(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    this_year = scope.as_of.year
    for sid, days in evergreen_days(fr, scope):
        now, now_field = _year_split(days, this_year)
        then, then_field = _year_split(days, this_year - 1)
        if min(len(now), len(then)) < YEAR_MIN_ROUNDS or not now_field or not then_field:
            continue
        raw = mean(now) - mean(then)
        field_gain = mean(now_field) - mean(then_field)
        if raw < YEAR_UP_RAW or field_gain < YEAR_UP_FIELD:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={
                "s": sid,
                "this": round(mean(now), 1),
                "last": round(mean(then), 1),
                "year": this_year,
                "last_year": this_year - 1,
                "day": days[-1].date,
            },
            strength=raw / YEAR_UP_RAW,
            named_shooter_ids=(sid,),
        )


def _year_chart(fact: Fact) -> ChartLink:
    sid, year = p_int(fact.params, "s"), p_int(fact.params, "year")
    window = Window(date(year - 1, 1, 1), p_date(fact.params, "day"))
    scores = charts.spec(Metric.SCORE, Agg.AVG, Dim.YEAR, window=window, shooters=(sid,), best=True)
    field = charts.spec(
        Metric.ADJUSTED, Agg.AVG, Dim.YEAR, window=window, shooters=(sid,), best=True
    )
    return charts.explorer(scores, label=YEAR_LABEL, hl=Highlight(keys=(str(year),)), compare=field)


register(
    Kind(
        id="pf.year-up",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"min_rounds": YEAR_MIN_ROUNDS, "raw": YEAR_UP_RAW, "field": YEAR_UP_FIELD},
        params=frozenset({"s", "this", "last", "year", "last_year", "day"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        " is averaging ",
                        Dec1("this"),
                        " in ",
                        Year("year"),
                        " vs ",
                        Dec1("last"),
                        " in ",
                        Year("last_year"),
                        ", and gaining on the field's middle score too.",
                    ),
                    you=named(
                        "You are averaging ",
                        Dec1("this"),
                        " in ",
                        Year("year"),
                        " vs ",
                        Dec1("last"),
                        " in ",
                        Year("last_year"),
                        ", and gaining on the field's middle score too.",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "The average of the best round each Sunday, this calendar year and "
                        "last; each year needs 10 Sundays."
                    ),
                    you=named(
                        "The average of your best round each Sunday, this calendar year "
                        "and last; each year needs 10 of your Sundays."
                    ),
                ),
                T(
                    named(
                        "Shown when up 1.5 or more, and up 1 or more against the field's "
                        "middle score as well."
                    ),
                    you=named(
                        "Shown when you are up 1.5 or more, and up 1 or more against "
                        "the field's middle score as well."
                    ),
                ),
            )
        },
        labels=(YEAR_LABEL,),
        chart=_year_chart,
        proof=(cell("this", key="year"), cell("last", key="last_year")),
        evaluate=_year_up,
    )
)


# --- pf.years-up-run -----------------------------------------------------------------------------

RUN_RISE, RUN_TOTAL = 0.5, 1.5


def _years_up_run(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        latest = scope.as_of.year
        if len([d for d in days if d.date.year == latest]) < YEAR_MIN_ROUNDS:
            latest -= 1
        years = (latest - 2, latest - 1, latest)
        per_year = [[float(d.score) for d in days if d.date.year == y] for y in years]
        if min(len(scores) for scores in per_year) < YEAR_MIN_ROUNDS:
            continue
        a, b, c = (mean(scores) for scores in per_year)
        if b - a < RUN_RISE or c - b < RUN_RISE or c - a < RUN_TOTAL:
            continue
        pages = {P.PROFILE} | ({P.HOME} if scope.as_of.month == 1 else set())
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset(pages),
            params={
                "s": sid,
                "a": round(a, 1),
                "b": round(b, 1),
                "c": round(c, 1),
                "y1": years[0],
                "y2": years[1],
                "y3": years[2],
                "day": days[-1].date,
            },
            strength=(c - a) / RUN_TOTAL,
            named_shooter_ids=(sid,),
        )


def _years_run_chart(fact: Fact) -> ChartLink:
    sid = p_int(fact.params, "s")
    years = tuple(str(p_int(fact.params, key)) for key in ("y1", "y2", "y3"))
    window = Window(date(int(years[0]), 1, 1), p_date(fact.params, "day"))
    query = charts.spec(Metric.SCORE, Agg.AVG, Dim.YEAR, window=window, shooters=(sid,), best=True)
    return charts.explorer(query, label=YEAR_LABEL, hl=Highlight(keys=years))


register(
    Kind(
        id="pf.years-up-run",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"rise": RUN_RISE, "total": RUN_TOTAL, "min_rounds": YEAR_MIN_ROUNDS},
        params=frozenset({"s", "a", "b", "c", "y1", "y2", "y3", "day"}),
        templates={
            "": (
                T(
                    named(
                        "Three years running, ",
                        Shooter("s"),
                        " has averaged more: ",
                        Dec1("a"),
                        ", ",
                        Dec1("b"),
                        ", ",
                        Dec1("c"),
                        ".",
                    ),
                    you=named(
                        "Three years running, you have averaged more: ",
                        Dec1("a"),
                        ", ",
                        Dec1("b"),
                        ", ",
                        Dec1("c"),
                        ".",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "The average of the best round each Sunday, per calendar year, with "
                        "10 or more Sundays in each year."
                    ),
                    you=named(
                        "The average of your best round each Sunday, per calendar year, "
                        "with 10 or more of your Sundays in each."
                    ),
                ),
                T(
                    named(
                        "Each year is up 0.5 or more on the one before, 1.5 or more in all. "
                        "On the home page in January."
                    ),
                    you=named(
                        "Each of your years is up 0.5 or more on the one before, 1.5 or "
                        "more in all."
                    ),
                ),
            )
        },
        labels=(YEAR_LABEL,),
        chart=_years_run_chart,
        proof=(cell("a", key="y1"), cell("b", key="y2"), cell("c", key="y3")),
        evaluate=_years_up_run,
    )
)


# --- pf.gaining-on-field -------------------------------------------------------------------------

GAIN_MIN = 2.0
GAIN_WINDOW = timedelta(weeks=52)
GAIN_MIN_EACH, GAIN_CAREER_ROUNDS, GAIN_CAREER_EACH = 10, 30, 10


def _gaining(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        adj = [(d.date, float(d.adjusted)) for d in held_only(days) if d.adjusted is not None]
        window_start = scope.as_of - 2 * GAIN_WINDOW
        recent = [a for d, a in adj if d > scope.as_of - GAIN_WINDOW]
        before = [a for d, a in adj if window_start < d <= scope.as_of - GAIN_WINDOW]
        if min(len(recent), len(before)) >= GAIN_MIN_EACH:
            variant, gain, first = "two_years", mean(recent) - mean(before), window_start
        elif len(adj) >= GAIN_CAREER_ROUNDS:
            first_ten = [a for _, a in adj[:GAIN_CAREER_EACH]]
            last_ten = [a for _, a in adj[-GAIN_CAREER_EACH:]]
            variant, gain, first = "career", mean(last_ten) - mean(first_ten), adj[0][0]
        else:
            continue
        if gain < GAIN_MIN:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant=variant,
            pages=frozenset({P.PROFILE}),
            params={"s": sid, "gain": round(gain, 1), "first": first, "day": days[-1].date},
            strength=gain / GAIN_MIN,
            named_shooter_ids=(sid,),
        )


GAIN_LABEL = T(
    named(Shooter("s"), " vs the field's middle score by year"),
    you=named("You vs the field's middle score by year"),
)


def _gain_chart(fact: Fact) -> ChartLink:
    sid, day = p_int(fact.params, "s"), p_date(fact.params, "day")
    query = charts.spec(
        Metric.ADJUSTED,
        Agg.AVG,
        Dim.YEAR,
        window=Window(p_date(fact.params, "first"), day),
        shooters=(sid,),
        best=True,
    )
    return charts.explorer(query, label=GAIN_LABEL, ref=0)


_GAIN_HOW_LIMIT = T(
    named("Shown at 2 or more targets gained. All round types count."),
    you=named("Shown when you have gained 2 or more targets. All round types count."),
)

register(
    Kind(
        id="pf.gaining-on-field",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={
            "min_gain": GAIN_MIN,
            "min_each": GAIN_MIN_EACH,
            "career_rounds": GAIN_CAREER_ROUNDS,
        },
        params=frozenset({"s", "gain", "first", "day"}),
        templates={
            "two_years": (
                T(
                    named(
                        Shooter("s"),
                        " has gained ",
                        Dec1("gain"),
                        " targets on the field's middle score in two years.",
                    ),
                    you=named(
                        "You have gained ",
                        Dec1("gain"),
                        " targets on the field's middle score in two years.",
                    ),
                ),
            ),
            "career": (
                T(
                    named(
                        Shooter("s"),
                        " has gained ",
                        Dec1("gain"),
                        " targets on the field's middle score since their first 10 Sundays.",
                    ),
                    you=named(
                        "You have gained ",
                        Dec1("gain"),
                        " targets on the field's middle score since your first 10 Sundays.",
                    ),
                ),
            ),
        },
        how={
            "two_years": (
                T(
                    named(
                        "The average gap to the field's middle score over the last 52 weeks, "
                        "against the 52 weeks before; each needs 10 Sundays."
                    ),
                    you=named(
                        "Your average gap to the field's middle score over the last 52 "
                        "weeks, against the 52 weeks before."
                    ),
                ),
                _GAIN_HOW_LIMIT,
            ),
            "career": (
                T(
                    named(
                        "The average gap to the field's middle score over the last 10 "
                        "Sundays, against the first 10; needs 30 Sundays."
                    ),
                    you=named(
                        "Your average gap to the field's middle score over your last 10 "
                        "Sundays, against your first 10."
                    ),
                ),
                _GAIN_HOW_LIMIT,
            ),
        },
        labels=(GAIN_LABEL,),
        chart=_gain_chart,
        proof=(na("gain", "a difference of two windows; the yearly bars show the direction"),),
        evaluate=_gaining,
    )
)
