"""Record kinds (spec §2.2.6): the wait for a 49, and the Sunday it ends."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import InsightFrames, Sunday
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
    Int,
    NameList,
    Shooter,
    T,
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
    count_rows,
    na,
    p_date,
    p_ids,
)
from sunday_clays.analytics.streaks import streaks
from sunday_clays.explorer.spec import Agg, Dim, Metric

DROUGHT_SCORE = 49
DROUGHT_WAIT = 16  # twice the median wait of 8 held Sundays between 49s
DROUGHT_NAMES = 3


def waits(fr: InsightFrames) -> Iterator[tuple[Sunday, Sunday | None, int]]:
    """(sunday, the last earlier Sunday with a 49+, held Sundays since it) for every Sunday."""
    last: Sunday | None = None
    for sunday in fr.sundays:
        wait = sunday.i - last.i if last is not None else sunday.i + 1
        yield sunday, last, wait
        if sunday.top is not None and sunday.top >= DROUGHT_SCORE:
            last = sunday


DROUGHT_LABEL = T(named("Top score each Sunday"))


def drought_chart(fact: Fact) -> ChartLink:
    last, day = p_date(fact.params, "last"), p_date(fact.params, "day")
    query = charts.spec(
        Metric.SCORE, Agg.MAX, Dim.EVENT, window=Window(last - timedelta(days=31), day)
    )
    return charts.explorer(
        query,
        label=DROUGHT_LABEL,
        chart_type="line",
        hl=Highlight(dates=(last, day)),
        ref=DROUGHT_SCORE,
    )


# --- rec.drought-clock (field only) --------------------------------------------------------------


def _drought_clock(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sunday, last, wait in waits(fr):
        if sunday.date not in scope.sundays or last is None or wait < DROUGHT_WAIT:
            continue
        if sunday.top is not None and sunday.top >= DROUGHT_SCORE:
            continue
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant="",
            pages=frozenset({P.RECORDS, P.SUNDAY, P.HOME}),
            params={"day": sunday.date, "last": last.date, "wait": wait},
            strength=wait / DROUGHT_WAIT,
        )


register(
    Kind(
        id="rec.drought-clock",
        family=Family.RECORD,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.RECORDS, P.SUNDAY, P.HOME}),
        polarity=Polarity.FIELD_NEGATIVE,
        care=3,
        anchored=True,
        guard={"score": DROUGHT_SCORE, "wait": DROUGHT_WAIT},
        params=frozenset({"day", "last", "wait"}),
        templates={
            "": (T(field_(Count("wait", "Sunday"), " since the last round of 49 or better.")),)
        },
        how={
            "": (
                T(
                    named(
                        "Held Sundays since the last round of 49 or better by anyone. Shown "
                        "once the wait reaches 16, twice the usual wait of 8."
                    )
                ),
            )
        },
        labels=(DROUGHT_LABEL,),
        chart=drought_chart,
        proof=(na("wait", "count the Sundays between the two highlighted points"),),
        evaluate=_drought_clock,
    )
)


# --- ev.drought-ended ----------------------------------------------------------------------------


def _drought_ended(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sunday, last, wait in waits(fr):
        if sunday.date not in scope.sundays or last is None or wait < DROUGHT_WAIT:
            continue
        high = [
            r
            for r in sunday.results
            if r.score >= DROUGHT_SCORE and not fr.profiles[r.shooter_id].deceased
        ][:DROUGHT_NAMES]
        if not high:
            continue
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant="one" if len(high) == 1 else "many",
            pages=frozenset({P.SUNDAY, P.HOME, P.RECORDS}),
            params={
                "day": sunday.date,
                "last": last.date,
                "wait": wait,
                "s": high[0].shooter_id,
                "score": high[0].score,
                "names": [r.shooter_id for r in high],
            },
            strength=wait / DROUGHT_WAIT,
            named_shooter_ids=tuple(r.shooter_id for r in high),
        )


register(
    Kind(
        id="ev.drought-ended",
        family=Family.RECORD,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY, P.HOME, P.RECORDS}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        guard={"score": DROUGHT_SCORE, "wait": DROUGHT_WAIT},
        params=frozenset({"day", "last", "wait", "s", "score", "names"}),
        templates={
            "one": (
                T(
                    named(
                        Shooter("s"),
                        "'s ",
                        Int("score"),
                        " ends a ",
                        Int("wait"),
                        "-Sunday wait for a round that high.",
                    )
                ),
            ),
            "many": (
                T(
                    named(
                        NameList("names"),
                        " ended a ",
                        Int("wait"),
                        "-Sunday wait for a round of 49 or better.",
                    )
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "A round of 49 or better after 16 or more held Sundays without one by "
                        "anyone. Up to three names, highest first."
                    )
                ),
            )
        },
        labels=(DROUGHT_LABEL,),
        chart=drought_chart,
        proof=(
            cell("score", key="day"),
            na("wait", "count the Sundays between the two highlighted points"),
        ),
        evaluate=_drought_ended,
        supersedes=frozenset({"rec.drought-clock"}),
    )
)


# --- rec.perfect-rarity --------------------------------------------------------------------------

PERFECT = 50
HIGH = 49
HIGHEST_LABEL = T(named("The club's highest rounds"))


def _perfect_rarity(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    scores = [
        int(s)
        for s, d in zip(fr.rounds["score"], fr.rounds["event_date"], strict=True)
        if d <= scope.as_of
    ]
    perfect = sum(s == PERFECT for s in scores)
    if not perfect:
        return
    yield Fact(
        subject_id="records",
        anchor_date=None,
        variant="",
        pages=frozenset({P.RECORDS, P.HOME}),
        params={
            "day": scope.as_of,
            "first": fr.sundays[0].date,
            "perfect": perfect,
            "rounds": len(scores),
            "high": sum(s >= HIGH for s in scores),
        },
        strength=1.0,
    )


def _highest_chart(fact: Fact) -> ChartLink:
    return charts.page(
        "/records",
        "rec-highest",
        label=HIGHEST_LABEL,
        window=Window(p_date(fact.params, "first"), p_date(fact.params, "day")),
    )


register(
    Kind(
        id="rec.perfect-rarity",
        family=Family.RECORD,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.RECORDS, P.HOME}),
        polarity=Polarity.NEUTRAL,
        care=2,
        anchored=False,
        guard={"perfect": 1},
        params=frozenset({"day", "first", "perfect", "rounds", "high"}),
        templates={
            "": (
                T(
                    field_(
                        Count("perfect", "perfect 50"),
                        " in ",
                        Count("rounds", "round"),
                        "; ",
                        Count("high", "round"),
                        " of 49 or better.",
                    )
                ),
            )
        },
        how={
            "": (T(named("Every round on record, all round types, from the first Sunday to now.")),)
        },
        labels=(HIGHEST_LABEL,),
        chart=_highest_chart,
        proof=(
            count_rows("perfect", "perfect"),
            count_rows("high", "high"),
            na("rounds", "every round on record, the records page summary"),
        ),
        evaluate=_perfect_rarity,
    )
)


# --- rec.streak-chase ----------------------------------------------------------------------------

CHASE_RUN = 15
STREAKS_LABEL = T(named("Longest runs of Sundays in a row"))


def win_streaks(fr: InsightFrames, as_of: date) -> dict[int, tuple[int, int]]:
    """shooter -> (current run of Sundays won, longest ever), over the held Sundays they shot."""
    out: dict[int, tuple[int, int]] = {}
    for sid, days in fr.histories.items():
        run = longest = 0
        for d in days:
            if d.date > as_of or not d.held:
                continue
            run = run + 1 if d.rank == 1 else 0
            longest = max(longest, run)
        out[sid] = (run, longest)
    return out


def _streak_chase(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    table = streaks(fr.appearances, fr.calendar, scope.as_of)  # special Sundays extend runs
    record = int(table["longest_streak"].max()) if len(table) else 0
    running = sorted(
        int(sid)
        for sid, current in zip(table["shooter_id"], table["current_streak"], strict=True)
        if current >= CHASE_RUN and not fr.profiles[int(sid)].deceased
    )
    base = {"day": scope.as_of, "first": fr.sundays[0].date if fr.sundays else scope.as_of}
    if running:
        longest_now = int(table["current_streak"].max())
        yield Fact(
            subject_id="records",
            anchor_date=None,
            variant="attendance",
            pages=frozenset({P.RECORDS, P.HOME}),
            params={**base, "n": len(running), "record": record, "ids": running},
            strength=longest_now / CHASE_RUN,
        )
    wins = win_streaks(fr, scope.as_of)
    win_record = max((longest for _run, longest in wins.values()), default=0)
    chasers = sorted(
        (
            (-run, sid)
            for sid, (run, _longest) in wins.items()
            if run >= 2 and run >= win_record - 1 and not fr.profiles[sid].deceased
        )
    )
    if chasers:
        sid = chasers[0][1]
        yield Fact(
            subject_id="records",
            anchor_date=None,
            variant="wins",
            pages=frozenset({P.RECORDS, P.HOME}),
            params={**base, "s": sid, "run": wins[sid][0], "record": win_record, "ids": [sid]},
            strength=1.5,
            named_shooter_ids=(sid,),
        )


def _chase_chart(fact: Fact) -> ChartLink:
    return charts.page(
        "/records",
        "rec-streaks",
        label=STREAKS_LABEL,
        window=Window(p_date(fact.params, "first"), p_date(fact.params, "day")),
        hl=Highlight(shooter_ids=p_ids(fact.params, "ids")),
    )


register(
    Kind(
        id="rec.streak-chase",
        family=Family.RECORD,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.CLUB,
        pages=frozenset({P.RECORDS, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"run": CHASE_RUN},
        params=frozenset({"day", "first", "n", "record", "ids", "s", "run"}),
        templates={
            "attendance": (
                T(
                    field_(
                        Count("n", "shooter is", "shooters are"),
                        " on runs of 15 or more Sundays in a row; the record is ",
                        Int("record"),
                        ".",
                    )
                ),
            ),
            "wins": (
                T(
                    named(
                        Shooter("s"),
                        " has won ",
                        Count("run", "Sunday"),
                        " in a row; the club record is ",
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
                        "Runs of Sundays with full results in a row, the records page's rule. "
                        "Shown at 15 or more."
                    )
                ),
                T(
                    named(
                        "Wins in a row count the Sundays the shooter shot; shown within 1 of "
                        "the record."
                    )
                ),
            )
        },
        labels=(STREAKS_LABEL,),
        chart=_chase_chart,
        proof=(
            na("n", "the highlighted rows' current runs"),
            na("record", "the top of the longest-run board"),
            na("run", "the win streaks table on the records page"),
        ),
        evaluate=_streak_chase,
    )
)
