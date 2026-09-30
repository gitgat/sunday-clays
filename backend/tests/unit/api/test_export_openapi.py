import json
import subprocess
import sys
from pathlib import Path

import pytest

from sunday_clays.api.export_openapi import main
from sunday_clays.config import SECRET_FIELDS


def test_export_openapi_without_env(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"

    result = subprocess.run(
        [sys.executable, "-m", "sunday_clays.api.export_openapi", "--out", str(out)],
        env={},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    schema = json.loads(text)
    assert text == json.dumps(schema, indent=2, sort_keys=True) + "\n"
    assert "/api/health" in schema["paths"]
    assert "HealthOut" in schema["components"]["schemas"]


def test_main_writes_the_schema_in_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SECRET_FIELDS:
        monkeypatch.delenv(name.upper(), raising=False)
    out = tmp_path / "openapi.json"

    assert main(["--out", str(out)]) == 0

    assert json.loads(out.read_text(encoding="utf-8"))["info"]["title"] == "Sunday Clays API"
