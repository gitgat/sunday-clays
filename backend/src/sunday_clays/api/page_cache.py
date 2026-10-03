"""The page cache (Plan 19 §3.7, D28-D33): finished 200 JSON bodies of an exact allowlist of GET
routes, stored in ``response_cache`` and keyed by everything the body may depend on.

It is an inner middleware under ``CacheHeadersMiddleware``: the outer one reads data_version, the
local date and the ``page_cache`` switch once (``request.state``) and still adds Cache-Control and
the ETag (and answers 304) for a cached body exactly as for a computed one. No ETag is stored.
A hit never runs the route; that is safe because the pin tests prove an allowlisted route depends
only on require_viewer, the session, settings and its own path and query parameters.
"""

import asyncio
import contextlib
import logging
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from fastapi import FastAPI, Request, Response
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import compile_path
from starlette.types import ASGIApp

from sunday_clays.api.etag import _dependency, _TagInputs, sorted_query
from sunday_clays.auth.sessions import COOKIE_NAME, load_session
from sunday_clays.config import get_settings
from sunday_clays.db import get_session

logger = logging.getLogger(__name__)

KEY_VERSION: Final = "v1"
MAX_BODY_BYTES: Final = 2 * 1024 * 1024
MAX_ROWS = 2000
PRUNE_TO_ROWS: Final = 1500
MAX_KEY_URL: Final = 2048
FOLLOW_TIMEOUT_S: Final = 30.0
CACHE_HEADER: Final = "X-Page-Cache"

#: Exact GET route templates (D30). A route joins only on purpose, after the pin tests pass.
ALLOWLIST: Final[tuple[str, ...]] = (
    "/api/insights/home",
    "/api/insights/club",
    "/api/insights/leaderboards",
    "/api/insights/records",
    "/api/insights/stations",
    "/api/insights/sundays/{date}",
    "/api/insights/shooters/{id}",
    "/api/events",
    "/api/events/{date}",
    "/api/events/{date}/achievements",
    "/api/leaderboards",
    "/api/leaderboards/movers",
    "/api/leaderboards/history",
    "/api/stations",
    "/api/stations/{label}",
    "/api/shooters/{id}/stations",
    "/api/club/summary",
    "/api/club/attendance",
    "/api/club/cohorts",
    "/api/club/distribution",
    "/api/club/first-rounds",
    "/api/club/regulars",
    "/api/club/conversion",
    "/api/club/parity",
    "/api/club/trends",
    "/api/records",
    "/api/achievements",
    "/api/achievements/{code}",
    "/api/shooters/{id}/achievements",
    "/api/shooters",
    "/api/shooters/{id}",
    "/api/shooters/{id}/rounds",
    "/api/shooters/{id}/special",
    "/api/shooters/{id}/rating",
    "/api/shooters/{id}/splits",
    "/api/shooters/{id}/insights",
    "/api/yir/{year}",
    "/api/yir/{year}/shooters/{id}",
    "/api/on-this-day",
)


@dataclass(frozen=True)
class CachedRoute:
    template: str
    regex: re.Pattern[str]
    query_names: frozenset[str]


def compile_template(template: str) -> re.Pattern[str]:
    """The path regex Starlette compiles for a route template (what FastAPI matches with)."""
    return compile_path(template)[0]


def _query_names(dependant: Dependant) -> set[str]:
    names = {str(field.alias) for field in dependant.query_params}
    for sub in dependant.dependencies:
        names |= _query_names(sub)
    return names


def resolve_allowlist(app: FastAPI, templates: Sequence[str]) -> tuple[CachedRoute, ...]:
    """Every template must name exactly one GET route of ``app``, or startup fails (D30)."""
    contexts = [
        c
        for c in iter_route_contexts(app.routes)
        if isinstance(c.original_route, APIRoute) and "GET" in (c.methods or set())
    ]
    resolved = []
    for template in templates:
        found = [c for c in contexts if c.path_format == template]
        if len(found) != 1:
            raise ValueError(f"page cache: {template} names {len(found)} GET routes, not 1")
        dependant = cast(Dependant, found[0].dependant)
        resolved.append(
            CachedRoute(template, compile_template(template), frozenset(_query_names(dependant)))
        )
    # match_route takes the first allowlisted regex that matches, not the route FastAPI will run.
    # So no other GET route may match an allowlisted regex: a later fixed route such as
    # /api/shooters/compare would otherwise be cached as /api/shooters/{id}, past the D30 pins.
    allowlisted = set(templates)
    for c in contexts:
        path = c.path_format
        if path is None or path in allowlisted:
            continue
        clash = next((r.template for r in resolved if r.regex.match(path)), None)
        if clash is not None:
            raise ValueError(f"page cache: GET {path} also matches {clash}")
    return tuple(resolved)


def match_route(routes: Sequence[CachedRoute], path: str) -> CachedRoute | None:
    """The allowlisted route for ``path``; unambiguous because resolve_allowlist rejects any other
    GET route that an allowlisted regex matches."""
    return next((r for r in routes if r.regex.match(path)), None)


def cache_key(
    app_version: str, data_version: int, local_date: str, role: str, path: str, query: str
) -> str:
    """v1|<app_version>|<data_version>|<local_date>|<role>|GET <path>?<sorted query> (D29)."""
    return f"{KEY_VERSION}|{app_version}|{data_version}|{local_date}|{role}|GET {path}?{query}"


