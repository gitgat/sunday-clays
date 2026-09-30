"""Club kinds (spec §2.2.7): weather, turnout and the year's pace, told about everyone at once.

Every kind here is a field kind: no names. Evergreen rows are "as of" the latest held Sunday in
scope; `cl.year-pace` also has anchored home rows on the Sunday it catches or passes last year.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterator, Sequence
from datetime import date

import pandas as pd

from sunday_clays.analytics import frames
from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    InsightFrames,
    Sunday,
    mean,
    stderr_diff,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Dec1,
    Int,
    Pct,
    ShortDate,
    T,
    Word,
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
    diff,
    mean_of,
    na,
    p_date,
    p_int,
    p_str,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric

CLUB = "club"
NOISE_MULTIPLE = 2.0


def held_to(fr: InsightFrames, as_of: date) -> list[Sunday]:
    return [s for s in fr.sundays if s.date <= as_of]


def head_counts(fr: InsightFrames, start: date, end: date) -> list[tuple[date, float]]:
    """(date, head count) of every event in [start, end] with one, oldest first: the Explorer
    `attendance` rows (Plan 11 T2 turnout rule; an event without full results still counts)."""
    return sorted(
        (day, float(heads))
        for day, heads in zip(fr.events["event_date"], fr.events["head_count"], strict=True)
        if start <= day <= end and not pd.isna(heads)
    )


def clear(gap: float, a: Sequence[float], b: Sequence[float]) -> bool:
    """The gap is more than twice its noise (standard error of the difference)."""
    return abs(gap) > NOISE_MULTIPLE * stderr_diff(a, b)


def _club_fact(
    scope: Scope, variant: str, pages: frozenset[P], params: dict[str, object], strength: float
) -> Fact:
    return Fact(
        subject_id=CLUB,
        anchor_date=None,
        variant=variant,
        pages=pages,
        params={"day": scope.as_of, **params},
        strength=strength,
    )


# --- cl.rain-turnout -----------------------------------------------------------------------------

RAIN_TURNOUT_GAP = 3.0
RAIN_TURNOUT_WET = 20
RAIN_TURNOUT_LABEL = T(named("Average turnout, wet and dry Sundays"))


def turnout_by_band(fr: InsightFrames, start: date, end: date) -> dict[str, list[float]]:
    """Head counts by rain band for every event dated in [start, end] with both (the Explorer
    `attendance` rows: an event without full results still has a head count)."""
    out: dict[str, list[float]] = {"wet": [], "dry": []}
    for day, heads, precip in zip(
        fr.events["event_date"], fr.events["head_count"], fr.events["precip_in"], strict=True
    ):
        band = frames.precip_band(precip)
        if start <= day <= end and band is not None and not pd.isna(heads):
            out[band].append(float(heads))
    return out


def _rain_turnout(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    sundays = held_to(fr, scope.as_of)
    if not sundays:
        return
    by_band = turnout_by_band(fr, sundays[0].date, scope.as_of)
    wet, dry = by_band["wet"], by_band["dry"]
    if len(wet) < RAIN_TURNOUT_WET or len(dry) < 2:
        return
    gap = mean(dry) - mean(wet)
    if gap < RAIN_TURNOUT_GAP or not clear(gap, dry, wet):
        return
    yield _club_fact(
        scope,
        "",
        frozenset({P.CLUB, P.HOME}),
        {
            "first": sundays[0].date,
            "gap": round(gap),  # the real gap, whole; wet and dry to a tenth so they can't disagree
            "wet": round(mean(wet), 1),
            "dry": round(mean(dry), 1),
            "wet_key": "wet",
            "dry_key": "dry",
        },
        gap / RAIN_TURNOUT_GAP,
    )


def _rain_turnout_chart(fact: Fact) -> ChartLink:
    window = Window(p_date(fact.params, "first"), p_date(fact.params, "day"))
    query = charts.spec(Metric.ATTENDANCE, Agg.AVG, Dim.PRECIP_BAND, window=window)
    return charts.explorer(query, label=RAIN_TURNOUT_LABEL, hl=Highlight(keys=("wet",)))


register(
    Kind(
        id="cl.rain-turnout",
        family=Family.TURNOUT,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.CLUB, P.HOME}),
        polarity=Polarity.FIELD_NEGATIVE,
        care=4,
        anchored=False,
        guard={"gap": RAIN_TURNOUT_GAP, "wet": RAIN_TURNOUT_WET, "noise": NOISE_MULTIPLE},
        params=frozenset({"day", "first", "gap", "wet", "dry", "wet_key", "dry_key"}),
        templates={
            "": (
                T(
                    field_(
                        "Rain keeps about ",
                        Int("gap"),
                        " shooters home: ",
                        Dec1("wet"),
                        " on wet Sundays vs ",
                        Dec1("dry"),
                        " on dry.",
                    )
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Average head count on every Sunday with weather and a head count. "
                        "Wet = 0.02 in of rain or more between 10:00 and 12:00."
                    )
                ),
                T(
                    named(
                        "Shown when the gap is 3 or more and at least twice its noise, with 20 "
                        "or more wet Sundays."
                    )
                ),
            )
        },
        labels=(RAIN_TURNOUT_LABEL,),
        chart=_rain_turnout_chart,
        proof=(
            cell("wet", key="wet_key"),
            cell("dry", key="dry_key"),
            diff("gap", key="dry_key", other="wet_key"),
        ),
        evaluate=_rain_turnout,
    )
)


# --- cl.rain-scores ------------------------------------------------------------------------------

RAIN_SCORES_GAP = 1.5
RAIN_SCORES_LABEL = T(named("How Sundays played, wet and dry"))


def _difficulty_split(
    sundays: Sequence[Sunday], band_of: str, band: str
) -> tuple[list[float], list[float]]:
    inside: list[float] = []
    outside: list[float] = []
    for s in sundays:
        value = getattr(s, band_of)
        if s.difficulty is None or value is None:
            continue
        (inside if value == band else outside).append(s.difficulty)
    return inside, outside


RAIN_KEYS = {"wet_key": "wet", "dry_key": "dry"}  # the two bars the gap is read between


def _rain_scores(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    sundays = held_to(fr, scope.as_of)
    wet, dry = _difficulty_split(sundays, "precip_band", "wet")
    if len(wet) < RAIN_TURNOUT_WET or len(dry) < 2:
        return
    gap = mean(wet) - mean(dry)
    first = sundays[0].date
    if not clear(gap, wet, dry):
        shown = round(abs(gap), 1)
        params = {"first": first, "gap": shown, "way": "tough", **RAIN_KEYS}
        # "within 0.0 targets" reads badly: a gap that rounds to nothing gets a number-free line
        yield _club_fact(scope, "steady" if shown else "same", frozenset({P.CLUB}), params, 1.0)
    elif abs(gap) >= RAIN_SCORES_GAP:
        way = "tough" if gap > 0 else "easy"
        params = {"first": first, "gap": round(abs(gap), 1), "way": way, **RAIN_KEYS}
        yield _club_fact(scope, "moves", frozenset({P.CLUB}), params, 1.0)


def _rain_scores_chart(fact: Fact) -> ChartLink:
    window = Window(p_date(fact.params, "first"), p_date(fact.params, "day"))
    query = charts.spec(Metric.DIFFICULTY, Agg.AVG, Dim.PRECIP_BAND, window=window)
    return charts.explorer(query, label=RAIN_SCORES_LABEL, hl=Highlight(keys=("wet",)), ref=0)


WAY = (("tough", "tougher"), ("easy", "easier"))

register(
    Kind(
        id="cl.rain-scores",
        family=Family.WEATHER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.CLUB}),
        polarity=Polarity.FIELD_NEGATIVE,
        care=2,
        anchored=False,
        guard={"gap": RAIN_SCORES_GAP, "noise": NOISE_MULTIPLE},
        params=frozenset({"day", "first", "gap", "way", "wet_key", "dry_key"}),
        templates={
            "steady": (
                T(
                    field_(
                        "Rain barely moves our scores: wet and dry Sundays play within ",
                        Dec1("gap"),
                        " targets of each other.",
                    )
                ),
            ),
            "same": (
                T(field_("Rain doesn't move our scores: wet and dry Sundays play the same.")),
            ),
            "moves": (
                T(
                    field_(
                        "Rain changes the day: wet Sundays play about ",
                        Dec1("gap"),
                        " targets ",
                        Word("way", WAY),
                        " than dry ones.",
                    )
                ),
            ),
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
                        "Wet and dry are compared over every Sunday with weather. A gap inside "
                        "twice its noise counts as no change."
                    )
                ),
            )
        },
        labels=(RAIN_SCORES_LABEL,),
        chart=_rain_scores_chart,
        proof=(diff("gap", key="wet_key", other="dry_key", absolute=True),),
        evaluate=_rain_scores,
    )
)


# --- cl.weather-scoreboard -----------------------------------------------------------------------

BAND_MIN_SUNDAYS = 8
BAND_WORDS = (
    ("dry", "dry Sundays"),
    ("wet", "wet Sundays"),
    ("<10", "Sundays with gusts under 10 mph"),
    ("10-20", "Sundays with gusts of 10 to 20 mph"),
    ("20+", "Sundays with gusts of 20 mph or more"),
    ("<40", "Sundays under 40°F"),
    ("40-55", "Sundays from 40 to 55°F"),
    ("55-70", "Sundays from 55 to 70°F"),
    ("70-85", "Sundays from 70 to 85°F"),
)
DIMS = (
    ("precip_band", ("wet",), Dim.PRECIP_BAND),  # wet against dry, told as "wet"
    ("wind_band", frames.WIND_BANDS, Dim.WIND_BAND),
    ("temp_band", tuple(b for b in frames.TEMP_BANDS if b != "85+"), Dim.TEMP_BAND),
)
DIM_BY_BAND = {band: dim for _attr, bands, dim in DIMS for band in bands}
SCOREBOARD_LABEL = T(named("How Sundays played, by weather"))


def _weather_scoreboard(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    sundays = [s for s in held_to(fr, scope.as_of) if s.temp_band != "85+"]
    best: tuple[float, str] | None = None
    judged = False
    for attr, bands, _dim in DIMS:
        for band in bands:
            inside, outside = _difficulty_split(sundays, attr, band)
            if len(inside) < BAND_MIN_SUNDAYS or len(outside) < BAND_MIN_SUNDAYS:
                continue
            judged = True
            gap = mean(inside) - mean(outside)
            moves = abs(gap) >= RAIN_SCORES_GAP and clear(gap, inside, outside)
            if moves and (best is None or abs(gap) > abs(best[0])):
                best = (gap, band)
    if not judged:
        return  # no band had enough Sundays on both sides: nothing to say, neutral or otherwise
    first = sundays[0].date
    if best is None:
        yield _club_fact(scope, "steady", frozenset({P.CLUB}), {"first": first, "band": "wet"}, 1)
        return
    gap, band = best
    params = {
        "first": first,
        "band": band,
        "gap": round(abs(gap), 1),
        "way": "tough" if gap > 0 else "easy",
    }
    yield _club_fact(scope, "moves", frozenset({P.CLUB}), params, 1.0)


def _scoreboard_chart(fact: Fact) -> ChartLink:
    window = Window(p_date(fact.params, "first"), p_date(fact.params, "day"))
    band = p_str(fact.params, "band")
    main_dim = DIM_BY_BAND[band] if fact.variant == "moves" else Dim.WIND_BAND
    hl = Highlight(keys=(band,)) if fact.variant == "moves" else Highlight()
    also = tuple(
        charts.explorer(
            charts.spec(Metric.DIFFICULTY, Agg.AVG, dim, window=window),
            label=SCOREBOARD_LABEL,
            ref=0,
        )
        for _attr, _bands, dim in DIMS
        if dim is not main_dim
    )
    return charts.explorer(
        charts.spec(Metric.DIFFICULTY, Agg.AVG, main_dim, window=window),
        label=SCOREBOARD_LABEL,
        hl=hl,
        ref=0,
        also=also,
    )


register(
    Kind(
        id="cl.weather-scoreboard",
        family=Family.WEATHER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.CLUB}),
        polarity=Polarity.FIELD_NEGATIVE,
        care=2,
        anchored=False,
        guard={"gap": RAIN_SCORES_GAP, "min_sundays": BAND_MIN_SUNDAYS},
        params=frozenset({"day", "first", "band", "gap", "way"}),
        templates={
            "steady": (
                T(
                    field_(
                        "Rain, wind and cold barely move our scores here. Turnout is what changes."
                    )
                ),
            ),
            "moves": (
                T(
                    field_(
                        "Scores run ",
                        Word("way", WAY),
                        " on ",
                        Word("band", BAND_WORDS),
                        ": about ",
                        Dec1("gap"),
                        " targets.",
                    )
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Each rain, gust and temperature band against every other Sunday, by how "
                        "the day played. Sundays of 85°F and up are too few to judge."
                    )
                ),
                T(
                    named(
                        "A band moves scores when the gap is 1.5 or more and at least twice its "
                        "noise, with 8 Sundays on each side."
                    )
                ),
            )
        },
        labels=(SCOREBOARD_LABEL,),
        chart=_scoreboard_chart,
        proof=(na("gap", "the highlighted bar against the other bars"),),
        evaluate=_weather_scoreboard,
    )
)


# --- cl.turnout-trend ----------------------------------------------------------------------------

TREND_YEAR_MIN = 20  # Sundays with a head count for a year to count
TREND_RECENT = 8
TREND_PCT = 15
TURNOUT_YEAR_LABEL = T(named("Average turnout by year"))
TURNOUT_EVENT_LABEL = T(named("Turnout each Sunday"))


def _turnout_trend(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    sundays = held_to(fr, scope.as_of)
    if not sundays:
        return
    counted = head_counts(fr, sundays[0].date, scope.as_of)
    by_year: dict[int, list[float]] = {}
    for day, t in counted:
        by_year.setdefault(day.year, []).append(t)
    years = sorted(y for y, ts in by_year.items() if len(ts) >= TREND_YEAR_MIN)[-3:]
    first = sundays[0].date
    if len(years) == 3 and years[-1] - years[0] == 2:
        a, b, c = (mean(by_year[y]) for y in years)
        if a < b < c:
            params = {"first": first, "a": round(a), "c": round(c), "y1": years[0], "y3": years[2]}
            yield _club_fact(scope, "years", frozenset({P.CLUB, P.HOME}), params, 1.5)
            return
    if len(counted) < 2 * TREND_RECENT:
        return
    recent = [t for _d, t in counted[-TREND_RECENT:]]
    before = [t for _d, t in counted[-2 * TREND_RECENT : -TREND_RECENT]]
    pct = 100 * (mean(recent) - mean(before)) / mean(before)
    if pct < TREND_PCT or not clear(mean(recent) - mean(before), recent, before):
        return
    params = {
        "first": counted[-2 * TREND_RECENT][0],
        "start": counted[-TREND_RECENT][0],
        "recent": round(mean(recent)),
        "before": round(mean(before)),
        "pct": round(pct),
    }
    yield _club_fact(scope, "recent", frozenset({P.CLUB, P.HOME}), params, pct / TREND_PCT)


def _turnout_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    window = Window(p_date(fact.params, "first"), day)
    if fact.variant == "years":
        query = charts.spec(Metric.ATTENDANCE, Agg.AVG, Dim.YEAR, window=window)
        keys = tuple(str(y) for y in range(p_int(fact.params, "y1"), p_int(fact.params, "y3") + 1))
        return charts.explorer(query, label=TURNOUT_YEAR_LABEL, hl=Highlight(keys=keys))
    query = charts.spec(Metric.ATTENDANCE, Agg.AVG, Dim.EVENT, window=window)
    hl = Highlight(span=(p_date(fact.params, "start"), day))
    return charts.explorer(query, label=TURNOUT_EVENT_LABEL, chart_type="line", hl=hl)


register(
    Kind(
        id="cl.turnout-trend",
        family=Family.TURNOUT,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.CLUB, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"year_sundays": TREND_YEAR_MIN, "recent": TREND_RECENT, "pct": TREND_PCT},
        params=frozenset(
            {"day", "first", "a", "c", "y1", "y3", "start", "recent", "before", "pct"}
        ),
        templates={
            "years": (
                T(
                    field_(
                        "Turnout has climbed 3 years running: ",
                        Int("a"),
                        " shooters a Sunday in ",
                        Year("y1"),
                        ", ",
                        Int("c"),
                        " in ",
                        Year("y3"),
                        ".",
                    )
                ),
            ),
            "recent": (
                T(
                    field_(
                        "Turnout is up ",
                        Pct("pct"),
                        " over the last 8 Sundays: ",
                        Int("recent"),
                        " a Sunday vs ",
                        Int("before"),
                        " before.",
                    )
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Turnout = the head count. Years need 20 Sundays with a head count; "
                        "each of the 3 must beat the year before."
                    )
                ),
                T(
                    named(
                        "Or: the last 8 Sundays against the 8 before, up 15% or more and by at "
                        "least twice the noise."
                    )
                ),
            )
        },
        labels=(TURNOUT_YEAR_LABEL, TURNOUT_EVENT_LABEL),
        chart=_turnout_chart,
        proof=(
            cell("a", key="y1"),
            cell("c", key="y3"),
            mean_of("recent"),
            na("before", "the 8 Sundays before the highlighted ones"),
            na("pct", "the highlighted average against the 8 Sundays before"),
        ),
        evaluate=_turnout_trend,
    )
)


# --- cl.year-pace --------------------------------------------------------------------------------

PACE_AHEAD_PCT = 5.0
PACE_LABEL = T(named("Rounds by year, to the same date"))
PACE_TOTAL_LABEL = T(named("Rounds by year"))


def rounds_by(dates: Sequence[date], start: date, end: date) -> int:
    """Round rows (every round, the Explorer `rounds` metric) dated in [start, end]; `dates` is
    every round's date, sorted."""
    return bisect_right(dates, end) - bisect_left(dates, start)


