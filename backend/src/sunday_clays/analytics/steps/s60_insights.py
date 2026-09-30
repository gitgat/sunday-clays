"""Recompute step 60 (Plan 12, spec §3.2): evaluate every insight kind and replace `insights`.

Static until the data changes (D5): nothing here reads the wall clock, the API only reads the
table, and phrasing is keyed by each insight's stable key, so re-running on unchanged data
rewrites identical content (only `generation` moves).
"""

from __future__ import annotations

import inspect

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.insights.context import AWARD_COLUMNS, InsightFrames
from sunday_clays.analytics.insights.engine import apply_rollups, build_rows, evaluate_all
from sunday_clays.analytics.insights.picks import compute_picks
from sunday_clays.analytics.insights.store import previous_versions, replace_all
from sunday_clays.analytics.pipeline import RecomputeStep, get_data_version

_AWARDS = text("SELECT shooter_id, code, event_date FROM achievements_awarded ORDER BY id")


def build_frames(session: Session) -> InsightFrames:
    """The loaders unwrapped: a memo entry could predate this run's s10/s30 writes (Plan 10 D5)."""
    awards = pd.DataFrame(
        [dict(r) for r in session.execute(_AWARDS).mappings()], columns=list(AWARD_COLUMNS)
    )
    return InsightFrames.from_frames(
        rounds=inspect.unwrap(frames.load_rounds)(session),
        events=inspect.unwrap(frames.load_events)(session),
        shooters=inspect.unwrap(frames.load_shooters)(session),
        rating=inspect.unwrap(frames.load_rating_history)(session),
        stations=inspect.unwrap(frames.load_station_hits)(session),
        awards=awards,
    )


def run(session: Session) -> None:
    clear_cache()
    fr = build_frames(session)
    generation = get_data_version(session) + 1  # the value run_pipeline bumps to
    pairs = apply_rollups(evaluate_all(fr))
    rows = build_rows(pairs, fr, generation=generation, previous=previous_versions(session))
    replace_all(session, rows, compute_picks(rows, fr.held_dates()))


STEP = RecomputeStep(name="insights", order=60, run=run)
