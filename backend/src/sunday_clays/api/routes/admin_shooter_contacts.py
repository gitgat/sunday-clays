"""/api/admin/shooter-contacts (Plan 20 §5.5): shooters' emails on file.

Admin-only by discovery, never ETagged or stored. Listing them is an audited read; setting and
removing one are audited writes whose details hold the shooter id only (`email_changed: true`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain import club_event_admin as admin
from sunday_clays.domain import club_event_store as store
from sunday_clays.domain import club_events as rules

router = APIRouter(prefix="/api/admin/shooter-contacts", tags=["admin"])
ActorDep = Annotated[Actor, Depends(admin_actor)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class ShooterContactOut(BaseModel):
    shooter_id: int
    name: str
    email: str
    source: Literal["signup", "organizer", "link"]
    updated_at: datetime
    last_used_at: datetime | None
    last_used_on: date | None  # club-time date of last_used_at (D21)


class ShooterContactIn(BaseModel):
    email: str  # unconstrained: the domain validates it (§5.3.6)


def _out(row: admin.ContactRow, tz: str) -> ShooterContactOut:
    used = row.last_used_at
    return ShooterContactOut.model_validate(
        {
            **row.__dict__,
            "last_used_on": None if used is None else used.astimezone(ZoneInfo(tz)).date(),
        }
    )


@router.get("")
def list_shooter_contacts(
    session: SessionDep, actor: ActorDep, settings: SettingsDep
) -> list[ShooterContactOut]:
    rows = admin.list_contacts(session)
    record_audit(session, actor.ip, actor.role, "shooter_contacts.view", {"rows": len(rows)})
    return [_out(row, settings.timezone) for row in rows]


@router.put("/{shooter_id}")
def set_shooter_contact(
    shooter_id: int,
    body: ShooterContactIn,
    session: SessionDep,
    actor: ActorDep,
    settings: SettingsDep,
) -> ShooterContactOut:
    with rules.scrub_db_errors(session):
        row = admin.set_contact(session, shooter_id, body.email, store.utcnow())
        record_audit(
            session,
            actor.ip,
            actor.role,
            "shooter_contacts.set",
            {"shooter_id": shooter_id, "email_changed": True},
        )
    return _out(row, settings.timezone)


@router.delete("/{shooter_id}", status_code=204)
def delete_shooter_contact(shooter_id: int, session: SessionDep, actor: ActorDep) -> None:
    with rules.scrub_db_errors(session):
        admin.delete_contact(session, shooter_id)
        record_audit(
            session, actor.ip, actor.role, "shooter_contacts.delete", {"shooter_id": shooter_id}
        )