def storable(status: int, content_type: str | None, has_set_cookie: bool, size: int) -> bool:
    """Only a clean 200 JSON answer of at most 2 MiB, with no Set-Cookie, is stored (D32)."""
    media = (content_type or "").split(";")[0].strip()
    return (
        status == 200
        and media == "application/json"
        and not has_set_cookie
        and size <= MAX_BODY_BYTES
    )


def bypass_reason(route: CachedRoute, path: str, query: Sequence[tuple[str, str]]) -> str | None:
    """None when the request may use the cache; else why not (never logged with the URL)."""
    if any(name not in route.query_names for name, _ in query):
        return "undeclared"
    if len(path) + sum(len(n) + len(v) + 2 for n, v in query) > MAX_KEY_URL:
        return "too_long"
    return None


@contextlib.contextmanager
def _open_session(app: FastAPI) -> Iterator[Session]:
    """A short session of its own (honouring test overrides), never the route's."""
    provider = cast(Callable[[], Iterator[Session]], _dependency(app, get_session))
    with contextlib.contextmanager(provider)() as session:
        yield session


def _read(app: FastAPI, key: str) -> bytes | None:
    with _open_session(app) as session:
        body = session.execute(
            text("SELECT body FROM response_cache WHERE key = :k"), {"k": key}
        ).scalar()
    return None if body is None else bytes(body)


_INSERT = text(
    "INSERT INTO response_cache (key, data_version, local_date, app_version, role, route, body) "
    "SELECT :key, :data_version, CAST(:local_date AS date), :app_version, :role, :route, :body "
    "WHERE (SELECT count(*) FROM response_cache) < :max_rows "
    "ON CONFLICT (key) DO NOTHING"
)


def _write(app: FastAPI, key: str, inputs: _TagInputs, role: str, route: str, body: bytes) -> None:
    with _open_session(app) as session:
        session.execute(
            _INSERT,
            {
                "key": key,
                "data_version": inputs.data_version,
                "local_date": inputs.local_date,
                "app_version": inputs.app_version,
                "role": role,
                "route": route,
                "body": body,
                "max_rows": MAX_ROWS,
            },
        )


def _tagged(response: Response, value: str) -> Response:
    response.headers[CACHE_HEADER] = value
    return response


def _hit(body: bytes) -> Response:
    return _tagged(Response(content=body, status_code=200, media_type="application/json"), "hit")


class PageCacheMiddleware(BaseHTTPMiddleware):
    """Serve, or compute once and store, allowlisted viewer GET bodies (§3.7.3)."""

    def __init__(self, app: ASGIApp, routes: tuple[CachedRoute, ...]) -> None:
        super().__init__(app)
        self.routes = routes
        self.flights: dict[str, asyncio.Future[bytes | None]] = {}

    def _key(self, request: Request, route: CachedRoute) -> tuple[str, _TagInputs, str] | None:
        if request.method != "GET":
            return None
        state: Any = request.state
        inputs = cast(_TagInputs | None, getattr(state, "tag_inputs", None))
        if inputs is None or not getattr(state, "page_cache_on", False):
            return None
        settings = _dependency(cast(FastAPI, request.app), get_settings)()
        token = request.cookies.get(COOKIE_NAME)
        role = load_session(settings, token) if token else None
        query = request.query_params.multi_items()
        if role is None or bypass_reason(route, request.url.path, query) is not None:
            return None
        key = cache_key(
            inputs.app_version,
            inputs.data_version,
            inputs.local_date,
            role,
            request.url.path,
            sorted_query(request),
        )
        return key, inputs, role

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        route = match_route(self.routes, request.url.path)
        if route is None:
            return await call_next(request)  # not allowlisted: no header at all
        keyed = self._key(request, route)
        if keyed is None:
            return _tagged(await call_next(request), "bypass")
        key, inputs, role = keyed
        app = cast(FastAPI, request.app)
        try:
            body = await run_in_threadpool(_read, app, key)
        except Exception:
            logger.warning("page cache unavailable for %s; answering uncached", route.template)
            return _tagged(await call_next(request), "bypass")
        if body is not None:
            return _hit(body)
        flight = self.flights.get(key)
        if flight is not None:  # D33: a follower waits for the leader, then uses its body
            try:
                leader_body = await asyncio.wait_for(asyncio.shield(flight), FOLLOW_TIMEOUT_S)
            except TimeoutError:
                leader_body = None  # waited 30 s: compute alone, store nothing
            if leader_body is not None:
                return _hit(leader_body)
            return _tagged(await call_next(request), "miss")
        flight = asyncio.get_running_loop().create_future()
        self.flights[key] = flight
        shared: bytes | None = None
        try:
            response = await call_next(request)
            content = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]
            if storable(
                response.status_code,
                response.headers.get("content-type"),
                "set-cookie" in response.headers,
                len(content),
            ):
                shared = content
                try:
                    await run_in_threadpool(_write, app, key, inputs, role, route.template, content)
                except Exception:
                    logger.warning("page cache unavailable for %s; not stored", route.template)
            rebuilt = Response(content=content, status_code=response.status_code)
            rebuilt.raw_headers = [*response.raw_headers]  # the route's own headers, unchanged
            return _tagged(rebuilt, "miss")
        finally:
            if not flight.done():
                flight.set_result(shared)
            self.flights.pop(key, None)
