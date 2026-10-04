"""/api/admin/club-events (Plan 20 §5.5): organizers manage club events.

Admin-only by discovery (`admin_*`), never ETagged or stored (`/api/admin/`), and served whether
the `events` switch is on or off, so the first event can be prepared before launch (D1). Every
mutation, the roster read, the CSV export and the email list write one audit row in the same
transaction. Audit details never hold an email or a person's name: a registration is its id, a
contact is its shooter id (§5.5). Every write runs inside scrub_db_errors (D22).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from sunday_clays.api.csv_safe import csv_safe
from sunday_clays.api.routes.club_events import ClubEventSummaryOut, summary_out
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain import club_event_admin as admin
from sunday_clays.domain import club_event_store as store
from sunday_clays.domain import club_events as rules
from sunday_clays.domain.identity import merge_map

router = APIRouter(prefix="/api/admin/club-events", tags=["admin"])
ActorDep = Annotated[Actor, Depends(admin_actor)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CSV_HEADER = (
    "status",
    "waitlist_position",
    "name",
    "shooter_id",
    "email",
    "guests",
    "spots",
    "signed_up_local",
)


class ClubEventIn(BaseModel):
    title: str
    starts_local: str
    deadline_local: str
    notes: str = ""
    capacity: int | None = None
    allow_guests: bool = False
    max_guests: int = 0


class ClubEventPatchIn(BaseModel):
    title: str | None = None
    starts_local: str | None = None
    deadline_local: str | None = None
    notes: str | None = None
    capacity: int | None = None
    allow_guests: bool | None = None
    max_guests: int | None = None


class ClubEventAdminOut(ClubEventSummaryOut):
    notes: str


class ClubSuggestedShooterOut(BaseModel):
    id: int
    name: str
    has_email: bool


class ClubAdminRosterRowOut(BaseModel):
    id: int
    name: str
    typed_name: str | None
    shooter_id: int | None
    email: str | None
    email_source: Literal["contact", "registration"] | None
    guests: int
    status: Literal["going", "waitlist", "cancelled", "removed"]
    waitlist_position: int | None
    signed_up_at: datetime
    signed_up_local: str  # club time "YYYY-MM-DD HH:MM" (D21): the page never converts a timestamp
    promoted_at: datetime | None
    cancelled_at: datetime | None
    cancelled_via: Literal["device", "email", "organizer"] | None
    suggested_shooter: ClubSuggestedShooterOut | None
    cancel_fail_count: int


class ClubEmailsOut(BaseModel):
    emails: list[str]


class ClubGuestsIn(BaseModel):
    guests: int


class ClubGuestsOut(BaseModel):
    guests: int


class ClubLinkIn(BaseModel):
    shooter_id: int


class ClubLinkOut(BaseModel):
    shooter_id: int
    email_moved: bool
    email_discarded: bool


class ClubClearedOut(BaseModel):
    cleared: int


def _admin_outs(
    session: SessionDep, events: list[store.EventRow], tz: str
) -> list[ClubEventAdminOut]:
    summaries = store.summarize(session, events, store.utcnow(), tz)
    return [
        ClubEventAdminOut(**summary_out(s).model_dump(), notes=s.event.notes) for s in summaries
    ]


def _admin_out(session: SessionDep, event_id: int, tz: str) -> ClubEventAdminOut:
    return _admin_outs(session, [store.get_event(session, event_id)], tz)[0]


def local_stamp(instant: datetime, tz: str) -> str:
    """An instant as club-time "YYYY-MM-DD HH:MM" (the CSV's signed_up_local and the roster's)."""
    return instant.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")


def _row_out(row: admin.AdminRosterRow, tz: str) -> ClubAdminRosterRowOut:
    hint = row.suggested_shooter
    return ClubAdminRosterRowOut.model_validate(
        {
            **row.__dict__,
            "signed_up_local": local_stamp(row.signed_up_at, tz),
            "suggested_shooter": None
            if hint is None
            else ClubSuggestedShooterOut(id=hint.id, name=hint.name, has_email=hint.has_email),
        }
    )


def roster_csv_text(rows: list[admin.AdminRosterRow], tz: str) -> str:
    """Active rows in queue order; every cell through csv_safe (§5.5)."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for row in rows:
        cells = (
            row.status,
            "" if row.waitlist_position is None else str(row.waitlist_position),
            row.name,
            "" if row.shooter_id is None else str(row.shooter_id),
            row.email or "",
            str(row.guests),
            str(row.guests + 1),
            local_stamp(row.signed_up_at, tz),
        )
        writer.writerow([csv_safe(cell) for cell in cells])
    return out.getvalue()


