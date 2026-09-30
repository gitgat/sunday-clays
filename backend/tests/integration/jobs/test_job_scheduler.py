from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from sunday_clays.jobs.scheduler import schedule_due
from sunday_clays.models import Job

PT = ZoneInfo("America/Los_Angeles")
AFTERNOON = datetime(2020, 1, 5, 15, 0, tzinfo=PT)  # a past date: real created_at values are later


def _kinds(session: Session) -> list[str]:
    return sorted(session.scalars(select(Job.kind)))


def _old_job(session: Session, kind: str, created_at: datetime) -> None:
    session.add(Job(kind=kind, status="done", created_at=created_at, dedupe_key=kind))
    session.flush()


def test_nothing_is_scheduled_when_weather_is_disabled(session: Session) -> None:
    assert schedule_due(session, AFTERNOON, weather_enabled=False) == []
    assert _kinds(session) == []


def test_after_14_local_both_jobs_are_due(session: Session) -> None:
    ids = schedule_due(session, AFTERNOON.astimezone(UTC), weather_enabled=True)
    assert len(ids) == 2
    assert _kinds(session) == ["forecast_refresh", "weather_sync"]


def test_before_14_local_only_the_forecast_is_due(session: Session) -> None:
    schedule_due(session, AFTERNOON.replace(hour=13, minute=59), weather_enabled=True)
    assert _kinds(session) == ["forecast_refresh"]


def test_called_twice_in_the_same_slot_creates_one_job_each(session: Session) -> None:
    first = schedule_due(session, AFTERNOON, weather_enabled=True)
    session.execute(update(Job).values(status="done"))  # finished, so dedupe cannot hide a repeat
    assert schedule_due(session, AFTERNOON + timedelta(hours=1), weather_enabled=True) == []
    assert len(first) == 2
    assert _kinds(session) == ["forecast_refresh", "weather_sync"]


def test_weather_sync_is_due_again_the_next_day_and_forecast_after_6h(session: Session) -> None:
    _old_job(session, "weather_sync", AFTERNOON - timedelta(days=1))
    _old_job(session, "forecast_refresh", AFTERNOON - timedelta(hours=5))
    schedule_due(session, AFTERNOON, weather_enabled=True)
    assert _kinds(session) == ["forecast_refresh", "weather_sync", "weather_sync"]
    session.execute(update(Job).values(status="done"))
    schedule_due(session, AFTERNOON + timedelta(hours=2), weather_enabled=True)
    assert _kinds(session).count("forecast_refresh") == 2
