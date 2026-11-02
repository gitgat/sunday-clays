"""The entrypoint hands the app to uvicorn with the hardened settings."""

import logging
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


def test_main_quietens_the_root_logger_before_serving(
    monkeypatch: pytest.MonkeyPatch, uvicorn_calls: list[dict[str, Any]]
) -> None:
    """The SDK warns on the root logger with the bad input of a malformed request: names could
    reach the logs. Root is ERROR, our own loggers WARNING, set before uvicorn starts."""
    seen: list[tuple[int, int]] = []
    monkeypatch.setattr(
        entry.uvicorn,
        "run",
        lambda app, **kw: seen.append(
            (logging.getLogger().level, logging.getLogger("sunday_clays").level)
        ),
    )
    root, ours = logging.getLogger(), logging.getLogger("sunday_clays")
    monkeypatch.setattr(root, "level", logging.INFO)
    monkeypatch.setattr(ours, "level", logging.NOTSET)

    entry.main()

    assert seen == [(logging.ERROR, logging.WARNING)]


def test_the_default_clock_is_timezone_aware_utc() -> None:
    import datetime as dt

    from sunday_clays.mcp import server

    now = server._utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset() == dt.timedelta(0)
    assert abs(dt.datetime.now(dt.UTC) - now) < dt.timedelta(seconds=5)