@router.get("")
def list_club_events(session: SessionDep, settings: SettingsDep) -> list[ClubEventAdminOut]:
    """Every event, newest first."""
    return _admin_outs(session, list(reversed(store.all_events(session))), settings.timezone)


@router.post("", status_code=201)
def create_club_event(
    body: ClubEventIn, session: SessionDep, actor: ActorDep, settings: SettingsDep
) -> ClubEventAdminOut:
    fields = admin.EventFields(**body.model_dump())
    with rules.scrub_db_errors(session):
        event_id = admin.create_event(session, fields, now=store.utcnow(), tz=settings.timezone)
        event = store.get_event(session, event_id)
        record_audit(
            session,
            actor.ip,
            actor.role,
            "club_events.create",
            {"id": event_id, "title": event.title, "starts_at": event.starts_at},
        )
    return _admin_out(session, event_id, settings.timezone)


@router.patch("/{event_id}")
def update_club_event(
    event_id: int,
    body: ClubEventPatchIn,
    session: SessionDep,
    actor: ActorDep,
    settings: SettingsDep,
) -> ClubEventAdminOut:
    patch = admin.EventPatch(
        **body.model_dump(exclude={"capacity"}),
        capacity=body.capacity,
        capacity_set="capacity" in body.model_fields_set,
    )
    with rules.scrub_db_errors(session):
        changed = admin.update_event(
            session, event_id, patch, now=store.utcnow(), tz=settings.timezone
        )
        record_audit(
            session,
            actor.ip,
            actor.role,
            "club_events.update",
            {"id": event_id, "changed": changed},
        )
    return _admin_out(session, event_id, settings.timezone)


@router.post("/{event_id}/cancel")
def cancel_club_event(
    event_id: int, session: SessionDep, actor: ActorDep, settings: SettingsDep
) -> ClubEventAdminOut:
    with rules.scrub_db_errors(session):
        going, waiting = admin.cancel_event(session, event_id, store.utcnow())
        record_audit(
            session,
            actor.ip,
            actor.role,
            "club_events.cancel",
            {"id": event_id, "going": going, "waitlist": waiting},
        )
    return _admin_out(session, event_id, settings.timezone)


@router.post("/{event_id}/restore")
def restore_club_event(
    event_id: int, session: SessionDep, actor: ActorDep, settings: SettingsDep
) -> ClubEventAdminOut:
    with rules.scrub_db_errors(session):
        admin.restore_event(session, event_id, store.utcnow())
        record_audit(session, actor.ip, actor.role, "club_events.restore", {"id": event_id})
    return _admin_out(session, event_id, settings.timezone)


@router.delete("/{event_id}", status_code=204)
def delete_club_event(event_id: int, session: SessionDep, actor: ActorDep) -> None:
    with rules.scrub_db_errors(session):
        title, registrations = admin.delete_event(session, event_id)
        record_audit(
            session,
            actor.ip,
            actor.role,
            "club_events.delete",
            {"id": event_id, "title": title, "registrations": registrations},
        )


@router.get("/{event_id}/roster")
def club_event_roster(
    event_id: int, session: SessionDep, actor: ActorDep, settings: SettingsDep
) -> list[ClubAdminRosterRowOut]:
    rows = admin.admin_roster(session, event_id, store.utcnow())
    record_audit(
        session,
        actor.ip,
        actor.role,
        "club_events.roster_view",
        {"id": event_id, "rows": len(rows)},
    )
    return [_row_out(row, settings.timezone) for row in rows]


