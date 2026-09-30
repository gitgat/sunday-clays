import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, select

from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionFactory, alembic_config, make_engine
from sunday_clays.jobs import worker
from sunday_clays.models import Job

# Runs the worker's real main() with HEARTBEAT_PATH = argv[1] (main() reads it at call time).
RUN_WORKER_MAIN = (
    "import pathlib, sys\n"
    "from sunday_clays.jobs import worker\n"
    "worker.HEARTBEAT_PATH = pathlib.Path(sys.argv[1])\n"
    "sys.exit(worker.main())\n"
)


@pytest.fixture
def restore_signal_handlers() -> Iterator[None]:
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


@pytest.fixture
def fast_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Points the worker's heartbeat at ``tmp_path`` and polls every 20 ms."""
    heartbeat = tmp_path / "heartbeat"
    monkeypatch.setattr(worker, "HEARTBEAT_PATH", heartbeat)
    monkeypatch.setattr(worker, "POLL_SECONDS", 0.02)
    return heartbeat


def test_wait_for_schema_returns_true_on_a_current_schema(engine: Engine, tmp_path: Path) -> None:
    heartbeat = tmp_path / "hb"

    ok = worker.wait_for_schema(
        engine, threading.Event(), timeout_s=5, poll_s=0.01, heartbeat=heartbeat
    )

    assert ok is True
    assert heartbeat.exists()


def test_wait_for_schema_treats_connection_errors_as_not_current(
    closed_port: int, tmp_path: Path
) -> None:
    unreachable = make_engine(f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x")
    heartbeat = tmp_path / "hb"

    ok = worker.wait_for_schema(
        unreachable, threading.Event(), timeout_s=0.2, poll_s=0.02, heartbeat=heartbeat
    )

    assert ok is False
    assert heartbeat.exists()


def test_wait_for_schema_keeps_waiting_while_a_revision_is_pending(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """This image knows the database's revision and has one more to apply (Plan 13: a database
    whose revision the image does not know at all is *ahead*, and counts as current)."""
    script = ScriptDirectory.from_config(alembic_config())
    shutil.copytree(
        Path(script.dir), tmp_path / "migrations", ignore=shutil.ignore_patterns("__pycache__")
    )
    (tmp_path / "migrations" / "versions" / "9999_pending.py").write_text(
        f'revision = "9999_pending"\ndown_revision = "{script.get_current_head()}"\n'
        "def upgrade() -> None: ...\ndef downgrade() -> None: ...\n"
    )
    (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = %(here)s/migrations\n")
    monkeypatch.chdir(tmp_path)

    ok = worker.wait_for_schema(
        engine, threading.Event(), timeout_s=0.2, poll_s=0.02, heartbeat=tmp_path / "hb"
    )

    assert ok is False


def test_wait_for_schema_returns_false_once_stopped(engine: Engine, tmp_path: Path) -> None:
    stop = threading.Event()
    stop.set()

    ok = worker.wait_for_schema(engine, stop, timeout_s=5, poll_s=0.01, heartbeat=tmp_path / "hb")

    assert ok is False


def test_main_exits_1_when_the_schema_never_becomes_current(
    settings_env: None,
    fast_worker: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_signal_handlers: None,
) -> None:
    monkeypatch.setattr(worker, "SCHEMA_TIMEOUT_SECONDS", 0.2)

    assert worker.main() == 1
    assert fast_worker.exists()


def test_main_exits_0_when_stopped_while_waiting_for_the_schema(
    settings_env: None, fast_worker: Path, restore_signal_handlers: None
) -> None:
    threading.Timer(0.2, os.kill, (os.getpid(), signal.SIGTERM)).start()

    assert worker.main() == 0


def test_main_heartbeats_until_sigint_then_exits_0(
    test_settings: Settings,
    committed_engine: Engine,
    fast_worker: Path,
    restore_signal_handlers: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEATHER_ENABLED", "false")  # the real loop must not call Open-Meteo
    get_settings.cache_clear()
    threading.Timer(0.3, os.kill, (os.getpid(), signal.SIGINT)).start()

    assert worker.main() == 0
    assert time.time() - fast_worker.stat().st_mtime < 5


def test_worker_module_heartbeats_and_stops_cleanly_on_sigterm(
    test_settings: Settings, committed_engine: Engine
) -> None:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "DATABASE_URL": test_settings.database_url.get_secret_value(),
        "SESSION_SECRET": test_settings.session_secret.get_secret_value(),
        "VIEWER_PASSWORD_HASH": test_settings.viewer_password_hash.get_secret_value(),
        "ADMIN_PASSWORD_HASH": test_settings.admin_password_hash.get_secret_value(),
        "WEATHER_ENABLED": "false",
    }
    # The real main() in its own process, but with a heartbeat path private to this run:
    # parallel worktrees share /tmp/worker-heartbeat, and another run's heartbeat must not
    # count as this worker's (SIGTERM would then arrive before its handler is installed).
    with tempfile.TemporaryDirectory() as scratch:
        heartbeat = Path(scratch) / "heartbeat"
        with subprocess.Popen(
            [sys.executable, "-c", RUN_WORKER_MAIN, str(heartbeat)],
            env=env,
            stderr=subprocess.DEVNULL,
        ) as proc:
            try:
                deadline = time.monotonic() + 30
                while proc.poll() is None and time.monotonic() < deadline:
                    if heartbeat.exists():
                        break
                    time.sleep(0.1)
                assert proc.poll() is None, "worker exited before its first heartbeat"
                assert heartbeat.exists(), "no heartbeat within 30 s"
                proc.send_signal(signal.SIGTERM)
                assert proc.wait(timeout=10) == 0
            finally:
                if proc.poll() is None:
                    proc.kill()


def test_main_recovers_orphaned_jobs_before_polling(
    test_settings: Settings,
    committed_engine: Engine,
    fast_worker: Path,
    restore_signal_handlers: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEATHER_ENABLED", "false")  # the real loop must not call Open-Meteo
    get_settings.cache_clear()
    with SessionFactory() as setup:  # a job a killed worker left behind
        orphan = Job(kind="rebuild", status="running", attempts=1)
        setup.add(orphan)
        setup.commit()
        orphan_id = orphan.id
    seen: list[tuple[str, str | None]] = []
    real_run_worker = worker.run_worker

    def first_poll(stop: threading.Event, poll_seconds: float = 2.0) -> None:
        # Not SessionFactory: main() rebound it to its own engine, and a connection left in that
        # pool would raise psycopg's ResourceWarning (an error under filterwarnings) when collected.
        with committed_engine.connect() as conn:
            row = conn.execute(select(Job.status, Job.error).where(Job.id == orphan_id)).one()
        seen.append((row.status, row.error))  # the orphan's state when the poll loop starts
        stop.set()
        real_run_worker(stop, poll_seconds)

    monkeypatch.setattr(worker, "run_worker", first_poll)

    assert worker.main() == 0
    assert seen == [("queued", "worker restarted")]
