"""backup.sh --once with stub pg_dump/pg_restore: only a verified dump counts as a success.

Bash ignores `set -e` inside a function called from an `if` condition, so every step of
dump_once must propagate its own failure. These tests pin that: a failed or unverifiable dump
exits 1, keeps no sc-*.dump, leaves last_success alone and pings Healthchecks' /fail URL.
"""

import fcntl
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

BACKUP_SH = Path(__file__).resolve().parents[3] / "backup" / "backup.sh"
BASH = shutil.which("bash") or "/bin/bash"

WRITES_DUMP = """#!/usr/bin/env bash
for arg in "$@"; do
  case "$arg" in --file=*) printf 'PGDMP stub' >"${arg#--file=}" ;; esac
done
"""
WRITES_PART_THEN_FAILS = WRITES_DUMP + "exit 1\n"
WRITES_DUMP_SLOWLY = WRITES_DUMP + "sleep 2\n"
FAILS = "#!/usr/bin/env bash\nexit 1\n"
SUCCEEDS = "#!/usr/bin/env bash\nexit 0\n"


@dataclass
class Healthchecks:
    """A local stand-in for Healthchecks.io: the URL file backup.sh reads and every ping path."""

    url_file: Path
    pings: list[str]


@pytest.fixture
def healthchecks(tmp_path: Path) -> Iterator[Healthchecks]:
    pings: list[str] = []

    class Recorder(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            pings.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            """Keeps the test output quiet."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url_file = tmp_path / "backup_hc_url"
    url_file.write_text(f"http://127.0.0.1:{server.server_address[1]}/check-uuid\n")
    try:
        yield Healthchecks(url_file=url_file, pings=pings)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def backup_command(
    tmp_path: Path,
    *,
    pg_dump: str,
    pg_restore: str,
    hc_url_file: Path,
    extra_env: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """backup.sh --once command and env: stubs first on PATH, dumps in tmp_path/backups."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("pg_dump", pg_dump), ("pg_restore", pg_restore)):
        stub = bin_dir / name
        stub.write_text(body)
        stub.chmod(0o755)
    (tmp_path / "backups").mkdir()
    password_file = tmp_path / "db_password"
    password_file.write_text("stub-password")
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "BACKUP_DIR": str(tmp_path / "backups"),
        "POSTGRES_PASSWORD_FILE": str(password_file),
        "BACKUP_HC_URL_FILE": str(hc_url_file),
        **(extra_env or {}),
    }
    return [BASH, str(BACKUP_SH), "--once"], env


