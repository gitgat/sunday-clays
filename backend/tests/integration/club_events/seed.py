"""Seed helpers for the club-event tests (Plan 20). Invented names only; emails on example.com.

Every helper writes with Core statements into the caller's session and returns ids. Nothing here
commits, so both the rolled-back `session` fixture and `committed_engine` sessions can use them.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from sunday_clays.ingest.names import name_key
from sunday_clays.models import (
    ClubEvent,
    ClubEventRegistration,
    Rule,
    Shooter,
    ShooterAlias,
    ShooterContact,
    ShooterProfile,
)

# Sat 2030-10-19 09:00 in Los Angeles (PDT): far enough ahead that a real clock never passes it.
STARTS = datetime(2030, 10, 19, 16, 0, tzinfo=UTC)
# Fri 2030-10-18 20:00 PDT, the admin form's default deadline for that start.
DEADLINE = datetime(2030, 10, 19, 3, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 2, 18, 0, tzinfo=UTC)


def seed_shooter(
    session: Session,
    display_name: str,
    *,
    status: str = "member",
    profile: bool = True,
    profile_name: str | None = None,
) -> int:
    """A shooter with its own alias; with `profile`, a live directory row (renamed if asked)."""
    sid = int(
        session.execute(
            insert(Shooter).values(display_name=display_name).returning(Shooter.id)
        ).scalar_one()
    )
    session.execute(insert(ShooterAlias).values(name_key=name_key(display_name), shooter_id=sid))
    if profile:
        session.execute(
            insert(ShooterProfile).values(
                shooter_id=sid,
                display_name=profile_name or display_name,
                status=status,
                first_event=date(2026, 1, 4),
                last_event=date(2026, 9, 27),
                n_rounds=1,
                n_events=1,
                left_censored=False,
            )
        )
    return sid


def add_alias(session: Session, key: str, shooter_id: int) -> None:
    session.execute(insert(ShooterAlias).values(name_key=key, shooter_id=shooter_id))


def add_rule(session: Session, rule_type: str, payload: dict[str, Any]) -> int:
    return int(
        session.execute(
            insert(Rule).values(rule_type=rule_type, payload=payload).returning(Rule.id)
        ).scalar_one()
    )


def seed_event(
    session: Session,
    *,
    title: str = "Fall Fun Shoot",
    starts_at: datetime = STARTS,
    deadline: datetime = DEADLINE,
    capacity: int | None = None,
    allow_guests: bool = False,
    max_guests: int = 0,
    notes: str = "",
    cancelled_at: datetime | None = None,
    roster_purged_at: datetime | None = None,
    final_signups: int | None = None,
    final_spots: int | None = None,
) -> int:
    return int(
        session.execute(
            insert(ClubEvent)
            .values(
                title=title,
                starts_at=starts_at,
                signup_deadline=deadline,
                capacity=capacity,
                allow_guests=allow_guests,
                max_guests=max_guests,
                notes=notes,
                cancelled_at=cancelled_at,
                roster_purged_at=roster_purged_at,
                final_signups=final_signups,
                final_spots=final_spots,
            )
            .returning(ClubEvent.id)
        ).scalar_one()
    )


def seed_registration(
    session: Session,
    event_id: int,
    *,
    shooter_id: int | None = None,
    name: str | None = None,
    email: str | None = None,
    guests: int = 0,
    status: str = "going",
    token_hash: str | None = None,
    cancelled_via: str | None = None,
) -> int:
    """A typed name gets the word-sorted sign-up key that domain.club_events.signup_key makes."""
    key = None if name is None else " ".join(sorted(name_key(name).split()))
    return int(
        session.execute(
            insert(ClubEventRegistration)
            .values(
                event_id=event_id,
                shooter_id=shooter_id,
                registrant_name=name,
                name_key=key,
                registrant_email=email,
                guests=guests,
                status=status,
                token_hash=token_hash,
                cancelled_via=cancelled_via,
            )
            .returning(ClubEventRegistration.id)
        ).scalar_one()
    )


def seed_contact(
    session: Session,
    shooter_id: int,
    email: str,
    *,
    source: str = "signup",
    updated_at: datetime | None = None,
    last_used_at: datetime | None = None,
) -> None:
    values: dict[str, Any] = {
        "shooter_id": shooter_id,
        "email": email,
        "source": source,
        "last_used_at": last_used_at,
    }
    if updated_at is not None:
        values["updated_at"] = updated_at
    session.execute(insert(ShooterContact).values(**values))


IP = {"X-Real-IP": "203.0.113.7"}  # the client every API test speaks for, unless it says otherwise


def seed_attempts(
    session: Session,
    ip: str,
    action: str,
    n: int,
    *,
    registration_id: int | None = None,
    at: datetime | None = None,
) -> None:
    """`n` rate-limit rows for the fingerprint `ip` (use auth.deps.fingerprint on an address)."""
    from sunday_clays.models import ClubEventAttempt  # local: keeps the block self-contained

    stamp = at or datetime.now(UTC)
    session.execute(
        insert(ClubEventAttempt),
        [
            {"ip": ip, "action": action, "registration_id": registration_id, "at": stamp}
            for _ in range(n)
        ],
    )
