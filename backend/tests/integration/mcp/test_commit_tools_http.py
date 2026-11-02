"""commit_week / rollback_week through the real MCP client."""

import asyncio
import inspect
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from tests.integration.mcp.test_backup_real import _skip_unless_pg_dump_is_new_enough
from tests.integration.mcp.test_commit import NOW, _preview, _statuses
from tests.integration.mcp.test_tools_http import _raw

from sunday_clays.mcp import backup, server
from sunday_clays.models import McpOperation

KEY = "http-key-00001"


@pytest.fixture
def session_factory(
    fx_session: Session,
) -> Callable[[], AbstractContextManager[Session]]:
    @contextmanager
    def factory() -> Iterator[Session]:
        yield fx_session

    return factory


def _fake_dump(*_a: object, **_k: object) -> Path:
    return Path("/x/pre-import-http.dump")


def test_tool_schemas_take_only_the_preview_and_a_key(mcp_server: str, mcp_token: str) -> None:
    async def schemas() -> dict[str, dict[str, Any]]:
        headers = {"Authorization": f"Bearer {mcp_token}"}
        async with (
            create_mcp_http_client(headers=headers) as http_client,
            streamable_http_client(f"{mcp_server}/mcp", http_client=http_client) as (r, w, _),
            ClientSession(r, w) as client,
        ):
            await client.initialize()
            return {t.name: t.inputSchema for t in (await client.list_tools()).tools}

    tools = asyncio.run(schemas())
    for name in ("commit_week", "rollback_week"):
        schema = tools[name]
        assert set(schema["properties"]) == {"preview_id", "idempotency_key"}
        assert set(schema["required"]) == {"preview_id", "idempotency_key"}
        assert schema["properties"]["idempotency_key"]["minLength"] == 8
        assert schema["properties"]["idempotency_key"]["maxLength"] == 100


def test_tools_run_off_the_event_loop() -> None:
    mcp = server.build_mcp(lambda: None, lambda: None)  # type: ignore[arg-type,return-value]
    for name in ("commit_week", "rollback_week"):
        tool = mcp._tool_manager.get_tool(name)
        assert tool is not None
        assert inspect.iscoroutinefunction(tool.fn)


def test_disabled_by_default_over_mcp(
    mcp_server: str, mcp_token: str, fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MCP_COMMIT_ENABLED", raising=False)
    pid = _preview(fx_session)
    is_error, text = asyncio.run(
        _raw(mcp_server, mcp_token, "commit_week", {"preview_id": pid, "idempotency_key": KEY})
    )
    assert is_error is True
    assert "commits_disabled" in text
    assert f"python -m sunday_clays.mcp.approve {pid}" in text
    assert _statuses(fx_session, pid) == ["pending", "pending"]


def test_commit_and_rollback_over_mcp(
    mcp_server: str, mcp_token: str, fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_COMMIT_ENABLED", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setattr(backup, "pre_import_dump", _fake_dump)
    pid = _preview(fx_session)
    args = {"preview_id": pid, "idempotency_key": KEY}
    is_error, text = asyncio.run(_raw(mcp_server, mcp_token, "commit_week", args))
    assert is_error is False
    assert '"committed"' in text
    op = fx_session.get(McpOperation, __import__("uuid").UUID(pid))
    assert op is not None
    fx_session.refresh(op)
    assert (op.status, op.commit_path) == ("committed", "mcp-auto")
    is_error, text = asyncio.run(
        _raw(mcp_server, mcp_token, "rollback_week", {**args, "idempotency_key": "http-key-00002"})
    )
    assert is_error is False
    fx_session.refresh(op)
    assert op.status == "rolled_back"


def test_a_correction_is_refused_over_mcp(
    mcp_server: str, mcp_token: str, fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.integration.mcp.test_commit import _correction

    monkeypatch.setenv("MCP_COMMIT_ENABLED", "true")
    pid = _correction(fx_session)
    is_error, text = asyncio.run(
        _raw(mcp_server, mcp_token, "commit_week", {"preview_id": pid, "idempotency_key": KEY})
    )
    assert is_error is True
    assert "correction_needs_human" in text
    assert _statuses(fx_session, pid) == ["pending"]


def test_bad_key_is_a_validation_error(mcp_server: str, mcp_token: str) -> None:
    is_error, _ = asyncio.run(
        _raw(mcp_server, mcp_token, "commit_week", {"preview_id": "x", "idempotency_key": "bad"})
    )
    assert is_error is True


def test_healthz_answers_during_a_slow_dump(
    mcp_server: str, mcp_token: str, fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_COMMIT_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    entered = threading.Event()
    release = threading.Event()

    def slow(*_a: object, **_k: object) -> Path:
        entered.set()
        release.wait(timeout=20)
        return Path("/x/pre-import-slow.dump")

    monkeypatch.setattr(backup, "pre_import_dump", slow)
    pid = _preview(fx_session)
    results: list[tuple[bool, str]] = []
    worker = threading.Thread(
        target=lambda: results.append(
            asyncio.run(
                _raw(
                    mcp_server,
                    mcp_token,
                    "commit_week",
                    {"preview_id": pid, "idempotency_key": KEY},
                )
            )
        )
    )
    worker.start()
    try:
        assert entered.wait(timeout=15)
        assert httpx.get(f"{mcp_server}/healthz", timeout=3).status_code == 200
    finally:
        release.set()
        worker.join(timeout=30)
    assert results
    assert results[0][0] is False


@pytest.mark.slow
def test_real_pg_dump_happy_path(
    mcp_server: str,
    mcp_token: str,
    fx_session: Session,
    fx_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Also shows pg_dump is not blocked by the commit's open transaction and its row locks."""
    _skip_unless_pg_dump_is_new_enough(fx_engine)
    monkeypatch.setattr("sunday_clays.mcp.backup.MIN_DUMP_BYTES", 100)
    monkeypatch.setenv("MCP_COMMIT_ENABLED", "true")
    monkeypatch.setenv("MCP_BACKUP_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", fx_engine.url.render_as_string(hide_password=False))
    pid = _preview(fx_session)
    is_error, text = asyncio.run(
        _raw(mcp_server, mcp_token, "commit_week", {"preview_id": pid, "idempotency_key": KEY})
    )
    assert is_error is False, text
    dumps = list(tmp_path.glob("pre-import-*.dump"))
    assert len(dumps) == 1
    assert dumps[0].name in text
    assert str(tmp_path) not in text
    assert NOW  # silence unused-import lint for the shared constant


def test_no_argument_can_allow_a_correction(mcp_server: str, mcp_token: str) -> None:
    args = {"preview_id": "x", "idempotency_key": KEY, "allow_correction": True}
    is_error, _ = asyncio.run(_raw(mcp_server, mcp_token, "commit_week", args))
    assert is_error is True
