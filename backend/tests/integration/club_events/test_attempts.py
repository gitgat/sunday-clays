"""The club-event rate-limit log (Plan 20 §5.2, D17): fingerprints only, pruned on insert."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import (
    club_event_attempts,
    club_event_registration_failures,
    record_club_event_attempt,
)
from sunday_clays.models import ClubEventAttempt

from .seed import seed_attempts

HOUR = timedelta(hours=1)


def test_attempts_count_by_fingerprint_action_and_window(session: Session) -> None:
    seed_attempts(session, "fp-a", "signup", 2)
    seed_attempts(session, "fp-a", "check", 1)
    seed_attempts(session, "fp-b", "signup", 4)
    seed_attempts(session, "fp-a", "signup", 3, at=datetime.now(UTC) - 2 * HOUR)
    assert club_event_attempts(session, "fp-a", "signup", HOUR) == 2
    assert club_event_attempts(session, "fp-a", "check", HOUR) == 1


def test_registration_failures_count_across_fingerprints(session: Session) -> None:
    for ip in ("fp-1", "fp-2", "fp-3"):
        seed_attempts(session, ip, "cancel_fail", 1, registration_id=7)
    seed_attempts(session, "fp-1", "cancel_fail", 1, registration_id=8)
    assert club_event_registration_failures(session, 7, HOUR) == 3


def test_inserts_prune_rows_older_than_a_day(session: Session) -> None:
    seed_attempts(session, "fp-old", "check", 1, at=datetime.now(UTC) - timedelta(days=2))
    record_club_event_attempt(session, "fp-new", "signup")
    assert session.scalars(select(ClubEventAttempt.ip)).all() == ["fp-new"]
