"""Race kinds about a Sunday's finish (spec §2.2.5). Names share a standing; nobody trails (D9)."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import FINISH_FIELD, InsightFrames, Result
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import Int, NameList, SundayDate, T, named
from sunday_clays.analytics.insights.types import (
    ChartLink,
    Fact,
    Family,
    HomeSlot,
    P,
    Polarity,
    Scope,
    SubjectType,
    cell,
    p_date,
    p_ids,
)

CLOSE_TOP = 45  # "top 3 within one" needs a top score of 45 or more
NAMES = 5


def _close_finish(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sunday in fr.sundays:
        if sunday.date not in scope.sundays or sunday.n < FINISH_FIELD:
            continue
        results = sunday.results  # the whole standings, deceased shooters included (n >= 15)
        top = results[0].score
        winners = [r for r in results if r.rank == 1]
        names: Sequence[Result]
        if len(winners) >= 2:
            variant, names, strength = ("tie2" if len(winners) == 2 else "tien"), winners, 1.5
        elif top >= CLOSE_TOP and results[2].score >= top - 1:
            variant, names, strength = "close", results[:3], 1.0
            if len(results) > 3 and results[3].score == results[2].score:
                continue  # third place is shared beyond three names; "top 3" would be untrue
        else:
            continue
        if len(names) > NAMES or any(fr.profiles[r.shooter_id].deceased for r in names):
            continue  # every named shooter must be shown, and never a shooter who has passed
        ids = [r.shooter_id for r in names[:NAMES]]
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant=variant,
            pages=frozenset({P.SUNDAY, P.HOME}),
            params={"day": sunday.date, "names": ids, "top": top, "n": sunday.n},
            strength=strength,
            named_shooter_ids=tuple(ids),
        )


CLOSE_LABEL = T(named("Results for ", SundayDate("day")))


def _close_chart(fact: Fact) -> ChartLink:
    return charts.results_chart(
        p_date(fact.params, "day"), p_ids(fact.params, "names"), label=CLOSE_LABEL
    )


register(
    Kind(
        id="ev.close-finish",
        family=Family.RACE,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        guard={"min_field": FINISH_FIELD, "min_top": CLOSE_TOP},
        params=frozenset({"day", "names", "top", "n"}),
        templates={
            "tie2": (
                T(named("Tie at the top: ", NameList("names"), " both shot ", Int("top"), ".")),
            ),
            "tien": (
                T(named("Tie at the top: ", NameList("names"), " all shot ", Int("top"), ".")),
            ),
            "close": (
                T(
                    named(
                        "The top 3 finished within one target: ",
                        NameList("names"),
                        ", led by a ",
                        Int("top"),
                        ".",
                    )
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "Finishes use each shooter's best round that Sunday; tied scores share "
                        "a place."
                    )
                ),
                T(
                    named(
                        "Shown when a field of 15 or more ends in a tie at the top, or when the "
                        "top 3 are within one target and the top score is 45 or more."
                    )
                ),
            )
        },
        labels=(CLOSE_LABEL,),
        chart=_close_chart,
        proof=(cell("top", "score"),),
        evaluate=_close_finish,
    )
)
