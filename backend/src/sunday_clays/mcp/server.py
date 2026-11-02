"""FastMCP app: tools (added by later tasks), a health probe and the bearer gate."""

import datetime as dt
import functools
import logging
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Annotated, Any
from uuid import UUID

import anyio.to_thread
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp

from sunday_clays import db
from sunday_clays.config import database_url_from_env
from sunday_clays.mcp import reads, writes
from sunday_clays.mcp.auth import BearerMiddleware
from sunday_clays.mcp.build import CorrectionInput, WeekInput
from sunday_clays.mcp.limits import BodyLimitMiddleware
from sunday_clays.mcp.schemas import (
    MAX_JOB_ID,
    EventSummary,
    FindShootersInput,
    FindShootersResult,
    GetEventInput,
    GetJobInput,
)

STATEMENT_TIMEOUT_MS = 10_000
# Staging parses and diffs a whole history workbook, so writes get a longer leash than reads.
WRITE_STATEMENT_TIMEOUT_MS = 60_000
SessionFactoryFn = Callable[[], AbstractContextManager[Session]]
ClockFn = Callable[[], dt.datetime]

_write_sessionmakers: dict[str, sessionmaker[Session]] = {}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@contextmanager
def default_session_factory() -> Iterator[Session]:
    """One session per tool call; commit on success, rollback on error (mirrors db.get_session)."""
    if db.SessionFactory.kw.get("bind") is None:
        # Only the database URL: the mcp service does not mount the login secrets Settings needs.
        # Read-only: the write tools use write_session_factory.
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


@contextmanager
def write_session_factory() -> Iterator[Session]:
    """A writable session (own engine, 60 s statement timeout); commit on success."""
    url = database_url_from_env()
    maker = _write_sessionmakers.get(url)
    if maker is None:
        maker = sessionmaker(bind=db.make_engine(url), expire_on_commit=False)
        _write_sessionmakers[url] = maker
    session = maker()
    try:
        session.execute(text(f"SET LOCAL statement_timeout = {WRITE_STATEMENT_TIMEOUT_MS}"))
        yield session
    except BaseException:
        session.rollback()
        raise
    else:
        session.commit()
    finally:
        session.close()


def build_mcp(
    session_factory: SessionFactoryFn,
    write_session_factory: SessionFactoryFn,
    clock: ClockFn = _utcnow,
) -> FastMCP:
    """The tool registry: read tools on the read-only factory, staging tools on the write one."""
    # The bearer middleware is the gate and the service is reached by a service alias, so the
    # SDK's localhost-only Host check (DNS-rebinding protection) is off.
    mcp = FastMCP(
        "sunday-clays-scores",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    _register_reads(mcp, session_factory)
    _register_writes(mcp, write_session_factory, clock)
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

    @mcp.tool(
        description=(
            "Check the status of a background job (queued, running, done or failed) by its "
            "integer id, or of a score preview or commit by its preview_id (a uuid)."
        )
    )
    def get_job(id: Annotated[int, Field(ge=1, le=MAX_JOB_ID)] | UUID) -> dict[str, Any]:
        args = GetJobInput(id=id)
        with session_factory() as session:
            return reads.get_job(session, args.id).model_dump(mode="json")


_RULES = (
    "Rules: count marks, not the row totals printed on the card. A thrown-out station is "
    "credited perfect for everyone. Drop a card's hits if they cannot be reconciled with its "
    "score (give the score alone). Use existing name spellings: map every name through "
    "find_shooters first. "
)


def _register_writes(mcp: FastMCP, write_factory: SessionFactoryFn, clock: ClockFn) -> None:
    @mcp.tool(
        description=(
            "Stage one new Sunday's scores for import and return a preview; nothing is "
            "committed. " + _RULES + "The date must be a Sunday after the latest stored one, "
            "at most 14 days ago, with no stored rounds. A new preview for the same date "
            "replaces the earlier one, but a refused new preview leaves any earlier preview for "
            "that date live. Invalid input comes back as a validation error explaining the "
            "problem (nothing is recorded); checks made after validation (dates, stored data) "
            "come back as an error beginning with a code and are recorded."
        )
    )
    async def preview_week(week: WeekInput) -> dict[str, Any]:
        work = functools.partial(
            writes.run_write,
            write_factory,
            lambda session: writes.preview_week(session, week, now=clock()),
        )
        try:
            result = await anyio.to_thread.run_sync(work)
        except writes.Refusal as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None
        return result.model_dump(mode="json")

    @mcp.tool(
        description=(
            "Stage a score correction (at most 5 rows) for the latest stored Sunday and return "
            "a preview. Corrections are score-only, for existing names; they need a human to "
            "approve them and can never be committed through this server. "
            + _RULES
            + "Invalid input comes back as a validation error explaining the problem (nothing is "
            "recorded); checks made after validation come back as an error beginning with a "
            "code and are recorded."
        )
    )
    async def preview_correction(correction: CorrectionInput) -> dict[str, Any]:
        work = functools.partial(
            writes.run_write,
            write_factory,
            lambda session: writes.preview_correction(session, correction, now=clock()),
        )
        try:
            result = await anyio.to_thread.run_sync(work)
        except writes.Refusal as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None
        return result.model_dump(mode="json")


async def _healthz(_request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


def build_app(
    token: str | None,
    session_factory: SessionFactoryFn,
    write_session_factory: SessionFactoryFn,
    clock: ClockFn = _utcnow,
) -> ASGIApp:
    """The SDK's own Starlette app (so its session-manager lifespan runs) plus /healthz, gated."""
    app = build_mcp(session_factory, write_session_factory, clock).streamable_http_app()
    app.router.routes.append(Route("/healthz", _healthz, methods=["GET"]))
    return BearerMiddleware(BodyLimitMiddleware(app), token)
