"""The club-event tables enforce their rules in Postgres too (Plan 20 §5.2): a backstop to the
domain checks, never a user path."""

from typing import Any

import pytest
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sunday_clays.models import ClubEvent, ClubEventRegistration

from .seed import DEADLINE, STARTS, seed_event, seed_registration, seed_shooter

R = ClubEventRegistration


def _rejects(session: Session, constraint: str, stmt: Any) -> None:
    savepoint = session.begin_nested()
    with pytest.raises(IntegrityError, match=constraint):
        session.execute(stmt)
    savepoint.rollback()


def _typed(event_id: int, **values: Any) -> Any:
    row = {
        "event_id": event_id,
        "registrant_name": "Dana Quill",
        "name_key": "dana quill",
        "registrant_email": "dana.quill@example.com",
        "status": "going",
    }
    return insert(R).values(**(row | values))


def test_guests_above_ten_are_refused(session: Session) -> None:
    event_id = seed_event(session)
    _rejects(session, "ck_club_event_registrations_guests_range", _typed(event_id, guests=11))


def test_max_guests_needs_guests_on(session: Session) -> None:
    _rejects(
        session,
        "ck_club_events_guest_rule",
        insert(ClubEvent).values(
            title="Fall Fun Shoot",
            starts_at=STARTS,
            signup_deadline=DEADLINE,
            allow_guests=False,
            max_guests=2,
        ),
    )


def test_a_deadline_after_the_start_is_refused(session: Session) -> None:
    _rejects(
        session,
        "ck_club_events_deadline_before_start",
        insert(ClubEvent).values(title="Banquet", starts_at=DEADLINE, signup_deadline=STARTS),
    )


def test_an_inactive_row_cannot_keep_an_email(session: Session) -> None:
    event_id = seed_event(session)
    _rejects(
        session,
        "ck_club_event_registrations_inactive_scrubbed",
        _typed(event_id, status="cancelled", cancelled_via="device"),
    )


def test_a_picked_shooter_row_cannot_hold_an_email(session: Session) -> None:
    event_id = seed_event(session)
    shooter_id = seed_shooter(session, "Hadley, Ike")
    _rejects(
        session,
        "ck_club_event_registrations_email_owner",
        _typed(event_id, shooter_id=shooter_id),
    )


def test_a_shooter_is_active_once_per_event(session: Session) -> None:
    event_id = seed_event(session)
    shooter_id = seed_shooter(session, "Hadley, Ike")
    seed_registration(session, event_id, shooter_id=shooter_id, status="cancelled")
    seed_registration(session, event_id, shooter_id=shooter_id)
    _rejects(
        session,
        "uq_club_event_registrations_shooter",
        insert(R).values(event_id=event_id, shooter_id=shooter_id, status="waitlist"),
    )


def test_a_typed_name_is_active_once_per_event(session: Session) -> None:
    event_id = seed_event(session)
    seed_registration(session, event_id, name="Dana Quill", status="removed")
    seed_registration(session, event_id, name="Dana Quill", email="dana.quill@example.com")
    _rejects(session, "uq_club_event_registrations_name", _typed(event_id, status="waitlist"))


def test_deleting_an_event_deletes_its_registrations(session: Session) -> None:
    event_id = seed_event(session)
    seed_registration(session, event_id, name="Dana Quill", email="dana.quill@example.com")
    session.execute(delete(ClubEvent).where(ClubEvent.id == event_id))
    assert session.scalar(select(func.count()).select_from(R)) == 0


def test_queue_at_is_the_insert_time_not_the_transaction_start(session: Session) -> None:
    # D9: inserted after the event lock, so clock_timestamp() is the decision time; now() would
    # give both rows of one transaction the same value.
    event_id = seed_event(session)
    first = seed_registration(session, event_id, name="Dana Quill")
    session.execute(text("SELECT pg_sleep(0.01)"))
    second = seed_registration(session, event_id, name="Pat Kim")
    times = dict(session.execute(select(R.id, R.queue_at).where(R.id.in_([first, second]))).all())
    assert times[second] > times[first]
