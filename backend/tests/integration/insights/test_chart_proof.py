"""Chart links on the fx world (spec §5): valid specs, known anchors, and proven numbers."""

import dataclasses
from collections import defaultdict
from datetime import date

import numpy as np
import pandas as pd

from sunday_clays.analytics.insights.anchors import ANCHORS
from sunday_clays.analytics.insights.context import InsightFrames
from sunday_clays.analytics.insights.engine import Pair, apply_rollups, evaluate_all
from sunday_clays.analytics.insights.proof import proof_problems
from sunday_clays.analytics.steps.s60_insights import build_frames
from sunday_clays.explorer import engine as explorer_engine

SAMPLE = 20  # facts per (kind, variant): the latest ones


def _sample(pairs: list[Pair]) -> list[Pair]:
    groups: dict[tuple[str, str], list[Pair]] = defaultdict(list)
    for p in pairs:
        groups[(p.kind.id, p.fact.variant)].append(p)
    out: list[Pair] = []
    for group in groups.values():
        group.sort(key=lambda p: (p.fact.anchor_date is not None, p.fact.anchor_date or 0))
        out.extend(group[-SAMPLE:])
    return out


def _problems(
    pairs: list[Pair], fr: InsightFrames, ex: explorer_engine.ExplorerFrames
) -> list[str]:
    problems: list[str] = []
    for pair in pairs:
        kind, fact = pair.kind, pair.fact
        where = f"{kind.id}/{fact.variant} {fact.subject_id} {fact.anchor_date}"
        link = kind.chart(fact)
        if not any(link.label is label for label in kind.labels):
            problems.append(f"{where}: label is not one of the kind's labels")
        if link.window.start > link.window.end:
            problems.append(f"{where}: empty window")
        if link.type == "explorer":
            assert link.spec is not None
            explorer_engine.run_query(ex, link.spec)
        elif link.anchor not in ANCHORS:
            problems.append(f"{where}: unknown anchor {link.anchor}")
        problems.extend(f"{where}: {p}" for p in proof_problems(kind, fact, fr, ex))
    return problems


def test_every_chart_link_is_valid_and_proves_its_numbers(fx_session):
    fr = build_frames(fx_session)
    ex = explorer_engine.load_explorer_frames(fx_session)
    problems = _problems(_sample(apply_rollups(evaluate_all(fr))), fr, ex)
    assert problems == [], "\n".join(problems)


SCORE_ANCHORED = {
    "pf.pb",
    "pf.tied-best",
    "pf.first-tier",
    "ev.record-watch",
    "ev.top-score",
    "ev.drought-ended",
    "ev.spotlight",
    "ev.how-it-played",
    "ev.toughest-since",
}
COUNT_ANCHORED = {
    "ev.close-finish",
    "ev.new-faces",
    "pf.targets-milestone",
    "pf.wins",
    "pf.podium-run",
    "pf.sunday-milestone",
    "home.sunday-recap",
}


def _flag_day(df: pd.DataFrame, day: date, nan_cols: tuple[str, ...]) -> pd.DataFrame:
    out = df.copy()
    mask = out["event_date"] == day
    out["stats_excluded"] = out["stats_excluded"].eq(True) | mask
    for col in nan_cols:
        if col in out.columns:
            out[col] = out[col].astype(float)
            out.loc[mask, col] = np.nan
    return out


def _thrown_out(
    fr0: InsightFrames, ex0: explorer_engine.ExplorerFrames, day: date
) -> tuple[InsightFrames, explorer_engine.ExplorerFrames]:
    """Mirror D5: the Sunday's rounds lose adjusted/residual/expected, its event row difficulty."""
    rounds = _flag_day(fr0.rounds, day, ("adjusted", "residual", "expected"))
    events = _flag_day(fr0.events, day, ("difficulty",))
    fr = InsightFrames.from_frames(
        rounds=rounds,
        events=events,
        shooters=fr0.shooters,
        rating=fr0.rating,
        stations=fr0.stations,
        awards=fr0.awards,
        appearances=fr0.appearances,
        calendar=fr0.calendar,
    )
    ex = dataclasses.replace(
        ex0,
        rounds=_flag_day(ex0.rounds, day, ("adjusted", "residual", "expected")),
        events=_flag_day(ex0.events, day, ("difficulty",)),
    )
    return fr, ex


def test_chart_links_prove_their_numbers_with_a_thrown_out_sunday(fx_session):
    fr0 = build_frames(fx_session)
    ex0 = explorer_engine.load_explorer_frames(fx_session)
    day = fr0.held_dates()[-3]
    fr, ex = _thrown_out(fr0, ex0, day)
    pairs = apply_rollups(evaluate_all(fr))
    on_day = {p.kind.id for p in pairs if p.fact.anchor_date == day}
    assert on_day & SCORE_ANCHORED == set()
    assert on_day & COUNT_ANCHORED  # Review Focus 4: counts still fire on that day
    problems = _problems(_sample(pairs), fr, ex)
    assert problems == [], "\n".join(problems)
