"""Error-shape tests. The probe routes are POSTs on purpose: from Plan 06 T1 on, an eligible
GET /api/* request with a session cookie first passes through CacheHeadersMiddleware, which
reads settings and the database, and these tests run with neither."""

import logging

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.app import create_app
from sunday_clays.domain.errors import ConflictError, DomainError, NotFoundError


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (DomainError("unreadable_file", "Could not read it"), 400),
        (NotFoundError("not_found", "No such import"), 404),
        (ConflictError("removals_not_confirmed", "Confirm the removals"), 409),
    ],
)
def test_domain_errors_become_json_with_their_status(error: DomainError, status: int) -> None:
    app = create_app()

    @app.post("/api/_raise")
    def raise_it() -> None:
        raise error

    response = TestClient(app).post("/api/_raise")

    assert response.status_code == status
    assert response.json() == {"error": {"code": error.code, "message": error.message}}


def test_unexpected_error_is_logged_and_hidden(caplog: pytest.LogCaptureFixture) -> None:
    app = create_app()

    @app.post("/api/_boom")
    def boom() -> None:
        raise RuntimeError("internal detail hunter2")

    with caplog.at_level(logging.ERROR, logger="sunday_clays.api.errors"):
        response = TestClient(app, raise_server_exceptions=False).post("/api/_boom")

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal", "message": "Internal server error"}}
    assert "hunter2" not in response.text
    records = [r for r in caplog.records if r.name == "sunday_clays.api.errors"]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert isinstance(records[0].exc_info[1], RuntimeError)


def test_unexpected_error_is_never_cached() -> None:
    """The catch-all 500 is served outside CacheHeadersMiddleware, so it sets no-store itself."""
    app = create_app()

    @app.post("/api/_boom")
    def boom() -> None:
        raise RuntimeError("boom")

    response = TestClient(app, raise_server_exceptions=False).post("/api/_boom")

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