def run_backup_once(
    tmp_path: Path,
    *,
    pg_dump: str,
    pg_restore: str,
    hc_url_file: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """backup.sh --once with the stubs first on PATH; dumps go to tmp_path/backups."""
    command, env = backup_command(
        tmp_path,
        pg_dump=pg_dump,
        pg_restore=pg_restore,
        hc_url_file=hc_url_file,
        extra_env=extra_env,
    )
    return subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def kept_dumps(tmp_path: Path) -> list[str]:
    return sorted(p.name for p in (tmp_path / "backups").glob("sc-*.dump"))


@pytest.mark.parametrize(
    "pg_dump", [FAILS, WRITES_PART_THEN_FAILS], ids=["no-output", "partial-output"]
)
def test_failed_pg_dump_is_reported_as_a_failure(
    tmp_path: Path, healthchecks: Healthchecks, pg_dump: str
) -> None:
    result = run_backup_once(
        tmp_path, pg_dump=pg_dump, pg_restore=SUCCEEDS, hc_url_file=healthchecks.url_file
    )

    assert result.returncode == 1
    assert "backup: dump failed" in result.stderr
    assert kept_dumps(tmp_path) == []
    assert not (tmp_path / "backups" / "last_success").exists()
    assert healthchecks.pings == ["/check-uuid/fail"]


def test_dump_that_pg_restore_cannot_list_is_never_kept(
    tmp_path: Path, healthchecks: Healthchecks
) -> None:
    result = run_backup_once(
        tmp_path, pg_dump=WRITES_DUMP, pg_restore=FAILS, hc_url_file=healthchecks.url_file
    )

    assert result.returncode == 1
    assert kept_dumps(tmp_path) == []
    assert not (tmp_path / "backups" / "last_success").exists()
    assert healthchecks.pings == ["/check-uuid/fail"]


def test_verified_dump_is_kept_and_reported(tmp_path: Path, healthchecks: Healthchecks) -> None:
    result = run_backup_once(
        tmp_path, pg_dump=WRITES_DUMP, pg_restore=SUCCEEDS, hc_url_file=healthchecks.url_file
    )

    assert result.returncode == 0, result.stderr
    dumps = kept_dumps(tmp_path)
    assert len(dumps) == 1
    assert re.fullmatch(r"sc-\d{8}T\d{6}Z\.dump", dumps[0])
    assert (tmp_path / "backups" / "last_success").exists()
    assert healthchecks.pings == ["/check-uuid"]


def test_empty_healthcheck_url_file_means_no_ping(
    tmp_path: Path, healthchecks: Healthchecks
) -> None:
    healthchecks.url_file.write_text("")

    result = run_backup_once(
        tmp_path, pg_dump=WRITES_DUMP, pg_restore=SUCCEEDS, hc_url_file=healthchecks.url_file
    )

    assert result.returncode == 0, result.stderr
    assert healthchecks.pings == []


def test_whitespace_only_healthcheck_url_file_means_no_ping(
    tmp_path: Path, healthchecks: Healthchecks
) -> None:
    healthchecks.url_file.write_text("\n  \n")  # Swarm rejects an empty secret; a newline disables

    result = run_backup_once(
        tmp_path, pg_dump=WRITES_DUMP, pg_restore=SUCCEEDS, hc_url_file=healthchecks.url_file
    )

    assert result.returncode == 0, result.stderr
    assert healthchecks.pings == []
    assert "healthcheck ping failed" not in result.stderr


def test_once_records_the_path_of_the_dump_it_kept(
    tmp_path: Path, healthchecks: Healthchecks
) -> None:
    wrote = tmp_path / "wrote"

    result = run_backup_once(
        tmp_path,
        pg_dump=WRITES_DUMP,
        pg_restore=SUCCEEDS,
        hc_url_file=healthchecks.url_file,
        extra_env={"BACKUP_WROTE_FILE": str(wrote)},
    )

    assert result.returncode == 0, result.stderr
    (dump,) = kept_dumps(tmp_path)
    assert wrote.read_text() == f"{tmp_path / 'backups' / dump}\n"


def test_concurrent_runs_never_delete_each_others_dump_in_progress(
    tmp_path: Path, healthchecks: Healthchecks
) -> None:
    command, env = backup_command(
        tmp_path,
        pg_dump=WRITES_DUMP_SLOWLY,
        pg_restore=SUCCEEDS,
        hc_url_file=healthchecks.url_file,
    )
    backups = tmp_path / "backups"
    first = subprocess.Popen(
        command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    deadline = time.monotonic() + 30
    while not list(backups.glob("*.dump.tmp")):  # the first run is inside pg_dump
        assert first.poll() is None, first.communicate()
        assert time.monotonic() < deadline
        time.sleep(0.02)

    second = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=60, check=False
    )
    _, first_err = first.communicate(timeout=60)

    assert first.returncode == 0, first_err
    assert second.returncode == 0, second.stderr
    assert list(backups.glob("*.tmp")) == []
    assert kept_dumps(tmp_path) != []
    assert healthchecks.pings == ["/check-uuid", "/check-uuid"]


def test_run_that_cannot_take_the_lock_in_time_is_a_failure(
    tmp_path: Path, healthchecks: Healthchecks
) -> None:
    command, env = backup_command(
        tmp_path,
        pg_dump=WRITES_DUMP,
        pg_restore=SUCCEEDS,
        hc_url_file=healthchecks.url_file,
        extra_env={"BACKUP_LOCK_TIMEOUT": "1"},
    )
    with (tmp_path / "backups" / "backup.lock").open("a") as other_run:
        fcntl.flock(other_run, fcntl.LOCK_EX)
        result = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=60, check=False
        )

    assert result.returncode == 1
    assert "backup: dump failed" in result.stderr
    assert kept_dumps(tmp_path) == []
    assert not (tmp_path / "backups" / "last_success").exists()
    assert healthchecks.pings == ["/check-uuid/fail"]
