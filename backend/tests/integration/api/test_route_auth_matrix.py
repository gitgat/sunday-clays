"""Every route's auth requirement, enumerated from the live app (C2, C8).

Walks the effective routes of ``create_app()`` at runtime, so routers added by later
waves are covered without editing this file.
"""

from datetime import date
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient

from sunday_clays.api.routes import discover_routers
from sunday_clays.db import get_session

PUBLIC = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    # Plan 19 D6: link previews for crawlers, which cannot log in (no names, no scores)
    *{
        (method, path)
        for method in ("GET", "HEAD")
        for path in (
            "/api/og/page/",
            "/api/og/page/{path}",
            "/api/og/image/generic.png",
            "/api/og/image/sunday/{day}.png",
        )
    },
}


def _calls(app: FastAPI) -> list[tuple[str, str, str]]:
    """(method, path template, concrete url) for every API route the app serves."""
    calls: list[tuple[str, str, str]] = []
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        if not isinstance(route, APIRoute) or context.path_format is None:
            continue
        values = {
            param.alias: "2026-09-13" if param.field_info.annotation is date else "1"
            for param in route.dependant.path_params
        }
        url = context.path_format.format(**values)
        calls.extend((method, context.path_format, url) for method in sorted(context.methods or ()))
    return calls


def test_walk_sees_the_auth_routes(anon_client: TestClient) -> None:
    seen = {(method, path) for method, path, _ in _calls(cast(FastAPI, anon_client.app))}
    assert {("GET", "/api/auth/me"), *PUBLIC} <= seen


def test_every_session_dependency_is_function_scoped(anon_client: TestClient) -> None:
    """C2 amendment: a request-scoped get_session commits after the response is sent.

    ``app.routes`` holds only FastAPI's included-router wrappers (Decision D23), so the walk
    goes through ``iter_route_contexts`` and each route's effective dependant, which also
    carries the include-time role dependencies.
    """
    scopes: dict[tuple[str, str], list[str | None]] = {}

    def walk(dependant: Dependant, key: tuple[str, str]) -> None:
        for sub in dependant.dependencies:
            if sub.call is get_session:
                scopes.setdefault(key, []).append(sub.scope)
            walk(sub, key)

    for context in iter_route_contexts(cast(FastAPI, anon_client.app).routes):
        if not isinstance(context.original_route, APIRoute) or context.path_format is None:
            continue
        dependant: Dependant = context.dependant
        for method in sorted(context.methods or ()):
            walk(dependant, (method, context.path_format))
    assert scopes.get(("POST", "/api/auth/login")) == ["function"]  # the walk is not vacuous
    wrong = {route: found for route, found in scopes.items() if set(found) != {"function"}}
    assert wrong == {}


@pytest.mark.parametrize("extra_headers", [{}, {"If-None-Match": "*"}])
def test_every_route_needs_a_session_except_public(
    anon_client: TestClient, extra_headers: dict[str, str]
) -> None:
    wrong: list[str] = []
    for method, path, url in _calls(cast(FastAPI, anon_client.app)):
        status = anon_client.request(method, url, headers=extra_headers).status_code
        public = (method, path) in PUBLIC
        if (public and status == 401) or (not public and status != 401):
            wrong.append(f"{method} {path} -> {status}")
    assert wrong == []


def test_viewer_gets_403_on_every_admin_route(
    anon_client: TestClient, viewer_client: TestClient
) -> None:
    wrong: list[str] = []
    for method, path, url in _calls(cast(FastAPI, anon_client.app)):
        if path.startswith("/api/admin/"):
            status = viewer_client.request(method, url).status_code
            if status != 403:
                wrong.append(f"{method} {path} -> {status}")
    assert wrong == []


def test_admin_paths_are_defined_only_in_admin_modules(anon_client: TestClient) -> None:
    from_admin_modules: set[tuple[str, str]] = set()
    misplaced: list[str] = []
    for module_name, router in discover_routers():
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            if module_name.startswith("admin_"):
                from_admin_modules |= {(m, route.path_format) for m in route.methods}
            elif route.path_format.startswith("/api/admin"):
                misplaced.append(f"{module_name}: {route.path_format}")
    served = [
        (m, p) for m, p, _ in _calls(cast(FastAPI, anon_client.app)) if p.startswith("/api/admin")
    ]
    assert misplaced == []
    assert [call for call in served if call not in from_admin_modules] == []
