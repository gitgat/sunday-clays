"""FastAPI application factory. Never edit this file to add a route (C2 API routers)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Final

from fastapi import Depends, FastAPI

from sunday_clays.api.bodylimit import BodySizeLimitMiddleware
from sunday_clays.api.csrf import CsrfGuardMiddleware
from sunday_clays.api.errors import install_error_handlers
from sunday_clays.api.etag import CacheHeadersMiddleware
from sunday_clays.api.routes import discover_routers
from sunday_clays.auth.deps import require_admin, require_viewer
from sunday_clays.config import get_settings
from sunday_clays.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    get_settings()  # a misconfigured secret fails server startup, not the first request
    yield


PUBLIC_ROUTE_MODULES: Final = frozenset({"health", "auth", "og"})  # og: Plan 19 D6


def role_dependencies(module_name: str) -> list[Any]:
    """C2: ``health``/``auth`` are public, ``admin_*`` need admin, all other modules a viewer."""
    if module_name in PUBLIC_ROUTE_MODULES:
        return []
    if module_name.startswith("admin_"):
        return [Depends(require_admin)]
    return [Depends(require_viewer)]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sunday Clays API",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    install_error_handlers(app)
    for name, router in discover_routers():
        app.include_router(router, dependencies=role_dependencies(name))
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(CsrfGuardMiddleware)
    # Last registered = outermost: 403/413 replies from inner middlewares also get
    # Cache-Control (Plan 06 T1, C8).
    app.add_middleware(CacheHeadersMiddleware)
    return app
