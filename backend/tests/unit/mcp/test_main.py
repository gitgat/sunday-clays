"""The entrypoint hands the app to uvicorn with the hardened settings."""

from typing import Any

import pytest

from sunday_clays.mcp import __main__ as entry


@pytest.fixture
def uvicorn_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setenv("MCP_AUTH_DISABLED", "1")
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: calls.append(kw))
    return calls


@pytest.mark.parametrize(("env", "port"), [(None, 8080), ("9123", 9123)])
def test_main_serves_on_the_configured_port(
    monkeypatch: pytest.MonkeyPatch,
    uvicorn_calls: list[dict[str, Any]],
    env: str | None,
    port: int,
) -> None:
    if env is None:
        monkeypatch.delenv("MCP_PORT", raising=False)
    else:
        monkeypatch.setenv("MCP_PORT", env)

    entry.main()

    assert uvicorn_calls == [
        {"host": "0.0.0.0", "port": port, "proxy_headers": False, "access_log": False}  # noqa: S104
    ]
