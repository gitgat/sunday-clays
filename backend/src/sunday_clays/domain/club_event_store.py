"""Club events (Plan 20): the database side for members.

Every write that can change who holds a spot locks the event row first (D13), then reads the
queue, decides and writes; the request's transaction commits. Every check runs before the first
write, so a refused request writes nothing. Names come from the live directory
(`shooter_profiles`) through merges (§5.3.8). Contacts are read only to decide `has_email`, to
skip the email field and to check a cancel; no function here hands an email to a viewer route.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import case, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import TooManyRequestsError
from sunday_clays.auth.ratelimit import (
    club_event_attempts,
    club_event_registration_failures,
    record_club_event_attempt,
)
from sunday_clays.config import get_settings
from sunday_clays.domain import club_events as rules
from sunday_clays.domain.errors import ConflictError, DomainError, NotFoundError
from sunday_clays.domain.identity import alias_rule_targets, merge_map
from sunday_clays.models import (
    ClubEvent,
    ClubEventRegistration,
    Shooter,
    ShooterAlias,
    ShooterContact,
    ShooterProfile,
)

R = ClubEventRegistration
EmailUsed = Literal["on_file", "given"]
CancelVia = Literal["device", "email"]
EMAIL_REQUIRED = "Enter your email so organizers can reach you."


def utcnow() -> datetime:
    """The store's clock: routes read "now" here, and tests freeze it with monkeypatch."""
    return datetime.now(UTC)


# --- events and the queue ------------------------------------------------------------------------


@dataclass(frozen=True)
class EventRow:
    id: int
    title: str
    starts_at: datetime
    signup_deadline: datetime
    notes: str
    capacity: int | None
    allow_guests: bool
    max_guests: int
    cancelled_at: datetime | None
    roster_purged_at: datetime | None
    final_signups: int | None
    final_spots: int | None

    def state(self, now: datetime) -> rules.EventState:
        return rules.event_state(now, self.starts_at, self.signup_deadline, self.cancelled_at)


_EVENT_COLUMNS = (
    ClubEvent.id,
    ClubEvent.title,
    ClubEvent.starts_at,
    ClubEvent.signup_deadline,
    ClubEvent.notes,
    ClubEvent.capacity,
    ClubEvent.allow_guests,
    ClubEvent.max_guests,
    ClubEvent.cancelled_at,
    ClubEvent.roster_purged_at,
    ClubEvent.final_signups,
    ClubEvent.final_spots,
)


def get_event(session: Session, event_id: int, *, lock: bool = False) -> EventRow:
    stmt = select(*_EVENT_COLUMNS).where(ClubEvent.id == event_id)
    if lock:
        stmt = stmt.with_for_update()
    row = session.execute(stmt).one_or_none()
    if row is None:
        raise NotFoundError("club_event_not_found", "That club event does not exist.")
    return EventRow(**row._mapping)


def lock_event(session: Session, event_id: int) -> EventRow:
    """D13: `SELECT … FROM club_events WHERE id = :id FOR UPDATE`, before anything else."""
    return get_event(session, event_id, lock=True)


def all_events(session: Session) -> list[EventRow]:
    found = session.execute(select(*_EVENT_COLUMNS).order_by(ClubEvent.starts_at, ClubEvent.id))
    return [EventRow(**row._mapping) for row in found]


def load_queue(session: Session, event_id: int) -> list[rules.QueueRow]:
    found = session.execute(
        select(R.id, R.status, R.guests, R.queue_at)
        .where(R.event_id == event_id, R.status.in_(rules.ACTIVE))
        .order_by(R.id)
    )
    return [
        rules.QueueRow(id=rid, status=status, guests=guests, queue_at=at)
        for rid, status, guests, at in found
    ]


def promote(session: Session, event: EventRow, now: datetime) -> int:
    """§5.3.2: promote from the front of the waitlist while parties fit; never once the event
    has started or while it is cancelled. Returns how many were promoted."""
    if event.cancelled_at is not None or now >= event.starts_at:
        return 0
    ids = rules.promotions(load_queue(session, event.id), event.capacity)
    if ids:
        session.execute(update(R).where(R.id.in_(ids)).values(status="going", promoted_at=now))
    return len(ids)


def inactive_values(status: str, via: str, now: datetime) -> dict[str, object]:
    """Leaving the queue scrubs the email and the token at once (D16, the inactive CHECK)."""
    return {
        "status": status,
        "cancelled_at": now,
        "cancelled_via": via,
        "registrant_email": None,
        "token_hash": None,
    }


# --- the directory (§4, §5.3.5, §5.3.8) ----------------------------------------------------------


