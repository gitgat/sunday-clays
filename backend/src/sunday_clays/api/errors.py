"""JSON error handlers (C2 Errors).

``DomainError`` subclasses and any unhandled exception answer ``{"error": {"code", "message"}}``
(unhandled ones as a logged 500 ``internal`` that hides the detail); ``bodylimit`` uses the same
shape for its 413. FastAPI's own ``HTTPException`` (routing 404/405 included) and
``RequestValidationError`` (422) keep FastAPI's default ``{"detail": ...}`` body.
"""

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sunday_clays.domain.errors import DomainError

logger = logging.getLogger(__name__)


def error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(DomainError, exc)
    return JSONResponse(
        status_code=error.status_code, content=error_body(error.code, error.message)
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Logged 500 ``internal``. Starlette serves it outside every user middleware, so it sets
    its own ``Cache-Control: no-store`` (C8; ``CacheHeadersMiddleware`` never sees it)."""
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=error_body("internal", "Internal server error"),
        headers={"Cache-Control": "no-store"},
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
