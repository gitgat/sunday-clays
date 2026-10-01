"""Fist-bump store (Plan 15): one row per (insight key, device), so every write is idempotent.

Nothing here checks that an insight exists: the API checks the key before it writes, and a bump
on an insight that later disappears (a recompute or a data correction) is kept but never shown.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.models import FistBump


@dataclass(frozen=True)
class BumpState:
    bumps: int
    bumped: bool


def add_bump(session: Session, insight_key: str, device_id: uuid.UUID) -> None:
    """Idempotent: a repeat from the same device, even a concurrent one, changes nothing."""
    session.execute(
        pg_insert(FistBump)
        .values(insight_key=insight_key, device_id=device_id)
        .on_conflict_do_nothing(index_elements=[FistBump.insight_key, FistBump.device_id])
    )


def remove_bump(session: Session, insight_key: str, device_id: uuid.UUID) -> None:
    """Idempotent: taking back a bump that is not there changes nothing."""
    session.execute(
        delete(FistBump).where(FistBump.insight_key == insight_key, FistBump.device_id == device_id)
    )


def bump_states(
    session: Session, insight_keys: Collection[str], device_id: uuid.UUID | None
) -> dict[str, BumpState]:
    """The count and "this device bumped it" for each key; a key nobody bumped is (0, False)."""
    keys = sorted(set(insight_keys))
    if not keys:
        return {}
    counts = {
        str(key): int(n)
        for key, n in session.execute(
            select(FistBump.insight_key, func.count())
            .where(FistBump.insight_key.in_(keys))
            .group_by(FistBump.insight_key)
        )
    }
    mine: set[str] = set()
    if device_id is not None:
        mine = set(
            session.scalars(
                select(FistBump.insight_key).where(
                    FistBump.insight_key.in_(keys), FistBump.device_id == device_id
                )
            )
        )
    return {key: BumpState(counts.get(key, 0), key in mine) for key in keys}


def bump_state(session: Session, insight_key: str, device_id: uuid.UUID | None) -> BumpState:
    return bump_states(session, [insight_key], device_id)[insight_key]
