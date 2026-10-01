"""/api/admin/analytics/* (Plan 16 Task 2): admin-only, read-only, no-store, windowed."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.models import Base, PageView

PATHS = ("visitors", "pages", "bumps", "me-states")
PT = ZoneInfo("America/Los_Angeles")
A = uuid.UUID("00000000-0000-4000-8000-00000000000a")


@pytest.mark.parametrize("path", PATHS)
def test_admin_only_and_never_cached(
    path: str, admin_client: TestClient, viewer_client: TestClient
) -> None:
    response = admin_client.get(f"/api/admin/analytics/{path}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    refused = viewer_client.get(f"/api/admin/analytics/{path}")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize("path", PATHS)
def test_a_since_after_as_of_is_400(path: str, admin_client: TestClient) -> None:
    response = admin_client.get(
        f"/api/admin/analytics/{path}", params={"since": "2026-09-21", "as_of": "2026-09-20"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"


def test_as_of_defaults_to_today_in_the_club_timezone(
    admin_client: TestClient, auth_env: Settings
) -> None:
    today = datetime.now(ZoneInfo(auth_env.timezone)).date()
    since = (today - timedelta(days=2)).isoformat()
    days = admin_client.get("/api/admin/analytics/visitors", params={"since": since}).json()["days"]
    assert [d["day"] for d in days] == [(today - timedelta(days=n)).isoformat() for n in (2, 1, 0)]


def test_the_four_answers_have_the_documented_shape(
    admin_client: TestClient, session: Session
) -> None:
    session.execute(
        insert(PageView).values(
            device_id=A,
            page_kind="profile",
            me_state="picked",
            at=datetime(2026, 9, 14, 10, 0, tzinfo=PT),
        )
    )
    window = {"since": "2026-09-14", "as_of": "2026-09-20"}
    visitors = admin_client.get("/api/admin/analytics/visitors", params=window).json()
    assert visitors["days"][0] == {"day": "2026-09-14", "devices": 1}
    assert visitors["weeks"] == [{"week": "2026-09-14", "devices": 1}]
    assert visitors["busiest"] == [{"day": "2026-09-14", "devices": 1}]
    pages = admin_client.get("/api/admin/analytics/pages", params=window).json()
    assert pages == [{"page_kind": "profile", "views": 1}]
    bumps = admin_client.get("/api/admin/analytics/bumps", params=window).json()
    assert bumps["top"] == []
    assert (bumps["devices"], bumps["devices_all_time"]) == (0, 0)
    assert len(bumps["days"]) == 7
    states = admin_client.get("/api/admin/analytics/me-states", params=window).json()
    assert states == {
        "weeks": [{"week": "2026-09-14", "picked": 1, "skipped": 0, "none": 0}],
        "latest": {"picked": 1, "skipped": 0, "none": 0},
        "latest_since": "2026-09-14",
    }


def test_reading_analytics_writes_nothing(admin_client: TestClient, session: Session) -> None:
    audit = Base.metadata.tables["audit_log"]
    before = session.scalar(select(func.count()).select_from(audit))  # the login's own entry
    for path in PATHS:
        assert admin_client.get(f"/api/admin/analytics/{path}").status_code == 200
    assert session.scalar(select(func.count()).select_from(audit)) == before
    assert session.scalar(select(func.count()).select_from(PageView)) == 0
