"""Admin operations (C8): data issues, possible duplicates, audit log, analytics recompute."""

from collections.abc import Mapping, Set
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.api.routes._admin import JobRefOut
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.db import SessionDep
from sunday_clays.ingest.names import similar_name_keys
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Base

router = APIRouter(prefix="/api/admin", tags=["admin"])

ActorDep = Annotated[Actor, Depends(admin_actor)]


class DataIssueOut(BaseModel):
    id: int
    code: str
    severity: str
    event_date: date | None
    shooter_id: int | None
    message: str
    details: dict[str, Any]  # C4 NOT NULL default '{}' (Plan 03 T1); non-null in openapi.json


class DuplicateSideOut(BaseModel):
    shooter_id: int
    name_key: str
    display_name: str
    n_rounds: int
    first_event: date | None
    last_event: date | None


class PossibleDuplicateOut(BaseModel):
    a: DuplicateSideOut
    b: DuplicateSideOut


class AuditEntryOut(BaseModel):
    id: int
    at: datetime
    ip: str | None
    role: str
    action: str
    details: dict[str, Any]  # C4 NOT NULL default '{}' (Plan 03 T1); non-null in openapi.json


class RecomputeIn(BaseModel):
    recalibrate: bool = False


def duplicate_key_pairs(
    key_dates: Mapping[str, Set[date]], key_shooter: Mapping[str, int]
) -> list[tuple[str, str]]:
    """Similar identity-key pairs (C3 rules) of different shooters, one pair per shooter pair.

    Pairs come back as (smaller key, larger key), sorted; a shooter pair reachable through
    several key pairs is reported once, via its smallest key pair.
    """
    key_pairs: set[tuple[str, str]] = set()
    for key, dates in key_dates.items():
        for other in similar_name_keys(key, dates, key_dates):
            if key_shooter[key] != key_shooter[other]:
                key_pairs.add((min(key, other), max(key, other)))
    seen: set[frozenset[int]] = set()
    result: list[tuple[str, str]] = []
    for first, second in sorted(key_pairs):
        shooters = frozenset((key_shooter[first], key_shooter[second]))
        if shooters not in seen:
            seen.add(shooters)
            result.append((first, second))
    return result


@router.get("/data-issues")
def data_issues(session: SessionDep) -> list[DataIssueOut]:
    t = Base.metadata.tables["data_issues"]
    rows = session.execute(
        select(
            t.c.id,
            t.c.code,
            t.c.severity,
            t.c.event_date,
            t.c.shooter_id,
            t.c.message,
            t.c.details,
        ).order_by(t.c.code, t.c.event_date.desc().nulls_last(), t.c.id)
    ).mappings()
    return [DataIssueOut.model_validate(dict(row)) for row in rows]


@cached_by_data_version
def _possible_duplicates(session: Session) -> list[PossibleDuplicateOut]:
    """All-pairs key comparison (~1.1 s on the fixtures), memoized per data_version (C7)."""
    rounds = Base.metadata.tables["rounds"]
    profiles = Base.metadata.tables["shooter_profiles"]
    key_dates: dict[str, set[date]] = {}
    key_shooter: dict[str, int] = {}
    for name_key, shooter_id, event_date in session.execute(
        select(rounds.c.name_key, rounds.c.shooter_id, rounds.c.event_date)
    ):
        key_dates.setdefault(name_key, set()).add(event_date)
        key_shooter[name_key] = shooter_id
    profile = {
        row["shooter_id"]: row
        for row in session.execute(
            select(
                profiles.c.shooter_id,
                profiles.c.display_name,
                profiles.c.n_rounds,
                profiles.c.first_event,
                profiles.c.last_event,
            )
        ).mappings()
    }

    def side(name_key: str) -> DuplicateSideOut:
        return DuplicateSideOut.model_validate(
            {**profile[key_shooter[name_key]], "name_key": name_key}
        )

    return [
        PossibleDuplicateOut(a=side(first), b=side(second))
        for first, second in duplicate_key_pairs(key_dates, key_shooter)
    ]


@router.get("/possible-duplicates")
def possible_duplicates(session: SessionDep) -> list[PossibleDuplicateOut]:
    return _possible_duplicates(session)


@router.get("/audit")
def audit(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditEntryOut]:
    t = Base.metadata.tables["audit_log"]
    rows = session.execute(
        select(t.c.id, t.c.at, t.c.ip, t.c.role, t.c.action, t.c.details)
        .order_by(t.c.id.desc())
        .limit(limit)
        .offset(offset)
    ).mappings()
    return [AuditEntryOut.model_validate(dict(row)) for row in rows]


@router.post("/recompute")
def recompute(session: SessionDep, actor: ActorDep, body: RecomputeIn | None = None) -> JobRefOut:
    recalibrate = body is not None and body.recalibrate
    if recalibrate:
        # Also clear the key here: a plain recompute may already be queued under the same
        # dedupe key, and enqueue() would then return that job without our payload.
        app_state = Base.metadata.tables["app_state"]
        session.execute(delete(app_state).where(app_state.c.key == "skill_params"))
    payload = {"recalibrate": True} if recalibrate else None
    job_id = enqueue(session, "recompute", payload, dedupe_key="recompute")
    record_audit(
        session,
        actor.ip,
        actor.role,
        "ops.recompute",
        {"recalibrate": recalibrate, "job_id": job_id},
    )
    return JobRefOut(job_id=job_id)