def live_shooters(session: Session) -> dict[int, str]:
    """Shooters that can be picked: a profile row whose status is not deceased."""
    found = session.execute(
        select(ShooterProfile.shooter_id, ShooterProfile.display_name).where(
            ShooterProfile.status != "deceased"
        )
    )
    return {int(sid): str(name) for sid, name in found}


def resolve(merges: dict[int, int], shooter_id: int) -> int:
    return merges.get(shooter_id, shooter_id)


def listed_keys(session: Session) -> frozenset[str]:
    """Sign-up keys a typed name may not use: each live shooter's display name, and every alias
    and alias_name rule key whose shooter resolves to a live shooter."""
    live = live_shooters(session)
    merges = merge_map(session)
    keys = {rules.signup_key(name) for name in live.values()}
    pairs: list[tuple[Any, Any]] = [
        (row[0], row[1])
        for row in session.execute(select(ShooterAlias.name_key, ShooterAlias.shooter_id))
    ]
    pairs += list(alias_rule_targets(session).items())
    for key, shooter_id in pairs:
        if "@" not in str(key) and resolve(merges, int(shooter_id)) in live:
            keys.add(rules.signup_key(str(key)))
    return frozenset(keys)


def display_names(session: Session, shooter_ids: Collection[int]) -> dict[int, str]:
    """The profile display name (renames applied) of each id, else `shooters.display_name`."""
    ids = sorted(set(shooter_ids))
    if not ids:
        return {}
    names = {
        int(sid): str(name)
        for sid, name in session.execute(
            select(Shooter.id, Shooter.display_name).where(Shooter.id.in_(ids))
        )
    }
    names.update(
        {
            int(sid): str(name)
            for sid, name in session.execute(
                select(ShooterProfile.shooter_id, ShooterProfile.display_name).where(
                    ShooterProfile.shooter_id.in_(ids)
                )
            )
        }
    )
    return names


@dataclass(frozen=True)
class Contact:
    shooter_id: int
    email: str


def contact_for(session: Session, shooter_id: int, merges: dict[int, int]) -> Contact | None:
    """The canonical shooter's contact, else the most recently updated one among the shooters
    merged into it."""
    canonical = resolve(merges, shooter_id)
    family = [canonical, *(source for source, target in merges.items() if target == canonical)]
    found = session.execute(
        select(ShooterContact.shooter_id, ShooterContact.email)
        .where(ShooterContact.shooter_id.in_(family))
        .order_by(
            (ShooterContact.shooter_id == canonical).desc(),
            ShooterContact.updated_at.desc(),
            ShooterContact.shooter_id,
        )
        .limit(1)
    ).one_or_none()
    return None if found is None else Contact(int(found[0]), str(found[1]))


def shooter_is_active(
    session: Session, event_id: int, shooter_id: int, merges: dict[int, int]
) -> bool:
    """Whether the (resolved) shooter already holds an active registration on the event."""
    found = session.scalars(
        select(R.shooter_id).where(
            R.event_id == event_id, R.status.in_(rules.ACTIVE), R.shooter_id.is_not(None)
        )
    )
    return any(sid is not None and resolve(merges, sid) == shooter_id for sid in found)


def name_key_is_active(session: Session, event_id: int, key: str) -> bool:
    found = session.scalar(
        select(R.id)
        .where(
            R.event_id == event_id,
            R.status.in_(rules.ACTIVE),
            R.shooter_id.is_(None),
            R.name_key == key,
        )
        .limit(1)
    )
    return found is not None


# --- reads (§5.4) --------------------------------------------------------------------------------


@dataclass(frozen=True)
class EventSummary:
    event: EventRow
    state: rules.EventState
    local_date: date
    local_time: str
    deadline_local_date: date
    deadline_local_time: str
    spots_taken: int
    waitlist_count: int
    signups: int
    purged: bool
    upcoming: bool


def _counts(session: Session, event_ids: Sequence[int]) -> dict[int, tuple[int, int, int]]:
    """(going spots, going registrations, waitlist registrations) per event."""
    if not event_ids:
        return {}
    spots = func.coalesce(func.sum(case((R.status == "going", R.guests + 1), else_=0)), 0)
    going = func.count().filter(R.status == "going")
    waiting = func.count().filter(R.status == "waitlist")
    found = session.execute(
        select(R.event_id, spots, going, waiting)
        .where(R.event_id.in_(event_ids), R.status.in_(rules.ACTIVE))
        .group_by(R.event_id)
    )
    return {int(e): (int(s), int(g), int(w)) for e, s, g, w in found}


