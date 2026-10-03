"""Worker entrypoint ``python -m sunday_clays.jobs.worker`` (C6 worker-health contract).

Plan 01 T1 stub + Plan 03 T7: wait for the schema, recover orphaned jobs, then poll the
queue with a heartbeat until SIGTERM/SIGINT.
"""

import logging
import signal
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.db import SessionFactory, make_engine, schema_is_current
from sunday_clays.jobs.handlers import load_handlers
from sunday_clays.jobs.queue import claim_next, complete, fail, fail_permanently, recover_orphans
from sunday_clays.jobs.scheduler import schedule_due
from sunday_clays.logging import configure_logging

HEARTBEAT_PATH = Path("/tmp/worker-heartbeat")  # noqa: S108 - fixed path read by the healthcheck
POLL_SECONDS = 2.0
SCHEMA_TIMEOUT_SECONDS = 180.0
HEARTBEAT_EVERY_S = 10.0  # well inside the healthcheck's 60 s staleness limit
MAX_JOB_HEARTBEAT_S = 30 * 60.0  # a job still running after this is treated as hung
WEATHER_KINDS = frozenset({"weather_sync", "forecast_refresh"})

logger = logging.getLogger(__name__)


def touch_heartbeat(path: Path) -> None:
    path.touch()


@contextmanager
def heartbeat_while_busy(path: Path) -> Iterator[None]:
    """Touch ``path`` every HEARTBEAT_EVERY_S from a daemon thread while the body runs.

    The thread has its own Event, not the worker's ``stop``, so it keeps beating while a job
    finishes during the SIGTERM grace period. It gives up after MAX_JOB_HEARTBEAT_S, so a hung
    job still lets the heartbeat go stale and the healthcheck fail.
    """
    done = threading.Event()
    every_s, deadline = HEARTBEAT_EVERY_S, time.monotonic() + MAX_JOB_HEARTBEAT_S

    def beat() -> None:
        while not done.wait(every_s) and time.monotonic() < deadline:
            touch_heartbeat(path)

    thread = threading.Thread(target=beat, name="job-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()


def wait_for_schema(
    engine: Engine,
    stop: threading.Event,
    *,
    timeout_s: float,
    poll_s: float,
    heartbeat: Path,
) -> bool:
    """True once the DB is at the Alembic head; False on timeout or stop. Heartbeats every poll."""
    deadline = time.monotonic() + timeout_s
    while not stop.is_set():
        touch_heartbeat(heartbeat)
        try:
            if schema_is_current(engine):
                return True
        except SQLAlchemyError:
            logger.info("database not reachable yet")
        if time.monotonic() >= deadline:
            return False
        stop.wait(poll_s)
    return False


def process_one(session: Session, *, weather_enabled: bool) -> bool:
    """Claim and run one job; returns False when nothing was runnable."""
    job = claim_next(session)
    if job is None:
        return False
    job_id, kind, payload = job.id, job.kind, dict(job.payload)
    try:
        handlers = load_handlers()  # a handler module that fails to import fails this job too
        if kind in WEATHER_KINDS and not weather_enabled:
            logger.info("job %s (%s) skipped: weather is disabled", job_id, kind)
        elif kind not in handlers:
            fail_permanently(session, job_id, "no_handler")
            session.commit()
            return True
        else:
            handlers[kind](session, payload)
        complete(session, job_id)
        session.commit()
    except Exception as exc:
        logger.exception("job %s (%s) failed", job_id, kind)
        session.rollback()
        fail(session, job_id, f"{type(exc).__name__}: {exc}")
        session.commit()
    return True


def run_worker(stop: threading.Event, poll_seconds: float = 2.0) -> None:
    """Poll until ``stop`` is set; a job in progress always finishes before the loop exits.

    A failed poll can leave its job ``running`` (e.g. the database went away before ``fail()``
    could record the error). With a single worker running one job at a time, any ``running`` row
    is then an orphan, so the next successful poll recovers it first.
    """
    settings = get_settings()
    recover = False
    while not stop.is_set():
        touch_heartbeat(HEARTBEAT_PATH)
        worked = False
        try:
            with heartbeat_while_busy(HEARTBEAT_PATH), SessionFactory() as session:
                if recover:
                    recovered = recover_orphans(session)
                    session.commit()
                    recover = False
                    logger.info("recovered %d orphaned jobs after a failed poll", len(recovered))
                schedule_due(
                    session,
                    datetime.now(UTC),
                    weather_enabled=settings.weather_enabled,
                    timezone=settings.timezone,
                    page_cache_enabled=settings.page_cache_enabled,
                    app_version=settings.app_version,
                )
                session.commit()
                worked = process_one(session, weather_enabled=settings.weather_enabled)
        except Exception:
            logger.exception("worker poll failed")
            recover = True
        if not worked:
            stop.wait(poll_seconds)


def main() -> int:
    configure_logging()
    stop = threading.Event()

    def request_stop(signum: int, frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    engine = make_engine(get_settings().database_url.get_secret_value())
    try:
        current = wait_for_schema(
            engine,
            stop,
            timeout_s=SCHEMA_TIMEOUT_SECONDS,
            poll_s=POLL_SECONDS,
            heartbeat=HEARTBEAT_PATH,
        )
        if stop.is_set():
            return 0
        if not current:
            logger.error("schema not at the Alembic head after %.0f s", SCHEMA_TIMEOUT_SECONDS)
            return 1
        SessionFactory.configure(bind=engine)
        with SessionFactory() as session:
            recovered = recover_orphans(session)
            session.commit()
        logger.info(
            "schema is current; worker running (recovered %d orphaned jobs)", len(recovered)
        )
        run_worker(stop, poll_seconds=POLL_SECONDS)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
