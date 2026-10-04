import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from sunday_clays.db import SessionFactory
from sunday_clays.jobs import worker
from sunday_clays.jobs.handlers import HANDLERS
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Job


@pytest.fixture
def test_handlers(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Register throwaway job kinds for one test (HANDLERS is restored afterwards)."""
    calls: dict[str, Any] = {"ran": []}

    def ok(session: Session, payload: dict[str, Any]) -> None:
        calls["ran"].append(payload)
        session.add(Job(kind="side_effect", status="done"))

    def boom(session: Session, payload: dict[str, Any]) -> None:
        session.add(Job(kind="side_effect", status="done"))
        session.flush()
        raise RuntimeError("kaput")

    monkeypatch.setitem(HANDLERS, "t_ok", ok)
    monkeypatch.setitem(HANDLERS, "t_boom", boom)
    return calls


@pytest.fixture
def schedule_calls() -> list[dict[str, Any]]:
    """The keyword arguments run_worker passed to each (stubbed) schedule_due call."""
    return []


@pytest.fixture
def worker_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, schedule_calls: list[dict[str, Any]]
) -> Path:
    heartbeat = tmp_path / "heartbeat"
    monkeypatch.setattr(worker, "HEARTBEAT_PATH", heartbeat)
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(
            weather_enabled=False,
            timezone="America/Los_Angeles",
            page_cache_enabled=False,
            app_version="v7",
        ),
    )

    # Plan 16: the real scheduler queues page_view_rollup from 03:00 local every day, which would
    # make these loop tests depend on the time of day. They test the loop; test_job_scheduler.py
    # tests the schedule.
    def record_schedule_due(*_args: Any, **kwargs: Any) -> list[int]:
        schedule_calls.append(kwargs)
        return []

    monkeypatch.setattr(worker, "schedule_due", record_schedule_due)
    return heartbeat


def _job(session: Session, job_id: int) -> Job:
    session.expire_all()
    job = session.get(Job, job_id)
    assert job is not None
    return job


def _beating() -> bool:
    return any(t.name == "job-heartbeat" and t.is_alive() for t in threading.enumerate())


def _wait_until(condition: Callable[[], bool], timeout_s: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    return condition()


def test_process_one_runs_the_handler_and_completes(
    session: Session, test_handlers: dict[str, Any]
) -> None:
    job_id = enqueue(session, "t_ok", {"n": 1})
    assert worker.process_one(session, weather_enabled=True) is True
    assert test_handlers["ran"] == [{"n": 1}]
    assert _job(session, job_id).status == "done"
    assert session.scalars(select(Job.kind).where(Job.kind == "side_effect")).all() == [
        "side_effect"
    ]


def test_handler_error_rolls_back_its_writes_and_requeues(
    session: Session, test_handlers: dict[str, Any]
) -> None:
    job_id = enqueue(session, "t_boom")
    assert worker.process_one(session, weather_enabled=True) is True
    job = _job(session, job_id)
    assert (job.status, job.attempts, job.error) == ("queued", 1, "RuntimeError: kaput")
    assert session.scalars(select(Job).where(Job.kind == "side_effect")).all() == []


def test_unknown_kind_fails_without_retry(session: Session) -> None:
    job_id = enqueue(session, "no_such_kind")
    worker.process_one(session, weather_enabled=True)
    job = _job(session, job_id)
    assert (job.status, job.error, job.attempts) == ("failed", "no_handler", 1)


def test_weather_jobs_complete_as_noops_when_weather_is_disabled(session: Session) -> None:
    ids = [enqueue(session, kind, dedupe_key=kind) for kind in ("weather_sync", "forecast_refresh")]
    while worker.process_one(session, weather_enabled=False):
        pass
    assert [_job(session, i).status for i in ids] == ["done", "done"]


def test_process_one_on_an_empty_queue(session: Session) -> None:
    assert worker.process_one(session, weather_enabled=True) is False


def test_a_handler_module_that_fails_to_import_fails_the_job(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_import() -> dict[str, Any]:
        raise ImportError("broken handler module")

    monkeypatch.setattr(worker, "load_handlers", broken_import)
    job_id = enqueue(session, "t_ok")
    assert worker.process_one(session, weather_enabled=True) is True
    job = _job(session, job_id)  # requeued through fail(), never left 'running'
    assert (job.status, job.attempts, job.error) == (
        "queued",
        1,
        "ImportError: broken handler module",
    )


def test_run_worker_finishes_the_job_in_progress_when_stopped(
    committed_engine: Engine, worker_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = threading.Event()

    def stopping(session: Session, payload: dict[str, Any]) -> None:
        stop.set()  # SIGTERM arrives mid-job
        session.add(Job(kind="side_effect", status="done"))

    monkeypatch.setitem(HANDLERS, "t_stop", stopping)
    with SessionFactory() as setup:
        job_id = enqueue(setup, "t_stop")
        pending = enqueue(setup, "t_stop_never")
        setup.commit()
    worker.run_worker(stop, poll_seconds=0.01)
    with SessionFactory() as check:
        assert _job(check, job_id).status == "done"
        assert _job(check, pending).status == "queued"
        assert check.scalars(select(Job.kind).where(Job.kind == "side_effect")).all() == [
            "side_effect"
        ]
    assert worker_settings.exists()


def test_run_worker_keeps_polling_after_a_failed_poll(
    committed_engine: Engine, worker_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = threading.Event()
    polls: list[int] = []

    def flaky(session: Session, *, weather_enabled: bool) -> bool:
        polls.append(1)
        if len(polls) == 1:
            raise RuntimeError("db hiccup")
        stop.set()
        return False

    monkeypatch.setattr(worker, "process_one", flaky)
    worker.run_worker(stop, poll_seconds=0.01)
    assert len(polls) == 2


def test_run_worker_passes_the_timezone_and_weather_flag_to_the_scheduler(
    committed_engine: Engine,
    worker_settings: Path,
    schedule_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = threading.Event()

    def once(session: Session, *, weather_enabled: bool) -> bool:
        stop.set()
        return False

    monkeypatch.setattr(worker, "process_one", once)
    worker.run_worker(stop, poll_seconds=0.01)
    assert schedule_calls == [
        {
            "weather_enabled": False,
            "timezone": "America/Los_Angeles",
            "page_cache_enabled": False,
            "app_version": "v7",
        }
    ]


def test_run_worker_keeps_the_heartbeat_fresh_during_a_long_job(
    committed_engine: Engine, worker_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker, "HEARTBEAT_EVERY_S", 0.01)
    stop = threading.Event()
    reappeared: list[bool] = []

    def long_job(session: Session, payload: dict[str, Any]) -> None:
        stop.set()  # SIGTERM mid-job: the job heartbeat must keep beating until the job ends
        worker_settings.unlink()
        reappeared.append(_wait_until(worker_settings.exists))

    monkeypatch.setitem(HANDLERS, "t_long", long_job)
    with SessionFactory() as setup:
        job_id = enqueue(setup, "t_long")
        setup.commit()
    worker.run_worker(stop, poll_seconds=0.01)
    assert reappeared == [True]
    assert not _beating()  # stopped and joined once the poll body finished
    with SessionFactory() as check:
        assert _job(check, job_id).status == "done"


def test_the_job_heartbeat_gives_up_at_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker, "HEARTBEAT_EVERY_S", 0.01)
    monkeypatch.setattr(worker, "MAX_JOB_HEARTBEAT_S", 0.05)
    heartbeat = tmp_path / "heartbeat"
    with worker.heartbeat_while_busy(heartbeat):
        # A hung job: the beat thread ends on its own while the body is still running, so the
        # heartbeat goes stale and the healthcheck can fail.
        assert _wait_until(lambda: not _beating())
        heartbeat.unlink(missing_ok=True)
    assert not heartbeat.exists()


def test_a_job_left_running_by_a_failed_poll_is_recovered_on_the_next_poll(
    committed_engine: Engine, worker_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = threading.Event()
    polls: list[int] = []
    real_process_one = worker.process_one

    def boom(session: Session, payload: dict[str, Any]) -> None:
        raise RuntimeError("kaput")

    def db_down(session: Session, job_id: int, error: str) -> None:
        raise RuntimeError("database went away")  # fail() cannot record the failure

    def counting(session: Session, *, weather_enabled: bool) -> bool:
        polls.append(1)
        if len(polls) == 2:
            stop.set()
        return real_process_one(session, weather_enabled=weather_enabled)

    monkeypatch.setitem(HANDLERS, "t_boom", boom)
    monkeypatch.setattr(worker, "fail", db_down)
    monkeypatch.setattr(worker, "process_one", counting)
    with SessionFactory() as setup:
        job_id = enqueue(setup, "t_boom")
        setup.commit()
    worker.run_worker(stop, poll_seconds=0.01)
    assert len(polls) == 2
    with SessionFactory() as check:
        job = _job(check, job_id)
        assert (job.status, job.attempts, job.error) == ("queued", 1, "worker restarted")
