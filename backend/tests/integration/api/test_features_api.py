"""GET /api/features, /api/admin/features, PUT, and feature_gate (Plan 19 D2, D3; §5.1, §5.2)."""

from typing import cast

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.api.routes._features import feature_gate
from sunday_clays.domain.features import FEATURES
from sunday_clays.models import Base

AUDIT = Base.metadata.tables["audit_log"]
ALL_KEYS = {f.key for f in FEATURES}


def _probe(app: FastAPI) -> None:
    """A gated viewer route, as T6/T7 will declare them."""
    router = APIRouter()

    @router.get("/api/probe-gated", dependencies=[feature_gate("summary_card")])
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    app.include_router(router)


@pytest.fixture
def gated(viewer_client: TestClient) -> TestClient:
    _probe(cast(FastAPI, viewer_client.app))
    return viewer_client


def test_viewer_sees_only_enabled_keys(viewer_client: TestClient, admin_client: TestClient) -> None:
    assert viewer_client.get("/api/features").json() == {"switches": {}}
    assert admin_client.put("/api/admin/features/pwa", json={"enabled": True}).status_code == 200
    assert viewer_client.get("/api/features").json() == {"switches": {"pwa": True}}


def test_admin_sees_every_key(admin_client: TestClient) -> None:
    switches = admin_client.get("/api/features").json()["switches"]
    assert set(switches) == ALL_KEYS
    assert set(switches.values()) == {False}


def test_features_without_a_session_is_401(anon_client: TestClient) -> None:
    anon_client.cookies.clear()
    assert anon_client.get("/api/features").status_code == 401


def test_features_is_no_store_and_never_tagged(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/features")
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers


def test_a_flip_shows_on_the_very_next_request(
    viewer_client: TestClient, admin_client: TestClient
) -> None:
    for enabled in (True, False, True):
        admin_client.put("/api/admin/features/club_milestones", json={"enabled": enabled})
        switches = viewer_client.get("/api/features").json()["switches"]
        assert ("club_milestones" in switches) is enabled


def test_admin_list_has_labels_dates_and_order(admin_client: TestClient) -> None:
    admin_client.put("/api/admin/features/pwa", json={"enabled": True})
    rows = admin_client.get("/api/admin/features").json()
    assert [r["key"] for r in rows] == [f.key for f in FEATURES]
    pwa = next(r for r in rows if r["key"] == "pwa")
    assert pwa["label"] == "Add to Home Screen"
    assert pwa["enabled"] is True
    assert pwa["updated_on"] is not None
    assert next(r for r in rows if r["key"] == "tour_glossary")["updated_on"] is None


def test_put_is_audited_once_per_call(admin_client: TestClient, session: Session) -> None:
    admin_client.put("/api/admin/features/pwa", json={"enabled": True})
    admin_client.put("/api/admin/features/pwa", json={"enabled": False})
    rows = session.execute(
        select(AUDIT.c.action, AUDIT.c.details).where(AUDIT.c.action == "feature_switch")
    ).all()
    assert [r.details for r in rows] == [
        {"key": "pwa", "enabled": True},
        {"key": "pwa", "enabled": False},
    ]


def test_put_unknown_key_is_404(admin_client: TestClient) -> None:
    response = admin_client.put("/api/admin/features/nope", json={"enabled": True})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "feature_not_found"


@pytest.mark.parametrize(
    "body", [{}, {"enabled": "yes"}, {"enabled": 1}, {"enabled": True, "extra": 1}, None]
)
def test_put_other_bodies_are_422(admin_client: TestClient, body: object) -> None:
    assert admin_client.put("/api/admin/features/pwa", json=body).status_code == 422


def test_viewer_cannot_put(viewer_client: TestClient) -> None:
    assert viewer_client.put("/api/admin/features/pwa", json={"enabled": True}).status_code == 403


def test_gate_viewer_off_is_the_unknown_route_404(gated: TestClient) -> None:
    gated_404 = gated.get("/api/probe-gated")
    unknown_404 = gated.get("/api/no-such-route")
    assert gated_404.status_code == unknown_404.status_code == 404
    assert gated_404.json() == unknown_404.json() == {"detail": "Not Found"}


def test_gate_viewer_on_is_200(gated: TestClient, admin_client: TestClient) -> None:
    admin_client.put("/api/admin/features/summary_card", json={"enabled": True})
    assert gated.get("/api/probe-gated").json() == {"ok": "yes"}


def test_gate_admin_off_is_200(gated: TestClient, admin_client: TestClient) -> None:
    assert admin_client.get("/api/probe-gated").status_code == 200


def test_gate_without_session_is_401(gated: TestClient, anon_client: TestClient) -> None:
    anon_client.cookies.clear()
    assert anon_client.get("/api/probe-gated").status_code == 401


def test_gated_route_off_is_untagged_404_even_with_if_none_match(
    gated: TestClient, admin_client: TestClient
) -> None:
    """Review Focus 1: a 200 tagged while on can never be revalidated to 304 after a switch-off."""
    admin_client.put("/api/admin/features/summary_card", json={"enabled": True})
    on = gated.get("/api/probe-gated")
    assert on.status_code == 200
    assert "etag" in on.headers
    admin_client.put("/api/admin/features/summary_card", json={"enabled": False})
    off = gated.get("/api/probe-gated", headers={"If-None-Match": on.headers["etag"]})
    assert off.status_code == 404
    assert "etag" not in off.headers
