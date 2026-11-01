"""FastMCP app: tools (added by later tasks), a health probe and the bearer gate."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from sunday_clays import db
from sunday_clays.config import get_settings
from sunday_clays.mcp.auth import BearerMiddleware

SessionFactoryFn = Callable[[], AbstractContextManager[Session]]


@contextmanager
def default_session_factory() -> Iterator[Session]:
    """One session per tool call; commit on success, rollback on error (mirrors db.get_session)."""
    if db.SessionFactory.kw.get("bind") is None:
        db.SessionFactory.configure(
            bind=db.make_engine(get_settings().database_url.get_secret_value())
        )
    session = db.SessionFactory()
    try:
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
    # host="0.0.0.0" keeps the SDK's localhost-only Host check off: the gateway reaches us by
    # service alias, and the bearer middleware is the gate.
    return FastMCP("sunday-clays-scores", host="0.0.0.0")  # noqa: S104


async def _healthz(_request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


def build_app(token: str | None, session_factory: SessionFactoryFn) -> Starlette:
    """The SDK's own Starlette app (so its session-manager lifespan runs) plus /healthz, gated."""
    app = build_mcp(session_factory).streamable_http_app()
    app.router.routes.append(Route("/healthz", _healthz, methods=["GET"]))
    return BearerMiddleware(app, token)  # type: ignore[return-value]
