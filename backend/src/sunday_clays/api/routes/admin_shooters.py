"""Shooter identity fixes (C8): merge (with dry run), rename, status, alias → overlay rules."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.api.routes._admin import RuleMutationOut, ensure_exists
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.rules import RuleType, create_rule
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Base

router = APIRouter(prefix="/api/admin/shooters", tags=["admin"])

ActorDep = Annotated[Actor, Depends(admin_actor)]
ShooterId = Annotated[int, Path(alias="id")]


class MergeIn(BaseModel):
    source_shooter_id: int
    target_shooter_id: int
    dry_run: bool = False


class MergeOut(BaseModel):
    shared_dates: int
    job_id: int | None


class RenameIn(BaseModel):
    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]


class StatusIn(BaseModel):
    status: Literal["member", "guest", "deceased"]


class AliasIn(BaseModel):
    # Taken verbatim after stripping (Decision D18): re-running name_key would mangle an identity
    # key such as "elias@2025-02-23"; create_rule rejects a key that is not one (400 invalid_rule).
    name_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def shared_dates(session: Session, first_id: int, second_id: int) -> int:
    """Number of distinct event dates on which both shooters have a live round."""
    rounds = Base.metadata.tables["rounds"]
    first = select(rounds.c.event_date).where(rounds.c.shooter_id == first_id)
    second = select(rounds.c.event_date).where(rounds.c.shooter_id == second_id)
    both = first.intersect(second).subquery()
    return int(session.scalar(select(func.count()).select_from(both)) or 0)


def _rule_then_rebuild(
    session: Session, actor: Actor, action: str, rule_type: RuleType, payload: dict[str, Any]
) -> RuleMutationOut:
    rule_id = create_rule(session, rule_type, payload, None)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session, actor.ip, actor.role, action, {**payload, "rule_id": rule_id, "job_id": job_id}
    )
    return RuleMutationOut(rule_id=rule_id, job_id=job_id)


@router.post("/merge")
def merge(body: MergeIn, session: SessionDep, actor: ActorDep) -> MergeOut:
    if body.source_shooter_id == body.target_shooter_id:
        raise DomainError("merge_same_shooter", "Pick two different shooters to merge")
    for shooter_id in (body.source_shooter_id, body.target_shooter_id):
        ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")
    shared = shared_dates(session, body.source_shooter_id, body.target_shooter_id)
    if body.dry_run:
        return MergeOut(shared_dates=shared, job_id=None)
    payload = {
        "source_shooter_id": body.source_shooter_id,
        "target_shooter_id": body.target_shooter_id,
    }
    done = _rule_then_rebuild(session, actor, "shooters.merge", RuleType.MERGE_SHOOTER, payload)
    return MergeOut(shared_dates=shared, job_id=done.job_id)


@router.post("/{id}/rename")
def rename(
    shooter_id: ShooterId, body: RenameIn, session: SessionDep, actor: ActorDep
) -> RuleMutationOut:
    ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")
    payload = {"shooter_id": shooter_id, "display_name": body.display_name}
    return _rule_then_rebuild(session, actor, "shooters.rename", RuleType.RENAME_SHOOTER, payload)


@router.post("/{id}/status")
def set_status(
    shooter_id: ShooterId, body: StatusIn, session: SessionDep, actor: ActorDep
) -> RuleMutationOut:
    ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")
    payload = {"shooter_id": shooter_id, "status": body.status}
    return _rule_then_rebuild(session, actor, "shooters.status", RuleType.SET_STATUS, payload)


@router.post("/{id}/aliases")
def add_alias(
    shooter_id: ShooterId, body: AliasIn, session: SessionDep, actor: ActorDep
) -> RuleMutationOut:
    ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")
    payload = {"name_key": body.name_key, "shooter_id": shooter_id}
    return _rule_then_rebuild(session, actor, "shooters.alias", RuleType.ALIAS_NAME, payload)
