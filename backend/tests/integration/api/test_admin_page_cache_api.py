"""GET /api/admin/page-cache (Plan 19 §3.7.6)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version


def test_status_shape_for_an_admin(fx_admin_client: TestClient, fx_session: Session) -> None:
    response = fx_admin_client.get("/api/admin/page-cache")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    body = response.json()
    assert body["forced_off"] is True  # pytest default: off
    assert body["enabled"] is False
    assert (body["rows"], body["bytes"], body["last_warm"]) == (0, 0, None)
    assert body["current"]["data_version"] == get_data_version(fx_session)


def test_viewer_gets_403(fx_viewer_client: TestClient) -> None:
    assert fx_viewer_client.get("/api/admin/page-cache").status_code == 403