def same_date(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:
        return day.replace(year=year, day=28)


def pace(dates: Sequence[date], day: date) -> tuple[int, int, int]:
    """(this year to `day`, last year to the same date, all of last year)."""
    this = rounds_by(dates, date(day.year, 1, 1), day)
    last_ytd = rounds_by(dates, date(day.year - 1, 1, 1), same_date(day, day.year - 1))
    last_all = rounds_by(dates, date(day.year - 1, 1, 1), date(day.year - 1, 12, 31))
    return this, last_ytd, last_all


def _pace_params(fr: InsightFrames, day: date, this: int, last: int) -> dict[str, object]:
    return {
        "first": fr.sundays[0].date,
        "this": this,
        "last": last,
        "year": day.year,
        "last_year": day.year - 1,
        "pct": round(100 * (this - last) / last) if last else 0,
    }


def _year_pace(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    held = held_to(fr, scope.as_of)
    if not held or held[0].date.year == scope.as_of.year:
        return
    dates = sorted(fr.rounds["event_date"])
    for i, sunday in enumerate(held):
        if sunday.date not in scope.sundays or i == 0 or held[i - 1].date.year != sunday.date.year:
            continue
        this, last_ytd, last_all = pace(dates, sunday.date)
        prev_this, prev_ytd, _ = pace(dates, held[i - 1].date)
        if last_all and prev_this < last_all <= this:
            params = _pace_params(fr, sunday.date, this, last_all)
            variant = "passed"
        elif last_ytd and prev_this <= prev_ytd and this > last_ytd:
            params = _pace_params(fr, sunday.date, this, last_ytd)
            variant = "caught"
        else:
            continue
        yield Fact(
            subject_id=CLUB,
            anchor_date=sunday.date,
            variant=variant,
            pages=frozenset({P.HOME}),
            params={"day": sunday.date, **params},
            strength=1.5,
        )
    this, last_ytd, last_all = pace(dates, scope.as_of)
    if last_all and this >= last_all:
        params = _pace_params(fr, scope.as_of, this, last_all)
        yield _club_fact(scope, "passed", frozenset({P.CLUB}), params, 1.5)
    elif last_ytd and 100 * (this - last_ytd) / last_ytd >= PACE_AHEAD_PCT:
        params = _pace_params(fr, scope.as_of, this, last_ytd)
        pct = 100 * (this - last_ytd) / last_ytd
        yield _club_fact(scope, "ahead", frozenset({P.CLUB}), params, pct / PACE_AHEAD_PCT)


def _pace_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    window = Window(p_date(fact.params, "first"), day)
    hl = Highlight(keys=(str(day.year), str(day.year - 1)))
    if fact.variant == "passed":
        query = charts.spec(Metric.ROUNDS, Agg.COUNT, Dim.YEAR, window=window)
        return charts.explorer(query, label=PACE_TOTAL_LABEL, hl=hl)
    query = charts.spec(
        Metric.ROUNDS, Agg.COUNT, Dim.YEAR, window=window, ytd=day.strftime("%m-%d")
    )
    return charts.explorer(query, label=PACE_LABEL, hl=hl)


register(
    Kind(
        id="cl.year-pace",
        family=Family.TURNOUT,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.CLUB, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=True,
        guard={"ahead_pct": PACE_AHEAD_PCT},
        params=frozenset({"day", "first", "this", "last", "year", "last_year", "pct"}),
        templates={
            "passed": (
                T(
                    field_(
                        Year("year"),
                        " has passed all of ",
                        Year("last_year"),
                        ": ",
                        Int("this"),
                        " rounds by ",
                        ShortDate("day"),
                        ", against ",
                        Int("last"),
                        " in the whole year.",
                    )
                ),
            ),
            "caught": (
                T(
                    field_(
                        Year("year"),
                        " is now ahead of ",
                        Year("last_year"),
                        "'s pace: ",
                        Int("this"),
                        " rounds by ",
                        ShortDate("day"),
                        " vs ",
                        Int("last"),
                        " at this point last year.",
                    )
                ),
            ),
            "ahead": (
                T(
                    field_(
                        Year("year"),
                        " is ",
                        Pct("pct"),
                        " ahead of ",
                        Year("last_year"),
                        " at this point: ",
                        Int("this"),
                        " rounds vs ",
                        Int("last"),
                        ".",
                    )
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Rounds = every round shot, counted from Jan 1 to the same date in each "
                        "year."
                    )
                ),
                T(
                    named(
                        "The club page shows a lead of 5% or more; home shows the Sunday the "
                        "year catches up or passes last year's total."
                    )
                ),
            )
        },
        labels=(PACE_LABEL, PACE_TOTAL_LABEL),
        chart=_pace_chart,
        proof=(
            cell("this", key="year"),
            cell("last", key="last_year"),
            na("pct", "the two highlighted bars"),
        ),
        evaluate=_year_pace,
    )
)
