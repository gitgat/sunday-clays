"""Scoring/competition trophies on the committed fixtures (Plan 10 T3 golden)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl
import pytest
from sqlalchemy import text

WORKBOOK = Path(__file__).parents[2] / "fixtures" / "scores_2026-09-27.xlsx"
# The raw Class cell of a qualifying round, after stripping. The one "29 Gauge" cell reads as
# 28 Gauge (C3 gauge normalization). SxS is an action, not a gauge, and never qualifies.
# Matching is exact after strip() on purpose: a differently cased or spaced cell should fail loudly.
SUB_GAUGE_CELLS = {"Sub-Gauge", "20 Gauge", "28 Gauge", "29 Gauge", ".410"}


def raw_sub_gauge_rows() -> list[tuple[str, str]]:
    """(name_key, class cell) of every qualifying row, read straight from the workbook."""
    book = openpyxl.load_workbook(WORKBOOK, read_only=True)
    try:
        rows = list(book["ALL SCORE DETAIL"].iter_rows(min_row=2, values_only=True))
    finally:
        book.close()
    out: list[tuple[str, str]] = []
    for name, _score, _event, _status, klass, *_rest in rows:
        cell = klass.strip() if isinstance(klass, str) else ""
        if cell in SUB_GAUGE_CELLS:
            last, first = (part.strip() for part in name.split(",", 1))
            out.append((f"{last} {first}".lower(), cell))
    return out


def scalar(session: Any, sql: str, **params: Any) -> int:
    return int(session.execute(text(sql), params).scalar_one())


def test_sub_gauge_holders_match_fixture(fx_session):
    raw = raw_sub_gauge_rows()
    cells = [cell for _, cell in raw]
    assert len(raw) == 18
    assert cells.count("Sub-Gauge") == 9
    assert cells.count("20 Gauge") == 1
    assert cells.count(".410") == 0
    assert sum(cell in {"28 Gauge", "29 Gauge"} for _, cell in raw) == 8
    expected = {key for key, _ in raw}
    keys = {
        key
        for (key,) in fx_session.execute(
            text(
                "SELECT r.name_key FROM achievements_awarded a JOIN rounds r ON r.id = a.round_id "
                "WHERE a.code = 'sub_gauge'"
            )
        ).all()
    }
    assert keys == expected
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'sub_gauge'")
        == len(expected)
        > 0
    )


@pytest.mark.parametrize(("code", "max_rank"), [("first_win", 1), ("podium", 3)])
def test_rank_trophy_holders_match_round_metrics(fx_session, code, max_rank):
    expected = scalar(
        fx_session,
        "SELECT count(DISTINCT r.shooter_id) FROM rounds r "
        "JOIN round_metrics m ON m.round_id = r.id "
        "WHERE m.is_best_round AND m.event_rank <= :rank AND r.event_date IN ("
        " SELECT event_date FROM rounds GROUP BY event_date"
        " HAVING count(DISTINCT shooter_id) >= 5)",
        rank=max_rank,
    )
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = :c", c=code)
        == expected
        > 0
    )
