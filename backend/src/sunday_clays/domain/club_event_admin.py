"""Club events (Plan 20 §5.5): organizer actions.

Create, edit, cancel, restore and delete an event; remove a sign-up, change its guests, reset its
cancel limit and link it to a shooter (D15); the roster with emails and the email list; and
shooters' contacts. Every write that can change who holds a spot locks the event first (D13) and
runs promotions in the same transaction, and every check runs before the first write.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.domain import club_event_store as store
from sunday_clays.domain import club_events as rules
from sunday_clays.domain.errors import ConflictError, DomainError, NotFoundError
from sunday_clays.domain.identity import merge_map
from sunday_clays.ingest.names import name_key, similar_name_keys
from sunday_clays.models import (
    ClubEvent,
    ClubEventAttempt,
    ClubEventRegistration,
    ShooterContact,
)

R = ClubEventRegistration
RosterStatus = Literal["going", "waitlist", "active"]
STARTS_IN_PAST = "Pick a start time in the future."
DEADLINE_AFTER_START = "The sign-up deadline must be on or before the start."
STARTED_MOVE = "This event has already started, so its date can't change."
NOT_ON_LIST = "That sign-up is not on the list."


# --- events --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EventFields:
    title: str
    starts_local: str
    deadline_local: str
    notes: str
    capacity: int | None
    allow_guests: bool
    max_guests: int


@dataclass(frozen=True)
class EventPatch:
    """A PATCH: `None` means "not sent", except `capacity`, which `capacity_set` qualifies (an
    explicit null clears the limit)."""

    title: str | None = None
    starts_local: str | None = None
    deadline_local: str | None = None
    notes: str | None = None
    capacity: int | None = None
    capacity_set: bool = False
    allow_guests: bool | None = None
    max_guests: int | None = None


def _title(raw: str) -> str:
    title = raw.strip()
    if not 1 <= len(title) <= rules.TITLE_MAX:
        raise DomainError("bad_title", "Give the event a title of 1 to 80 characters.")
    return title


def _notes(raw: str) -> str:
    if len(raw) > rules.NOTES_MAX:
        raise DomainError("notes_too_long", "Notes can be up to 2,000 characters.")
    return raw


def _capacity(value: int | None) -> int | None:
    if value is not None and not 1 <= value <= rules.CAPACITY_MAX:
        raise DomainError("bad_capacity", "Capacity is 1 to 500, or empty for no limit.")
    return value


def _max_guests(allow_guests: bool, max_guests: int) -> int:
    if not allow_guests:
        return 0
    if not 1 <= max_guests <= rules.MAX_GUESTS:
        raise DomainError("bad_max_guests", "Allow 1 to 10 guests each.")
    return max_guests


def create_event(session: Session, fields: EventFields, *, now: datetime, tz: str) -> int:
    starts = rules.local_to_utc(fields.starts_local, tz)
    if starts <= now:
        raise DomainError("starts_in_past", STARTS_IN_PAST)
    deadline = rules.local_to_utc(fields.deadline_local, tz)
    if deadline > starts:
        raise DomainError("deadline_after_start", DEADLINE_AFTER_START)
    values = {
        "title": _title(fields.title),
        "starts_at": starts,
        "signup_deadline": deadline,
        "notes": _notes(fields.notes),
        "capacity": _capacity(fields.capacity),
        "allow_guests": fields.allow_guests,
        "max_guests": _max_guests(fields.allow_guests, fields.max_guests),
    }
    return int(
        session.execute(insert(ClubEvent).values(**values).returning(ClubEvent.id)).scalar_one()
    )


def update_event(
    session: Session, event_id: int, patch: EventPatch, *, now: datetime, tz: str
) -> list[str]:
    """§5.3.11 and §5.3.3; runs promotions after. Returns the names of the fields that changed."""
    event = store.lock_event(session, event_id)
    values: dict[str, object] = {}
    changed: list[str] = []
    if patch.title is not None and _title(patch.title) != event.title:
        values["title"] = _title(patch.title)
        changed.append("title")
    starts, deadline = event.starts_at, event.signup_deadline
    if patch.starts_local is not None:
        candidate = rules.local_to_utc(patch.starts_local, tz)
        if candidate != event.starts_at:
            if now >= event.starts_at or event.roster_purged_at is not None:
                raise ConflictError("event_started", STARTED_MOVE)
            if candidate <= now:
                raise DomainError("starts_in_past", STARTS_IN_PAST)
            values["starts_at"] = starts = candidate
            changed.append("starts_local")
    if patch.deadline_local is not None:
        candidate = rules.local_to_utc(patch.deadline_local, tz)
        if candidate != event.signup_deadline:
            values["signup_deadline"] = deadline = candidate
            changed.append("deadline_local")
    if deadline > starts:
        raise DomainError("deadline_after_start", DEADLINE_AFTER_START)
    if patch.notes is not None and _notes(patch.notes) != event.notes:
        values["notes"] = patch.notes
        changed.append("notes")
    if patch.capacity_set and patch.capacity != event.capacity:
        capacity = _capacity(patch.capacity)
        taken = rules.going_spots(store.load_queue(session, event.id))
        if capacity is not None and capacity < taken:
            raise ConflictError(
                "capacity_below_going",
                f"{taken} spots are already taken. Remove people first, or set at least {taken}.",
            )
        values["capacity"] = capacity
        changed.append("capacity")
    if patch.allow_guests is not None or patch.max_guests is not None:
        allow = event.allow_guests if patch.allow_guests is None else patch.allow_guests
        most = _max_guests(
            allow, event.max_guests if patch.max_guests is None else patch.max_guests
        )
        if allow != event.allow_guests:
            values["allow_guests"] = allow
            changed.append("allow_guests")
        if most != event.max_guests:
            values["max_guests"] = most
            changed.append("max_guests")
    if values:
        session.execute(
            update(ClubEvent)
            .where(ClubEvent.id == event_id)
            .values(**values, updated_at=func.now())
        )
    store.promote(session, store.get_event(session, event_id), now)
    return changed


def cancel_event(session: Session, event_id: int, now: datetime) -> tuple[int, int]:
    """Sets `cancelled_at`; registrations stay as they are, so a restore puts everyone back.
    Returns (going, waitlist) counts."""
    event = store.lock_event(session, event_id)
    queue = store.load_queue(session, event_id)
    if event.cancelled_at is None:
        session.execute(
            update(ClubEvent)
            .where(ClubEvent.id == event_id)
            .values(cancelled_at=now, updated_at=func.now())
        )
    going = sum(row.status == "going" for row in queue)
    return going, len(queue) - going


def restore_event(session: Session, event_id: int, now: datetime) -> None:
    event = store.lock_event(session, event_id)
    if now >= event.starts_at:
        raise ConflictError("event_started", "This event has started, so it can't be restored.")
    if event.cancelled_at is not None:
        session.execute(
            update(ClubEvent)
            .where(ClubEvent.id == event_id)
            .values(cancelled_at=None, updated_at=func.now())
        )
    store.promote(session, store.get_event(session, event_id), now)


def delete_event(session: Session, event_id: int) -> tuple[str, int]:
    """Hard delete (registrations cascade). Returns (title, registrations deleted)."""
    event = store.lock_event(session, event_id)
    count = session.scalar(select(func.count()).select_from(R).where(R.event_id == event_id))
    session.execute(delete(ClubEvent).where(ClubEvent.id == event_id))
    return event.title, int(count or 0)


# --- registrations -------------------------------------------------------------------------------


def _active(
    session: Session, event_id: int, registration_id: int
) -> tuple[int | None, str | None, int, str]:
    found = session.execute(
        select(R.shooter_id, R.registrant_email, R.guests, R.status).where(
            R.id == registration_id, R.event_id == event_id, R.status.in_(rules.ACTIVE)
        )
    ).one_or_none()
    if found is None:
        raise NotFoundError("registration_not_found", NOT_ON_LIST)
    return found[0], found[1], int(found[2]), str(found[3])


def remove_registration(
    session: Session, event_id: int, registration_id: int, now: datetime
) -> None:
    """Never blocked by any rate limit (§5.5)."""
    event = store.lock_event(session, event_id)
    _active(session, event_id, registration_id)
    session.execute(
        update(R)
        .where(R.id == registration_id)
        .values(**store.inactive_values("removed", "organizer", now))
    )
    store.promote(session, event, now)


def set_guests(
    session: Session, event_id: int, registration_id: int, guests: int, now: datetime
) -> tuple[int, int]:
    """§5.3.4: 0-10 whatever the event's maximum; a going row may not go over capacity.
    Returns (from, to)."""
    event = store.lock_event(session, event_id)
    _, _, before, status = _active(session, event_id, registration_id)
    if not 0 <= guests <= rules.MAX_GUESTS:
        raise DomainError("bad_guests", "Guests are 0 to 10.")
    if status == "going" and event.capacity is not None and guests > before:
        taken = rules.going_spots(store.load_queue(session, event_id))
        over = taken - before + guests - event.capacity
        if over > 0:
            raise ConflictError("over_capacity", f"That would go over capacity by {over}.")
    if guests != before:
        session.execute(update(R).where(R.id == registration_id).values(guests=guests))
    store.promote(session, event, now)
    return before, guests


def reset_cancel_limit(session: Session, event_id: int, registration_id: int) -> int:
    """Deletes the registration's failed email cancels; returns how many."""
    store.lock_event(session, event_id)
    owned = session.scalar(select(R.id).where(R.id == registration_id, R.event_id == event_id))
    if owned is None:
        raise NotFoundError("registration_not_found", NOT_ON_LIST)
    cleared = session.execute(
        delete(ClubEventAttempt)
        .where(
            ClubEventAttempt.action == "cancel_fail",
            ClubEventAttempt.registration_id == registration_id,
        )
        .returning(ClubEventAttempt.id)
    ).all()
    return len(cleared)


