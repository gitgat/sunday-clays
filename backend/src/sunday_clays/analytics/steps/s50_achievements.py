"""Recompute step 50 (C6): evaluate every registered achievement and replace achievements_awarded.

Replacing (not merging) is what keeps rollbacks honest: a trophy whose data vanished disappears.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.achievements.context import build_context
from sunday_clays.analytics.achievements.registry import evaluate_all
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.pipeline import RecomputeStep

_INSERT = text(
    "INSERT INTO achievements_awarded (shooter_id, code, event_date, round_id, details) "
    "VALUES (:shooter_id, :code, :event_date, :round_id, CAST(:details AS jsonb))"
)


def _json_scalar(value: object) -> bool | int | float:
    """json.dumps fallback: numpy scalars (what a frame yields) become Python scalars."""
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def details_json(details: Mapping[str, Any]) -> str:
    """Award.details as the JSON text stored in achievements_awarded.details (jsonb)."""
    return json.dumps(dict(details), sort_keys=True, default=_json_scalar)


def run(session: Session) -> None:
    clear_cache()  # a memo entry may be keyed at a rolled-back run's uncommitted data_version
    awards = evaluate_all(build_context(session))
    session.execute(text("DELETE FROM achievements_awarded"))
    if awards:
        session.execute(
            _INSERT,
            [
                {
                    "shooter_id": award.shooter_id,
                    "code": award.code,
                    "event_date": award.event_date,
                    "round_id": award.round_id,
                    "details": details_json(award.details),
                }
                for award in awards
            ],
        )


STEP = RecomputeStep(name="achievements", order=50, run=run)
