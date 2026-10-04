"""/api/club-events (Plan 20 §5.4): club events for members.

The list, one event with its roster, the sign-up check, signing up and cancelling. Behind the
`events` launch switch: while it is off a viewer gets exactly the unknown-path 404, decided by
the router-level `feature_gate` before any body check, rate limit or read (D1, D23). Never
ETagged or stored (D20, api/etag.py). No response carries an email, a token hash, `queue_at` or
`created_at`; request fields are unconstrained so a 422 can never echo an email (§5.3.6).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from sunday_clays.api.routes._features import feature_gate
from sunday_clays.auth.deps import ForbiddenError, TooManyRequestsError, ip_fingerprint
from sunday_clays.auth.ratelimit import club_event_attempts, record_club_event_attempt
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain import club_event_store as store
from sunday_clays.domain import club_events as rules
from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.identity import merge_map

router = APIRouter(
    prefix="/api/club-events",
    tags=["club-events"],
    # Plan 19's feature_gate returns Depends(gate) and gate depends on require_viewer (401 first);
    # route discovery adds require_viewer as well. Never wrap it in a second Depends.
    dependencies=[feature_gate("events")],
)
SettingsDep = Annotated[Settings, Depends(get_settings)]


class ClubEventSummaryOut(BaseModel):
    id: int
    title: str
    starts_at: datetime
    local_date: date
    local_time: str
    signup_deadline: datetime
    deadline_local_date: date
    deadline_local_time: str
    state: Literal["open", "closed", "started", "cancelled"]
    capacity: int | None
    spots_taken: int
    waitlist_count: int
    allow_guests: bool
    max_guests: int
    signups: int
    purged: bool
    upcoming: bool


class ClubEventListOut(BaseModel):
    upcoming: list[ClubEventSummaryOut]
    past: list[ClubEventSummaryOut]


class ClubRosterRowOut(BaseModel):
    registration_id: int
    name: str
    shooter_id: int | None
    guests: int
    status: Literal["going", "waitlist"]
    waitlist_position: int | None


class ClubEventDetailOut(ClubEventSummaryOut):
    notes: str
    roster: list[ClubRosterRowOut]


class ClubSignupCheckOut(BaseModel):
    has_email: bool
    already_signed_up: bool


class ClubSignupIn(BaseModel):
    shooter_id: int | None = None
    name: str | None = None
    email: str | None = None
    guests: int = 0


class ClubSignupOut(BaseModel):
    registration_id: int
    token: str
    status: Literal["going", "waitlist"]
    waitlist_position: int | None
    email_used: Literal["on_file", "given"]


class ClubCancelIn(BaseModel):
    token: str | None = None
    email: str | None = None


class ClubCancelOut(BaseModel):
    status: Literal["cancelled"] = "cancelled"
    promoted: int


def summary_out(summary: store.EventSummary) -> ClubEventSummaryOut:
    event = summary.event
    return ClubEventSummaryOut(
        id=event.id,
        title=event.title,
        starts_at=event.starts_at,
        local_date=summary.local_date,
        local_time=summary.local_time,
        signup_deadline=event.signup_deadline,
        deadline_local_date=summary.deadline_local_date,
        deadline_local_time=summary.deadline_local_time,
        state=summary.state,
        capacity=event.capacity,
        spots_taken=summary.spots_taken,
        waitlist_count=summary.waitlist_count,
        allow_guests=event.allow_guests,
        max_guests=event.max_guests,
        signups=summary.signups,
        purged=summary.purged,
        upcoming=summary.upcoming,
    )


@router.get("")
def list_club_events(session: SessionDep, settings: SettingsDep) -> ClubEventListOut:
    upcoming, past = store.list_for_viewers(session, store.utcnow(), settings.timezone)
    return ClubEventListOut(
        upcoming=[summary_out(s) for s in upcoming], past=[summary_out(s) for s in past]
    )


@router.get("/{event_id}")
def get_club_event(event_id: int, session: SessionDep, settings: SettingsDep) -> ClubEventDetailOut:
    event = store.get_event(session, event_id)
    [summary] = store.summarize(session, [event], store.utcnow(), settings.timezone)
    rows = store.roster(session, event)
    return ClubEventDetailOut(
        **summary_out(summary).model_dump(),
        notes=event.notes,
        roster=[
            ClubRosterRowOut(
                registration_id=row.registration_id,
                name=row.name,
                shooter_id=row.shooter_id,
                guests=row.guests,
                status="going" if row.status == "going" else "waitlist",
                waitlist_position=row.waitlist_position,
            )
            for row in rows
        ],
    )


@router.get("/{event_id}/signup-check")
def signup_check(
    event_id: int, shooter_id: int, request: Request, session: SessionDep
) -> ClubSignupCheckOut:
    """`has_email` is the one bit the form needs (D11 accepted exception); never the address."""
    ip = ip_fingerprint(request)
    record_club_event_attempt(session, ip, "check")
    session.commit()  # get_session rolls back on any error; a refused check still counts
    if (
        club_event_attempts(session, ip, "check", rules.CHECK_WINDOW)
        > get_settings().club_event_check_limit
    ):
        raise TooManyRequestsError("rate_limited", rules.TOO_MANY)
    found = store.signup_check(session, event_id, shooter_id)
    return ClubSignupCheckOut(has_email=found.has_email, already_signed_up=found.already_signed_up)


@router.post("/{event_id}/registrations", status_code=201)
def sign_up(
    event_id: int, body: ClubSignupIn, request: Request, session: SessionDep
) -> ClubSignupOut:
    ip = ip_fingerprint(request)
    record_club_event_attempt(session, ip, "signup")
    session.commit()  # get_session rolls back on any error; a refused sign-up still counts
    if (body.shooter_id is None) == (body.name is None):
        raise DomainError("pick_or_type", "Pick a name from the list, or choose I'm not listed.")
    if (
        club_event_attempts(session, ip, "signup", rules.SIGNUP_WINDOW)
        > get_settings().club_event_signup_limit
    ):
        raise TooManyRequestsError("rate_limited", rules.TOO_MANY)
    # A sign-up that loses a race on a unique index gets the spec's "{name} is already on the
    # list." (§5.4), not the generic fallback.
    who: str | None
    if body.shooter_id is not None:
        resolved = store.resolve(merge_map(session), body.shooter_id)
        who = store.display_names(session, [resolved]).get(resolved)
    else:
        try:
            who = rules.typed_name(body.name or "")[0]
        except DomainError:
            who = None  # the store raises the same refusal; the generic fallback is never shown
    duplicate = f"{who} is already on the list." if who else "That name is already on the list."
    with rules.scrub_db_errors(session, duplicate_message=duplicate):
        result = store.sign_up(
            session,
            event_id,
            shooter_id=body.shooter_id,
            name=body.name,
            email=body.email,
            guests=body.guests,
            now=store.utcnow(),
        )
    return ClubSignupOut(
        registration_id=result.registration_id,
        token=result.token,
        status=result.status,
        waitlist_position=result.waitlist_position,
        email_used=result.email_used,
    )


@router.post("/{event_id}/registrations/{registration_id}/cancel")
def cancel_registration(
    event_id: int, registration_id: int, body: ClubCancelIn, request: Request, session: SessionDep
) -> ClubCancelOut:
    if (body.token is None) == (body.email is None):
        raise DomainError("token_or_email", "Send the sign-up's token or an email, not both.")
    ip = ip_fingerprint(request)
    via: store.CancelVia
    if body.token is not None:
        proof, via = body.token, "device"
    else:
        proof, via = body.email or "", "email"
    with rules.scrub_db_errors(session):
        promoted = store.cancel(
            session, event_id, registration_id, proof=proof, via=via, ip=ip, now=store.utcnow()
        )
    if promoted is None:
        session.commit()  # the failure counts although the answer is an error
        raise ForbiddenError("cancel_not_matched", rules.CANCEL_NOT_MATCHED)
    return ClubCancelOut(promoted=promoted)
