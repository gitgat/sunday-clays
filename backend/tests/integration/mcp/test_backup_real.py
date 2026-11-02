"""The real pg_dump against the test database produces a restorable dump."""

import subprocess
import uuid
from pathlib import Path

import pytest

from sunday_clays.mcp.backup import pre_import_dump


@pytest.mark.slow
def test_real_pg_dump_is_restorable(
    database_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
