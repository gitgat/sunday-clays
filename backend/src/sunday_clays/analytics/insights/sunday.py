"""Sunday-subject kinds (spec §2.2.5): the day's stories, told once per held Sunday."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    Day,
    InsightFrames,
    Sunday,
    anchor_days,
    mean,
    split_by_rain,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
    Int,
    MonthYear,
    NameList,
    Pct,
    Shooter,
    SundayDate,
    T,
    Word,
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
)
from sunday_clays.explorer.spec import Agg, Dim, Metric

SPOTLIGHT_MIN = 7.0  # targets over the shooter's usual for a day like this
SPOTLIGHT_PRIOR = 20  # earlier rounds needed before the usual means much
SPOTLIGHT_NAMES = 3


def spotlight_days(fr: InsightFrames, scope: Scope) -> dict[date, list[Day]]:
    """Per anchor Sunday: the shooter-days over their usual by >= 7, biggest first (<= 3)."""
    by_day: dict[date, list[Day]] = {}
    for i, days in anchor_days(fr, scope):
        d = days[i]
        if (
            d.residual is not None
            and d.residual >= SPOTLIGHT_MIN
            and d.prior_rounds >= SPOTLIGHT_PRIOR
        ):
            by_day.setdefault(d.date, []).append(d)
    for day, found in by_day.items():
        by_day[day] = sorted(
            found, key=lambda d: (-(d.residual or 0.0), fr.names.get(d.shooter_id, ""))
        )[:SPOTLIGHT_NAMES]
    return by_day


def _spotlight(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for _day, top in sorted(spotlight_days(fr, scope).items()):
        best = top[0]
        residual = best.residual or 0.0
        yield Fact(
            subject_id=best.date.isoformat(),
            anchor_date=best.date,
            variant="one" if len(top) == 1 else "many",
            pages=frozenset({P.SUNDAY, P.HOME}),
            params={
                "day": best.date,
                "s": best.shooter_id,
                "score": best.score,
                "over": round(residual),
                "names": [d.shooter_id for d in top],
            },
            strength=residual / SPOTLIGHT_MIN,
            named_shooter_ids=tuple(d.shooter_id for d in top),
        )


SPOTLIGHT_LABEL = T(named("Vs usual for a day like this, ", SundayDate("day")))


def _spotlight_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    return charts.explorer(
        charts.spec(
            Metric.RESIDUAL,
            Agg.MAX,
            Dim.SHOOTER,
            window=Window(day, day),
            best=True,
            sort="value_desc",
        ),
        label=SPOTLIGHT_LABEL,
        hl=Highlight(shooter_ids=p_ids(fact.params, "names")),
        ref=0,
    )


register(
    Kind(
        id="ev.spotlight",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        guard={"min_over": SPOTLIGHT_MIN, "min_prior_rounds": SPOTLIGHT_PRIOR},
        params=frozenset({"day", "s", "score", "over", "names"}),
        templates={
            "one": (
                T(
                    named(
                        "Biggest day of the Sunday: ",
                        Shooter("s"),
                        " shot ",
                        Int("score"),
                        ", ",
                        Int("over"),
                        " more than their usual for a day like this.",
                    )
                ),
            ),
            "many": (
                T(
                    named("Well above their usual for a day like this: ", NameList("names"), "."),
                    named(
                        "Top of the list: ",
                        Shooter("s"),
                        " shot ",
                        Int("score"),
                        ", ",
                        Int("over"),
                        " more than their usual.",
                    ),
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Usual for a day like this = the score the skill model predicted for "
                        "that shooter on that Sunday, before the round."
                    )
                ),
                T(
                    named(
                        "Named: 7 or more targets over their usual, with 20 or more earlier rounds."
                    )
                ),
                T(named("Up to three names, biggest gap first. All round types count.")),
            )
        },
        labels=(SPOTLIGHT_LABEL,),
        chart=_spotlight_chart,
        proof=(
            cell("over", key="s"),
            na("score", "the score itself is in the Sunday's results; the chart shows the gap"),
        ),
        evaluate=_spotlight,
    )
)


# --- ev.rain-day (mixed: a field line plus positive names) ---------------------------------------

RAIN_BETTER = (4, 8, 2.0)  # prior wet Sundays, prior dry Sundays, wet-minus-dry gap
RAIN_STEADY = (6, 12, 0.75)  # the same, with |gap| at most this
PLAYED_SAME = 1.0  # |difficulty| under 1 target: "about the same as a typical Sunday"
CROWD_SAME = 2.0  # within 2 of the dry-Sunday average turnout: "about as many"
RAIN_NAMES = 3
PLAYED = {
    "same": "The field shot about the same as on a typical Sunday",
    "tough": "Scores ran tougher than a typical Sunday",
    "easy": "Scores ran easier than a typical Sunday",
}
CROWD = {
    "same": "about as many shooters turned out as on a dry Sunday",
    "fewer": "fewer shooters turned out than on a dry Sunday",
    "more": "more shooters turned out than on a dry Sunday",
}


def _lead(played: str, crowd: str) -> str:
    """The opening line; a comparison with no data behind it (no difficulty, no earlier dry
    Sunday) is dropped rather than guessed."""
    p, c = PLAYED.get(played), CROWD.get(crowd)
    if p and c:
        return f"Rain Sunday. {p}, and {c}"
    if p or c:
        return f"Rain Sunday. {p or (c or '').capitalize()}"
    return "Rain Sunday"


LEADS = tuple((f"{p}/{c}", _lead(p, c)) for p in (*PLAYED, "unknown") for c in (*CROWD, "unknown"))


def _turnout(sunday: Sunday) -> float:
    return float(sunday.head_count if sunday.head_count is not None else sunday.n)


def _rain_day(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sunday in fr.sundays:
        if sunday.date not in scope.sundays or sunday.precip_band != "wet":
            continue
        dry_before = [_turnout(s) for s in fr.sundays[: sunday.i] if s.precip_band == "dry"]
        crowd = "unknown"
        if dry_before:
            crowd_gap = _turnout(sunday) - mean(dry_before)
            crowd = (
                "same" if abs(crowd_gap) < CROWD_SAME else ("fewer" if crowd_gap < 0 else "more")
            )
        played = "unknown"
        if (d := sunday.difficulty) is not None:
            played = "same" if abs(d) < PLAYED_SAME else ("tough" if d > 0 else "easy")
        better: list[tuple[float, int]] = []
        steady: list[int] = []
        for r in sunday.results:
            if fr.profiles[r.shooter_id].deceased:
                continue
            wet, dry = split_by_rain(fr.histories[r.shooter_id], sunday.date)
            if len(wet) >= RAIN_BETTER[0] and len(dry) >= RAIN_BETTER[1]:
                gap = mean(wet) - mean(dry)
                if gap >= RAIN_BETTER[2]:
                    better.append((gap, r.shooter_id))
                    continue
            enough = len(wet) >= RAIN_STEADY[0] and len(dry) >= RAIN_STEADY[1]
            if enough and abs(mean(wet) - mean(dry)) <= RAIN_STEADY[2]:
                steady.append(r.shooter_id)
        better_ids = [sid for _gap, sid in sorted(better, key=lambda g: (-g[0], g[1]))][:RAIN_NAMES]
        steady_ids = sorted(steady)[:RAIN_NAMES]
        variant = {
            (True, True): "both",
            (True, False): "better",
            (False, True): "steady",
        }.get((bool(better_ids), bool(steady_ids)), "field")
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant=variant,
            pages=frozenset({P.SUNDAY, P.HOME}),
            params={
                "day": sunday.date,
                "first": fr.sundays[0].date,
                "played": played,
                "crowd": crowd,
                "lead": f"{played}/{crowd}",
                "heads": round(_turnout(sunday)),
                "better": better_ids,
                "steady": steady_ids,
                "wet_key": "wet",
            },
            strength=1 + (len(better_ids) + len(steady_ids)) / 3,
            named_shooter_ids=tuple(better_ids + steady_ids),
        )


RAIN_TURNOUT_LABEL = T(named("Turnout on wet and dry Sundays"))
RAIN_NAME_LABEL = T(named("Their Sundays vs the field's middle score, wet and dry"))


def _rain_day_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    window = Window(p_date(fact.params, "first"), day)
    names = [*p_ids(fact.params, "better"), *p_ids(fact.params, "steady")]
    also = tuple(
        charts.explorer(
            charts.spec(
                Metric.ADJUSTED,
                Agg.AVG,
                Dim.PRECIP_BAND,
                window=Window(window.start, day - timedelta(days=1)),
                shooters=(sid,),
                best=True,
            ),
            label=RAIN_NAME_LABEL,
            hl=Highlight(keys=("wet",)),
            ref=0,
        )
        for sid in names
    )
    return charts.explorer(
        charts.spec(Metric.ATTENDANCE, Agg.AVG, Dim.PRECIP_BAND, window=window),
        label=RAIN_TURNOUT_LABEL,
        hl=Highlight(keys=("wet",)),
        also=also,
    )


_RAIN_FIELD = field_(
    Word("lead", LEADS),
    " (",
    Count("heads", "shooter"),
    ").",
)
_RAIN_BETTER = named("Better in the rain: ", NameList("better"), ".")
_RAIN_STEADY = named("Rain doesn't slow down: ", NameList("steady"), ".")

register(
    Kind(
        id="ev.rain-day",
        family=Family.WEATHER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY, P.HOME}),
        polarity=Polarity.MIXED,
        care=4,
        anchored=True,
        guard={"better_gap": RAIN_BETTER[2], "steady_gap": RAIN_STEADY[2]},
        params=frozenset(
            {"day", "first", "played", "crowd", "lead", "heads", "better", "steady", "wet_key"}
        ),
        templates={
            "field": (T(_RAIN_FIELD),),
            "better": (T(_RAIN_FIELD, _RAIN_BETTER),),
            "steady": (T(_RAIN_FIELD, _RAIN_STEADY),),
            "both": (T(_RAIN_FIELD, _RAIN_BETTER, _RAIN_STEADY),),
        },
        how={
            "": (
                T(
                    named(
                        "Wet = 0.02 in of rain or more between 10:00 and 12:00. How it played "
                        "comes from the skill model's day adjustment; turnout is compared with "
                        "the average of earlier dry Sundays."
                    )
                ),
                T(
                    named(
                        "Better in the rain: 4 wet and 8 dry earlier Sundays, and 2 or more "
                        "better against the field's middle score when wet."
                    )
                ),
                T(
                    named(
                        "Rain doesn't slow down: 6 wet and 12 dry earlier Sundays, within 0.75 "
                        "of each other."
                    )
                ),
            )
        },
        labels=(RAIN_TURNOUT_LABEL, RAIN_NAME_LABEL),
        chart=_rain_day_chart,
        proof=(na("heads", "the Sunday's own head count is on the Sunday page"),),
        evaluate=_rain_day,
    )
)


# --- ev.how-it-played (field only) ---------------------------------------------------------------

PLAYED_MIN = 2.5


def _how_it_played(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sunday in fr.sundays:
        d = sunday.difficulty
        if (
            sunday.date not in scope.sundays
            or d is None
            or abs(d) < PLAYED_MIN
            or sunday.median is None
        ):
            continue
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant="tough" if d > 0 else "easy",
            pages=frozenset({P.SUNDAY}),
            params={"day": sunday.date, "by": round(abs(d)), "median": sunday.median},
            strength=abs(d) / PLAYED_MIN,
        )


PLAYED_LABEL = T(named("How each Sunday played, last 3 months"))


def _how_it_played_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    query = charts.spec(Metric.DIFFICULTY, Agg.AVG, Dim.EVENT, window=charts.recent(day))
    return charts.explorer(
        query, label=PLAYED_LABEL, chart_type="line", hl=Highlight(dates=(day,)), ref=0
    )


register(
    Kind(
        id="ev.how-it-played",
        family=Family.WEATHER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY}),
        polarity=Polarity.FIELD_NEGATIVE,
        care=3,
        anchored=True,
        guard={"min_targets": PLAYED_MIN},
        params=frozenset({"day", "by", "median"}),
        templates={
            "tough": (
                T(
                    field_(
                        "A tough Sunday: scores ran about ",
                        Int("by"),
                        " targets under a typical Sunday for this crowd. The middle score was ",
                        Int("median"),
                        ".",
                    )
                ),
            ),
            "easy": (
                T(
                    field_(
                        "A friendly Sunday: scores ran about ",
                        Int("by"),
                        " targets over a typical Sunday for this crowd. The middle score was ",
                        Int("median"),
                        ".",
                    )
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "The skill model compares each shooter's round with what they usually "
                        "shoot; the shared part of the gap is how the day played."
                    )
                ),
                T(
                    named(
                        "Shown when the day played 2.5 targets or more away from a typical "
                        "recent Sunday."
                    )
                ),
            )
        },
        labels=(PLAYED_LABEL,),
        chart=_how_it_played_chart,
        proof=(
            cell("by", absolute=True),
            na("median", "the middle score is on the Sunday's results card"),
        ),
        evaluate=_how_it_played,
    )
)


# --- ev.toughest-since (field only) --------------------------------------------------------------

SINCE_MIN = 2.0
SINCE_WEEKS = 26


def _toughest_since(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sunday in fr.sundays:
        d = sunday.difficulty
        if sunday.date not in scope.sundays or d is None or abs(d) < SINCE_MIN:
            continue
        sign = 1.0 if d > 0 else -1.0
        prev = next(
            (
                s
                for s in reversed(fr.sundays[: sunday.i])
                if s.difficulty is not None and sign * s.difficulty >= sign * d
            ),
            None,
        )
        if prev is None:
            continue
        weeks = (sunday.date - prev.date).days // 7
        if weeks < SINCE_WEEKS:
            continue
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant="tough" if d > 0 else "easy",
            pages=frozenset({P.SUNDAY}),
            params={"day": sunday.date, "prev": prev.date},
            strength=weeks / SINCE_WEEKS,
        )


TOUGH_SINCE_LABEL = T(named("How each Sunday played"))


def _toughest_since_chart(fact: Fact) -> ChartLink:
    prev, day = p_date(fact.params, "prev"), p_date(fact.params, "day")
    query = charts.spec(
        Metric.DIFFICULTY, Agg.AVG, Dim.EVENT, window=Window(prev - timedelta(weeks=2), day)
    )
    return charts.explorer(
        query, label=TOUGH_SINCE_LABEL, chart_type="line", hl=Highlight(dates=(prev, day)), ref=0
    )


register(
    Kind(
        id="ev.toughest-since",
        family=Family.WEATHER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY}),
        polarity=Polarity.FIELD_NEGATIVE,
        care=3,
        anchored=True,
        guard={"min_targets": SINCE_MIN, "weeks": SINCE_WEEKS},
        params=frozenset({"day", "prev"}),
        templates={
            "tough": (T(field_("Toughest Sunday since ", MonthYear("prev"), ".")),),
            "easy": (T(field_("Friendliest Sunday since ", MonthYear("prev"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "How a Sunday played comes from the skill model: the shared part of "
                        "everyone's gap from what they usually shoot."
                    )
                ),
                T(
                    named(
                        "Shown when the day played 2 or more targets from typical and no Sunday "
                        "in the 26 weeks before went further."
                    )
                ),
            )
        },
        labels=(TOUGH_SINCE_LABEL,),
        chart=_toughest_since_chart,
        proof=(),
        evaluate=_toughest_since,
    )
)


# --- ev.week-jump --------------------------------------------------------------------------------

JUMP_MIN = 10
JUMP_WEEKS = 6
JUMP_PRIOR = 12
JUMP_NAMES = 2


def _week_jump(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    spotlit = {day: {d.shooter_id for d in top} for day, top in spotlight_days(fr, scope).items()}
    found: dict[date, list[tuple[int, Day, Day]]] = {}
    for i, days in anchor_days(fr, scope):
        d = days[i]
        prev = days[i - 1] if i else None
        sunday = fr.sunday(d.date)
        if prev is None or sunday is None or sunday.median is None:
            continue
        if d.date - prev.date > timedelta(weeks=JUMP_WEEKS) or d.prior_rounds < JUMP_PRIOR:
            continue
        jump = d.score - prev.score
        if jump < JUMP_MIN or d.expected is None or d.score < d.expected:
            continue
        if d.score < sunday.median or d.shooter_id in spotlit.get(d.date, set()):
            continue
        found.setdefault(d.date, []).append((jump, prev, d))
    for day, jumps in sorted(found.items()):
        top = sorted(jumps, key=lambda j: (-j[0], fr.names.get(j[2].shooter_id, "")))[:JUMP_NAMES]
        jump, prev, d = top[0]
        yield Fact(
            subject_id=day.isoformat(),
            anchor_date=day,
            variant="one" if len(top) == 1 else "two",
            pages=frozenset({P.SUNDAY, P.HOME}),
            params={
                "day": day,
                "s": d.shooter_id,
                "score": d.score,
                "prev": prev.date,
                "names": [x[2].shooter_id for x in top],
            },
            strength=jump / JUMP_MIN,
            named_shooter_ids=tuple(x[2].shooter_id for x in top),
        )


JUMP_LABEL = T(named(Shooter("s"), "'s best round each Sunday"))


def _week_jump_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    query = charts.spec(
        Metric.SCORE,
        Agg.MAX,
        Dim.EVENT,
        window=Window(day - timedelta(weeks=JUMP_WEEKS), day),
        shooters=(p_int(fact.params, "s"),),
    )
    hl = Highlight(dates=(p_date(fact.params, "prev"), day))
    return charts.explorer(query, label=JUMP_LABEL, chart_type="line", hl=hl)


register(
    Kind(
        id="ev.week-jump",
        family=Family.FORM,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        guard={"jump": JUMP_MIN, "weeks": JUMP_WEEKS, "min_prior_rounds": JUMP_PRIOR},
        params=frozenset({"day", "s", "score", "prev", "names"}),
        templates={
            "one": (
                T(
                    named(
                        "Biggest jump from the Sunday before: ",
                        Shooter("s"),
                        ", with a ",
                        Int("score"),
                        ".",
                    )
                ),
            ),
            "two": (T(named("Big jumps from the Sunday before: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "The best round compared with the same shooter's previous Sunday, "
                        "within 6 weeks: up 10 or more."
                    )
                ),
                T(
                    named(
                        "The new round must be at or over their usual for a day like this and "
                        "the field's middle score; needs 12 earlier rounds."
                    )
                ),
                T(named("Up to two names; anyone already in the Sunday's spotlight is left out.")),
            )
        },
        labels=(JUMP_LABEL,),
        chart=_week_jump_chart,
        proof=(cell("score", key="day"),),
        evaluate=_week_jump,
    )
)


# --- ev.record-watch and ev.top-score ------------------------------------------------------------

WATCH_MIN = 48
TOP_YEARS = 3
TOP_SHARE = 0.10
TOP_MIN_SUNDAYS = 20


def _record_watch(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    record: int | None = None
    for sunday in fr.sundays:
        if not sunday.results:
            continue
        top = sunday.results[0]
        before, record = record, top.score if record is None else max(record, top.score)
        if before is None or sunday.date not in scope.sundays or top.score < WATCH_MIN:
            continue
        variant = "new" if top.score > before else "tie" if top.score == before else "near"
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant=variant,
            pages=frozenset({P.SUNDAY, P.HOME}),
            params={
                "day": sunday.date,
                "first": fr.sundays[0].date,
                "s": top.shooter_id,
                "score": top.score,
                "record": before,
                "gap": max(0, before - top.score),
            },
            strength=1 + (top.score - WATCH_MIN) / 2,
            named_shooter_ids=(top.shooter_id,),
        )


HIGHEST_LABEL = T(named("The club's highest rounds"))


def _record_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    return charts.page(
        "/records",
        "rec-highest",
        label=HIGHEST_LABEL,
        window=Window(p_date(fact.params, "first"), day),
        hl=Highlight(dates=(day,), shooter_ids=(p_int(fact.params, "s"),)),
    )


register(
    Kind(
        id="ev.record-watch",
        family=Family.RECORD,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        guard={"min_score": WATCH_MIN},
        params=frozenset({"day", "first", "s", "score", "record", "gap"}),
        templates={
            "new": (
                T(
                    named(
                        Shooter("s"),
                        " set a new club record: ",
                        Int("score"),
                        ", past the ",
                        Int("record"),
                        " that stood before.",
                    )
                ),
            ),
            "tie": (
                T(named(Shooter("s"), " shot ", Int("score"), ", level with the club record.")),
            ),
            "near": (
                T(
                    named(
                        Shooter("s"),
                        " shot ",
                        Int("score"),
                        ", ",
                        Count("gap", "target"),
                        " off the club record of ",
                        Int("record"),
                        ".",
                    )
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "The Sunday's top round, when it is 48 or more, against the highest "
                        "round on any earlier Sunday. All round types count."
                    )
                ),
            )
        },
        labels=(HIGHEST_LABEL,),
        chart=_record_chart,
        proof=(
            cell("score"),
            na("record", "the top of the highest-rounds board before this Sunday"),
            na("gap", "the record minus the highlighted round"),
        ),
        evaluate=_record_watch,
        supersedes=frozenset({"ev.top-score"}),
    )
)


def _top_score(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sunday in fr.sundays:
        if sunday.date not in scope.sundays or sunday.top is None:
            continue
        month_day = (sunday.date.month, sunday.date.day)
        start = (
            date(sunday.date.year - TOP_YEARS, 2, 28)
            if month_day == (2, 29)
            else (sunday.date.replace(year=sunday.date.year - TOP_YEARS))
        )
        earlier = [s.top for s in fr.sundays[: sunday.i] if s.top is not None and s.date >= start]
        if len(earlier) < TOP_MIN_SUNDAYS:
            continue
        higher = sum(t > sunday.top for t in earlier)
        if higher > TOP_SHARE * len(earlier):
            continue
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant="",
            pages=frozenset({P.SUNDAY, P.HOME}),
            params={"day": sunday.date, "top": sunday.top, "start": start},
            strength=1.0,
        )


TOP_LABEL = T(named("Top score each Sunday, last 3 years"))


def _top_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    query = charts.spec(
        Metric.SCORE, Agg.MAX, Dim.EVENT, window=Window(p_date(fact.params, "start"), day)
    )
    return charts.explorer(query, label=TOP_LABEL, chart_type="line", hl=Highlight(dates=(day,)))


register(
    Kind(
        id="ev.top-score",
        family=Family.RECORD,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY, P.HOME}),
        polarity=Polarity.NEUTRAL,
        care=3,
        anchored=True,
        guard={"years": TOP_YEARS, "top_share": TOP_SHARE, "min_sundays": TOP_MIN_SUNDAYS},
        params=frozenset({"day", "top", "start"}),
        templates={
            "": (
                T(
                    field_(
                        "Top score ",
                        Int("top"),
                        ": one of the best top scores of the last 3 years.",
                    )
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "The Sunday's top round is in the highest 10% of Sunday top scores over "
                        "the 3 years before. Needs 20 earlier Sundays in that time."
                    )
                ),
            )
        },
        labels=(TOP_LABEL,),
        chart=_top_chart,
        proof=(cell("top"),),
        evaluate=_top_score,
    )
)


# --- ev.new-faces --------------------------------------------------------------------------------

STRONG_SHARE = 70  # percent of earlier first rounds beaten
STRONG_MIN_FIRSTS = 20
NEW_AFTER = timedelta(weeks=8)  # before this, the club's records cannot say who is new


def new_cutoff(fr: InsightFrames) -> date | None:
    """The first date a first Sunday can be trusted as one; None with no Sundays."""
    return fr.sundays[0].date + NEW_AFTER if fr.sundays else None


def first_rounds_before(fr: InsightFrames, day: date) -> list[int]:
    """Every shooter's first-Sunday best round, for first Sundays strictly before `day`."""
    cutoff = new_cutoff(fr)
    return [
        days[0].score
        for days in fr.histories.values()
        if days and days[0].date < day and cutoff is not None and days[0].date >= cutoff
    ]


