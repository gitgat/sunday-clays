"""Recompute step 30: skill model -> round_metrics, difficulty, rating_history."""

import json
import math
from dataclasses import asdict, fields

from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, skill
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.pipeline import RecomputeStep

_PARAM_NAMES: tuple[str, ...] = tuple(f.name for f in fields(skill.SkillParams))

_UPDATE_ROUNDS = """
UPDATE round_metrics
SET expected = :expected, residual = :residual, mu_before = :mu_before,
    var_before = :var_before, mu_after = :mu_after, var_after = :var_after
WHERE round_id = :round_id
"""
_UPDATE_EVENTS = "UPDATE event_metrics SET difficulty = :difficulty WHERE event_date = :event_date"
_INSERT_HISTORY = """
INSERT INTO rating_history (shooter_id, event_date, mu, var)
VALUES (:shooter_id, :event_date, :mu, :var)
"""
_UPSERT_STATE = """
INSERT INTO app_state (key, value) VALUES (:key, CAST(:value AS jsonb))
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
"""


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def load_params(session: Session) -> skill.SkillParams | None:
    """`app_state.skill_params` as SkillParams, or None when absent or unusable.

    Unusable counts as absent (Decision 14), so `run` recalibrates and overwrites it: not
    a JSON object, a field missing or not a JSON number, a number that is not finite as a
    float (too large: OverflowError or inf), or values SkillParams rejects (ValueError: a
    non-positive variance, negative drift).
    Keys that are not SkillParams fields are ignored.
    """
    value = session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_params'")
    ).scalar_one_or_none()
    if not isinstance(value, dict):
        return None
    numbers = [value.get(name) for name in _PARAM_NAMES]
    if not all(_is_number(number) for number in numbers):
        return None
    try:
        # A huge integral number loads as an int (float() raises OverflowError); a huge
        # fractional one loads as float inf, which SkillParams would accept.
        floats = [float(number) for number in numbers]
        if not all(math.isfinite(number) for number in floats):
            return None
        return skill.SkillParams(**dict(zip(_PARAM_NAMES, floats, strict=True)))
    except (OverflowError, ValueError):
        return None


def store_state(session: Session, key: str, value: object) -> None:
    """Upsert `value` as JSON into `app_state[key]` in the caller's transaction."""
    session.execute(text(_UPSERT_STATE), {"key": key, "value": json.dumps(value)})


def run(session: Session) -> None:
    """Stored params if present, else calibrate over CALIBRATION_GRID.

    Calibration scores only held events after the burn-in. With no such event (empty
    DB, stations-only first import) every grid point ties at 0.0 and the first point
    wins, so that result is used for this run but never stored: the next run with
    enough data calibrates for real.
    """
    clear_cache()
    rounds = frames.load_rounds(session)
    params = load_params(session)
    if params is None:
        params = skill.calibrate(rounds, skill.CALIBRATION_GRID)
        if rounds.loc[rounds["held"], "event_date"].nunique() > skill.BURN_IN_HELD_EVENTS:
            store_state(session, "skill_params", asdict(params))
    result = skill.run_skill_model(rounds, params)
    if not result.rounds.empty:
        session.execute(text(_UPDATE_ROUNDS), frames.db_records(result.rounds))
        session.execute(
            text(_UPDATE_EVENTS),
            frames.db_records(result.events[["event_date", "difficulty"]]),
        )
    session.execute(text("DELETE FROM rating_history"))
    if not result.history.empty:
        session.execute(text(_INSERT_HISTORY), frames.db_records(result.history))
    store_state(session, "skill_level", result.current_level)
    clear_cache()


STEP = RecomputeStep(name="skill", order=30, run=run)
