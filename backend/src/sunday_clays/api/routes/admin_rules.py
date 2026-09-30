"""Overlay rules (C5, C8): list, create and deactivate; every mutation enqueues a rebuild."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy import select

from sunday_clays.api.routes._admin import RuleMutationOut, ensure_exists
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.db import SessionDep
from sunday_clays.domain.rules import RuleType, create_rule, deactivate_rule
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Base

router = APIRouter(prefix="/api/admin/rules", tags=["admin"])

ActorDep = Annotated[Actor, Depends(admin_actor)]
RuleId = Annotated[int, Path(alias="id")]


class RuleIn(BaseModel):
    rule_type: RuleType
    payload: dict[str, Any]
    note: str | None = Field(default=None, max_length=500)


class RuleOut(BaseModel):
    id: int
    rule_type: RuleType
    payload: dict[str, Any]
    active: bool
    note: str | None
    created_at: datetime
    deactivated_at: datetime | None


@router.get("")
def list_rules(session: SessionDep) -> list[RuleOut]:
    t = Base.metadata.tables["rules"]
    rows = session.execute(
        select(
            t.c.id,
            t.c.rule_type,
            t.c.payload,
            t.c.active,
            t.c.note,
            t.c.created_at,
            t.c.deactivated_at,
        ).order_by(t.c.id.desc())
    ).mappings()
    return [RuleOut.model_validate(dict(row)) for row in rows]


@router.post("")
def add_rule(body: RuleIn, session: SessionDep, actor: ActorDep) -> RuleMutationOut:
    rule_id = create_rule(session, body.rule_type, body.payload, body.note)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session,
        actor.ip,
        actor.role,
        "rules.create",
        {
            "rule_id": rule_id,
            "rule_type": body.rule_type,
            "payload": body.payload,
            "job_id": job_id,
        },
    )
    return RuleMutationOut(rule_id=rule_id, job_id=job_id)


@router.post("/{id}/deactivate")
def deactivate(rule_id: RuleId, session: SessionDep, actor: ActorDep) -> RuleMutationOut:
    ensure_exists(session, "rules", rule_id, "rule_not_found", "Rule")
    deactivate_rule(session, rule_id)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session, actor.ip, actor.role, "rules.deactivate", {"rule_id": rule_id, "job_id": job_id}
    )
    return RuleMutationOut(rule_id=rule_id, job_id=job_id)
