"""Fixtures that run the MCP app under uvicorn on a free localhost port."""

import json
import socket
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from sqlalchemy.orm import Session

from sunday_clays.mcp.server import build_app

TOKEN = "test-token-not-secret"
# Frozen server clock for the staging tools; tests that need another one override mcp_clock.
FROZEN_NOW = datetime(2026, 10, 6, 18, 0, tzinfo=UTC)


async def call_tool(url: str, name: str, args: dict[str, Any], token: str = TOKEN) -> Any:
    """Call one tool through the real MCP client and return its parsed JSON result."""
    headers = {"Authorization": f"Bearer {token}"}
    async with (
        create_mcp_http_client(headers=headers) as http_client,
        streamable_http_client(f"{url}/mcp", http_client=http_client) as (read, write, _),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        result = await client.call_tool(name, args)
    text = "".join(getattr(part, "text", "") for part in result.content)
    return json.loads(text)


@pytest.fixture
def mcp_token() -> str:
    return TOKEN


@pytest.fixture
def session_factory(session: Session) -> Callable[[], AbstractContextManager[Session]]:
    @contextmanager
    def factory() -> Iterator[Session]:
        yield session

    return factory


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def mcp_clock() -> Callable[[], datetime]:
    return lambda: FROZEN_NOW


@pytest.fixture
def mcp_server(
    session_factory: Callable[[], AbstractContextManager[Session]],
    mcp_clock: Callable[[], datetime],
) -> Iterator[str]:
    port = _free_port()
    app = build_app(TOKEN, session_factory, session_factory, mcp_clock)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15
    while True:
        try:
            if httpx.get(f"{url}/healthz", timeout=1).status_code == 200:
                break
        except httpx.TransportError:
            pass
        if time.monotonic() > deadline:
            server.should_exit = True
            raise RuntimeError("MCP test server did not start")
        time.sleep(0.05)
    try:
        yield url
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive()
