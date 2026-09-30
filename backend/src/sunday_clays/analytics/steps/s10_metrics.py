"""Recompute step 10: round_metrics field columns and event_metrics (C6/C7)."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.metrics import compute_event_metrics, compute_round_metrics
from sunday_clays.analytics.pipeline import RecomputeStep

_INSERT_ROUND_METRICS = """
INSERT INTO round_metrics
    (round_id, field_median, adjusted, event_rank, is_best_round, percentile)
VALUES (:round_id, :field_median, :adjusted, :event_rank, :is_best_round, :percentile)
"""
_INSERT_EVENT_METRICS = """
INSERT INTO event_metrics (event_date, n, median, mean, stdev, top_score, difficulty)
VALUES (:event_date, :n, :median, :mean, :stdev, :top_score, :difficulty)
"""


def run(session: Session) -> None:
    """Rewrite round_metrics (skill columns NULL until s30) and event_metrics."""
    clear_cache()
    rounds = frames.load_rounds(session)
    round_metrics = compute_round_metrics(rounds)
    round_metrics["event_rank"] = round_metrics["event_rank"].astype("Int64")
    event_metrics = compute_event_metrics(rounds)
    session.execute(text("DELETE FROM round_metrics"))
    session.execute(text("DELETE FROM event_metrics"))
    if not round_metrics.empty:
        session.execute(text(_INSERT_ROUND_METRICS), frames.db_records(round_metrics))
        session.execute(text(_INSERT_EVENT_METRICS), frames.db_records(event_metrics))
    clear_cache()


STEP = RecomputeStep(name="metrics", order=10, run=run)
