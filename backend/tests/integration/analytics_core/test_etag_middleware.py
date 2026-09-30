from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from sunday_clays.analytics import cache
from sunday_clays.analytics.pipeline import bump_data_version
from sunday_clays.api.app import create_app
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.jobs.queue import enqueue

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_viewer_get_gets_weak_etag_and_304_on_match(viewer_client: TestClient) -> None:
    first = viewer_client.get("/api/meta")
    assert first.status_code == 200
    tag = first.headers["etag"]
    assert tag.startswith('W/"')
    assert first.headers["cache-control"] == "private, no-cache"

    again = viewer_client.get("/api/meta", headers={"If-None-Match": tag})

    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["etag"] == tag


def test_query_string_order_does_not_change_etag(viewer_client: TestClient) -> None:
    a = viewer_client.get("/api/meta?b=2&a=1").headers["etag"]
    b = viewer_client.get("/api/meta?a=1&b=2").headers["etag"]
    c = viewer_client.get("/api/meta?a=1&b=3").headers["etag"]
    assert a == b
    assert c != a


def test_data_version_bump_changes_etag(viewer_client: TestClient, session: Session) -> None:
    before = viewer_client.get("/api/meta").headers["etag"]
    bump_data_version(session)  # what rebuild_live and run_pipeline do (Plan 03 T7)

    after = viewer_client.get("/api/meta", headers={"If-None-Match": before})

    assert after.status_code == 200
    assert after.headers["etag"] != before


def test_app_version_change_changes_etag(viewer_client: TestClient) -> None:
    app: Any = viewer_client.app
    before = viewer_client.get("/api/meta").headers["etag"]
    base = app.dependency_overrides.get(get_settings, get_settings)()
    bumped = base.model_copy(update={"app_version": f"{base.app_version}-next"})
    app.dependency_overrides[get_settings] = lambda: bumped

    after = viewer_client.get("/api/meta", headers={"If-None-Match": before})

    assert after.status_code == 200
    assert after.headers["etag"] != before


