"""The real pg_dump against the test database produces a restorable dump."""

import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from sunday_clays.mcp.backup import pre_import_dump


def _skip_unless_pg_dump_is_new_enough(engine: Engine) -> None:
    """pg_dump aborts on a server newer than itself, so an older host client cannot run this."""
    if shutil.which("pg_dump") is None:
        pytest.skip("pg_dump is not installed on this host")
    out = subprocess.run(["pg_dump", "--version"], capture_output=True, text=True, check=True)  # noqa: S607
    match = re.search(r"\(PostgreSQL\)\s+(\d+)", out.stdout)
    if match is None:
        pytest.skip(f"could not read the pg_dump version from {out.stdout.strip()!r}")
    with engine.connect() as conn:
        server_major = int(conn.execute(text("SHOW server_version_num")).scalar_one()) // 10000
    if int(match.group(1)) < server_major:
        pytest.skip(
            f"host pg_dump ({out.stdout.strip()}) is older than the test server "
            f"(major {server_major}); pg_dump aborts on a version mismatch"
        )


@pytest.mark.slow
def test_real_pg_dump_is_restorable(
    database_url: str, engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _skip_unless_pg_dump_is_new_enough(engine)
    monkeypatch.setattr("sunday_clays.mcp.backup.MIN_DUMP_BYTES", 100)

    path = pre_import_dump(uuid.uuid4(), backup_dir=tmp_path, database_url=database_url)

    listing = subprocess.run(
        ["pg_restore", "--list", str(path)],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    assert "TOC Entries" in listing.stdout
    assert list(tmp_path.glob("*.dump.tmp")) == []
