"""Block cross-site state-changing requests before routing (C8 CSRF). Pure ASGI."""

from typing import Final
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from sunday_clays.api.errors import error_body

SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})
ALLOWED_FETCH_SITES: Final = frozenset({"same-origin", "none"})


def is_cross_site(method: str, headers: Headers) -> bool:
    if method in SAFE_METHODS:
        return False
    fetch_site = headers.get("sec-fetch-site")
    if fetch_site is not None and fetch_site.lower() not in ALLOWED_FETCH_SITES:
        return True
    origin = headers.get("origin")
    if origin is None:
        return False
    try:
        netloc = urlsplit(origin).netloc.lower()
    except ValueError:
        return True
    return not netloc or netloc != headers.get("host", "").lower()


class CsrfGuardMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and is_cross_site(scope["method"], Headers(scope=scope)):
            response = JSONResponse(
                error_body("csrf", "Cross-site request blocked"), status_code=403
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
