from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import is_limited, record_attempt
from sunday_clays.config import Settings
from sunday_clays.models import Base

ATTEMPTS = Base.metadata.tables["login_attempts"]


def _failures(session: Session, ip: str, n: int, *, age: timedelta = timedelta(0)) -> None:
    at = datetime.now(UTC) - age
    session.execute(insert(ATTEMPTS), [{"ip": ip, "at": at, "success": False}] * n)


def test_limited_from_the_tenth_failure_in_window(session: Session, auth_env: Settings) -> None:
    _failures(session, "203.0.113.7", 9)
    assert is_limited(session, "203.0.113.7") is False
    _failures(session, "203.0.113.7", 1)
    assert is_limited(session, "203.0.113.7") is True


def test_failures_outside_the_window_do_not_count(session: Session, auth_env: Settings) -> None:
    _failures(session, "203.0.113.7", 10, age=timedelta(minutes=16))
    assert is_limited(session, "203.0.113.7") is False
    _failures(session, "203.0.113.7", 10, age=timedelta(minutes=14))
    assert is_limited(session, "203.0.113.7") is True


def test_successes_and_other_ips_do_not_count(session: Session, auth_env: Settings) -> None:
    now = datetime.now(UTC)
    session.execute(insert(ATTEMPTS), [{"ip": "203.0.113.7", "at": now, "success": True}] * 10)
    _failures(session, "198.51.100.1", 10)
    assert is_limited(session, "203.0.113.7") is False


def test_record_attempt_inserts_and_prunes_rows_older_than_a_day(
    session: Session, auth_env: Settings
) -> None:
    _failures(session, "198.51.100.1", 1, age=timedelta(hours=25))
    _failures(session, "198.51.100.1", 1, age=timedelta(hours=23))
    record_attempt(session, "203.0.113.7", True)
    rows = session.execute(select(ATTEMPTS.c.ip, ATTEMPTS.c.success).order_by(ATTEMPTS.c.id)).all()
    assert [tuple(r) for r in rows] == [("198.51.100.1", False), ("203.0.113.7", True)]
