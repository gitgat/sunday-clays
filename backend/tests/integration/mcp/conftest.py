"""Fixtures that run the MCP app under uvicorn on a free localhost port."""

import copy
import hashlib
import json
import socket
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import uvicorn
from alembic import command
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from tests.conftest import FIXTURES_DIR

from sunday_clays.db import SessionFactory, alembic_config, make_engine
from sunday_clays.domain import imports as domain_imports
from sunday_clays.domain.imports import commit_import, stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.mcp import writes
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


# --- a committed base shared by the real-commit tests --------------------------------------------
# Parsing and staging the full scores workbook (about 330 names, each compared with the others for
# possible duplicates) costs seconds, and every real-commit test used to do it again. It is done
# once per run into a template database; each test then gets its own copy (CREATE DATABASE ...
# TEMPLATE), so tests stay independent and need no truncate afterwards.
def _admin_engine(engine: Engine) -> Engine:
    return create_engine(
        engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )


@pytest.fixture(scope="session")
def mcp_base_template(engine: Engine) -> Iterator[str]:
    """Name of a database with the Alembic head and the fixture scores committed and rebuilt."""
    name = f"{engine.url.database}_mcpbase"
    admin = _admin_engine(engine)
    with admin.connect() as conn:
        conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    world = make_engine(engine.url.set(database=name).render_as_string(hide_password=False))
    try:
        with world.begin() as connection:
            config = alembic_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(world) as s:
            base = stage_import(
                s, (FIXTURES_DIR / "scores_2026-09-27.xlsx").read_bytes(), "base.xlsx"
            )
            commit_import(s, base.import_id)
            rebuild_live(s)
            s.commit()
        world.dispose()  # a template must have no open connection
        yield name
    finally:
        world.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.dispose()


@pytest.fixture
def base_engine(engine: Engine, mcp_base_template: str) -> Iterator[Engine]:
    """A private copy of the committed base database; ``SessionFactory`` is bound to it."""
    name = f"{mcp_base_template}_{uuid.uuid4().hex[:10]}"
    admin = _admin_engine(engine)
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}" TEMPLATE "{mcp_base_template}"')
    copy = make_engine(engine.url.set(database=name).render_as_string(hide_password=False))
    previous_bind = SessionFactory.kw.get("bind")
    SessionFactory.configure(bind=copy)
    try:
        yield copy
    finally:
        SessionFactory.configure(bind=previous_bind)
        copy.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.dispose()


# --- memoised workbook work -----------------------------------------------------------------------
# Most tests preview the same Sunday on the same base, and each preview parses and rebuilds the
# 320 KB scores workbook several times (seconds of openpyxl). parse_upload and the build_* functions
# are pure functions of their arguments, so the first call per run does the real work and later
# identical calls reuse the result (parse results are copied, so no test can change another's).
# Calls that raise are never cached. The functions themselves are tested directly in tests/unit/mcp.
_CACHE: dict[tuple[Any, ...], Any] = {}


def _memoised(name: str, fn: Callable[..., Any], key: Callable[..., Any], copy_result: bool) -> Any:
    def wrapper(*args: Any) -> Any:
        k = (name, *key(*args))
        if k not in _CACHE:
            _CACHE[k] = fn(*args)
        return copy.deepcopy(_CACHE[k]) if copy_result else _CACHE[k]

    return wrapper


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _model_key(model: Any) -> str:
    return str(model.model_dump_json(by_alias=True))


@pytest.fixture(autouse=True)
def _memoised_workbook_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        domain_imports,
        "parse_upload",
        _memoised("parse", domain_imports.parse_upload, lambda d: (_digest(d),), True),
    )
    monkeypatch.setattr(
        writes,
        "build_scores",
        _memoised("scores", writes.build_scores, lambda b, w: (_digest(b), _model_key(w)), False),
    )
    monkeypatch.setattr(
        writes,
        "build_correction",
        _memoised(
            "correction", writes.build_correction, lambda b, c: (_digest(b), _model_key(c)), False
        ),
    )
    monkeypatch.setattr(
        writes,
        "build_stations",
        _memoised("stations", writes.build_stations, lambda w: (_model_key(w),), False),
    )
