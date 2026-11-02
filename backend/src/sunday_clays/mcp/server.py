"""FastMCP app: tools (added by later tasks), a health probe and the bearer gate."""

import datetime as dt
import logging
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp

from sunday_clays import db
from sunday_clays.config import database_url_from_env
from sunday_clays.mcp import reads
from sunday_clays.mcp.auth import BearerMiddleware
from sunday_clays.mcp.schemas import (
    MAX_JOB_ID,
    EventSummary,
    FindShootersInput,
    FindShootersResult,
    GetEventInput,
    GetJobInput,
)

STATEMENT_TIMEOUT_MS = 10_000
SessionFactoryFn = Callable[[], AbstractContextManager[Session]]


@contextmanager
def default_session_factory() -> Iterator[Session]:
    """One session per tool call; commit on success, rollback on error (mirrors db.get_session)."""
    if db.SessionFactory.kw.get("bind") is None:
        # Only the database URL: the mcp service does not mount the login secrets Settings needs.
        # Read-only until the write tools exist (phase 2).
        engine = db.make_engine(database_url_from_env())
        db.SessionFactory.configure(bind=engine.execution_options(postgresql_readonly=True))
    session = db.SessionFactory()
    try:
        # A hung query must not block a tool call (and the event loop) indefinitely.
        session.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))
        yield session
    except BaseException:
        session.rollback()
        raise
    else:
        session.commit()
    finally:
        session.close()


def build_mcp(session_factory: SessionFactoryFn) -> FastMCP:
    """The tool registry. Read and import tools are registered by later tasks."""
    # The bearer middleware is the gate and the service is reached by a service alias, so the
    # SDK's localhost-only Host check (DNS-rebinding protection) is off.
    mcp = FastMCP(
        "sunday-clays-scores",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    _register_reads(mcp, session_factory)
    _forbid_extra_arguments(mcp)
    # The SDK logs whole request messages (tool arguments hold shooter names) at DEBUG; keep the
    # server side of the SDK at WARNING so a debug-level root logger can never write them.
    logging.getLogger("mcp.server").setLevel(logging.WARNING)
    return mcp


def _forbid_extra_arguments(mcp: FastMCP) -> None:
    """FastMCP ignores unknown argument keys; an unknown key is a caller mistake, so reject it."""
    for tool in mcp._tool_manager.list_tools():
        arg_model = tool.fn_metadata.arg_model
        arg_model.model_config["extra"] = "forbid"
        arg_model.model_rebuild(force=True)


def _register_reads(mcp: FastMCP, session_factory: SessionFactoryFn) -> None:
    @mcp.tool(
        description=(
            "Look up shooters by name, in any word order and any case. Use it to map handwritten "
            'names to the exact stored "Last, First" spelling before reading or importing scores.'
        )
    )
    def find_shooters(
        query: Annotated[str, Field(min_length=1, max_length=60)],
        limit: Annotated[int, Field(ge=1, le=25)] = 10,
    ) -> dict[str, Any]:
        args = FindShootersInput(query=query, limit=limit)
        with session_factory() as session:
            hits = reads.find_shooters(session, args.query, args.limit)
        return FindShootersResult(shooters=hits).model_dump(mode="json")

    @mcp.tool(
        description=(
            "Summarise one Sunday's stored results: head count, round type, totals, stations "
            "(with thrown-out ones flagged) and data issues; set include_rows for every round."
        )
    )
    def get_event(date: dt.date, include_rows: bool = False) -> dict[str, Any]:
        args = GetEventInput(date=date, include_rows=include_rows)
        with session_factory() as session:
            result = reads.get_event(session, args.date, args.include_rows)
        skip = {"rows"} if isinstance(result, EventSummary) and result.rows is None else None
        return result.model_dump(mode="json", exclude=skip)

    @mcp.tool(description="Check the status of a background job (queued, running, done or failed).")
    def get_job(id: Annotated[int, Field(ge=1, le=MAX_JOB_ID)]) -> dict[str, Any]:
        args = GetJobInput(id=id)
        with session_factory() as session:
            return reads.get_job(session, args.id).model_dump(mode="json")


async def _healthz(_request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


def build_app(token: str | None, session_factory: SessionFactoryFn) -> ASGIApp:
    """The SDK's own Starlette app (so its session-manager lifespan runs) plus /healthz, gated."""
    app = build_mcp(session_factory).streamable_http_app()
    app.router.routes.append(Route("/healthz", _healthz, methods=["GET"]))
    return BearerMiddleware(app, token)
