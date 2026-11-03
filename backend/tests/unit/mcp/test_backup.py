"""Fail-closed pre-import dump, with fake pg_dump / pg_restore scripts on a temporary PATH."""

import fcntl
import os
import stat
import uuid
from pathlib import Path

import pytest

from sunday_clays.mcp import backup
from sunday_clays.mcp.backup import BackupDirNotShared, BackupError, pre_import_dump

URL = "postgresql+psycopg://clays_user:s3cret%40pw@db.internal:5433/sunday_clays"
PREVIEW = uuid.UUID("12345678-1234-5678-1234-567812345678")

FAKE_PG_DUMP = """#!/bin/sh
printf '%s\\n' "$@" > "$FAKE_DIR/dump_argv"
printf '%s' "${PGPASSWORD-}" > "$FAKE_DIR/dump_pgpassword"
[ -n "${FAKE_DUMP_FAIL-}" ] && exit 3
for a in "$@"; do case "$a" in --file=*) out="${a#--file=}";; esac; done
[ -n "${FAKE_DUMP_PARTIAL-}" ] && { head -c 500 /dev/zero > "$out"; exit 1; }
[ -n "${FAKE_DUMP_HANG-}" ] && { printf x > "$out"; exec sleep 30; }
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
    (path / "last_success").write_text("")  # the nightly job's marker: this is the shared bind
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
    [
        {"FAKE_DUMP_FAIL": "1"},
        {"FAKE_DUMP_PARTIAL": "1"},
        {"FAKE_RESTORE_FAIL": "1"},
        {"FAKE_DUMP_BYTES": "100"},
    ],
    ids=["pg_dump fails", "pg_dump partial then fails", "pg_restore fails", "too small"],
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


def test_child_timeout_is_applied(
    fake_pg: Path, backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_DUMP_HANG", "1")
    monkeypatch.setattr(backup, "CHILD_TIMEOUT_S", 0.5)

    with pytest.raises(BackupError):
        pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)

    assert_nothing_left(backup_dir)


def test_lock_is_released_after_a_failure(
    fake_pg: Path, backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_DUMP_FAIL", "1")
    with pytest.raises(BackupError):
        pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL, lock_timeout_s=0.3)
    monkeypatch.delenv("FAKE_DUMP_FAIL")

    path = pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL, lock_timeout_s=0.3)

    assert path.exists()


def test_rename_failure_raises_and_leaves_nothing(
    fake_pg: Path, backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_rename = Path.rename

    def failing_rename(self: Path, target: Path) -> Path:
        if self.name.endswith(".dump.tmp"):
            raise OSError(116, "stale")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", failing_rename)

    with pytest.raises(BackupError):
        pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)

    assert_nothing_left(backup_dir)


def test_unlink_failure_in_cleanup_is_still_a_backup_error(
    fake_pg: Path, backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_DUMP_FAIL", "1")
    real_unlink = Path.unlink

    def failing_unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name.endswith(".dump.tmp"):
            raise OSError(116, "stale")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", failing_unlink)

    with pytest.raises(BackupError, match="pg_dump"):
        pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)


def test_successful_dump_survives_a_failing_cleanup(
    fake_pg: Path, backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_unlink = Path.unlink

    def failing_unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name.endswith(".dump.tmp"):
            raise PermissionError(13, "denied")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", failing_unlink)

    assert pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL).exists()


def test_earlier_dump_of_the_same_second_is_not_deleted_on_failure(
    fake_pg: Path, backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)
    monkeypatch.setenv("FAKE_DUMP_FAIL", "1")
    monkeypatch.setattr(backup, "datetime", _FrozenClock(first))

    with pytest.raises(BackupError):
        pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL)

    assert first.exists()


class _FrozenClock:
    """Stands in for ``datetime`` so the second call gets the first call's stamp."""

    def __init__(self, earlier: Path) -> None:
        self.stamp = earlier.name.rsplit("-", 1)[1].removesuffix(".dump")

    def now(self, tz: object) -> "_FrozenClock":
        return self

    def strftime(self, fmt: str) -> str:
        return self.stamp


