"""Chart-link constructors every kind uses (spec §3.6).

Every link carries an explicit window (never "no from/to", which the time-window work reads as
"last 3 months") and no round-type filter: insights are computed over all round types.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Literal

from sunday_clays.analytics.insights.context import add_months
from sunday_clays.analytics.insights.templates import Shooter, T, Template, named
from sunday_clays.analytics.insights.types import (
    NO_HIGHLIGHT,
    ChartLink,
    Fact,
    Highlight,
    Window,
    p_date,
    p_ids,
)
from sunday_clays.explorer.spec import Agg, Dim, Filters, Metric, QuerySpec

BEST_EACH_LABEL = T(
    named(Shooter("s"), "'s best round each Sunday"),
    you=named("Your best round each Sunday"),
)
FINISH_LABEL = T(named(Shooter("s"), "'s finishes"), you=named("Your finishes"))
CAL_LABEL = T(named(Shooter("s"), "'s Sundays"), you=named("Your Sundays"))
RESULTS_LABEL = T(named("Results for the Sunday"))

SortOrder = Literal["value_desc", "value_asc", "key_asc", "key_desc"]


def recent(anchor: date, months: int = 3) -> Window:
    """The default evidence window [anchor - months, anchor] (D8)."""
    return Window(add_months(anchor, -months), anchor)


def since(start: date, anchor: date, *, months_before: int = 0) -> Window:
    return Window(add_months(start, -months_before), anchor)


def spec(
    metric: Metric,
    agg: Agg,
    *group_by: Dim,
    window: Window,
    shooters: tuple[int, ...] = (),
    best: bool = False,
    min_rounds: int = 0,
    sort: SortOrder = "key_asc",
    **extra: object,
) -> QuerySpec:
    """A QuerySpec over `window` with no round-type filter; `extra` adds later Filters fields."""
    filters = Filters.model_validate(
        {
            "date_from": window.start,
            "date_to": window.end,
            "shooter_ids": list(shooters),
            "min_rounds": min_rounds,
            "best_round_only": best,
            **extra,
        }
    )
    return QuerySpec(metric=metric, agg=agg, group_by=list(group_by), filters=filters, sort=sort)


def explorer(
    query: QuerySpec,
    *,
    label: Template,
    chart_type: Literal["bar", "line"] = "bar",
    hl: Highlight = NO_HIGHLIGHT,
    ref: float | None = None,
    compare: QuerySpec | None = None,
    also: tuple[ChartLink, ...] = (),
) -> ChartLink:
    start, end = query.filters.date_from, query.filters.date_to
    if start is None or end is None:
        # A registry bug, never a data problem: kinds build specs with `spec(..., window=)`, and
        # test_chart_proof builds every kind's link on the fx world, so CI fails first (s60 is
        # otherwise raise-free, spec §3.2).
        raise ValueError("an insight's Explorer spec needs an explicit window")
    return ChartLink(
        type="explorer",
        label=label,
        window=Window(start, end),
        highlight=hl,
        spec=query,
        chart_type=chart_type,
        ref=ref,
        compare=compare,
        also=also,
    )


def page(
    route: str,
    anchor: str,
    *,
    label: Template,
    window: Window,
    hl: Highlight = NO_HIGHLIGHT,
    params: Mapping[str, str] | None = None,
    also: tuple[ChartLink, ...] = (),
) -> ChartLink:
    return ChartLink(
        type="page",
        label=label,
        window=window,
        highlight=hl,
        route=route,
        anchor=anchor,
        params=dict(params or {}),
        also=also,
    )


def profile_chart(
    shooter_id: int,
    anchor: str,
    *,
    label: Template,
    window: Window,
    hl: Highlight = NO_HIGHLIGHT,
    params: Mapping[str, str] | None = None,
) -> ChartLink:
    return page(f"/shooters/{shooter_id}", anchor, label=label, window=window, hl=hl, params=params)


def results_chart(day: date, shooter_ids: tuple[int, ...], *, label: Template) -> ChartLink:
    """The Sunday page's Results card with the named rows highlighted."""
    return page(
        f"/events/{day.isoformat()}",
        "results",
        label=label,
        window=Window(day, day),
        hl=Highlight(shooter_ids=shooter_ids),
    )


def rollup_results(fact: Fact) -> ChartLink:
    """The chart of every rollup row: the Sunday's Results card with the named shooters marked."""
    return results_chart(
        p_date(fact.params, "day"), p_ids(fact.params, "names"), label=RESULTS_LABEL
    )
