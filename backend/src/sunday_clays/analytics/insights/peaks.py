"""Peak kinds (spec §2.2.1): best stretches, averages crossing a level, highs and best days."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterator
from datetime import date, timedelta

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    InsightFrames,
    add_months,
    anchor_days,
    crossed,
    evergreen_days,
    held_only,
    jan1,
    mean,
    shot_recently,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Dec1,
    FullDate,
    Int,
    NameList,
    Shooter,
    ShortDate,
    Signed,
    T,
    Template,
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
    p_int,
)
from sunday_clays.analytics.profile import learning_curve
from sunday_clays.explorer.spec import Agg, Dim, Metric

RESULTS_LABEL = charts.RESULTS_LABEL


def _trend(
    fact: Fact, label: Template, window: Window, hl: Highlight, line: str | None
) -> ChartLink:
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "trend",
        label=label,
        window=window,
        hl=hl,
        params={} if line is None else {"line": line},
    )


# --- pf.best-stretch ------------------------------------------------------------------------------

STRETCH = 10
STRETCH_MIN_ROUNDS = 30
STRETCH_OVER_BEST = 0.3
STRETCH_OVER_CAREER = 2.0
ROLL10_LABEL = T(
    named(Shooter("s"), "'s scores with the 10-Sunday average line"),
    you=named("Your scores with the 10-Sunday average line"),
)


def _best_stretch(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        upto = days[: i + 1]
        if upto[-1].rounds_through < STRETCH_MIN_ROUNDS or len(upto) < STRETCH + 1:
            continue
        scores = [float(d.score) for d in upto]
        now = mean(scores[-STRETCH:])
        earlier = max(mean(scores[j : j + STRETCH]) for j in range(len(scores) - STRETCH))
        career = mean(scores)
        if now < earlier + STRETCH_OVER_BEST or now < career + STRETCH_OVER_CAREER:
            continue
        yield Fact(
            subject_id=str(upto[-1].shooter_id),
            anchor_date=upto[-1].date,
            variant="",
            pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
            params={
                "s": upto[-1].shooter_id,
                "avg": round(now, 1),
                "start": upto[-STRETCH].date,
                "day": upto[-1].date,
            },
            strength=(now - career) / STRETCH_OVER_CAREER,
            named_shooter_ids=(upto[-1].shooter_id,),
        )


def _stretch_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    start, day = p_date(fact.params, "start"), p_date(fact.params, "day")
    window = Window(min(start, add_months(day, -6)), day)
    return _trend(fact, ROLL10_LABEL, window, Highlight(span=(start, day)), "roll10")


register(
    Kind(
        id="pf.best-stretch",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        guard={
            "min_rounds": STRETCH_MIN_ROUNDS,
            "over_best": STRETCH_OVER_BEST,
            "over_career": STRETCH_OVER_CAREER,
        },
        params=frozenset({"s", "avg", "start", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"), "'s best 10-Sunday stretch ever: ", Dec1("avg"), " a round."
                    ),
                    you=named("Your best 10-Sunday stretch ever: ", Dec1("avg"), " a round."),
                ),
            ),
            ROLLUP: (T(named("Best 10-Sunday stretches ever: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "The average of the best round on each of the last 10 Sundays shot, "
                        "higher than any earlier 10 Sundays in a row by 0.3 or more."
                    ),
                    you=named(
                        "The average of your best round on each of your last 10 Sundays, "
                        "higher than any earlier 10 in a row by 0.3 or more."
                    ),
                ),
                T(
                    named(
                        "Needs 30 rounds, and the stretch must be 2 or more over their career "
                        "average."
                    ),
                    you=named(
                        "Needs 30 rounds, and the stretch must be 2 or more over your "
                        "career average."
                    ),
                ),
            ),
            ROLLUP: (T(named("Each has just set their best 10-Sunday average.")),),
        },
        labels=(ROLL10_LABEL, RESULTS_LABEL),
        chart=_stretch_chart,
        proof=(mean_of("avg", "score"),),
        evaluate=_best_stretch,
    )
)


# --- pf.average-milestone -------------------------------------------------------------------------

AVG_WINDOW = 20
AVG_LEVELS = (30, 35, 40, 45)
AVG_STRENGTH = {30: 1.0, 35: 1.25, 40: 1.5, 45: 2.0}
AVG_YEAR_GAIN = 1.0
ROLL20_LABEL = T(
    named(Shooter("s"), "'s scores with the 20-Sunday average line"),
    you=named("Your scores with the 20-Sunday average line"),
)


def _average_milestone(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    # rolling[k] is the mean of days[k : k + AVG_WINDOW], so it is the same at every anchor; each
    # anchor at i reads the first i - AVG_WINDOW + 2 of them.
    cache: dict[int, tuple[list[float], list[float], list[date]]] = {}
    for i, days in anchor_days(fr, scope):
        upto = days[: i + 1]
        if len(upto) < AVG_WINDOW + 1:
            continue
        if id(days) not in cache:
            full = [
                mean([float(d.score) for d in days[k : k + AVG_WINDOW]])
                for k in range(len(days) - AVG_WINDOW + 1)
            ]
            best = [full[0]]
            for r in full[1:]:
                best.append(max(best[-1], r))
            cache[id(days)] = (full, best, [d.date for d in days[AVG_WINDOW - 1 :]])
        full, best, dates = cache[id(days)]
        last = i - AVG_WINDOW + 1  # index in `full` of the current rolling average
        rolling_now = full[last]
        level = crossed(best[last - 1], rolling_now, AVG_LEVELS)
        if level is None:
            continue
        stop = bisect_right(dates, upto[-1].date - timedelta(days=364), 0, last + 1)
        if stop and rolling_now < full[stop - 1] + AVG_YEAR_GAIN:
            continue
        yield Fact(
            subject_id=str(upto[-1].shooter_id),
            anchor_date=upto[-1].date,
            variant="",
            pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
            params={
                "s": upto[-1].shooter_id,
                "level": level,
                "avg": round(rolling_now, 1),
                "day": upto[-1].date,
            },
            strength=AVG_STRENGTH[level],
            named_shooter_ids=(upto[-1].shooter_id,),
        )


def _avg_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    day = p_date(fact.params, "day")
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "trend",
        label=ROLL20_LABEL,
        window=Window(add_months(day, -12), day),
        hl=Highlight(dates=(day,)),
        params={"line": "roll20", "ref": str(p_int(fact.params, "level"))},
    )


register(
    Kind(
        id="pf.average-milestone",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        expires={P.HOME: 3, P.PROFILE: 4},
        guard={"window": AVG_WINDOW, "year_gain": AVG_YEAR_GAIN},
        params=frozenset({"s", "level", "avg", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        "'s 20-Sunday average just went over ",
                        Int("level"),
                        " for the first time: ",
                        Dec1("avg"),
                        ".",
                    ),
                    you=named(
                        "Your 20-Sunday average just went over ",
                        Int("level"),
                        " for the first time: ",
                        Dec1("avg"),
                        ".",
                    ),
                ),
            ),
            ROLLUP: (T(named("20-Sunday averages over a new mark: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "The average of the best round on each of the last 20 Sundays shot, "
                        "crossing 30, 35, 40 or 45 for the first time."
                    ),
                    you=named(
                        "The average of your best round on each of your last 20 Sundays, "
                        "crossing 30, 35, 40 or 45 for the first time."
                    ),
                ),
                T(
                    named("It must also be 1 or more above where it stood a year ago."),
                    you=named("It must also be 1 or more above where yours stood a year ago."),
                ),
            ),
            ROLLUP: (
                T(named("Each 20-Sunday average crossed 30, 35, 40 or 45 for the first time.")),
            ),
        },
        labels=(ROLL20_LABEL, RESULTS_LABEL),
        chart=_avg_chart,
        proof=(cell("avg", "roll20"), na("level", "the round number the line has just crossed")),
        evaluate=_average_milestone,
    )
)


# --- pf.rating-high -------------------------------------------------------------------------------

RATING_MIN_ROUNDS = 15
RATING_LOOKBACK = 8
RATING_RISE = 0.5
RATING_LABEL = T(named(Shooter("s"), "'s skill rating"), you=named("Your skill rating"))


def _rating_high(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        points = [p for p in fr.ratings.get(sid, ()) if p[0] <= scope.as_of]
        if len(points) < max(RATING_MIN_ROUNDS, RATING_LOOKBACK + 1) or not shot_recently(
            days, scope.as_of
        ):
            continue
        now = points[-1][1]
        if any(mu > now for _d, mu in points[:-1]):
            continue
        rise = now - points[-1 - RATING_LOOKBACK][1]
        if rise < RATING_RISE:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE, P.HOME}),
            params={"s": sid, "rise": round(rise, 1), "day": points[-1][0]},
            strength=rise / RATING_RISE,
            named_shooter_ids=(sid,),
        )


def _rating_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "rating",
        label=RATING_LABEL,
        window=Window(add_months(day, -12), day),
        hl=Highlight(dates=(day,)),
    )


register(
    Kind(
        id="pf.rating-high",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"min_rounds": RATING_MIN_ROUNDS, "rise": RATING_RISE, "lookback": RATING_LOOKBACK},
        params=frozenset({"s", "rise", "day"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        "'s skill rating is at an all-time high, up ",
                        Dec1("rise"),
                        " in the last 8 Sundays.",
                    ),
                    you=named(
                        "Your skill rating is at an all-time high, up ",
                        Dec1("rise"),
                        " in the last 8 Sundays.",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Skill rating = the model's estimate of current skill, in targets. "
                        "It is higher now than at any earlier Sunday."
                    ),
                    you=named(
                        "Skill rating = the model's estimate of your current skill, in "
                        "targets. Yours is higher now than at any earlier Sunday."
                    ),
                ),
                T(
                    named(
                        "Needs 15 rated Sundays, a rise of 0.5 or more over their last 8, and "
                        "a round in the last 8 weeks."
                    ),
                    you=named(
                        "Needs 15 rated Sundays, a rise of 0.5 or more over your last 8, "
                        "and a round in the last 8 weeks."
                    ),
                ),
            )
        },
        labels=(RATING_LABEL,),
        chart=_rating_chart,
        proof=(na("rise", "the gap between the highlighted point and 8 points earlier"),),
        evaluate=_rating_high,
    )
)


# --- pf.learning-curve ----------------------------------------------------------------------------

LEARN_K = 10
LEARN_GAP = 2.0
LEARN_MAX_SUNDAYS = 40
LEARN_LABEL = T(
    named(Shooter("s"), "'s learning curve vs the club"),
    you=named("Your learning curve vs the club"),
)


def _learning_curve(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        if fr.profiles[sid].left_censored or len(days) > LEARN_MAX_SUNDAYS:
            continue
        points = learning_curve(fr.rounds, fr.shooters, sid)[:LEARN_K]
        if len(points) < LEARN_K or any(p.club_median is None for p in points):
            continue
        mine = mean([p.value for p in points])
        club = mean([p.club_median or 0.0 for p in points])
        if mine < club + LEARN_GAP:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={
                "s": sid,
                "own": round(mine, 1),
                "club": round(club, 1),
                "first": days[0].date,
                "day": days[-1].date,
            },
            strength=(mine - club) / LEARN_GAP,
            named_shooter_ids=(sid,),
        )


def _learn_chart(fact: Fact) -> ChartLink:
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "learn",
        label=LEARN_LABEL,
        window=Window(p_date(fact.params, "first"), p_date(fact.params, "day")),
        hl=Highlight(keys=tuple(str(k) for k in range(1, LEARN_K + 1))),
    )


register(
    Kind(
        id="pf.learning-curve",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"sundays": LEARN_K, "gap": LEARN_GAP, "max_sundays": LEARN_MAX_SUNDAYS},
        params=frozenset({"s", "own", "club", "first", "day"}),
        templates={
            "": (
                T(
                    named(
                        "Ahead of the usual pace: over their first 10 Sundays, ",
                        Shooter("s"),
                        " averaged ",
                        Signed("own"),
                        " against the field's middle score; the club's newcomer line averages ",
                        Signed("club"),
                        ".",
                    ),
                    you=named(
                        "Ahead of the usual pace: over your first 10 Sundays you averaged ",
                        Signed("own"),
                        " against the field's middle score; the club's newcomer line averages ",
                        Signed("club"),
                        ".",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Each of the first 10 Sundays with full results: the average round "
                        "minus the middle score of everyone who shot."
                    ),
                    you=named(
                        "Each of your first 10 Sundays with full results: your average "
                        "round minus the middle score of everyone who shot."
                    ),
                ),
                T(
                    named(
                        "The newcomer line is the club's middle value at Sunday 1, 2, ... 10, "
                        "leaving out shooters whose first Sunday is before our records."
                    ),
                    you=named(
                        "The newcomer line is the club's middle value at Sunday 1, 2, ... "
                        "10, leaving out shooters whose first Sunday predates our records."
                    ),
                ),
                T(
                    named("Shown at 2 or more ahead, while they have shot 40 Sundays or fewer."),
                    you=named("Shown at 2 or more ahead, while you have shot 40 Sundays or fewer."),
                ),
            )
        },
        labels=(LEARN_LABEL,),
        chart=_learn_chart,
        proof=(mean_of("own"), mean_of("club", "club")),
        evaluate=_learning_curve,
    )
)


# --- pf.season-best -------------------------------------------------------------------------------

SEASON_RECENT = 8
SEASON_MIN_ROUNDS = 5
SEASON_OVER_AVG = 3.0
SEASON_LABEL = T(named(Shooter("s"), "'s scores this year"), you=named("Your scores this year"))


def _season_best(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    year = scope.as_of.year
    for sid, days in evergreen_days(fr, scope):
        this_year = [d for d in days if d.date.year == year]
        if len(this_year) < SEASON_MIN_ROUNDS:
            continue
        # ties keep the earliest date: the card quotes when the mark was first set
        best = max(this_year, key=lambda d: (d.score, -d.date.toordinal()))
        average = mean([float(d.score) for d in this_year])
        is_pb = (
            best.prior_rounds >= 5 and best.prior_best is not None and best.score > best.prior_best
        )
        recent = fr.held_between(best.date, scope.as_of) < SEASON_RECENT
        if is_pb or not recent or best.score < average + SEASON_OVER_AVG:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={
                "s": sid,
                "best": best.score,
                "year": year,
                "day": best.date,
                "latest": days[-1].date,
            },
            strength=(best.score - average) / SEASON_OVER_AVG,
            named_shooter_ids=(sid,),
        )


register(
    Kind(
        id="pf.season-best",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=2,
        anchored=False,
        guard={
            "recent_sundays": SEASON_RECENT,
            "min_rounds": SEASON_MIN_ROUNDS,
            "over_avg": SEASON_OVER_AVG,
        },
        params=frozenset({"s", "best", "year", "day", "latest"}),
        templates={
            "": (
                T(
                    named(
                        "Best round of ",
                        Year("year"),
                        " so far for ",
                        Shooter("s"),
                        ": ",
                        Int("best"),
                        " on ",
                        ShortDate("day"),
                        ".",
                    ),
                    you=named(
                        "Your best round of ",
                        Year("year"),
                        " so far: ",
                        Int("best"),
                        " on ",
                        ShortDate("day"),
                        ".",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "The highest round this calendar year, set in the last 8 Sundays and "
                        "3 or more over their average for the year."
                    ),
                    you=named(
                        "Your highest round this calendar year, set in the last 8 Sundays "
                        "and 3 or more over your average for the year."
                    ),
                ),
                T(
                    named(
                        "Needs 5 Sundays this year. A personal best shows as a personal best "
                        "instead."
                    ),
                    you=named(
                        "Needs 5 of your Sundays this year. A personal best shows as a "
                        "personal best instead."
                    ),
                ),
            )
        },
        labels=(SEASON_LABEL,),
        chart=lambda fact: _trend(
            fact,
            SEASON_LABEL,
            Window(jan1(p_date(fact.params, "day")), p_date(fact.params, "latest")),
            Highlight(dates=(p_date(fact.params, "day"),)),
            None,
        ),
        proof=(cell("best", "score"),),
        evaluate=_season_best,
    )
)


# --- pf.best-day-vs-field -------------------------------------------------------------------------

BEST_DAY_MIN = 10.0
BEST_DAY_FALLBACK = 6.0
BEST_DAY_LABEL = T(
    named(Shooter("s"), " vs the field's middle score"),
    you=named("You vs the field's middle score"),
)


def _best_day(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        field_days = [d for d in held_only(days) if d.adjusted is not None]
        if not field_days:
            continue
        best = max(field_days, key=lambda d: (d.adjusted or 0.0, -d.date.toordinal()))
        gap = best.adjusted or 0.0
        if gap >= BEST_DAY_MIN:
            variant, strength = "", gap / BEST_DAY_MIN
        elif gap >= BEST_DAY_FALLBACK:
            variant, strength = "fallback", 1.0
        else:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant=variant,
            pages=frozenset({P.PROFILE}),
            params={"s": sid, "best": round(gap, 1), "day": best.date, "latest": days[-1].date},
            strength=strength,
            named_shooter_ids=(sid,),
        )


def _best_day_chart(fact: Fact) -> ChartLink:
    day, latest = p_date(fact.params, "day"), p_date(fact.params, "latest")
    window = Window(add_months(day, -3), min(add_months(day, 3), latest))
    query = charts.spec(
        Metric.ADJUSTED, Agg.MAX, Dim.EVENT, window=window, shooters=(p_int(fact.params, "s"),)
    )
    return charts.explorer(
        query, label=BEST_DAY_LABEL, chart_type="line", hl=Highlight(dates=(day,)), ref=0
    )


_BEST_DAY_TEXT = (
    T(
        named(
            Shooter("s"),
            "'s best day against the field: ",
            Signed("best", 0),
            " on ",
            FullDate("day"),
            ".",
        ),
        you=named(
            "Your best day against the field: ", Signed("best", 0), " on ", FullDate("day"), "."
        ),
    ),
)
_BEST_DAY_HOW = (
    T(
        named(
            "The best round minus the middle score of everyone who shot that Sunday; the "
            "biggest gap on record."
        ),
        you=named(
            "Your best round minus the middle score of everyone who shot that Sunday; "
            "your biggest gap on record."
        ),
    ),
)

register(
    Kind(
        id="pf.best-day-vs-field",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=1,
        anchored=False,
        guard={"min_gap": BEST_DAY_MIN, "fallback_gap": BEST_DAY_FALLBACK},
        params=frozenset({"s", "best", "day", "latest"}),
        templates={"": _BEST_DAY_TEXT, "fallback": _BEST_DAY_TEXT},
        how={"": _BEST_DAY_HOW},
        labels=(BEST_DAY_LABEL,),
        chart=_best_day_chart,
        proof=(cell("best"),),
        evaluate=_best_day,
    )
)
