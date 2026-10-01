"""Fist-bump store (Plan 14): one row per (post, device), so every write is idempotent.

Nothing here checks that a post exists: the API resolves a post key before it writes, and a bump
on a post that later disappears (a data correction) is kept but never counted on a Sheet.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.models import FistBump


@dataclass(frozen=True)
class BumpState:
    bumps: int
    bumped: bool


@dataclass(frozen=True)
class BumpTotal:
    post_key: str
    bumps: int
    last_at: datetime


def add_bump(session: Session, post_key: str, device_id: uuid.UUID) -> None:
    """Idempotent: a repeat from the same device, even a concurrent one, changes nothing."""
    session.execute(
        pg_insert(FistBump)
        .values(post_key=post_key, device_id=device_id)
        .on_conflict_do_nothing(index_elements=[FistBump.post_key, FistBump.device_id])
    )


def remove_bump(session: Session, post_key: str, device_id: uuid.UUID) -> None:
    """Idempotent: taking back a bump that is not there changes nothing."""
    session.execute(
        delete(FistBump).where(FistBump.post_key == post_key, FistBump.device_id == device_id)
    )


def bump_states(
    session: Session, post_keys: Collection[str], device_id: uuid.UUID | None
) -> dict[str, BumpState]:
    """The count and "this device bumped it" for each key; a key nobody bumped is (0, False)."""
    keys = sorted(set(post_keys))
    if not keys:
        return {}
    counts = {
        str(key): int(n)
        for key, n in session.execute(
            select(FistBump.post_key, func.count())
            .where(FistBump.post_key.in_(keys))
            .group_by(FistBump.post_key)
        )
    }
    mine: set[str] = set()
    if device_id is not None:
        mine = set(
            session.scalars(
                select(FistBump.post_key).where(
                    FistBump.post_key.in_(keys), FistBump.device_id == device_id
                )
            )
        )
    return {key: BumpState(counts.get(key, 0), key in mine) for key in keys}


def bump_state(session: Session, post_key: str, device_id: uuid.UUID | None) -> BumpState:
    return bump_states(session, [post_key], device_id)[post_key]


def wipe_bumps(session: Session, post_key: str) -> int:
    """Delete every bump on one post; returns how many there were."""
    removed = session.scalars(
        delete(FistBump).where(FistBump.post_key == post_key).returning(FistBump.device_id)
    )
    return len(removed.all())


def bump_totals(session: Session, limit: int) -> list[BumpTotal]:
    """Bumped posts, most recently bumped first (ties by key), at most `limit` of them."""
    last = func.max(FistBump.created_at)
    rows = session.execute(
        select(FistBump.post_key, func.count(), last)
        .group_by(FistBump.post_key)
        .order_by(last.desc(), FistBump.post_key)
        .limit(limit)
    )
    return [BumpTotal(str(key), int(n), at) for key, n, at in rows]