@dataclass(frozen=True)
class LinkResult:
    shooter_id: int
    email_moved: bool
    email_discarded: bool


def link_registration(
    session: Session, event_id: int, registration_id: int, shooter_id: int, now: datetime
) -> LinkResult:
    """D15: the registration's email moves to the shooter's contact when the shooter has none,
    else it is deleted (the contact on file wins). The typed name stays for the organizer."""
    store.lock_event(session, event_id)
    linked, email, _, _ = _active(session, event_id, registration_id)
    if linked is not None:
        raise ConflictError("already_linked", "This sign-up is already linked to a shooter.")
    merges = merge_map(session)
    sid = store.resolve(merges, shooter_id)
    live = store.live_shooters(session)
    if sid not in live:
        raise NotFoundError("shooter_not_found", "That shooter is not on the list.")
    if store.shooter_is_active(session, event_id, sid, merges):
        raise ConflictError("already_signed_up", f"{live[sid]} is already on the list.")
    existing = store.contact_for(session, sid, merges)
    session.execute(
        update(R).where(R.id == registration_id).values(shooter_id=sid, registrant_email=None)
    )
    moved = False
    if existing is not None:
        # The sign-up now uses the contact on file, and a use stamps `last_used_at` (§5.2).
        session.execute(
            update(ShooterContact)
            .where(ShooterContact.shooter_id == existing.shooter_id)
            .values(last_used_at=now)
        )
    if email is not None and existing is None:
        inserted = session.execute(
            pg_insert(ShooterContact)
            .values(shooter_id=sid, email=email, source="link", updated_at=now, last_used_at=now)
            .on_conflict_do_nothing(index_elements=[ShooterContact.shooter_id])
            .returning(ShooterContact.shooter_id)
        ).first()
        moved = inserted is not None
    return LinkResult(sid, moved, email is not None and not moved)


