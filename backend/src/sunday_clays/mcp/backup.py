"""Fail-closed database dump taken before any MCP write is committed.

Mirrors backend/backup/backup.sh: custom-format pg_dump without response_cache rows, verified with
``pg_restore --list``, written under the same ``backup.lock`` the nightly backup holds. Anything
short of a verified dump raises BackupError and leaves no file behind. The database password goes
to the child only through PGPASSWORD, and neither it nor the URL is ever put in a message.
"""

import contextlib
import fcntl
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from sqlalchemy.engine import URL, make_url

MIN_DUMP_BYTES = 1024 * 1024
KEEP_DUMPS = 20
LOCK_TIMEOUT_S = 600.0
CHILD_TIMEOUT_S = 600.0
LOCK_FILE = "backup.lock"
_STAMPED = re.compile(r"^pre-import-.*-(\d{8}T\d{6}Z)\.dump$")


class BackupError(RuntimeError):
    """The pre-import dump could not be taken and verified; the caller must not write."""


def _libpq(database_url: str) -> tuple[str, str | None]:
    """(passwordless libpq URI, password) from a SQLAlchemy URL."""
    try:
        url = make_url(database_url)
    except Exception:  # never echo the URL
        raise BackupError("DATABASE_URL is not a valid database URL") from None
    plain = URL.create(  # url.set(password=None) would keep the password
        "postgresql", url.username, None, url.host, url.port, url.database
    )
    pairs = [
        f"{quote(key, safe='')}={quote(str(value), safe='')}"
        for key, raw in sorted(url.query.items())
        if key.lower() != "password"  # a ?password= would reach argv
        for value in ([raw] if isinstance(raw, str) else raw)
    ]
    uri = plain.render_as_string(hide_password=False)
    return (uri + "?" + "&".join(pairs) if pairs else uri), url.password


def _acquire(fd: int, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise BackupError(
                    f"another backup still holds the lock after {timeout_s:g} s"
                ) from None
            time.sleep(0.1)


def _run(args: list[str], env: dict[str, str], what: str) -> None:
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell
            args, env=env, capture_output=True, timeout=CHILD_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BackupError(f"{what} could not run ({type(exc).__name__})") from None
    if done.returncode != 0:
        raise BackupError(f"{what} failed (exit {done.returncode})")


def _prune(backup_dir: Path) -> None:
    stamped = sorted(
        (m.group(1), p.name)
        for p in backup_dir.iterdir()
        if (m := _STAMPED.match(p.name)) is not None
    )
    for _, name in stamped[:-KEEP_DUMPS]:
        with contextlib.suppress(OSError):  # the new dump is safe; a stale one is only clutter
            (backup_dir / name).unlink()


def pre_import_dump(
    preview_id: UUID,
    *,
    backup_dir: Path,
    database_url: str,
    lock_timeout_s: float = LOCK_TIMEOUT_S,
) -> Path:
    """Take, verify and keep a dump; return its path. Raises BackupError on any failure."""
    uri, password = _libpq(database_url)
    env = dict(os.environ)
    env.pop("PGPASSWORD", None)
    if password:
        env["PGPASSWORD"] = password
    tmp: Path | None = None
    try:
        with (backup_dir / LOCK_FILE).open("a") as lock_file:
            _acquire(lock_file.fileno(), lock_timeout_s)
            # Named after the wait, so the stamp is when the snapshot was actually taken.
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            final = backup_dir / f"pre-import-{preview_id}-{stamp}.dump"
            tmp = final.with_name(final.name + ".tmp")
            _run(
                [
                    "pg_dump",
                    "--format=custom",
                    "--exclude-table-data=response_cache",
                    f"--file={tmp}",
                    f"--dbname={uri}",
                ],
                env,
                "pg_dump",
            )
            _run(["pg_restore", "--list", str(tmp)], env, "pg_restore --list")
            size = tmp.stat().st_size
            if size < MIN_DUMP_BYTES:
                raise BackupError(f"dump is {size} bytes, below the {MIN_DUMP_BYTES} byte minimum")
            tmp.rename(final)
            _prune(backup_dir)
    except OSError as exc:
        raise BackupError(f"backup directory is not usable ({type(exc).__name__})") from None
    finally:
        if tmp is not None:
            with contextlib.suppress(OSError):  # after a rename it is already gone
                tmp.unlink(missing_ok=True)
    return final
