"""promote() at the store level (Plan 20 §5.3.2): nobody is promoted once the event started."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.domain import club_event_store as store
from sunday_clays.models import ClubEventRegistration

from .seed import STARTS, seed_event, seed_registration


def _waiting(session: Session) -> tuple[int, int]:
    event_id = seed_event(session, capacity=1)
    return event_id, seed_registration(
        session, event_id, name="Pat Kim", email="pat.kim@example.com", status="waitlist"
    )


def test_promote_takes_the_front_of_the_waitlist_before_the_start(session: Session) -> None:
    event_id, rid = _waiting(session)
    assert (
        store.promote(session, store.get_event(session, event_id), STARTS - timedelta(hours=1)) == 1
    )
    assert (
        session.scalar(select(ClubEventRegistration.status).where(ClubEventRegistration.id == rid))
        == "going"
    )


def test_promote_does_nothing_once_the_event_has_started(session: Session) -> None:
    event_id, rid = _waiting(session)
    assert store.promote(session, store.get_event(session, event_id), STARTS) == 0
    assert (
        session.scalar(select(ClubEventRegistration.status).where(ClubEventRegistration.id == rid))
        == "waitlist"
    )