def test_local_date_change_changes_etag(
    viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = viewer_client.get("/api/meta").headers["etag"]
    real = _filters.today_local
    monkeypatch.setattr(_filters, "today_local", lambda tz: real(tz).replace(year=2099))

    after = viewer_client.get("/api/meta", headers={"If-None-Match": before})

    assert after.status_code == 200
    assert after.headers["etag"] != before


def test_local_date_is_read_before_the_route_runs(
    viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A request straddling local midnight is tagged with the day its body was computed on."""
    app: Any = viewer_client.app
    clock = {"today": date(2026, 9, 27)}
    monkeypatch.setattr(_filters, "today_local", lambda tz: clock["today"])

    @app.get("/api/_straddles_midnight")
    def straddles_midnight() -> dict[str, str]:
        clock["today"] = date(2026, 9, 28)  # local midnight passes while the route runs
        return {"as_of": "2026-09-27"}

    r = viewer_client.get("/api/_straddles_midnight")

    assert r.status_code == 200
    assert "-2026-09-27-" in r.headers["etag"]


def test_tag_and_meta_read_data_version_through_the_cache_module(
    viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache, "read_data_version", lambda session: 424242)

    r = viewer_client.get("/api/meta")

    assert r.json()["data_version"] == 424242
    assert "-424242-" in r.headers["etag"]


def test_health_has_no_etag(client: TestClient) -> None:
    r = client.get("/api/health", headers={"If-None-Match": "*"})
    assert r.status_code == 200
    assert "etag" not in r.headers
    assert r.headers["cache-control"] == "private, no-cache"


def test_non_api_paths_get_no_cache_headers(client: TestClient) -> None:
    r = client.get("/index.html", headers={"If-None-Match": "*"})
    assert r.status_code == 404
    assert "cache-control" not in r.headers
    assert "etag" not in r.headers


def test_middleware_rejections_still_get_cache_control(client: TestClient) -> None:
    r = client.post(
        "/api/auth/login",
        json={"password": "x"},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
    assert r.headers["cache-control"] == "no-store"

    # Content-Length 300,002 > the 262,144-byte limit for non-import /api paths (C2).
    big = client.post(
        "/api/auth/login",
        content=b"{" + b" " * 300_000 + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert big.status_code == 413
    assert big.headers["cache-control"] == "no-store"


def test_401_is_never_turned_into_304(client: TestClient) -> None:
    r = client.get("/api/meta", headers={"If-None-Match": "*"})
    assert r.status_code == 401
    assert "etag" not in r.headers


def test_404_is_never_turned_into_304(viewer_client: TestClient) -> None:
    r = viewer_client.get("/api/no-such-route", headers={"If-None-Match": "*"})
    assert r.status_code == 404
    assert "etag" not in r.headers


def test_staging_an_import_changes_admin_imports_list(
    admin_client: TestClient, stations_bytes: bytes
) -> None:
    before = admin_client.get("/api/admin/imports")
    assert before.status_code == 200
    assert "etag" not in before.headers
    assert before.headers["cache-control"] == "no-store"
    meta_tag = admin_client.get("/api/meta").headers["etag"]

    staged = admin_client.post(
        "/api/admin/imports", files={"file": ("stations.xlsx", stations_bytes, XLSX)}
    )
    assert staged.is_success
    after = admin_client.get("/api/admin/imports", headers={"If-None-Match": f"{meta_tag}, *"})

    assert after.status_code == 200
    assert len(after.json()) == len(before.json()) + 1


def test_admin_job_status_is_never_cached(admin_client: TestClient, session: Session) -> None:
    job_id = enqueue(session, "etag_probe")
    seen = []
    for status in ("queued", "running", "failed"):
        session.execute(
            text("UPDATE jobs SET status = :s WHERE id = :i"),
            {"s": status, "i": job_id},
        )
        r = admin_client.get(f"/api/admin/jobs/{job_id}", headers={"If-None-Match": "*"})
        assert r.status_code == 200
        assert "etag" not in r.headers
        seen.append(r.json()["status"])
    assert seen == ["queued", "running", "failed"]


def test_me_after_logout_is_401_not_304(viewer_client: TestClient) -> None:
    assert viewer_client.get("/api/auth/me").json()["role"] == "viewer"
    viewer_client.post("/api/auth/logout")

    r = viewer_client.get("/api/auth/me", headers={"If-None-Match": "*"})

    assert r.status_code == 401
    assert r.headers["cache-control"] == "no-store"


def test_me_after_admin_logout_then_viewer_login_is_viewer(
    request: pytest.FixtureRequest,
) -> None:
    viewer: TestClient = request.getfixturevalue("viewer_client")
    viewer_cookie = viewer.cookies.get("sc_session")
    admin: TestClient = request.getfixturevalue("admin_client")
    assert admin.get("/api/auth/me").json()["role"] == "admin"
    admin.post("/api/auth/logout")

    r = admin.get(
        "/api/auth/me",
        headers={"Cookie": f"sc_session={viewer_cookie}", "If-None-Match": "*"},
    )

    assert r.status_code == 200
    assert r.json()["role"] == "viewer"
    assert "etag" not in r.headers


def test_production_get_session_path_returns_every_connection(
    committed_engine: Engine, auth_env: Settings, login_passwords: dict[str, str]
) -> None:
    """No get_session override: the middleware opens, commits and closes its own session."""
    with TestClient(create_app()) as viewer:
        login = viewer.post("/api/auth/login", json={"password": login_passwords["viewer"]})
        assert login.status_code == 200
        baseline = committed_engine.pool.checkedout()

        first = viewer.get("/api/meta")
        again = viewer.get("/api/meta", headers={"If-None-Match": first.headers["etag"]})
        with committed_engine.begin() as conn:
            bump_data_version(Session(bind=conn))
        bumped = viewer.get("/api/meta", headers={"If-None-Match": first.headers["etag"]})

        assert (first.status_code, again.status_code, bumped.status_code) == (200, 304, 200)
        assert bumped.json()["data_version"] == first.json()["data_version"] + 1
        assert bumped.headers["etag"] != first.headers["etag"]
        assert committed_engine.pool.checkedout() == baseline