@router.get(
    "/{event_id}/roster.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def club_event_roster_csv(
    event_id: int, session: SessionDep, actor: ActorDep, settings: SettingsDep
) -> Response:
    event = store.get_event(session, event_id)
    rows = [
        row
        for row in admin.admin_roster(session, event_id, store.utcnow())
        if row.status in rules.ACTIVE
    ]
    local_date, _ = rules.local_parts(event.starts_at, settings.timezone)
    record_audit(
        session,
        actor.ip,
        actor.role,
        "club_events.roster_export",
        {"id": event_id, "rows": len(rows)},
    )
    filename = f"club-event-{event_id}-{local_date.isoformat()}-roster.csv"
    return Response(
        content=roster_csv_text(rows, settings.timezone),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{event_id}/emails")
def club_event_emails(
    event_id: int,
    session: SessionDep,
    actor: ActorDep,
    status: Literal["going", "waitlist", "active"] = "going",
) -> ClubEmailsOut:
    emails = admin.roster_emails(admin.admin_roster(session, event_id, store.utcnow()), status)
    record_audit(
        session,
        actor.ip,
        actor.role,
        "club_events.emails_copy",
        {"id": event_id, "status": status, "count": len(emails)},
    )
    return ClubEmailsOut(emails=emails)


@router.delete("/{event_id}/registrations/{registration_id}", status_code=204)
def remove_registration(
    event_id: int, registration_id: int, session: SessionDep, actor: ActorDep
) -> None:
    with rules.scrub_db_errors(session):
        admin.remove_registration(session, event_id, registration_id, store.utcnow())
        record_audit(
            session,
            actor.ip,
            actor.role,
            "club_events.registration.remove",
            {"id": event_id, "registration_id": registration_id},
        )


@router.patch("/{event_id}/registrations/{registration_id}")
def change_guests(
    event_id: int, registration_id: int, body: ClubGuestsIn, session: SessionDep, actor: ActorDep
) -> ClubGuestsOut:
    with rules.scrub_db_errors(session):
        before, after = admin.set_guests(
            session, event_id, registration_id, body.guests, store.utcnow()
        )
        record_audit(
            session,
            actor.ip,
            actor.role,
            "club_events.registration.guests",
            {"id": event_id, "registration_id": registration_id, "from": before, "to": after},
        )
    return ClubGuestsOut(guests=after)


@router.post("/{event_id}/registrations/{registration_id}/reset-cancel-limit")
def reset_cancel_limit(
    event_id: int, registration_id: int, session: SessionDep, actor: ActorDep
) -> ClubClearedOut:
    with rules.scrub_db_errors(session):
        cleared = admin.reset_cancel_limit(session, event_id, registration_id)
        record_audit(
            session,
            actor.ip,
            actor.role,
            "club_events.registration.reset_cancel_limit",
            {"id": event_id, "registration_id": registration_id, "cleared": cleared},
        )
    return ClubClearedOut(cleared=cleared)


@router.post("/{event_id}/registrations/{registration_id}/link")
def link_registration(
    event_id: int, registration_id: int, body: ClubLinkIn, session: SessionDep, actor: ActorDep
) -> ClubLinkOut:
    target = store.resolve(merge_map(session), body.shooter_id)
    who = store.display_names(session, [target]).get(target)
    duplicate = f"{who} is already on the list." if who else "That name is already on the list."
    with rules.scrub_db_errors(session, duplicate_message=duplicate):
        result = admin.link_registration(
            session, event_id, registration_id, body.shooter_id, store.utcnow()
        )
        record_audit(
            session,
            actor.ip,
            actor.role,
            "club_events.registration.link",
            {
                "id": event_id,
                "registration_id": registration_id,
                "email_moved": result.email_moved,
                "email_discarded": result.email_discarded,
            },
        )
    return ClubLinkOut(
        shooter_id=result.shooter_id,
        email_moved=result.email_moved,
        email_discarded=result.email_discarded,
    )
