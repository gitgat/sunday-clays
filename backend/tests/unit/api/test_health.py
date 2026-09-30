import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.app import create_app


def test_health_reports_ok_and_the_app_version(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_VERSION", "sha-abc1234")

    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "sha-abc1234"}