# --- the roster with emails ----------------------------------------------------------------------


@dataclass(frozen=True)
class SuggestedShooter:
    id: int
    name: str
    has_email: bool


@dataclass(frozen=True)
class AdminRosterRow:
    id: int
    name: str
    typed_name: str | None
    shooter_id: int | None
    email: str | None
    email_source: Literal["contact", "registration"] | None
    guests: int
    status: str
    waitlist_position: int | None
    signed_up_at: datetime
    promoted_at: datetime | None
    cancelled_at: datetime | None
    cancelled_via: str | None
    suggested_shooter: SuggestedShooter | None
    cancel_fail_count: int


def _by_key(live: dict[int, str]) -> dict[str, int]:
    return {name_key(name): sid for sid, name in sorted(live.items())}


def suggest(typed: str, live: dict[int, str], by_key: dict[str, int] | None = None) -> int | None:
    """D15 with this plan's Decision 9: `similar_name_keys` with empty date sets, tried on the
    typed key and on its last-word-first rotation ("ike hadly" and "hadly ike"). A caller with
    many rows passes `by_key` (built once from `live`)."""
    by_key = _by_key(live) if by_key is None else by_key
    candidates: dict[str, frozenset[date]] = {key: frozenset() for key in by_key}
    words = name_key(typed).split()
    keys = {" ".join(words), " ".join(words[-1:] + words[:-1])}
    matches = sorted({m for key in keys for m in similar_name_keys(key, frozenset(), candidates)})
    return by_key[matches[0]] if matches else None


