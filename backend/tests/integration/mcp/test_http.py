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
    async def run() -> set[str]:
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
            return {t.name for t in (await client.list_tools()).tools}

    assert asyncio.run(run()) == {
        "find_shooters",
        "get_event",
        "get_job",
        "preview_week",
        "preview_correction",
    }


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


def _big(n: int) -> bytes:
    return b"x" * n


def test_body_over_the_cap_is_413_by_content_length(mcp_server: str, mcp_token: str) -> None:
    response = httpx.post(
        f"{mcp_server}/mcp",
        content=_big(1024 * 1024 + 1),
        headers={"Authorization": f"Bearer {mcp_token}", "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.content == b'{"error":"too_large"}'


def test_streamed_body_over_the_cap_is_413_without_content_length(
    mcp_server: str, mcp_token: str
) -> None:
    def chunks():  # type: ignore[no-untyped-def]
        for _ in range(17):
            yield _big(64 * 1024)

    request = httpx.Request(
        "POST",
        f"{mcp_server}/mcp",
        content=chunks(),
        headers={"Authorization": f"Bearer {mcp_token}", "Content-Type": "application/json"},
    )
    assert "content-length" not in request.headers
    with httpx.Client() as client:
        response = client.send(request)
    assert response.status_code == 413
    assert response.content == b'{"error":"too_large"}'


def test_a_full_200_shooter_week_fits_under_the_cap() -> None:
    from sunday_clays.mcp.build import WeekInput
    from sunday_clays.mcp.limits import MAX_BODY_BYTES

    shooters = [
        {
            "name": f"{'L' * 25}{chr(97 + i // 26)}{chr(97 + i % 26)}, {'F' * 28}",
            "score": 50,
            "status": "Member",
            "class": "12 Gauge",
            "hits": [10] * 5,
        }
        for i in range(200)
    ]
    week = WeekInput.model_validate(
        {
            "date": "2026-10-04",
            "stations": ["1", "2", "3", "4", "5"],
            "counts": [10] * 5,
            "shooters": shooters,
        }
    )
    assert len(week.model_dump_json(by_alias=True)) < MAX_BODY_BYTES // 10


def test_unauthenticated_oversized_posts_get_401_not_413(mcp_server: str) -> None:
    by_length = httpx.post(f"{mcp_server}/mcp", content=_big(1024 * 1024 + 1))
    assert by_length.status_code == 401

    def chunks():  # type: ignore[no-untyped-def]
        for _ in range(17):
            yield _big(64 * 1024)

    request = httpx.Request("POST", f"{mcp_server}/mcp", content=chunks())
    assert "content-length" not in request.headers
    with httpx.Client() as client:
        assert client.send(request).status_code == 401


@pytest.mark.parametrize(
    ("length", "status"),
    [(b"abc", 400), (b"-5", 400), (b"1e9", 400), (b"9" * 5000, 413), (b"10", 200)],
)
def test_malformed_content_length_is_never_a_500(length: bytes, status: int) -> None:
    from sunday_clays.mcp.limits import BodyLimitMiddleware

    sent: list[dict[str, object]] = []

    async def app(scope, receive, send):  # type: ignore[no-untyped-def]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(message):  # type: ignore[no-untyped-def]
        sent.append(message)

    async def receive():  # type: ignore[no-untyped-def]
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "headers": [(b"content-length", length)]}
    asyncio.run(BodyLimitMiddleware(app)(scope, receive, send))
    assert sent[0]["status"] == status
    if status == 400:
        assert sent[1]["body"] == b'{"error":"bad_request"}'
