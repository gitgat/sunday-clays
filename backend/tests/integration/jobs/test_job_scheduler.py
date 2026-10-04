from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from sunday_clays.jobs.scheduler import ROLLUP_LOCAL_HOUR, schedule_due
from sunday_clays.models import Job

PT = ZoneInfo("America/Los_Angeles")
AFTERNOON = datetime(2020, 1, 5, 15, 0, tzinfo=PT)  # a past date: real created_at values are later
WEATHER = frozenset({"weather_sync", "forecast_refresh"})


def _kinds(session: Session, only: frozenset[str] | None = None) -> list[str]:
    kinds = sorted(session.scalars(select(Job.kind)))
    return kinds if only is None else [kind for kind in kinds if kind in only]


def _old_job(session: Session, kind: str, created_at: datetime) -> None:
    session.add(Job(kind=kind, status="done", created_at=created_at, dedupe_key=kind))
    session.flush()


def test_only_the_daily_jobs_are_scheduled_when_weather_is_disabled(session: Session) -> None:
    assert len(schedule_due(session, AFTERNOON, weather_enabled=False)) == 2
    assert _kinds(session) == ["club_event_retention", "page_view_rollup"]


def test_after_14_local_every_job_is_due(session: Session) -> None:
    ids = schedule_due(session, AFTERNOON.astimezone(UTC), weather_enabled=True)
    assert len(ids) == 4
    assert _kinds(session) == [
        "club_event_retention",
        "forecast_refresh",
        "page_view_rollup",
        "weather_sync",
    ]


def test_before_14_local_the_weather_sync_is_not_due(session: Session) -> None:
    schedule_due(session, AFTERNOON.replace(hour=13, minute=59), weather_enabled=True)
    assert _kinds(session, WEATHER) == ["forecast_refresh"]


def test_called_twice_in_the_same_slot_creates_one_job_each(session: Session) -> None:
    first = schedule_due(session, AFTERNOON, weather_enabled=True)
    session.execute(update(Job).values(status="done"))  # finished, so dedupe cannot hide a repeat
    assert schedule_due(session, AFTERNOON + timedelta(hours=1), weather_enabled=True) == []
    assert len(first) == 4
    assert _kinds(session) == [
        "club_event_retention",
        "forecast_refresh",
        "page_view_rollup",
        "weather_sync",
    ]


def test_weather_sync_is_due_again_the_next_day_and_forecast_after_6h(session: Session) -> None:
    _old_job(session, "weather_sync", AFTERNOON - timedelta(days=1))
    _old_job(session, "forecast_refresh", AFTERNOON - timedelta(hours=5))
    schedule_due(session, AFTERNOON, weather_enabled=True)
    assert _kinds(session, WEATHER) == ["forecast_refresh", "weather_sync", "weather_sync"]
    session.execute(update(Job).values(status="done"))
    schedule_due(session, AFTERNOON + timedelta(hours=2), weather_enabled=True)
    assert _kinds(session, WEATHER).count("forecast_refresh") == 2


def test_the_rollup_waits_for_3_local(session: Session) -> None:
    assert ROLLUP_LOCAL_HOUR == 3
    early = datetime(2020, 1, 5, 2, 59, tzinfo=PT)
    assert schedule_due(session, early, weather_enabled=False) == []
    assert len(schedule_due(session, early.replace(hour=3, minute=0), weather_enabled=False)) == 2


def test_the_rollup_slot_is_local_time_not_utc(session: Session) -> None:
    # 10:59 UTC is 02:59 in Los Angeles (PST, UTC-8): not yet due there.
    assert (
        schedule_due(session, datetime(2020, 1, 5, 10, 59, tzinfo=UTC), weather_enabled=False) == []
    )
    assert _kinds(session) == []
    schedule_due(session, datetime(2020, 1, 5, 11, 0, tzinfo=UTC), weather_enabled=False)
    assert _kinds(session) == ["club_event_retention", "page_view_rollup"]


def test_the_rollup_runs_once_a_local_day(session: Session) -> None:
    # A job created now gets a real (later) created_at, so the earlier day's job is backdated, as
    # in the weather test: it counts for its own day only.
    morning = datetime(2020, 1, 5, 3, 0, tzinfo=PT)
    _old_job(session, "page_view_rollup", morning)
    _old_job(session, "club_event_retention", morning)
    assert schedule_due(session, morning.replace(hour=23), weather_enabled=False) == []
    next_day = morning + timedelta(days=1)
    assert len(schedule_due(session, next_day, weather_enabled=False)) == 2
    session.execute(update(Job).values(status="done"))  # finished, so dedupe cannot hide a repeat
    assert schedule_due(session, next_day.replace(hour=23), weather_enabled=False) == []
    assert _kinds(session) == [
        "club_event_retention",
        "club_event_retention",
        "page_view_rollup",
        "page_view_rollup",
    ]


def test_the_club_event_retention_is_daily_with_its_dedupe_key(session: Session) -> None:
    schedule_due(session, AFTERNOON, weather_enabled=False)
    job = session.execute(
        select(Job.kind, Job.dedupe_key).where(Job.kind == "club_event_retention")
    ).one()
    assert tuple(job) == ("club_event_retention", "club_event_retention")
