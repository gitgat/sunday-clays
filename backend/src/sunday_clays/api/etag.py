"""Cache-Control + weak ETag middleware for GET /api responses (C8)."""

import contextlib
import hashlib
from collections.abc import Callable, Iterator
from typing import NamedTuple, cast
from urllib.parse import urlencode

from fastapi import FastAPI, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from sunday_clays.analytics import cache
from sunday_clays.api.routes import _filters
from sunday_clays.auth.sessions import COOKIE_NAME
from sunday_clays.config import get_settings
from sunday_clays.db import get_session

NO_ETAG_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/auth/",
    "/api/admin/",
    "/api/predictions/",
    "/api/features/",
    "/api/og/",  # Plan 19 D6: public previews set their own Cache-Control
)
# Plan 19: routes whose own Cache-Control must stand (the middleware sets none for them)
OWN_CACHE_CONTROL_PREFIXES: tuple[str, ...] = ("/api/og/",)
NO_STORE_PREFIXES: tuple[str, ...] = ("/api/auth/", "/api/admin/", "/api/features/")
# Plan 19 D3: switches change without a data_version bump. Matched exactly (plus the "/"
# prefixes above), so a sibling such as /api/features-x is not swept in.
SWITCH_PATH = "/api/features"
# Plan 15: fist-bump counts change without a data_version bump, so a data_version ETag would
# answer 304 with stale counts. They are never tagged and never stored.
NO_STORE_SUFFIXES: tuple[str, ...] = ("/bumps",)


def etag_eligible(method: str, path: str) -> bool:
    """GET under /api/, except health, auth, admin, predictions and bump counts."""
    return (
        method == "GET"
        and path.startswith("/api/")
        and path != SWITCH_PATH
        and not path.startswith(NO_ETAG_PREFIXES)
        and not path.endswith(NO_STORE_SUFFIXES)
    )


def cache_control_for(path: str) -> str | None:
    """`no-store` for auth, admin and bump counts, `private, no-cache` for other /api paths.

    None for link previews (their route sets public caching) and for non-API paths.
    """
    if path.startswith(OWN_CACHE_CONTROL_PREFIXES):
        return None
    if (
        path == SWITCH_PATH
        or path.startswith(NO_STORE_PREFIXES)
        or (path.startswith("/api/") and path.endswith(NO_STORE_SUFFIXES))
    ):
        return "no-store"
    if path == "/api" or path.startswith("/api/"):
        return "private, no-cache"
    return None


def compute_etag(
    app_version: str, data_version: int, local_date: str, path: str, query: str
) -> str:
    """W/"<app_version>-<data_version>-<local_date>-<sha1(path?sorted query)[:16]>"."""
    # A cache key, not a security digest: usedforsecurity=False keeps ruff S324 clean.
    digest = hashlib.sha1(f"{path}?{query}".encode(), usedforsecurity=False).hexdigest()[:16]
    return f'W/"{app_version}-{data_version}-{local_date}-{digest}"'


def if_none_match_matches(header: str | None, etag: str) -> bool:
    """Weak comparison against a comma-separated If-None-Match list; `*` matches."""
    if not header:
        return False
    opaque = etag.removeprefix("W/")
    for candidate in header.split(","):
        tag = candidate.strip()
        if tag == "*" or tag.removeprefix("W/") == opaque:
            return True
    return False


def sorted_query(request: Request) -> str:
    return urlencode(sorted(request.query_params.multi_items()))


def _dependency[T](app: FastAPI, dependency: Callable[[], T]) -> Callable[[], T]:
    """The callable FastAPI would use for `dependency`, honouring test overrides."""
    return cast(Callable[[], T], app.dependency_overrides.get(dependency, dependency))


class _TagInputs(NamedTuple):
    app_version: str
    data_version: int
    local_date: str


def _tag_inputs(app: FastAPI) -> _TagInputs:
    """Everything the tag needs except the URL, read before the route runs (D2)."""
    settings = _dependency(app, get_settings)()
    provider = cast(Callable[[], Iterator[Session]], _dependency(app, get_session))
    with contextlib.contextmanager(provider)() as session:
        data_version = cache.read_data_version(session)
    local_date = _filters.today_local(settings.timezone).isoformat()
    return _TagInputs(settings.app_version, data_version, local_date)


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """Cache-Control on every /api response; weak ETag (+304) on eligible GET 200s.

    data_version and the local date are read once per eligible request, before the route
    runs, so the tag can only be older than the body, never newer. A request without a
    session cookie skips that read: every eligible path needs a viewer, so it can never be
    a 200. The route always runs; nothing short-circuits.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        inputs: _TagInputs | None = None
        if etag_eligible(request.method, path) and request.cookies.get(COOKIE_NAME):
            inputs = await run_in_threadpool(_tag_inputs, cast(FastAPI, request.app))
        response = await call_next(request)
        cache_control = cache_control_for(path)
        if cache_control is not None:
            response.headers["Cache-Control"] = cache_control
        if inputs is None or response.status_code != 200:
            return response
        etag = compute_etag(*inputs, path, sorted_query(request))
        if if_none_match_matches(request.headers.get("if-none-match"), etag):
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": cache_control or "private, no-cache"},
            )
        response.headers["ETag"] = etag
        return response
