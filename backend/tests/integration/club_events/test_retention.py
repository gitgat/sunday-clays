"""The daily club_event_retention job (Plan 20 D16, §5.6): sign-ups go 30 days after the event's
start instant, emails after 730 days unused, rate-limit rows after a day. Logs counts only."""

import logging
from datetime import UTC, datetime, timedelta, tzinfo

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from sunday_clays.jobs import club_event_retention
from sunday_clays.jobs.club_event_retention import (
    due_events,
    handle_club_event_retention,
    purge_club_events,
)
from sunday_clays.jobs.handlers import load_handlers
from sunday_clays.models import ClubEvent, ClubEventAttempt, ClubEventRegistration, ShooterContact

from .seed import seed_contact, seed_event, seed_registration, seed_shooter

R = ClubEventRegistration
RUN = datetime(2026, 11, 20, 11, 0, tzinfo=UTC)  # 03:00 in Los Angeles


def _registrations(session: Session, event_id: int) -> int:
    return int(
        session.scalar(select(func.count()).select_from(R).where(R.event_id == event_id)) or 0
    )


def test_an_event_31_days_old_is_purged_and_29_days_old_is_kept(session: Session) -> None:
    old = seed_event(
        session,
        starts_at=RUN - timedelta(days=31),
        deadline=RUN - timedelta(days=32),
        capacity=10,
        allow_guests=True,
        max_guests=2,
    )
    seed_registration(session, old, name="Amy Ace", email="amy@example.com", guests=2)
    seed_registration(session, old, shooter_id=seed_shooter(session, "Bee, Bob"))
    seed_registration(session, old, name="Cal Cy", email="cal@example.com", status="waitlist")
    seed_registration(session, old, name="Pat Kim", status="cancelled", cancelled_via="device")
    recent = seed_event(
        session, starts_at=RUN - timedelta(days=29), deadline=RUN - timedelta(days=30)
    )
    seed_registration(session, recent, name="Dana Quill", email="dana.quill@example.com")

    assert purge_club_events(session, RUN).events == 1
    row = session.execute(
        select(ClubEvent.final_signups, ClubEvent.final_spots, ClubEvent.roster_purged_at).where(
            ClubEvent.id == old
        )
    ).one()
    assert tuple(row) == (2, 4, RUN)
    assert (_registrations(session, old), _registrations(session, recent)) == (0, 1)
    assert purge_club_events(session, RUN + timedelta(days=1)).events == 0  # already purged


def test_two_due_events_are_both_purged(session: Session) -> None:
    ids = [
        seed_event(session, starts_at=RUN - timedelta(days=days), deadline=RUN - timedelta(days=60))
        for days in (45, 31)
    ]
    for event_id in ids:
        seed_registration(session, event_id, name="Amy Ace", email="amy@example.com")
    assert purge_club_events(session, RUN).events == 2
    assert [_registrations(session, event_id) for event_id in ids] == [0, 0]


def test_an_event_exactly_30_days_old_is_kept(session: Session) -> None:
    """The cutoff is strict: starts_at exactly 30 days before the run is not yet due."""
    event_id = seed_event(
        session, starts_at=RUN - timedelta(days=30), deadline=RUN - timedelta(days=31)
    )
    seed_registration(session, event_id, name="Amy Ace", email="amy@example.com")
    assert purge_club_events(session, RUN).events == 0
    assert _registrations(session, event_id) == 1
    assert purge_club_events(session, RUN + timedelta(seconds=1)).events == 1


def test_purge_counts_from_starts_at(session: Session) -> None:
    starts = datetime(2026, 10, 18, 6, 30, tzinfo=UTC)  # Sat Oct 17, 23:30 in Los Angeles
    event_id = seed_event(session, starts_at=starts, deadline=starts - timedelta(hours=2))
    seed_registration(session, event_id, name="Dana Quill", email="dana.quill@example.com")
    nov_16_run = datetime(2026, 11, 16, 11, 0, tzinfo=UTC)
    nov_17_run = datetime(2026, 11, 17, 11, 0, tzinfo=UTC)
    assert purge_club_events(session, nov_16_run).events == 0  # a local-date count would purge
    assert purge_club_events(session, nov_17_run).events == 1


def test_due_events_are_locked_in_id_order() -> None:
    # Checked on the compiled SQL only, by choice: lock order matters only under a concurrent
    # writer, and a two-connection race test here would add time without catching more (the
    # store's own race tests cover the event row lock).
    sql = str(due_events(RUN).compile(dialect=postgresql.dialect()))
    assert "ORDER BY club_events.id" in sql
    assert sql.rstrip().endswith("FOR UPDATE")


def test_contacts_unused_for_730_days_expire(session: Session) -> None:
    expired = seed_shooter(session, "Ace, Amy")
    kept = seed_shooter(session, "Bee, Bob")
    used = seed_shooter(session, "Cy, Cal")
    used_long_ago = seed_shooter(session, "Kim, Pat")
    seed_contact(session, expired, "amy@example.com", updated_at=RUN - timedelta(days=731))
    seed_contact(session, kept, "bob@example.com", updated_at=RUN - timedelta(days=729))
    seed_contact(
        session,
        used,
        "cal@example.com",
        updated_at=RUN - timedelta(days=900),
        last_used_at=RUN - timedelta(days=10),
    )
    seed_contact(
        session,
        used_long_ago,
        "pat@example.com",
        updated_at=RUN - timedelta(days=800),
        last_used_at=RUN - timedelta(days=731),
    )
    assert purge_club_events(session, RUN).contacts == 2
    assert sorted(session.scalars(select(ShooterContact.shooter_id))) == sorted([kept, used])


def test_attempts_older_than_a_day_are_pruned(session: Session) -> None:
    session.execute(
        insert(ClubEventAttempt),
        [
            {"ip": "fp-old", "action": "signup", "at": RUN - timedelta(days=2)},
            {"ip": "fp-new", "action": "check", "at": RUN - timedelta(hours=1)},
        ],
    )
    assert purge_club_events(session, RUN).attempts == 1
    assert session.scalars(select(ClubEventAttempt.ip)).all() == ["fp-new"]


def test_the_handler_is_registered_and_logs_counts_only(
    session: Session, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> "FrozenDatetime":
            return cls.fromtimestamp(RUN.timestamp(), tz)

    monkeypatch.setattr(club_event_retention, "datetime", FrozenDatetime)
    caplog.set_level(logging.DEBUG)
    assert "club_event_retention" in load_handlers()
    event_id = seed_event(
        session, starts_at=RUN - timedelta(days=40), deadline=RUN - timedelta(days=41)
    )
    seed_registration(session, event_id, name="Dana Quill", email="dana.quill@example.com")
    handle_club_event_retention(session, {})
    assert "club events purged=1 contacts expired=0" in caplog.text
    assert "@" not in caplog.text
    assert "Quill" not in caplog.text
