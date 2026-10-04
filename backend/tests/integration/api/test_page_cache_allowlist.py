"""The page-cache allowlist pins (Plan 19 D30; §5.1)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from sunday_clays.api import page_cache as pc
from sunday_clays.api.app import PUBLIC_ROUTE_MODULES, create_app
from sunday_clays.auth.deps import current_role, require_viewer
from sunday_clays.config import get_settings
from sunday_clays.db import get_session

ALLOWED: set[Callable[..., Any]] = {require_viewer, current_role, get_settings, get_session}
NEVER = (
    "/api/bumps",
    "/api/pageviews",
    "/api/features",
    "/api/meta",
    "/api/health",
    "/api/predictions/next",
    "/api/club/milestones",
    "/api/shooters/{id}/summary",
    "/api/club-events",
    "/api/club-events/{event_id}",
    "/api/club-events/{event_id}/signup-check",
)


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return create_app()


def _context(app: FastAPI, template: str) -> Any:
    (found,) = [
        c
        for c in iter_route_contexts(app.routes)
        if isinstance(c.original_route, APIRoute)
        and c.path_format == template
        and "GET" in (c.methods or set())
    ]
    return found


def _problems(dependant: Dependant, where: str) -> list[str]:
    problems = []
    if dependant.request_param_name or dependant.response_param_name:
        problems.append(f"{where}: reads Request/Response")
    if dependant.cookie_params or dependant.header_params:
        problems.append(f"{where}: reads cookies or headers")
    if any(str(f.alias) == "device_id" for f in dependant.query_params):
        problems.append(f"{where}: takes a device_id")
    for sub in dependant.dependencies:
        if sub.call in ALLOWED:
            continue  # require_viewer -> current_role reads the cookie by design; that is the role
        if getattr(sub.call, "feature_gate_key", None) is not None:
            problems.append(f"{where}: has a feature_gate")
        else:
            problems.append(f"{where}: depends on {getattr(sub.call, '__name__', sub.call)}")
    return problems


def test_every_template_names_exactly_one_get_route(app: FastAPI) -> None:
    assert len(pc.resolve_allowlist(app, pc.ALLOWLIST)) == len(pc.ALLOWLIST)


def test_allowlist_has_no_gated_admin_or_public_route(app: FastAPI) -> None:
    problems = []
    for template in pc.ALLOWLIST:
        context = _context(app, template)
        module = context.original_route.endpoint.__module__.rsplit(".", 1)[-1]
        if module in PUBLIC_ROUTE_MODULES or module.startswith("admin_"):
            problems.append(f"{template}: from module {module}")
        problems += _problems(context.dependant, template)
    assert problems == []


@pytest.mark.parametrize("template", NEVER)
def test_named_exclusions_are_not_allowlisted(template: str) -> None:
    assert template not in pc.ALLOWLIST
    assert not any(t.startswith(("/api/weather/", "/api/og/", "/api/admin/")) for t in pc.ALLOWLIST)


def test_a_bogus_template_fails_startup() -> None:
    with pytest.raises(ValueError, match="/api/nope names 0 GET routes"):
        create_app(page_cache_allowlist=("/api/nope",))