def _new_faces(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    cutoff = new_cutoff(fr)
    for sunday in fr.sundays:
        if sunday.date not in scope.sundays or cutoff is None or sunday.date < cutoff:
            continue
        firsts = [
            fr.histories[r.shooter_id][0]
            for r in sunday.results
            if fr.appearance_dates[r.shooter_id][0] == sunday.date  # a special debut is a first
            and not fr.profiles[r.shooter_id].deceased
        ]
        if not firsts:
            continue
        earlier = first_rounds_before(fr, sunday.date)
        strong: tuple[int, Day] | None = None
        if len(earlier) >= STRONG_MIN_FIRSTS and sunday.median is not None:
            for d in sorted(firsts, key=lambda x: (-x.score, fr.names.get(x.shooter_id, ""))):
                share = 100 * sum(e < d.score for e in earlier) // len(earlier)
                if share >= STRONG_SHARE and d.score >= sunday.median:
                    strong = (share, d)
                    break
        params: dict[str, object] = {"day": sunday.date, "n": len(firsts)}
        if strong is not None:
            params |= {"s": strong[1].shooter_id, "score": strong[1].score, "pct": strong[0]}
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant="strong" if strong else "welcome",
            pages=frozenset({P.SUNDAY, P.HOME}),
            params=params,
            strength=1.5 if strong else 1.0,
            named_shooter_ids=(strong[1].shooter_id,) if strong else (),
        )


