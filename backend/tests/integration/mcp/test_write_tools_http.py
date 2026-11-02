"""preview_week / preview_correction through the real MCP client."""

import asyncio
import inspect
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

import httpx
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.mcp.test_tools_http import _raw, call_tool

from sunday_clays.mcp import server, writes
from sunday_clays.models import Import, McpOperation

WEEK: dict[str, Any] = {
    "date": "2026-10-04",
    "stations": ["1", "2", "3", "4", "5"],
    "counts": [10, 10, 10, 10, 10],
    "shooters": [{"name": "Testshooter, Beta", "score": 30, "status": "Guest"}],
}


@pytest.fixture
def session_factory(
    fx_session: Session,
) -> Callable[[], AbstractContextManager[Session]]:
    @contextmanager
    def factory() -> Iterator[Session]:
        yield fx_session

    return factory


async def _schemas(url: str, token: str) -> dict[str, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    async with (
        create_mcp_http_client(headers=headers) as http_client,
        streamable_http_client(f"{url}/mcp", http_client=http_client) as (r, w, _),
        ClientSession(r, w) as client,
    ):
        await client.initialize()
        return {t.name: t.inputSchema for t in (await client.list_tools()).tools}


def test_schemas_are_bounded(mcp_server: str, mcp_token: str) -> None:
    schemas = asyncio.run(_schemas(mcp_server, mcp_token))
    week = schemas["preview_week"]["$defs"]
    assert week["WeekInput"]["additionalProperties"] is False
    assert week["WeekInput"]["properties"]["shooters"]["maxItems"] == 200
    assert week["WeekInput"]["properties"]["stations"]["maxItems"] == 12
    corr = schemas["preview_correction"]["$defs"]
    assert corr["CorrectionInput"]["properties"]["rows"]["maxItems"] == 5
    shooter = week["ShooterRow"]["properties"]
    assert shooter["name"]["maxLength"] == 60
    assert shooter["class"]["anyOf"][0]["maxLength"] == 20
    assert shooter["hits"]["anyOf"][0]["maxItems"] == 12
    assert corr["CorrectionRow"]["properties"]["name"]["maxLength"] == 60


def test_descriptions_carry_the_procedure_rules(mcp_server: str, mcp_token: str) -> None:
    async def descriptions() -> dict[str, str]:
        headers = {"Authorization": f"Bearer {mcp_token}"}
        async with (
            create_mcp_http_client(headers=headers) as http_client,
            streamable_http_client(f"{mcp_server}/mcp", http_client=http_client) as (r, w, _),
            ClientSession(r, w) as client,
        ):
            await client.initialize()
            return {t.name: t.description or "" for t in (await client.list_tools()).tools}

    tools = asyncio.run(descriptions())
    for name in ("preview_week", "preview_correction"):
        low = tools[name].lower()
        assert "count marks" in low
        assert "thrown-out station is credited perfect" in low
        assert "drop a card's hits" in low
        assert "find_shooters" in low


def test_preview_week_over_mcp(mcp_server: str, fx_session: Session) -> None:
    out = asyncio.run(call_tool(mcp_server, "preview_week", {"week": WEEK}))
    assert out["head_count"] == 1
    assert fx_session.get(McpOperation, out["preview_id"]) is not None


def test_refusal_is_a_tool_error_with_its_code_and_is_recorded(
    mcp_server: str, mcp_token: str, fx_session: Session
) -> None:
    is_error, text = asyncio.run(
        _raw(mcp_server, mcp_token, "preview_week", {"week": {**WEEK, "date": "2026-10-05"}})
    )
    assert is_error is True
    assert "not_sunday" in text
    ops = fx_session.scalars(select(McpOperation).where(McpOperation.status == "refused")).all()
    assert [o.result["code"] for o in ops] == ["not_sunday"]
    assert fx_session.scalar(select(func.count(Import.id)).where(Import.status == "pending")) == 0


def test_correction_refusal_over_mcp_leaves_nothing_pending(
    mcp_server: str, mcp_token: str, fx_session: Session
) -> None:
    args = {"correction": {"date": "2026-09-27", "rows": [{"name": "Nobody, Nemo", "score": 5}]}}
    is_error, text = asyncio.run(_raw(mcp_server, mcp_token, "preview_correction", args))
    assert is_error is True
    assert "name_not_on_date" in text
    assert fx_session.scalar(select(func.count(Import.id)).where(Import.status == "pending")) == 0


@pytest.mark.parametrize(
    "args",
    [
        {"week": {**WEEK, "bogus": 1}},
        {"week": {**WEEK, "shooters": []}},
        {"week": WEEK, "extra": 1},
        {"correction": {"date": "2026-09-27", "rows": []}},
    ],
)
def test_bad_input_is_tool_error(mcp_server: str, mcp_token: str, args: dict[str, Any]) -> None:
    tool = "preview_correction" if "correction" in args else "preview_week"
    is_error, _ = asyncio.run(_raw(mcp_server, mcp_token, tool, args))
    assert is_error is True


def _with_shooters(*shooters: dict[str, Any]) -> dict[str, Any]:
    return {"week": {**WEEK, "shooters": list(shooters)}}


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            _with_shooters(
                {"name": "Testshooter, Beta", "score": 30, "status": "Guest", "hits": [1] * 5}
            ),
            "hits sum to 5, not the score 30",
        ),
        (
            _with_shooters(
                {"name": "Testshooter, Beta", "score": 30, "status": "Guest"},
                {"name": "testshooter, beta", "score": 31, "status": "Guest"},
            ),
            "duplicate shooter name",
        ),
    ],
)
def test_validation_errors_explain_the_problem_and_record_nothing(
    mcp_server: str, mcp_token: str, fx_session: Session, args: dict[str, Any], message: str
) -> None:
    is_error, text = asyncio.run(_raw(mcp_server, mcp_token, "preview_week", args))
    assert is_error is True
    assert message in text
    assert fx_session.scalar(select(func.count(McpOperation.id))) == 0


