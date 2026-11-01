"""MCP app over real HTTP: gateway bearer auth, health probe and the SDK handshake."""

import asyncio

import httpx
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client


def test_healthz_open(mcp_server: str) -> None:
    response = httpx.get(f"{mcp_server}/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/mcp"),
        ("GET", "/mcp"),
        ("DELETE", "/mcp"),
        ("POST", "/mcp/"),
        ("OPTIONS", "/mcp"),
    ],
)
@pytest.mark.parametrize("auth", [None, "Bearer wrong", "Basic x"])
def test_mcp_requires_bearer(mcp_server: str, method: str, path: str, auth: str | None) -> None:
    headers = {} if auth is None else {"Authorization": auth}
    response = httpx.request(method, f"{mcp_server}{path}", headers=headers)
    assert response.status_code == 401
    assert response.content == b'{"error":"unauthorized"}'


def test_initialize_and_list_tools(mcp_server: str, mcp_token: str) -> None:
    async def run() -> int:
        headers = {"Authorization": f"Bearer {mcp_token}"}
        async with (
            create_mcp_http_client(headers=headers) as http_client,
            streamable_http_client(f"{mcp_server}/mcp", http_client=http_client) as (
                read,
                write,
                _,
            ),
            ClientSession(read, write) as client,
        ):
            await client.initialize()
            return len((await client.list_tools()).tools)

    assert asyncio.run(run()) == 0


def test_gateway_host_header_accepted(mcp_server: str, mcp_token: str) -> None:
    """Gateway requests carry a service-alias Host; DNS-rebinding protection must be off."""
    response = httpx.post(
        f"{mcp_server}/mcp",
        headers={
            "Host": "sundayclays-mcp:8080",
            "Authorization": f"Bearer {mcp_token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "host-test", "version": "0"},
            },
        },
    )
    assert response.status_code == 200
    assert '"result"' in response.text
