"""The entrypoint hands the app to uvicorn with the hardened settings."""

import logging
import os
import subprocess
import sys
from collections.abc import Iterator
from typing import Any

import pytest

from sunday_clays.mcp import __main__ as entry


@pytest.fixture
def uvicorn_calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    root, ours = logging.getLogger(), logging.getLogger("sunday_clays")
    saved = (root.level, list(root.handlers), ours.level, list(ours.handlers))
    calls: list[dict[str, Any]] = []
    monkeypatch.setenv("MCP_AUTH_DISABLED", "1")
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: calls.append(kw))
    try:
        yield calls
    finally:  # main() sets log levels and FastMCP may add handlers: do not leak them
        root.setLevel(saved[0])
        root.handlers[:] = saved[1]
        ours.setLevel(saved[2])
        ours.handlers[:] = saved[3]


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


_PROBE = """
import logging, sys
import uvicorn
from sunday_clays.mcp import __main__ as entry

def fake_run(app, **kw):
    root, ours = logging.getLogger(), logging.getLogger("sunday_clays")
    print("LEVELS", root.level, ours.level)
    logging.warning("bad input for Zebulon Fakename")
    ours.info("our info line")
    ours.warning("our warning line")
    logging.getLogger("uvicorn.error").error("uvicorn error line")

uvicorn.run = fake_run
entry.main()
"""


def test_main_keeps_the_logs_quiet_in_a_clean_process() -> None:
    """A clean process (no handlers on root, unlike pytest) is where FastMCP's own startup calls
    ``basicConfig(level=INFO)``: the levels must be set after it, or the SDK's root warning
    (which carries a malformed request's names) is logged."""
    env = {
        **os.environ,
        "MCP_AUTH_TOKEN": "fake-token-for-test",
        "DATABASE_URL": "postgresql+psycopg://u:p@h/d",
    }
    env.pop("MCP_AUTH_DISABLED", None)
    done = subprocess.run(
        [sys.executable, "-c", _PROBE], env=env, capture_output=True, text=True, timeout=60
    )
    out = done.stdout + done.stderr

    assert done.returncode == 0, out
    assert f"LEVELS {logging.ERROR} {logging.WARNING}" in out
    assert "Zebulon" not in out
    assert "our info line" not in out
    assert "our warning line" in out
    assert "uvicorn error line" in out


def test_the_default_clock_is_timezone_aware_utc() -> None:
    import datetime as dt

    from sunday_clays.mcp import server

    now = server._utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset() == dt.timedelta(0)
    assert abs(dt.datetime.now(dt.UTC) - now) < dt.timedelta(seconds=5)
