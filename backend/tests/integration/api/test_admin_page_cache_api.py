"""GET /api/admin/page-cache (Plan 19 §3.7.6)."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.domain.features import LAST_WARM_KEY


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
    from sunday_clays.config import get_settings as _settings

    assert body["current"]["app_version"] == _settings().app_version
    from sunday_clays.config import get_settings
    from sunday_clays.jobs.page_warm import warm_targets

    assert body["targets"] == warm_targets(fx_session, get_settings())


def test_viewer_gets_403(fx_viewer_client: TestClient) -> None:
    assert fx_viewer_client.get("/api/admin/page-cache").status_code == 403


def test_a_malformed_last_warm_row_is_none_and_logs_a_warning(
    fx_admin_client: TestClient, fx_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    fx_session.execute(
        text('INSERT INTO app_state (key, value) VALUES (:k, \'{"warmed": "lots"}\'::jsonb)'),
        {"k": LAST_WARM_KEY},
    )
    with caplog.at_level(logging.WARNING, logger="sunday_clays.api.routes.admin_page_cache"):
        response = fx_admin_client.get("/api/admin/page-cache")
    assert response.status_code == 200
    assert response.json()["last_warm"] is None
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


def test_last_warm_carries_its_app_version_and_old_rows_read_as_none(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    """The status line compares last_warm to current (data_version, local_date, app_version);
    a row written before app_version existed reads as None, never as a match."""
    row: dict[str, object] = {
        "data_version": 1,
        "local_date": "2026-10-02",
        "finished_at": "2026-10-02T10:00:00Z",
        "warmed": 25,
        "skipped": 0,
        "failed": 0,
        "seconds": 3.5,
    }
    upsert = text(
        "INSERT INTO app_state (key, value) VALUES (:k, CAST(:v AS jsonb))"
        " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
    )
    fx_session.execute(
        upsert, {"k": LAST_WARM_KEY, "v": json.dumps({**row, "app_version": "rel-9"})}
    )
    last = fx_admin_client.get("/api/admin/page-cache").json()["last_warm"]
    assert last["app_version"] == "rel-9"
    fx_session.execute(upsert, {"k": LAST_WARM_KEY, "v": json.dumps(row)})
    last = fx_admin_client.get("/api/admin/page-cache").json()["last_warm"]
    assert last["app_version"] is None
