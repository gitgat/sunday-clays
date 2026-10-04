from typing import Annotated

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel

from sunday_clays.api import app as app_module
from sunday_clays.auth.deps import Actor, admin_actor
from sunday_clays.auth.sessions import COOKIE_NAME, Role, issue_session
from sunday_clays.config import Settings


class ProbeOut(BaseModel):
    who: str


def _probe_routers() -> list[tuple[str, APIRouter]]:
    """Probe routes; only /api/admin/actor-probe declares an auth dependency of its own.

    The other three rely on create_app()'s wiring alone, so a wrong role choice fails a test.
    All are POST (Decision D24): Plan 06's ETag middleware reads the DB for eligible GETs, and a
    TestClient POST carries no Origin, so the CSRF guard lets it through.
    """
    admin, viewer, public = APIRouter(), APIRouter(), APIRouter()

    @admin.post("/api/admin/probe")
    def admin_probe() -> ProbeOut:
        return ProbeOut(who="admin-route")

    @admin.post("/api/admin/actor-probe")
    def admin_actor_probe(actor: Annotated[Actor, Depends(admin_actor)]) -> ProbeOut:
        return ProbeOut(who=f"{actor.role}@{actor.ip}")

    @viewer.post("/api/probe")
    def viewer_probe() -> ProbeOut:
        return ProbeOut(who="viewer-route")

    @public.post("/api/public-probe")
    def public_probe() -> ProbeOut:
        return ProbeOut(who="public-route")

    return [("admin_probe", admin), ("health", public), ("probe", viewer)]


@pytest.fixture
def probe_client(monkeypatch: pytest.MonkeyPatch, auth_env: Settings) -> TestClient:
    monkeypatch.setattr(app_module, "discover_routers", _probe_routers)
    return TestClient(app_module.create_app(page_cache_allowlist=()))


def _as(test_client: TestClient, settings: Settings, role: Role | None) -> TestClient:
    test_client.cookies.clear()
    if role is not None:
        test_client.cookies.set(COOKIE_NAME, issue_session(settings, role))
    return test_client


@pytest.mark.parametrize(
    ("role", "admin_status", "viewer_status", "public_status"),
    [(None, 401, 401, 200), ("viewer", 403, 200, 200), ("admin", 200, 200, 200)],
)
def test_module_name_decides_required_role(
    probe_client: TestClient,
    auth_env: Settings,
    role: Role | None,
    admin_status: int,
    viewer_status: int,
    public_status: int,
) -> None:
    client = _as(probe_client, auth_env, role)
    assert client.post("/api/admin/probe").status_code == admin_status
    assert client.post("/api/probe").status_code == viewer_status
    assert client.post("/api/public-probe").status_code == public_status


def test_admin_actor_carries_role_and_bucketed_ip(
    probe_client: TestClient, auth_env: Settings
) -> None:
    client = _as(probe_client, auth_env, "admin")
    response = client.post("/api/admin/actor-probe", headers={"X-Real-IP": "2001:db8:5:6::9"})
    assert response.json() == {"who": "admin@2001:db8:5:6::/64"}


def test_denials_use_the_error_envelope(probe_client: TestClient, auth_env: Settings) -> None:
    assert _as(probe_client, auth_env, None).post("/api/probe").json() == {
        "error": {"code": "unauthenticated", "message": "Log in to continue"}
    }
    assert _as(probe_client, auth_env, "viewer").post("/api/admin/probe").json() == {
        "error": {"code": "forbidden", "message": "Admin access required"}
    }
