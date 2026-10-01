"""Bump rate limit (Plan 14 Task 1): 120 actions per client IP per 10 minutes."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import (
    BUMP_LIMIT,
    bumps_limited,
    record_bump_action,
)
from sunday_clays.models import Base

ATTEMPTS = Base.metadata.tables["bump_attempts"]


def _actions(session: Session, ip: str, n: int, *, age: timedelta = timedelta(0)) -> None:
    at = datetime.now(UTC) - age
    session.execute(insert(ATTEMPTS), [{"ip": ip, "at": at}] * n)


def test_120_actions_are_allowed_and_the_next_is_limited(session: Session) -> None:
    ip = "203.0.113.7"
    for _ in range(BUMP_LIMIT):
        assert bumps_limited(session, ip) is False
        record_bump_action(session, ip)
    assert BUMP_LIMIT == 120
    assert bumps_limited(session, ip) is True  # the 121st is refused


def test_window_edges_are_10_minutes(session: Session) -> None:
    _actions(session, "203.0.113.7", BUMP_LIMIT, age=timedelta(minutes=10, seconds=30))
    assert bumps_limited(session, "203.0.113.7") is False
    _actions(session, "198.51.100.1", BUMP_LIMIT, age=timedelta(minutes=9, seconds=30))
    assert bumps_limited(session, "198.51.100.1") is True


def test_limited_from_the_120th_action_in_the_window(session: Session) -> None:
    _actions(session, "203.0.113.7", BUMP_LIMIT - 1)
    assert bumps_limited(session, "203.0.113.7") is False
    _actions(session, "203.0.113.7", 1)
    assert bumps_limited(session, "203.0.113.7") is True


def test_actions_outside_the_window_and_other_ips_do_not_count(session: Session) -> None:
    _actions(session, "203.0.113.7", BUMP_LIMIT, age=timedelta(minutes=11))
    _actions(session, "198.51.100.1", BUMP_LIMIT)
    assert bumps_limited(session, "203.0.113.7") is False
    assert bumps_limited(session, "198.51.100.1") is True


def test_record_inserts_one_row_and_prunes_rows_outside_the_window(session: Session) -> None:
    _actions(session, "198.51.100.1", 1, age=timedelta(minutes=11))
    _actions(session, "198.51.100.1", 1, age=timedelta(minutes=9))
    record_bump_action(session, "203.0.113.7")
    rows = session.execute(select(ATTEMPTS.c.ip).order_by(ATTEMPTS.c.id)).scalars().all()
    assert rows == ["198.51.100.1", "203.0.113.7"]