def test_a_directory_without_the_nightly_marker_is_refused_and_nothing_is_taken(
    fake_pg: Path, tmp_path: Path
) -> None:
    unshared = tmp_path / "container-layer"
    unshared.mkdir()

    with pytest.raises(BackupDirNotShared, match="shared"):
        pre_import_dump(PREVIEW, backup_dir=unshared, database_url=URL)

    assert list(unshared.iterdir()) == []  # not even a lock file
    assert not (fake_pg / "dump_argv").exists()  # pg_dump never ran


def test_a_directory_with_the_nightly_marker_is_accepted(fake_pg: Path, backup_dir: Path) -> None:
    assert pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=URL).exists()


def test_unusable_directories_raise_backup_error(tmp_path: Path, fake_pg: Path) -> None:
    not_a_dir = tmp_path / "afile"
    not_a_dir.write_text("")
    with pytest.raises(BackupError):
        pre_import_dump(PREVIEW, backup_dir=not_a_dir, database_url=URL)
    with pytest.raises(BackupError):
        pre_import_dump(PREVIEW, backup_dir=tmp_path / "missing", database_url=URL)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_permission_problems_raise_backup_error(
    tmp_path: Path, fake_pg: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    no_search = tmp_path / "nx"
    no_search.mkdir()
    no_search.chmod(0o000)
    read_only = tmp_path / "ro"
    read_only.mkdir()
    (read_only / "last_success").write_text("")
    read_only.chmod(0o555)
    late = tmp_path / "late"
    late.mkdir()
    (late / "last_success").write_text("")
    try:
        with pytest.raises(BackupError):
            pre_import_dump(PREVIEW, backup_dir=no_search, database_url=URL)
        with pytest.raises(BackupError):
            pre_import_dump(PREVIEW, backup_dir=read_only, database_url=URL)
        # The directory turns read-only after the dump: rename and tmp cleanup both fail.
        (tmp_path / "bin" / "pg_restore").write_text(f"#!/bin/sh\nchmod 555 {late}\nexit 0\n")
        with pytest.raises(BackupError):
            pre_import_dump(PREVIEW, backup_dir=late, database_url=URL)
    finally:
        for path in (no_search, read_only, late):
            path.chmod(0o755)


def test_uri_has_no_password_param_and_encodes_the_query(fake_pg: Path, backup_dir: Path) -> None:
    url = "postgresql+psycopg://u:pw@h/db?sslmode=verify-full&password=leak&application_name=a b"

    pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url=url)

    argv = (fake_pg / "dump_argv").read_text()
    assert "leak" not in argv
    assert "--dbname=postgresql://u@h/db?application_name=a%20b&sslmode=verify-full" in argv


@pytest.mark.parametrize(
    ("url", "uri"),
    [
        ("postgresql+psycopg://u:p@h/db", "postgresql://u@h/db"),
        (
            "postgresql+psycopg://u:p@h:6543/db?sslmode=require",
            "postgresql://u@h:6543/db?sslmode=require",
        ),
    ],
    ids=["no port", "sslmode"],
)
def test_libpq_uri_rendering(url: str, uri: str) -> None:
    assert backup._libpq(url) == (uri, "p")


def test_an_unparseable_database_url_is_a_backup_error_that_does_not_echo_it(
    fake_pg: Path, backup_dir: Path
) -> None:
    with pytest.raises(BackupError, match="not a valid database URL") as caught:
        pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url="not-a-url://hunter2")

    assert "hunter2" not in str(caught.value)
    assert not (fake_pg / "dump_argv").exists()


def test_a_url_without_a_password_sends_no_pgpassword(
    fake_pg: Path, backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PGPASSWORD", "from-the-parent-environment")

    pre_import_dump(PREVIEW, backup_dir=backup_dir, database_url="postgresql+psycopg://u@h/db")

    assert (fake_pg / "dump_pgpassword").read_text() == ""
