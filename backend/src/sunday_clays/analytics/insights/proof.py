"""Chart-proof harness (spec §5): every headline number can be read off the linked chart.

CI only: the recompute step never runs this. For each Fact, the linked chart's rows come from
`run_query` (Explorer links, `round_types=[]`) or the anchor's `source` (page links), and each of
the kind's `ProofCheck`s is applied to the highlighted rows.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date

import pandas as pd

from sunday_clays.analytics.insights.anchors import ANCHORS
from sunday_clays.analytics.insights.context import InsightFrames
from sunday_clays.analytics.insights.registry import Kind
from sunday_clays.analytics.insights.templates import (
    Count,
    Int,
    Ordinal,
    Pct,
    Signed,
    Slot,
    template_slots,
)
from sunday_clays.analytics.insights.types import ChartLink, Fact, Highlight, ProofCheck, ProofHow
from sunday_clays.explorer.engine import ExplorerFrames, run_query

WHOLE = 0.5 + 1e-9  # a whole-number slot matches any chart value that rounds to it
TENTH = 0.05 + 1e-9  # a one-decimal slot


def chart_table(link: ChartLink, fr: InsightFrames, ex: ExplorerFrames) -> pd.DataFrame:
    if link.type == "explorer":
        if link.spec is None:
            raise ValueError("an Explorer link needs a spec")
        result = run_query(ex, link.spec)
        return pd.DataFrame(result.rows, columns=[c.key for c in result.columns])
    anchor = ANCHORS[str(link.anchor)]
    return anchor.source(fr, link)


def _key_column(table: pd.DataFrame) -> str | None:
    for column in (
        "event",
        "shooter_id",
        "year",
        "key",
        "precip_band",
        "temp_band",
        "wind_band",
        "month",
        "station",
        "season",
    ):
        if column in table.columns:
            return column
    return None


def highlighted(table: pd.DataFrame, hl: Highlight) -> pd.Series:
    """Rows the target chart would draw in the accent colour."""
    mask = pd.Series(False, index=table.index)
    if hl.dates and "event" in table.columns:
        mask |= table["event"].isin([d.isoformat() for d in hl.dates])
    if hl.span is not None and "event" in table.columns:
        start, end = hl.span[0].isoformat(), hl.span[1].isoformat()
        mask |= (table["event"] >= start) & (table["event"] <= end)
    if hl.shooter_ids and "shooter_id" in table.columns:
        ids = table["shooter_id"].isin(list(hl.shooter_ids))
        narrowed = (hl.dates or hl.span is not None) and "event" in table.columns
        mask = (mask & ids) if narrowed else (mask | ids)
    if hl.keys:
        column = next(
            (
                c
                for c in (
                    "year",
                    "key",
                    "precip_band",
                    "temp_band",
                    "wind_band",
                    "month",
                    "station",
                )
                if c in table.columns
            ),
            None,
        )
        if column is not None:
            mask |= table[column].astype(str).isin(list(hl.keys))
    return mask


def _tolerance(kind: Kind, param: str) -> float:
    for template in (t for ts in kind.templates.values() for t in ts):
        for slot in template_slots(template):
            if slot.param == param:
                return _slot_tolerance(slot)
    return TENTH


def _slot_tolerance(slot: Slot) -> float:
    if isinstance(slot, Int | Count | Ordinal | Pct):
        return WHOLE
    if isinstance(slot, Signed):
        return WHOLE if slot.digits == 0 else TENTH
    return TENTH


def _key_row(table: pd.DataFrame, params: Mapping[str, object], key: str) -> pd.DataFrame:
    value = params[key]
    if isinstance(value, date):
        return table[table["event"] == value.isoformat()]
    if isinstance(value, int) and "shooter_id" in table.columns:
        return table[table["shooter_id"] == value]
    column = _key_column(table)
    return table if column is None else table[table[column].astype(str) == str(value)]


def read_value(
    check: ProofCheck, table: pd.DataFrame, hl: Highlight, params: Mapping[str, object]
) -> float | None:
    """The number `check` reads off the chart, or None when the chart cannot show it."""
    if check.how is ProofHow.NA:
        return None
    if check.how is ProofHow.ROWS:
        return float(len(table))
    mask = highlighted(table, hl)
    no_highlight = not (hl.dates or hl.shooter_ids or hl.keys or hl.span)
    rows = table if no_highlight else table[mask]
    if check.how is ProofHow.CELL:
        target = _key_row(table, params, check.key) if check.key else rows
        values = pd.to_numeric(target[check.column], errors="coerce").dropna()
        if values.empty:
            return None
        return abs(float(values.max())) if check.absolute else float(values.max())
    if check.how is ProofHow.COUNT:
        return float(int(pd.to_numeric(rows[check.column], errors="coerce").notna().sum()))
    if check.how is ProofHow.RUN:
        run = best = 0
        for flag in mask:
            run = run + 1 if flag else 0
            best = max(best, run)
        return float(best)
    values = pd.to_numeric(rows[check.column], errors="coerce").dropna()
    if check.how is ProofHow.SUM:
        return float(values.sum())
    if check.how is ProofHow.MEAN:
        return None if values.empty else float(values.mean())
    if check.how is ProofHow.MAX_BEFORE:
        first = int(mask.to_numpy().argmax()) if mask.any() else len(table)
        before = pd.to_numeric(table[check.column].iloc[:first], errors="coerce").dropna()
        return None if before.empty else float(before.max())
    if check.how is ProofHow.RANK:
        target = _key_row(table, params, check.key) if check.key else rows
        if target.empty:
            return None
        ordered = pd.to_numeric(table[check.column], errors="coerce")
        value = float(pd.to_numeric(target[check.column], errors="coerce").iloc[0])
        if math.isnan(value):
            return None
        return float(int((ordered > value).sum()) + 1)
    if check.how is ProofHow.DISTINCT:
        return float(rows[check.column].dropna().nunique())
    if check.how is ProofHow.LEAD:
        top = pd.to_numeric(table[check.column], errors="coerce").dropna().nlargest(2)
        return None if len(top) < 2 else float(top.iloc[0]) - float(top.iloc[1])
    if check.how is ProofHow.DIFF:
        if check.key is None or check.other is None:
            return None
        left = pd.to_numeric(_key_row(table, params, check.key)[check.column], errors="coerce")
        right = pd.to_numeric(_key_row(table, params, check.other)[check.column], errors="coerce")
        left, right = left.dropna(), right.dropna()
        if left.empty or right.empty:
            return None
        gap = float(left.max()) - float(right.max())
        return abs(gap) if check.absolute else gap
    if check.how is ProofHow.SHARE:
        all_values = pd.to_numeric(table[check.column], errors="coerce").dropna()
        threshold = check.threshold if check.threshold is not None else 0.0
        return None if all_values.empty else 100.0 * float((all_values >= threshold).mean())
    raise ValueError(f"unknown proof check {check.how}")  # pragma: no cover - exhaustive enum


def proof_problems(kind: Kind, fact: Fact, fr: InsightFrames, ex: ExplorerFrames) -> list[str]:
    """Every headline number the linked chart does not show (empty = proven)."""
    link = kind.chart(fact)
    table = chart_table(link, fr, ex)
    problems: list[str] = []
    for check in kind.proof:
        if check.param not in fact.params or check.how is ProofHow.NA:
            continue
        seen = read_value(check, table, link.highlight, fact.params)
        claimed = fact.params[check.param]
        if not isinstance(claimed, int | float) or isinstance(claimed, bool):
            problems.append(f"{check.param}: not a number ({claimed!r})")
        elif seen is None:
            problems.append(f"{check.param}: the chart has no value for it")
        elif abs(seen - float(claimed)) > _tolerance(kind, check.param):
            problems.append(f"{check.param}: headline {claimed} vs chart {seen:.2f}")
    return problems