def admin_roster(session: Session, event_id: int, now: datetime) -> list[AdminRosterRow]:
    """Every registration, all statuses: going, then waitlist, then the rest, each by id."""
    store.get_event(session, event_id)
    rows = session.execute(
        select(
            R.id,
            R.shooter_id,
            R.registrant_name,
            R.registrant_email,
            R.guests,
            R.status,
            R.queue_at,
            R.promoted_at,
            R.cancelled_at,
            R.cancelled_via,
        )
        .where(R.event_id == event_id)
        .order_by(R.id)
    ).all()
    merges = merge_map(session)
    live = store.live_shooters(session)
    resolved = {int(r[0]): store.resolve(merges, int(r[1])) for r in rows if r[1] is not None}
    names = store.display_names(session, resolved.values())
    positions = rules.waitlist_positions(
        [
            rules.QueueRow(id=int(r[0]), status=str(r[5]), guests=int(r[4]))
            for r in rows
            if r[5] in rules.ACTIVE
        ]
    )
    failures = {
        int(rid): int(n)
        for rid, n in session.execute(
            select(ClubEventAttempt.registration_id, func.count())
            .where(
                ClubEventAttempt.action == "cancel_fail",
                ClubEventAttempt.registration_id.in_([int(r[0]) for r in rows]),
                ClubEventAttempt.at > now - rules.CANCEL_FAIL_WINDOW,
            )
            .group_by(ClubEventAttempt.registration_id)
        )
        if rid is not None
    }
    by_key = _by_key(live)
    contacts: dict[int, store.Contact | None] = {}

    def contact(sid: int) -> store.Contact | None:
        if sid not in contacts:
            contacts[sid] = store.contact_for(session, sid, merges)
        return contacts[sid]

    out: list[AdminRosterRow] = []
    for row in rows:
        rid, typed, email = row.id, row.registrant_name, row.registrant_email
        guests, status, queue_at = row.guests, row.status, row.queue_at
        promoted, cancelled, via = row.promoted_at, row.cancelled_at, row.cancelled_via
        sid = resolved.get(int(rid))
        suggestion: SuggestedShooter | None = None
        source: Literal["contact", "registration"] | None
        if sid is not None:
            found = contact(sid)
            name, email_out = names[sid], None if found is None else found.email
            source = None if found is None else "contact"
        else:
            name, email_out = str(typed), email
            source = None if email is None else "registration"
            hit = suggest(str(typed), live, by_key)
            if hit is not None:
                suggestion = SuggestedShooter(hit, live[hit], contact(hit) is not None)
        out.append(
            AdminRosterRow(
                id=int(rid),
                name=name,
                typed_name=typed,
                shooter_id=sid,
                email=email_out,
                email_source=source,
                guests=int(guests),
                status=str(status),
                waitlist_position=positions.get(int(rid)),
                signed_up_at=queue_at,
                promoted_at=promoted,
                cancelled_at=cancelled,
                cancelled_via=via,
                suggested_shooter=suggestion,
                cancel_fail_count=failures.get(int(rid), 0),
            )
        )
    rank = {"going": 0, "waitlist": 1}
    return sorted(out, key=lambda row: (rank.get(row.status, 2), row.id))


def roster_emails(rows: list[AdminRosterRow], status: RosterStatus) -> list[str]:
    """Distinct emails of the chosen rows, in queue order, for "Copy emails"."""
    wanted = rules.ACTIVE if status == "active" else (status,)
    emails: list[str] = []
    for row in rows:
        if row.status in wanted and row.email is not None and row.email not in emails:
            emails.append(row.email)
    return emails


# --- contacts ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ContactRow:
    shooter_id: int
    name: str
    email: str
    source: str
    updated_at: datetime
    last_used_at: datetime | None


def list_contacts(session: Session, shooter_id: int | None = None) -> list[ContactRow]:
    stmt = select(
        ShooterContact.shooter_id,
        ShooterContact.email,
        ShooterContact.source,
        ShooterContact.updated_at,
        ShooterContact.last_used_at,
    )
    if shooter_id is not None:
        stmt = stmt.where(ShooterContact.shooter_id == shooter_id)
    rows = session.execute(stmt).all()
    names = store.display_names(session, [int(r[0]) for r in rows])
    out = [
        ContactRow(
            int(sid), names.get(int(sid), f"Shooter {sid}"), str(email), str(source), updated, used
        )
        for sid, email, source, updated, used in rows
    ]
    return sorted(out, key=lambda row: (row.name.casefold(), row.shooter_id))


def set_contact(session: Session, shooter_id: int, raw_email: str, now: datetime) -> ContactRow:
    """Upsert with source `organizer`: only an organizer changes an email on file (D5). Sets
    `updated_at` (the "last email change") to the store clock; `last_used_at` is untouched."""
    if shooter_id in merge_map(session) or shooter_id not in store.live_shooters(session):
        raise NotFoundError("shooter_not_found", "That shooter is not on the list.")
    email = rules.normalise_email(raw_email)
    session.execute(
        pg_insert(ShooterContact)
        .values(shooter_id=shooter_id, email=email, source="organizer", updated_at=now)
        .on_conflict_do_update(
            index_elements=[ShooterContact.shooter_id],
            set_={"email": email, "source": "organizer", "updated_at": now},
        )
    )
    return list_contacts(session, shooter_id)[0]


def delete_contact(session: Session, shooter_id: int) -> None:
    gone = session.execute(
        delete(ShooterContact)
        .where(ShooterContact.shooter_id == shooter_id)
        .returning(ShooterContact.shooter_id)
    ).first()
    if gone is None:
        raise NotFoundError("contact_not_found", "There is no email on file for that shooter.")
