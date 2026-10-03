"""When page_warm is enqueued (Plan 19 §3.7.5; §5.1) and the single-worker invariant (§5.2)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine, select, text, update
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import bump_data_version, get_data_version
from sunday_clays.config import Settings, get_settings
from sunday_clays.domain.features import LAST_WARM_KEY, set_switch
from sunday_clays.jobs import worker
from sunday_clays.jobs.queue import enqueue
from sunday_clays.jobs.scheduler import schedule_due
from sunday_clays.models import Job

PT = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 2, 9, 0, tzinfo=PT)  # 09:00: the 03:00 rollup is due too; filter on kind


def _warm_jobs(session: Session) -> int:
    return len(session.scalars(select(Job.id).where(Job.kind == "page_warm")).all())


def _last_warm(
    session: Session, data_version: int, local_date: str, *, skipped: int = 0, failed: int = 0
) -> None:
    session.execute(
        text(
            "INSERT INTO app_state (key, value) VALUES (:k, jsonb_build_object("
            "'data_version', CAST(:dv AS int), 'local_date', CAST(:ld AS text), "
            "'skipped', CAST(:s AS int), 'failed', CAST(:f AS int))) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        ),
        {"k": LAST_WARM_KEY, "dv": data_version, "ld": local_date, "s": skipped, "f": failed},
    )


def _due(session: Session, now: datetime = NOW, enabled: bool = True) -> None:
    schedule_due(session, now, weather_enabled=False, page_cache_enabled=enabled)


def test_never_warmed_is_due(session: Session) -> None:
    _due(session)
    assert _warm_jobs(session) == 1


def test_a_new_data_version_is_due(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02")
    bump_data_version(session)
    _due(session)
    assert _warm_jobs(session) == 1


def test_a_new_local_date_is_due_a_minute_after_midnight(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02")
    _due(session, datetime(2026, 10, 3, 0, 1, tzinfo=PT).astimezone(UTC))
    assert _warm_jobs(session) == 1


def test_nothing_changed_is_not_due(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02")
    _due(session)
    assert _warm_jobs(session) == 0


def test_a_partial_warm_up_is_due_again_after_five_minutes(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02", skipped=3)
    _due(session)
    assert _warm_jobs(session) == 1  # same version and date, but 3 targets never warmed
    # Finished (so dedupe cannot absorb a second one) 4 minutes ago: the 5-minute gap holds it back.
    session.execute(
        update(Job)
        .where(Job.kind == "page_warm")
        .values(status="done", created_at=NOW - timedelta(minutes=4))
    )
    _due(session)
    assert _warm_jobs(session) == 1
    session.execute(
        update(Job).where(Job.kind == "page_warm").values(created_at=NOW - timedelta(minutes=6))
    )
    _due(session)
    assert _warm_jobs(session) == 2  # still partial and over 5 minutes: retried


def test_a_failed_warm_up_is_due_again(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02", failed=1)
    _due(session)
    assert _warm_jobs(session) == 1


def test_not_due_with_the_switch_off_or_the_setting_false(session: Session) -> None:
    _due(session, enabled=False)
    assert _warm_jobs(session) == 0
    set_switch(
        session,
        Settings.model_construct(features_default_on="", timezone="UTC"),
        "page_cache",
        False,
    )
    _due(session)
    assert _warm_jobs(session) == 0


def test_a_recent_attempt_waits_five_minutes_and_dedupe_keeps_one_queued(session: Session) -> None:
    _due(session)
    session.execute(
        update(Job).where(Job.kind == "page_warm").values(created_at=NOW - timedelta(minutes=4))
    )
    _due(session)
    assert _warm_jobs(session) == 1  # under 5 minutes: not again
    session.execute(
        update(Job).where(Job.kind == "page_warm").values(created_at=NOW - timedelta(minutes=6))
    )
    _due(session)
    assert _warm_jobs(session) == 1  # due again, but the queued twin absorbs it (dedupe)


def test_warm_waits_for_the_recompute_commit_then_warms_the_new_version(
    committed_engine: Engine, auth_env: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§5.2 single worker: page_warm is never due while the recompute that bumps data_version is
    queued or running, only once its commit lands; the warm-up then records the bumped version.
    Kills: enqueueing page_warm from the rebuild/recompute handlers, or reading an uncommitted
    data_version."""
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
    get_settings.cache_clear()
    timezone = get_settings().timezone
    with Session(committed_engine) as s:
        now = datetime.now(UTC)
        before = get_data_version(s)
        _last_warm(s, before, now.astimezone(ZoneInfo(timezone)).date().isoformat())
        enqueue(s, "recompute", dedupe_key="recompute")
        s.commit()
        schedule_due(s, now, weather_enabled=False, timezone=timezone, page_cache_enabled=True)
        assert _warm_jobs(s) == 0  # the recompute has not run: nothing to warm yet
        s.commit()
        assert worker.process_one(s, weather_enabled=False)  # runs the recompute, commits the bump
        after = get_data_version(s)
        assert after > before
        assert _warm_jobs(s) == 0  # the handlers enqueue nothing themselves (D35)
        schedule_due(s, now, weather_enabled=False, timezone=timezone, page_cache_enabled=True)
        s.commit()
        assert _warm_jobs(s) == 1
        while worker.process_one(s, weather_enabled=False):
            pass
        last = s.execute(
            text("SELECT value FROM app_state WHERE key = :k"), {"k": LAST_WARM_KEY}
        ).scalar_one()
        assert last["data_version"] == after