def summarize(
    session: Session, events: Sequence[EventRow], now: datetime, tz: str
) -> list[EventSummary]:
    counts = _counts(session, [event.id for event in events])
    out: list[EventSummary] = []
    for event in events:
        spots, going, waiting = counts.get(event.id, (0, 0, 0))
        purged = event.roster_purged_at is not None
        if purged:
            spots, going, waiting = event.final_spots or 0, event.final_signups or 0, 0
        day, clock = rules.local_parts(event.starts_at, tz)
        deadline_day, deadline_clock = rules.local_parts(event.signup_deadline, tz)
        out.append(
            EventSummary(
                event,
                event.state(now),
                day,
                clock,
                deadline_day,
                deadline_clock,
                spots,
                waiting,
                going,
                purged,
                rules.is_upcoming(event.starts_at, now, tz),
            )
        )
    return out


def list_for_viewers(
    session: Session, now: datetime, tz: str
) -> tuple[list[EventSummary], list[EventSummary]]:
    """Upcoming by start ascending (cancelled ones included), past by start descending."""
    summaries = summarize(session, all_events(session), now, tz)
    upcoming = [s for s in summaries if rules.is_upcoming(s.event.starts_at, now, tz)]
    past = [s for s in reversed(summaries) if not rules.is_upcoming(s.event.starts_at, now, tz)]
    return upcoming, past


@dataclass(frozen=True)
class RosterRow:
    registration_id: int
    name: str
    shooter_id: int | None
    guests: int
    status: str
    waitlist_position: int | None


def roster(session: Session, event: EventRow) -> list[RosterRow]:
    """Active registrations: going first, then the waitlist, each in queue order. Empty once
    purged. A picked shooter shows by the resolved shooter's display name and id."""
    if event.roster_purged_at is not None:
        return []
    rows = session.execute(
        select(R.id, R.shooter_id, R.registrant_name, R.guests, R.status)
        .where(R.event_id == event.id, R.status.in_(rules.ACTIVE))
        .order_by(R.id)
    ).all()
    merges = merge_map(session)
    resolved = {int(r[0]): resolve(merges, int(r[1])) for r in rows if r[1] is not None}
    names = display_names(session, resolved.values())
    positions = rules.waitlist_positions(
        [rules.QueueRow(id=int(r[0]), status=str(r[4]), guests=int(r[3])) for r in rows]
    )
    out = [
        RosterRow(
            registration_id=int(rid),
            name=names[resolved[rid]] if rid in resolved else str(typed),
            shooter_id=resolved.get(rid),
            guests=int(guests),
            status=str(status),
            waitlist_position=positions.get(rid),
        )
        for rid, _shooter, typed, guests, status in rows
    ]
    return sorted(out, key=lambda row: (row.status != "going", row.registration_id))


@dataclass(frozen=True)
class SignupCheck:
    has_email: bool
    already_signed_up: bool


def signup_check(session: Session, event_id: int, shooter_id: int) -> SignupCheck:
    get_event(session, event_id)
    merges = merge_map(session)
    sid = resolve(merges, shooter_id)
    if sid not in live_shooters(session):
        raise NotFoundError("shooter_not_found", "That shooter is not on the list.")
    return SignupCheck(
        has_email=contact_for(session, sid, merges) is not None,
        already_signed_up=shooter_is_active(session, event_id, sid, merges),
    )


# --- writes (§5.4) -------------------------------------------------------------------------------


@dataclass(frozen=True)
class SignupResult:
    registration_id: int
    token: str
    status: rules.Admission
    waitlist_position: int | None
    email_used: EmailUsed


def _required_email(email: str | None) -> str:
    if email is None or not email.strip():
        raise DomainError("email_required", EMAIL_REQUIRED)
    return rules.normalise_email(email)


def _use_contact(session: Session, owner: int, given: str | None, now: datetime) -> EmailUsed:
    """Save `given` for a shooter with no email on file; the first email wins (§5.3.9), so a
    racing sign-up keeps its registration but its email is ignored. Stamps `last_used_at`."""
    if given is not None:
        inserted = session.execute(
            pg_insert(ShooterContact)
            .values(
                shooter_id=owner,
                email=given,
                source="signup",
                updated_at=now,
                last_used_at=now,
            )
            .on_conflict_do_nothing(index_elements=[ShooterContact.shooter_id])
            .returning(ShooterContact.shooter_id)
        ).first()
        if inserted is not None:
            return "given"
    session.execute(
        update(ShooterContact).where(ShooterContact.shooter_id == owner).values(last_used_at=now)
    )
    return "on_file"


