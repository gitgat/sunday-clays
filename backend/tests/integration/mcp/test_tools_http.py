"""The read tools through the real MCP client."""

import asyncio
import json
import logging
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.models import Event, Round, Shooter

TOKEN = "test-token-not-secret"


@pytest.fixture
def session_factory(
    fx_session: Session,
) -> Callable[[], AbstractContextManager[Session]]:
    @contextmanager
    def factory() -> Iterator[Session]:
        yield fx_session

    return factory


async def _raw(url: str, token: str, name: str, args: dict[str, Any]) -> tuple[bool, str]:
    headers = {"Authorization": f"Bearer {token}"}
    async with (
        create_mcp_http_client(headers=headers) as http_client,
        streamable_http_client(f"{url}/mcp", http_client=http_client) as (read, write, _),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        result = await client.call_tool(name, args)
    text = "".join(getattr(part, "text", "") for part in result.content)
    return result.isError, text


async def call_tool(url: str, name: str, args: dict[str, Any], token: str = TOKEN) -> Any:
    is_error, text = await _raw(url, token, name, args)
    assert not is_error, text
    return json.loads(text)


async def _list(url: str, token: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    async with (
        create_mcp_http_client(headers=headers) as http_client,
        streamable_http_client(f"{url}/mcp", http_client=http_client) as (read, write, _),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        return {t.name: t.description or "" for t in (await client.list_tools()).tools}


def test_tools_listed(mcp_server: str, mcp_token: str) -> None:
    tools = asyncio.run(_list(mcp_server, mcp_token))
    assert set(tools) == {"find_shooters", "get_event", "get_job"}
    assert "Last, First" in tools["find_shooters"]


def test_find_shooters_over_mcp(mcp_server: str, mcp_token: str, fx_session: Session) -> None:
    name = fx_session.scalars(select(Shooter.display_name).limit(1)).one()
    last = name.split(",")[0]
    hits = asyncio.run(call_tool(mcp_server, "find_shooters", {"query": last, "limit": 50}))
    found = hits["shooters"]
    assert name in [h["display_name"] for h in found]
    assert set(found[0]) == {"display_name", "rounds", "last_shot", "usual_status"}


def test_get_event_over_mcp(mcp_server: str, fx_session: Session) -> None:
    event = fx_session.scalars(select(Event).order_by(Event.event_date.desc())).first()
    assert event is not None
    out = asyncio.run(call_tool(mcp_server, "get_event", {"date": event.event_date.isoformat()}))
    assert out["date"] == event.event_date.isoformat()
    assert out["score_sum"] == fx_session.scalar(
        select(func.sum(Round.score)).where(Round.event_date == event.event_date)
    )
    assert "rows" not in out
    rows = asyncio.run(
        call_tool(
            mcp_server,
            "get_event",
            {"date": event.event_date.isoformat(), "include_rows": True},
        )
    )
    assert len(rows["rows"]) == out["n_rounds"]
    missing = asyncio.run(call_tool(mcp_server, "get_event", {"date": "1999-01-03"}))
    assert missing["found"] is False


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("find_shooters", {"query": "x", "limit": 500}),
        ("find_shooters", {"query": ""}),
        ("find_shooters", {"query": "x", "bogus": 1}),
        ("get_event", {"date": "not-a-date"}),
        ("get_job", {"id": 0}),
    ],
)
def test_bad_input_is_tool_error(
    mcp_server: str, mcp_token: str, tool: str, args: dict[str, Any]
) -> None:
    is_error, _ = asyncio.run(_raw(mcp_server, mcp_token, tool, args))
    assert is_error is True
    ok, _ = asyncio.run(_raw(mcp_server, mcp_token, "get_job", {"id": 1}))
    assert ok is False  # server still healthy (a missing job is a normal result)


def test_tool_arguments_not_logged(
    mcp_server: str, mcp_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "zzqx-private-shooter-name"
    with caplog.at_level(logging.DEBUG):
        asyncio.run(_raw(mcp_server, mcp_token, "find_shooters", {"query": secret}))
        asyncio.run(_raw(mcp_server, mcp_token, "find_shooters", {"query": secret, "limit": 999}))
    server_side = [r for r in caplog.records if r.name.startswith(("mcp.server", "sunday_clays"))]
    assert not [r for r in server_side if secret in r.getMessage()]
    assert not [r for r in server_side if secret in str(r.__dict__.get("args", ""))]
