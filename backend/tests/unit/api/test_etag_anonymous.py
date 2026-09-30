"""CacheHeadersMiddleware with the database down: a request without a session cookie never
reads data_version, because every ETag-eligible path needs a viewer and so can't be a 200."""

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.app import create_app
from sunday_clays.db import SessionFactory


def test_anonymous_eligible_get_never_touches_the_database(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Unbound, so get_session would bind to settings_env's closed port and answer 500.
    monkeypatch.setitem(SessionFactory.kw, "bind", None)
    client = TestClient(create_app(), raise_server_exceptions=False)

    meta = client.get("/api/meta", headers={"If-None-Match": "*"})
    unknown = client.get("/api/no-such-route")

    assert (meta.status_code, unknown.status_code) == (401, 404)
    assert meta.headers["cache-control"] == "private, no-cache"
    assert unknown.headers["cache-control"] == "private, no-cache"
    assert "etag" not in meta.headers
