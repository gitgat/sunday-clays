"""Fail-closed pre-import dump, with fake pg_dump / pg_restore scripts on a temporary PATH."""

import fcntl
import os
import stat
import uuid
from pathlib import Path

import pytest

from sunday_clays.mcp import backup
from sunday_clays.mcp.backup import BackupError, pre_import_dump

URL = "postgresql+psycopg://clays_user:s3cret%40pw@db.internal:5433/sunday_clays"
PREVIEW = uuid.UUID("12345678-1234-5678-1234-567812345678")

FAKE_PG_DUMP = """#!/bin/sh
printf '%s\\n' "$@" > "$FAKE_DIR/dump_argv"
printf '%s' "${PGPASSWORD-}" > "$FAKE_DIR/dump_pgpassword"
[ -n "${FAKE_DUMP_FAIL-}" ] && exit 3
for a in "$@"; do case "$a" in --file=*) out="${a#--file=}";; esac; done
head -c "${FAKE_DUMP_BYTES:-2048}" /dev/zero > "$out"
"""
FAKE_PG_RESTORE = """#!/bin/sh
printf '%s\\n' "$@" > "$FAKE_DIR/restore_argv"
[ -n "${FAKE_RESTORE_FAIL-}" ] && exit 4
exit 0
"""


@pytest.fixture
def fake_pg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("pg_dump", FAKE_PG_DUMP), ("pg_restore", FAKE_PG_RESTORE)):
        script = bin_dir / name
        script.write_text(body)
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
    fake_dir = tmp_path / "fake"
    fake_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_DIR", str(fake_dir))
    monkeypatch.setattr(backup, "MIN_DUMP_BYTES", 1024)
    return fake_dir


@pytest.fixture
def backup_dir(tmp_path: Path) -> Path:
    path = tmp_path / "backups"
    path.mkdir()
    return path


def assert_nothing_left(directory: Path) -> None:
    assert list(directory.glob("*.dump.tmp")) == []
    assert list(directory.glob("*.dump")) == []


def test_success_names_and_keeps_the_dump(fake_pg: Path, backup_dir: Path) -> None:
    path = pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)

    assert path.parent == backup_dir
    assert path.exists()
    assert path.stat().st_size >= 1024
    assert path.name.startswith(f"pre-import-{PREVIEW}-")
    assert path.name.endswith("Z.dump")
    assert list(backup_dir.glob("*.dump.tmp")) == []
    dump_argv = (fake_pg / "dump_argv").read_text().split()
    assert "--format=custom" in dump_argv
    assert "--exclude-table-data=response_cache" in dump_argv
    assert any(a.startswith("--file=") and a.endswith(".dump.tmp") for a in dump_argv)
    assert (fake_pg / "restore_argv").read_text().split()[0] == "--list"


def test_password_is_env_only_never_argv(fake_pg: Path, backup_dir: Path) -> None:
    pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)

    argv = (fake_pg / "dump_argv").read_text() + (fake_pg / "restore_argv").read_text()
    assert "s3cret" not in argv
    assert "clays_user" in argv
    assert "db.internal:5433/sunday_clays" in argv
    assert (fake_pg / "dump_pgpassword").read_text() == "s3cret@pw"


@pytest.mark.parametrize(
    "env",
    [{"FAKE_DUMP_FAIL": "1"}, {"FAKE_RESTORE_FAIL": "1"}, {"FAKE_DUMP_BYTES": "100"}],
    ids=["pg_dump fails", "pg_restore fails", "too small"],
)
def test_failures_raise_and_leave_nothing(
    fake_pg: Path, backup_dir: Path, monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(BackupError) as caught:
        pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)

    assert "s3cret" not in str(caught.value)
    assert_nothing_left(backup_dir)


def test_missing_binary_raises_and_leaves_nothing(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    with pytest.raises(BackupError):
        pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)

    assert_nothing_left(backup_dir)


def test_prune_keeps_newest_20_and_leaves_other_files(fake_pg: Path, backup_dir: Path) -> None:
    for day in range(1, 26):
        (backup_dir / f"pre-import-{uuid.uuid4()}-202601{day:02d}T000000Z.dump").write_bytes(b"x")
    (backup_dir / "sc-20200101T000000Z.dump").write_bytes(b"x")
    (backup_dir / "last_success").write_text("")

    path = pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)

    kept = sorted(p.name for p in backup_dir.glob("pre-import-*.dump"))
    assert len(kept) == 20
    assert path.name in kept
    assert not any(f"202601{d:02d}T" in n for d in range(1, 7) for n in kept)
    assert (backup_dir / "sc-20200101T000000Z.dump").exists()
    assert (backup_dir / "last_success").exists()


def test_held_lock_times_out(fake_pg: Path, backup_dir: Path) -> None:
    with (backup_dir / "backup.lock").open("a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        with pytest.raises(BackupError, match="lock"):
            pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL, lock_timeout_s=0.3)

    assert_nothing_left(backup_dir)
    assert not (fake_pg / "dump_argv").exists()