def sign_up(
    session: Session,
    event_id: int,
    *,
    shooter_id: int | None,
    name: str | None,
    email: str | None,
    guests: int,
    now: datetime,
) -> SignupResult:
    """§5.4 from the event lock on. The route has already counted the attempt, checked "exactly
    one of shooter_id and name" and the rate limit."""
    event = lock_event(session, event_id)
    if event.cancelled_at is not None:
        raise ConflictError("event_cancelled", "This event was cancelled by the organizers.")
    if now >= event.signup_deadline:
        raise ConflictError("signups_closed", "Sign-ups for this event have closed.")
    queue = load_queue(session, event.id)
    if len(queue) >= rules.MAX_ACTIVE_PER_EVENT:
        raise ConflictError("signups_full", "This list has reached its limit. Ask an organizer.")
    rules.check_guests(guests, event.allow_guests, event.max_guests)
    merges = merge_map(session)
    values: dict[str, Any]
    owner: int | None = None
    given: str | None = None
    if shooter_id is not None:
        live = live_shooters(session)
        sid = resolve(merges, shooter_id)
        if sid not in live:
            raise NotFoundError("shooter_not_found", "That shooter is not on the list.")
        if shooter_is_active(session, event.id, sid, merges):
            raise ConflictError("already_signed_up", f"{live[sid]} is already on the list.")
        contact = contact_for(session, sid, merges)
        if contact is None:
            given = _required_email(email)
        owner = sid if contact is None else contact.shooter_id
        values = {"shooter_id": sid}
    else:
        display, key = rules.typed_name(name or "")
        if key in listed_keys(session):
            raise ConflictError(
                "name_on_list",
                "That name is already on the shooter list. Pick it from the list instead.",
            )
        if name_key_is_active(session, event.id, key):
            raise ConflictError("already_signed_up", f"{display} is already on the list.")
        values = {
            "registrant_name": display,
            "name_key": key,
            "registrant_email": _required_email(email),
        }
    status = rules.admit(queue, event.capacity, 1 + guests)
    token, digest = rules.new_token()
    registration_id = int(
        session.execute(
            insert(R)
            .values(event_id=event.id, guests=guests, status=status, token_hash=digest, **values)
            .returning(R.id)
        ).scalar_one()
    )
    email_used: EmailUsed = "given" if owner is None else _use_contact(session, owner, given, now)
    position = None
    if status == "waitlist":
        mine = rules.QueueRow(id=registration_id, status=status, guests=guests)
        position = rules.waitlist_positions([*queue, mine])[registration_id]
    return SignupResult(registration_id, token, status, position, email_used)


def cancel(
    session: Session,
    event_id: int,
    registration_id: int,
    *,
    proof: str,
    via: CancelVia,
    ip: str,
    now: datetime,
) -> int | None:
    """§5.4 cancel from the event lock on. Returns the number promoted, or None after a recorded
    failure (the route commits it and answers 403 `cancel_not_matched`). `proof` is the device
    token (`via="device"`) or the typed email (`via="email"`)."""
    event = lock_event(session, event_id)
    found = session.execute(
        select(R.shooter_id, R.registrant_email, R.token_hash).where(
            R.id == registration_id, R.event_id == event_id, R.status.in_(rules.ACTIVE)
        )
    ).one_or_none()
    if found is None:
        raise NotFoundError("registration_not_found", "That sign-up is not on the list.")
    if now >= event.starts_at:
        raise ConflictError(
            "event_started", "This event has started. Ask an organizer to change the list."
        )
    limit = get_settings().club_event_cancel_fail_limit
    if club_event_attempts(session, ip, "cancel_fail", rules.CANCEL_FAIL_WINDOW) >= limit:
        raise TooManyRequestsError("rate_limited", rules.TOO_MANY)
    if via == "email" and (
        club_event_registration_failures(session, registration_id, rules.CANCEL_FAIL_WINDOW)
        >= rules.CANCEL_FAIL_PER_REGISTRATION
    ):
        raise TooManyRequestsError("rate_limited", rules.TOO_MANY)
    shooter_id, stored_email, stored_hash = found
    if via == "device":
        matched = rules.token_matches(stored_hash, proof)
    else:
        if stored_email is None and shooter_id is not None:
            contact = contact_for(session, int(shooter_id), merge_map(session))
            stored_email = None if contact is None else contact.email
        matched = rules.email_matches(stored_email, proof)
    if not matched:
        # Every failure counts for this client; only email failures count against the
        # registration (§5.3.7), so a wrong token never locks anyone's email path.
        counted = registration_id if via == "email" else None
        record_club_event_attempt(session, ip, "cancel_fail", counted)
        return None
    session.execute(
        update(R).where(R.id == registration_id).values(**inactive_values("cancelled", via, now))
    )
    return promote(session, event, now)
