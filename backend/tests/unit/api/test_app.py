from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.app import create_app
from sunday_clays.config import SECRET_FIELDS, ConfigError


def test_create_app_reads_no_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SECRET_FIELDS:
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv(f"{name.upper()}_FILE", raising=False)

    app = create_app()

    assert "/api/health" in app.openapi()["paths"]


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_docs_and_schema_are_not_served(settings_env: None, path: str) -> None:
    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 404


def test_startup_fails_on_conflicting_secret_sources(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret_file = tmp_path / "session_secret"
    secret_file.write_text("x" * 40, encoding="utf-8")
    monkeypatch.setenv("SESSION_SECRET_FILE", str(secret_file))

    with pytest.raises(ConfigError, match="SESSION_SECRET_FILE"), TestClient(create_app()):
        pass


def test_og_is_the_only_new_public_module() -> None:
    from sunday_clays.api.app import PUBLIC_ROUTE_MODULES, role_dependencies

    assert frozenset({"health", "auth", "og"}) == PUBLIC_ROUTE_MODULES
    assert role_dependencies("og") == []