FIRST_ROUNDS_LABEL = T(named("First rounds at the club"))


def _new_faces_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    keys = (str(p_int(fact.params, "score")),) if fact.variant == "strong" else ()
    return charts.page(
        "/club",
        "first-rounds",
        label=FIRST_ROUNDS_LABEL,
        window=Window(date(day.year - 10, 1, 1), day),
        hl=Highlight(keys=keys),
    )


_WELCOME = field_("Welcome to ", Count("n", "first-timer"), ".")

register(
    Kind(
        id="ev.new-faces",
        family=Family.NEWCOMER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        guard={
            "strong_share": STRONG_SHARE,
            "min_first_rounds": STRONG_MIN_FIRSTS,
            "new_after_weeks": NEW_AFTER.days // 7,
        },
        params=frozenset({"day", "n", "s", "score", "pct"}),
        templates={
            "welcome": (T(_WELCOME),),
            "strong": (
                T(
                    _WELCOME,
                    named(
                        Shooter("s"),
                        " opened with a ",
                        Int("score"),
                        ", better than ",
                        Pct("pct"),
                        " of first rounds here.",
                    ),
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "First-timer = a shooter whose first Sunday on record is this one. "
                        "Not shown for the club's first 8 weeks of records, when we cannot "
                        "yet tell who is new."
                    )
                ),
                T(
                    named(
                        "Strong start: a first round better than 70% of every earlier first "
                        "round at the club and at or over the field's middle score."
                    )
                ),
            )
        },
        labels=(FIRST_ROUNDS_LABEL,),
        chart=_new_faces_chart,
        proof=(
            na("n", "the first-timers are marked on the Sunday's results"),
            na("score", "the highlighted bar of the first-round histogram"),
            na("pct", "the share of the histogram left of the highlighted bar"),
        ),
        evaluate=_new_faces,
    )
)