def test_names_are_not_logged(
    mcp_server: str, mcp_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "Zzqxprivate, Nemo"
    args = {"correction": {"date": "2026-09-27", "rows": [{"name": secret, "score": 5}]}}
    with caplog.at_level(logging.DEBUG):
        asyncio.run(_raw(mcp_server, mcp_token, "preview_correction", args))
    server_side = [r for r in caplog.records if r.name.startswith(("mcp.server", "sunday_clays"))]
    assert not [r for r in server_side if "Zzqxprivate" in r.getMessage()]
    assert not [r for r in server_side if "Zzqxprivate" in str(r.__dict__.get("args", ""))]


def test_tools_run_off_the_event_loop() -> None:
    mcp = server.build_mcp(lambda: None, lambda: None)  # type: ignore[arg-type,return-value]
    for name in ("preview_week", "preview_correction"):
        tool = mcp._tool_manager.get_tool(name)
        assert tool is not None
        assert inspect.iscoroutinefunction(tool.fn)


def test_healthz_answers_while_a_preview_is_running(
    mcp_server: str, mcp_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = threading.Event()
    release = threading.Event()

    def slow(*_a: object, **_k: object) -> object:
        entered.set()
        release.wait(timeout=20)
        raise writes.Refusal("invalid_input", "released")

    monkeypatch.setattr(writes, "preview_week", slow)
    results: list[tuple[bool, str]] = []
    worker = threading.Thread(
        target=lambda: results.append(
            asyncio.run(_raw(mcp_server, mcp_token, "preview_week", {"week": WEEK}))
        )
    )
    worker.start()
    try:
        assert entered.wait(timeout=15)
        assert httpx.get(f"{mcp_server}/healthz", timeout=3).status_code == 200
    finally:
        release.set()
        worker.join(timeout=20)
    assert results
    assert results[0][0] is True
