"""MCP bearer token loading (fail closed unless explicitly disabled)."""

from pathlib import Path

import pytest

from sunday_clays.config import ConfigError
from sunday_clays.mcp.auth import load_auth_token


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MCP_AUTH_TOKEN", "MCP_AUTH_TOKEN_FILE", "MCP_AUTH_DISABLED"):
        monkeypatch.delenv(name, raising=False)


def test_missing_token_refuses_start() -> None:
    with pytest.raises(ConfigError, match="MCP_AUTH_TOKEN"):
        load_auth_token()


def test_blank_token_file_refuses_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("  \n", encoding="utf-8")
    monkeypatch.setenv("MCP_AUTH_TOKEN_FILE", str(token_file))
    with pytest.raises(ConfigError):
        load_auth_token()


def test_disabled_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_AUTH_DISABLED", "1")
    assert load_auth_token() is None


def test_token_file_read_and_stripped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("abc\n", encoding="utf-8")
    monkeypatch.setenv("MCP_AUTH_TOKEN_FILE", str(token_file))
    assert load_auth_token() == "abc"