# --- ev.second-visit -----------------------------------------------------------------------------

SECOND_WEEKS = 10
SECOND_NAMES = 5


def _second_visit(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    found: dict[date, list[int]] = {}
    cutoff = new_cutoff(fr)
    for i, days in anchor_days(fr, scope):
        d = days[i]
        if fr.appearances_through(d.shooter_id, d.date) != 2:  # the real second Sunday
            continue
        first = fr.appearance_dates[d.shooter_id][0]
        if cutoff is None or first < cutoff:
            continue
        if d.date - first <= timedelta(weeks=SECOND_WEEKS):
            found.setdefault(d.date, []).append(d.shooter_id)
    for day, ids in sorted(found.items()):
        ids = sorted(ids, key=lambda sid: fr.names.get(sid, ""))
        many = len(ids) > SECOND_NAMES
        yield Fact(
            subject_id=day.isoformat(),
            anchor_date=day,
            variant="many" if many else "",
            pages=frozenset({P.SUNDAY, P.HOME}),
            params={"day": day, "names": ids, "n": len(ids)},
            strength=1.0,
            named_shooter_ids=() if many else tuple(ids),
        )


SECOND_LABEL = T(named("Results for the Sunday"))

register(
    Kind(
        id="ev.second-visit",
        family=Family.NEWCOMER,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY, P.HOME}),
        polarity=Polarity.NEUTRAL,
        care=2,
        anchored=True,
        guard={"weeks": SECOND_WEEKS, "new_after_weeks": NEW_AFTER.days // 7},
        params=frozenset({"day", "names", "n"}),
        templates={
            "": (T(named("Second visit for ", NameList("names"), ". Welcome back.")),),
            "many": (
                T(field_(Count("n", "shooter"), " came back for a second visit. Welcome back.")),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Shooters on their second Sunday, within 10 weeks of their first. "
                        "Scores are not shown. Not shown for the club's first 8 weeks of "
                        "records, when we cannot yet tell who is new."
                    )
                ),
            )
        },
        labels=(SECOND_LABEL,),
        chart=lambda fact: charts.results_chart(
            p_date(fact.params, "day"), p_ids(fact.params, "names"), label=SECOND_LABEL
        ),
        proof=(na("n", "the highlighted rows of the Sunday's results"),),
        evaluate=_second_visit,
    )
)
