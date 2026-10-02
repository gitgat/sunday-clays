"""The page_view_rollup job (Plan 16 Task 1): registered, run by the worker in the club's
timezone, and it folds old views into the rollups."""

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.domain.page_views import RollupReport
from sunday_clays.jobs import page_view_rollup, worker
from sunday_clays.jobs.handlers import load_handlers
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import (
    BumpAttempt,
    Job,
    LoginAttempt,
    PageView,
    PageViewAttempt,
    PageViewRollup,
)


def test_the_handler_is_registered() -> None:
    assert "page_view_rollup" in load_handlers()


def test_the_job_runs_the_rollup_for_today_in_the_club_timezone(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    def fake(_: Session, today: object, tz: str) -> RollupReport:
        seen.update(today=today, tz=tz)
        return RollupReport(date(2026, 1, 5), 0)

    monkeypatch.setattr(page_view_rollup, "rollup_page_views", fake)
    monkeypatch.setattr(
        page_view_rollup, "get_settings", lambda: SimpleNamespace(timezone="Pacific/Auckland")
    )
    job_id = enqueue(session, "page_view_rollup")
    assert worker.process_one(session, weather_enabled=False) is True
    assert session.scalar(select(Job.status).where(Job.id == job_id)) == "done"
    assert seen == {
        "today": datetime.now(ZoneInfo("Pacific/Auckland")).date(),
        "tz": "Pacific/Auckland",
    }


def test_the_job_folds_a_view_120_days_old(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        page_view_rollup,
        "get_settings",
        lambda: SimpleNamespace(timezone="America/Los_Angeles"),
    )
    old = datetime.now(UTC) - timedelta(days=120)
    session.execute(
        insert(PageView).values(device_id=uuid.uuid4(), page_kind="home", me_state="none", at=old)
    )
    enqueue(session, "page_view_rollup")
    worker.process_one(session, weather_enabled=False)
    assert session.scalar(select(func.count()).select_from(PageView)) == 0
    assert (
        session.scalar(
            select(func.count()).select_from(PageViewRollup).where(PageViewRollup.period == "week")
        )
        == 1
    )


def test_the_job_prunes_rate_limit_rows_left_by_a_quiet_spell(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        page_view_rollup,
        "get_settings",
        lambda: SimpleNamespace(timezone="America/Los_Angeles"),
    )
    now = datetime.now(UTC)
    session.execute(
        insert(PageViewAttempt),
        [{"ip": "203.0.113.7", "at": now - timedelta(hours=5)}, {"ip": "198.51.100.1", "at": now}],
    )
    enqueue(session, "page_view_rollup")
    worker.process_one(session, weather_enabled=False)
    assert list(session.scalars(select(PageViewAttempt.ip))) == ["198.51.100.1"]


def test_the_job_deletes_bump_and_login_attempts_older_than_a_day(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A quiet winter must not keep the last Sunday's rate-limit rows for months."""
    monkeypatch.setattr(
        page_view_rollup,
        "get_settings",
        lambda: SimpleNamespace(timezone="America/Los_Angeles"),
    )
    now = datetime.now(UTC)
    old, fresh = now - timedelta(hours=25), now - timedelta(hours=1)
    session.execute(insert(BumpAttempt), [{"ip": "old", "at": old}, {"ip": "fresh", "at": fresh}])
    session.execute(
        insert(LoginAttempt),
        [
            {"ip": "old", "at": old, "success": True},
            {"ip": "fresh", "at": fresh, "success": False},
        ],
    )
    enqueue(session, "page_view_rollup")
    worker.process_one(session, weather_enabled=False)
    assert list(session.scalars(select(BumpAttempt.ip))) == ["fresh"]
    assert list(session.scalars(select(LoginAttempt.ip))) == ["fresh"]
