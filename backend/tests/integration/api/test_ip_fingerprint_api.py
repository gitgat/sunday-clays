"""Rate-limit rows keep a keyed hash of the client IP, never the address (Plan 16 final fixes)."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.models import Base

A = "00000000-0000-4000-8000-00000000000a"
IP = "203.0.113.7"
HEADERS = {"X-Real-IP": IP}
BUMPS = Base.metadata.tables["bump_attempts"]
VIEWS = Base.metadata.tables["page_view_attempts"]
LOGINS = Base.metadata.tables["login_attempts"]


def _ips(session: Session, table: object) -> list[str]:
    return list(session.scalars(select(table.c.ip)))  # type: ignore[attr-defined]


def _is_fingerprint(value: str) -> bool:
    return len(value) == 32 and value != IP and all(c in "0123456789abcdef" for c in value)


def test_a_beacon_stores_a_fingerprint_not_the_ip(
    viewer_client: TestClient, session: Session
) -> None:
    body = {"device_id": A, "page_kind": "home", "me_state": "none"}
    assert viewer_client.post("/api/pageviews", json=body, headers=HEADERS).status_code == 204

    stored = _ips(session, VIEWS)
    assert len(stored) == 1
    assert _is_fingerprint(stored[0])


def test_a_bump_stores_a_fingerprint_not_the_ip(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    feed = fx_viewer_client.get("/api/insights/home").json()
    key = (feed["top"] + feed["more"])[0]["key"]
    response = fx_viewer_client.post(
        "/api/bumps", json={"key": key, "device_id": A}, headers=HEADERS
    )
    assert response.status_code == 200

    stored = _ips(fx_session, BUMPS)
    assert len(stored) == 1
    assert _is_fingerprint(stored[0])


def test_a_failed_login_stores_a_fingerprint_not_the_ip(
    anon_client: TestClient, session: Session
) -> None:
    response = anon_client.post("/api/auth/login", json={"password": "nope"}, headers=HEADERS)
    assert response.status_code == 401

    stored = _ips(session, LOGINS)
    assert len(stored) == 1
    assert _is_fingerprint(stored[0])
