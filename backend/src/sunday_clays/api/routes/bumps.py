"""/api/bumps (Plan 15): anonymous fist bumps on insights, keyed by the insight's stable `key`.

Counts change without a data_version bump, so they are never part of an insight feed (which is
ETagged by data_version), and this path is never ETagged or stored (api/etag.py, "/bumps").
A bump on an insight that later disappears is kept but never listed.
A bump belongs to the insight's identity (its key), not its current wording: evergreen insights
keep their bumps when their numbers change. GET refuses a key over 200 characters with 400.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.store import existing_keys
from sunday_clays.auth.deps import TooManyRequestsError, ip_fingerprint
from sunday_clays.auth.ratelimit import bumps_limited, record_bump_action
from sunday_clays.db import SessionDep
from sunday_clays.domain.bumps import add_bump, bump_state, bump_states, remove_bump
from sunday_clays.domain.errors import DomainError, NotFoundError

router = APIRouter(tags=["bumps"])

MAX_KEYS = 100
MAX_KEY_LEN = 200


class BumpIn(BaseModel):
    key: str
    device_id: str


class BumpStateOut(BaseModel):
    bumps: int
    bumped: bool


def parse_device_id(value: str) -> uuid.UUID:
    """A canonical UUID (8-4-4-4-12 hex, any case), else a 400."""
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        parsed = None
    if parsed is None or str(parsed) != value.lower():
        raise DomainError("bad_device_id", "device_id must be a UUID")
    return parsed


def parse_keys(raw: str) -> list[str]:
    """`k1,k2,…` as distinct non-empty keys in order; more than MAX_KEYS is a 400."""
    keys = list(dict.fromkeys(k for k in (part.strip() for part in raw.split(",")) if k))
    if any(len(k) > MAX_KEY_LEN for k in keys):
        raise DomainError("bad_key", f"A key is at most {MAX_KEY_LEN} characters")
    if len(keys) > MAX_KEYS:
        raise DomainError("too_many_keys", f"Ask for at most {MAX_KEYS} keys at a time")
    return keys


@router.get("/api/bumps")
def bump_counts(
    session: SessionDep, keys: str = "", device_id: str | None = None
) -> dict[str, BumpStateOut]:
    """Counts for the asked keys that are insights now, zeros included; other keys are left out."""
    device = None if device_id is None else parse_device_id(device_id)
    current = existing_keys(session, parse_keys(keys))
    states = bump_states(session, current, device)
    return {key: BumpStateOut(bumps=s.bumps, bumped=s.bumped) for key, s in states.items()}


def _bump_action(
    request: Request,
    session: Session,
    body: BumpIn,
    act: Callable[[Session, str, uuid.UUID], None],
) -> BumpStateOut:
    ip = ip_fingerprint(request)
    if bumps_limited(session, ip):
        raise TooManyRequestsError("rate_limited", "Too many bumps from here. Try again soon.")
    record_bump_action(session, ip)
    session.commit()  # get_session rolls back on any error; a refused action still counts
    if not body.key or len(body.key) > MAX_KEY_LEN:
        raise DomainError("bad_key", f"key must be 1 to {MAX_KEY_LEN} characters")
    device = parse_device_id(body.device_id)
    if not existing_keys(session, [body.key]):
        raise NotFoundError("insight_not_found", "That insight is not on the site now")
    act(session, body.key, device)
    state = bump_state(session, body.key, device)
    return BumpStateOut(bumps=state.bumps, bumped=state.bumped)


@router.post("/api/bumps")
def bump_insight(body: BumpIn, request: Request, session: SessionDep) -> BumpStateOut:
    """Idempotent: bumping twice from one device counts once."""
    return _bump_action(request, session, body, add_bump)


@router.delete("/api/bumps")
def unbump_insight(body: BumpIn, request: Request, session: SessionDep) -> BumpStateOut:
    """Idempotent: taking back a bump that is not there changes nothing."""
    return _bump_action(request, session, body, remove_bump)
