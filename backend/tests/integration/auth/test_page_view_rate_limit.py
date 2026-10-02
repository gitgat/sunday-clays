"""Page-view rate limit (Plan 16 Task 1): ``page_view_limit`` (default 600) beacons per client IP
per 10 minutes, and the daily prune that clears the IPs a quiet spell leaves behind."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import (
    PAGE_VIEW_WINDOW,
    page_views_limited,
    prune_page_view_attempts,
    record_page_view_attempt,
)
from sunday_clays.config import Settings, get_settings
from sunday_clays.models import Base

ATTEMPTS = Base.metadata.tables["page_view_attempts"]


def _attempts(session: Session, ip: str, n: int, *, age: timedelta = timedelta(0)) -> None:
    at = datetime.now(UTC) - age
    session.execute(insert(ATTEMPTS), [{"ip": ip, "at": at}] * n)


def _ips(session: Session) -> list[str]:
    return [ip for (ip,) in session.execute(select(ATTEMPTS.c.ip))]


def test_the_default_is_600_per_10_minutes() -> None:
    assert Settings.model_fields["page_view_limit"].default == 600
    assert timedelta(minutes=10) == PAGE_VIEW_WINDOW


def test_the_limitth_beacon_is_the_last_allowed(session: Session, auth_env: Settings) -> None:
    limit = auth_env.page_view_limit
    assert limit == 600  # the test env leaves PAGE_VIEW_LIMIT unset
    _attempts(session, "203.0.113.7", limit - 1)
    assert page_views_limited(session, "203.0.113.7") is False
    record_page_view_attempt(session, "203.0.113.7")
    assert page_views_limited(session, "203.0.113.7") is True
    assert page_views_limited(session, "198.51.100.1") is False


def test_the_limit_comes_from_settings(
    session: Session, auth_env: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Kills a hard-coded 600: the e2e stack relies on PAGE_VIEW_LIMIT to raise it.
    monkeypatch.setenv("PAGE_VIEW_LIMIT", "3")
    get_settings.cache_clear()
    _attempts(session, "203.0.113.7", 2)
    assert page_views_limited(session, "203.0.113.7") is False
    record_page_view_attempt(session, "203.0.113.7")
    assert page_views_limited(session, "203.0.113.7") is True


def test_the_window_is_10_minutes(session: Session, auth_env: Settings) -> None:
    limit = auth_env.page_view_limit
    _attempts(session, "203.0.113.7", limit, age=timedelta(minutes=10, seconds=30))
    assert page_views_limited(session, "203.0.113.7") is False
    _attempts(session, "198.51.100.1", limit, age=timedelta(minutes=9, seconds=30))
    assert page_views_limited(session, "198.51.100.1") is True


def test_recording_prunes_rows_outside_the_window(session: Session) -> None:
    _attempts(session, "203.0.113.7", 3, age=timedelta(minutes=11))
    record_page_view_attempt(session, "198.51.100.1")
    assert _ips(session) == ["198.51.100.1"]


def test_the_daily_prune_clears_old_rows_with_no_new_beacon(session: Session) -> None:
    # The last burst before a quiet spell: no beacon arrives to prune it, so the job must.
    _attempts(session, "203.0.113.7", 2, age=timedelta(minutes=11))
    _attempts(session, "198.51.100.1", 1, age=timedelta(minutes=9))
    prune_page_view_attempts(session)
    assert _ips(session) == ["198.51.100.1"]  # a row inside the window is kept
