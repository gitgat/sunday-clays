import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

from sunday_clays.db import alembic_config

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_LOCK_KEY = 7263001  # the pg_advisory_xact_lock key in migrations/env.py
WAITING_FOR_LOCK = text(
    "SELECT count(*) FROM pg_locks"
    " WHERE locktype = 'advisory' AND objid::bigint = :key AND NOT granted"
)


def run_alembic(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={"PATH": os.environ.get("PATH", ""), **env},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_alembic_cli_migrates_using_database_url(database_url: str) -> None:
    upgrade = run_alembic("upgrade", "head", env={"DATABASE_URL": database_url})
    current = run_alembic("current", env={"DATABASE_URL": database_url})

    assert upgrade.returncode == 0, upgrade.stderr
    assert current.returncode == 0, current.stderr


def test_alembic_cli_reads_database_url_file(database_url: str, tmp_path: Path) -> None:
    url_file = tmp_path / "database_url"
    url_file.write_text(database_url + "\n", encoding="utf-8")

    result = run_alembic("current", env={"DATABASE_URL_FILE": str(url_file)})

    assert result.returncode == 0, result.stderr


def test_alembic_cli_without_database_url_fails_with_a_clear_message() -> None:
    result = run_alembic("current", env={})

    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr


def test_alembic_cli_retries_an_unreachable_database_before_failing(closed_port: int) -> None:
    url = f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x"
    started = time.monotonic()

    result = run_alembic(
        "-x", "connect_retry_seconds=3", "upgrade", "head", env={"DATABASE_URL": url}
    )

    assert result.returncode != 0
    assert time.monotonic() - started >= 2.0


def lock_waiters(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(WAITING_FOR_LOCK, {"key": MIGRATION_LOCK_KEY}).scalar_one())


def test_migrations_wait_for_the_advisory_lock(database_url: str, engine: Engine) -> None:
    """Two `api` replicas starting at once: the second `alembic upgrade` blocks on the lock."""
    with engine.connect() as holder:
        holder.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        proc = subprocess.Popen(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env={"PATH": os.environ.get("PATH", ""), "DATABASE_URL": database_url},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            waiting = 0
            deadline = time.monotonic() + 30
            while proc.poll() is None and time.monotonic() < deadline:
                waiting = lock_waiters(engine)
                if waiting == 1:
                    break
                time.sleep(0.1)
            assert proc.poll() is None, "alembic finished without waiting for the migration lock"
            assert waiting == 1

            holder.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
            _, stderr = proc.communicate(timeout=60)
            assert proc.returncode == 0, stderr
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            holder.invalidate()  # closes the DB session, so the lock never outlives the test


def test_an_image_older_than_the_schema_starts_without_migrating(
    engine: Engine, database_url: str, tmp_path: Path
) -> None:
    """Plan 13 rollback: `alembic upgrade head` from the previous release's image must succeed
    (and change nothing) on a database already at the newer revision."""
    script = ScriptDirectory.from_config(alembic_config())
    head = script.get_revision(script.get_current_head())
    shutil.copytree(
        BACKEND_DIR / "migrations",
        tmp_path / "migrations",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (tmp_path / "migrations" / "versions" / Path(head.path).name).unlink()
    shutil.copy(BACKEND_DIR / "alembic.ini", tmp_path / "alembic.ini")

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(tmp_path / "alembic.ini"), "upgrade", "head"],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", ""), "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "newer than this image's migrations" in result.stderr
    assert f"database at {head.revision}" in result.stderr
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            head.revision
        )
