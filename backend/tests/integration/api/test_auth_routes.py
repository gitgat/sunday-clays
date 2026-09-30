import threading
import time
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from itsdangerous.timed import TimestampSigner
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from sunday_clays.api.app import create_app
from sunday_clays.api.routes import auth as auth_routes
from sunday_clays.auth.sessions import COOKIE_NAME, Role, issue_session
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionFactory
from sunday_clays.models import Base

ATTEMPTS = Base.metadata.tables["login_attempts"]
AUDIT = Base.metadata.tables["audit_log"]
WRONG = {"password": "definitely-wrong"}


@pytest.mark.parametrize(("role", "max_age"), [("viewer", 2_592_000), ("admin", 43_200)])
def test_login_sets_role_cookie_and_me_reports_role(
    anon_client: TestClient, login_passwords: dict[Role, str], role: Role, max_age: int
) -> None:
    response = anon_client.post("/api/auth/login", json={"password": login_passwords[role]})
    assert response.status_code == 200
    assert response.json() == {"role": role}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert "HttpOnly" in cookie
    assert "samesite=strict" in cookie.lower()
    assert f"Max-Age={max_age}" in cookie
    assert "Secure" not in cookie
    assert anon_client.get("/api/auth/me").json() == {"role": role}


def test_login_cookie_secure_when_enabled(
    anon_client: TestClient,
    login_passwords: dict[Role, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    response = anon_client.post("/api/auth/login", json={"password": login_passwords["viewer"]})
    assert "; Secure" in response.headers["set-cookie"]


def test_admin_login_is_audited(
    anon_client: TestClient, login_passwords: dict[Role, str], session: Session
) -> None:
    anon_client.post(
        "/api/auth/login",
        json={"password": login_passwords["admin"]},
        headers={"X-Real-IP": "203.0.113.7"},
    )
    rows = session.execute(select(AUDIT.c.ip, AUDIT.c.role, AUDIT.c.action)).all()
    assert [tuple(r) for r in rows] == [("203.0.113.7", "admin", "auth.login")]


def test_me_without_cookie_is_401(anon_client: TestClient) -> None:
    response = anon_client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def _flipped_signature(settings: Settings) -> str:
    """A real admin token whose signature's first character (6 full bits) is changed."""
    payload, timestamp, signature = issue_session(settings, "admin").split(".")
    first = "B" if signature[0] == "A" else "A"
    return f"{payload}.{timestamp}.{first}{signature[1:]}"


def _viewer_signature_on_admin_payload(settings: Settings) -> str:
    """Role escalation attempt: an admin payload carrying a viewer token's signature."""
    admin_payload, _, _ = issue_session(settings, "admin").split(".")
    _, timestamp, viewer_signature = issue_session(settings, "viewer").split(".")
    return f"{admin_payload}.{timestamp}.{viewer_signature}"


@pytest.mark.parametrize(
    "make_cookie",
    [
        pytest.param(lambda settings: "garbage", id="garbage"),
        pytest.param(_flipped_signature, id="tampered-signature"),
        pytest.param(_viewer_signature_on_admin_payload, id="swapped-payload"),
    ],
)
def test_me_with_a_bad_session_cookie_is_401(
    anon_client: TestClient, auth_env: Settings, make_cookie: Callable[[Settings], str]
) -> None:
    anon_client.cookies.set(COOKIE_NAME, make_cookie(auth_env))
    response = anon_client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_wrong_password_is_401(anon_client: TestClient) -> None:
    response = anon_client.post("/api/auth/login", json=WRONG)
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "invalid_password", "message": "Wrong password"}}
    assert "set-cookie" not in response.headers


REAL_SESSION_PROBE_IP = "192.0.2.201"


@pytest.fixture
def real_session_client(auth_env: Settings, engine: Engine) -> Iterator[TestClient]:
    """create_app() on the real get_session (no override), whose commits reach the test DB.

    Those rows live outside every test transaction, so the probe IP's rows are deleted after.
    """
    previous_bind = SessionFactory.kw.get("bind")
    SessionFactory.configure(bind=engine)
    try:
        with TestClient(create_app()) as test_client:
            yield test_client
    finally:
        SessionFactory.configure(bind=previous_bind)
        with engine.begin() as conn:
            conn.execute(delete(ATTEMPTS).where(ATTEMPTS.c.ip == REAL_SESSION_PROBE_IP))


def test_failed_attempt_row_persists_after_401(
    real_session_client: TestClient, engine: Engine
) -> None:
    """get_session rolls back on the 401, yet a new connection sees the row: login commits it first.

    Runs on the real get_session: login also ends its rate-limit SELECT's transaction early, which
    closes the ``client`` override's request savepoint, so that world cannot see a lost commit.
    """
    headers = {"X-Real-IP": REAL_SESSION_PROBE_IP}
    response = real_session_client.post("/api/auth/login", json=WRONG, headers=headers)
    assert response.status_code == 401
    with engine.connect() as conn:
        rows = conn.execute(
            select(ATTEMPTS.c.ip, ATTEMPTS.c.success).where(ATTEMPTS.c.ip == REAL_SESSION_PROBE_IP)
        ).all()
    assert [tuple(r) for r in rows] == [(REAL_SESSION_PROBE_IP, False)]


def test_login_holds_no_pooled_connection_while_waiting_for_and_running_a_verify(
    real_session_client: TestClient,
    engine: Engine,
    login_passwords: dict[Role, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rate-limit SELECT's transaction ends before the slot wait and the argon2 verify."""
    checked_out: dict[str, int] = {}
    real_match_role = auth_routes.match_role

    class ObservedSlots(threading.BoundedSemaphore):
        def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
            checked_out["slot wait"] = engine.pool.checkedout()
            return super().acquire(blocking, timeout)

    def observed_match_role(settings: Settings, password: str) -> Role | None:
        checked_out["verify"] = engine.pool.checkedout()
        return real_match_role(settings, password)

    monkeypatch.setattr(auth_routes, "_VERIFY_SLOTS", ObservedSlots(4))
    monkeypatch.setattr(auth_routes, "match_role", observed_match_role)
    response = real_session_client.post(
        "/api/auth/login",
        json={"password": login_passwords["viewer"]},
        headers={"X-Real-IP": REAL_SESSION_PROBE_IP},
    )
    assert response.status_code == 200
    assert checked_out == {"slot wait": 0, "verify": 0}


def test_eleventh_failure_returns_429(
    anon_client: TestClient,
    login_passwords: dict[Role, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for _ in range(10):
        assert anon_client.post("/api/auth/login", json=WRONG).status_code == 401
    verifies: list[str] = []
    real_match_role = auth_routes.match_role

    def counting_match_role(settings: Settings, password: str) -> Role | None:
        verifies.append(password)
        return real_match_role(settings, password)

    monkeypatch.setattr(auth_routes, "match_role", counting_match_role)
    response = anon_client.post("/api/auth/login", json={"password": login_passwords["admin"]})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert verifies == []  # limited before any argon2 work


def test_rate_limit_ignores_spoofed_x_forwarded_for(anon_client: TestClient) -> None:
    for i in range(10):
        spoofed = {"X-Forwarded-For": f"192.0.2.{i}"}
        assert anon_client.post("/api/auth/login", json=WRONG, headers=spoofed).status_code == 401
    spoofed = {"X-Forwarded-For": "192.0.2.200"}
    assert anon_client.post("/api/auth/login", json=WRONG, headers=spoofed).status_code == 429


def test_rate_limit_buckets_by_x_real_ip(anon_client: TestClient) -> None:
    first = {"X-Real-IP": "203.0.113.10"}
    second = {"X-Real-IP": "203.0.113.11"}
    for _ in range(10):
        assert anon_client.post("/api/auth/login", json=WRONG, headers=first).status_code == 401
    assert anon_client.post("/api/auth/login", json=WRONG, headers=first).status_code == 429
    assert anon_client.post("/api/auth/login", json=WRONG, headers=second).status_code == 401


def test_ipv6_bucketed_by_64(anon_client: TestClient) -> None:
    same_64 = ["2001:db8:0:1::a", "2001:db8:0:1:ffff:ffff:ffff:fffe"]
    for i in range(10):
        headers = {"X-Real-IP": same_64[i % 2]}
        assert anon_client.post("/api/auth/login", json=WRONG, headers=headers).status_code == 401
    neighbour = {"X-Real-IP": "2001:db8:0:1::77"}
    other_64 = {"X-Real-IP": "2001:db8:0:2::a"}
    assert anon_client.post("/api/auth/login", json=WRONG, headers=neighbour).status_code == 429
    assert anon_client.post("/api/auth/login", json=WRONG, headers=other_64).status_code == 401


def test_login_returns_429_when_no_verify_slot_frees_up(
    anon_client: TestClient,
    login_passwords: dict[Role, str],
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
) -> None:
    exhausted = threading.BoundedSemaphore(1)
    exhausted.acquire()
    monkeypatch.setattr(auth_routes, "_VERIFY_SLOTS", exhausted)
    monkeypatch.setattr(auth_routes, "VERIFY_ACQUIRE_TIMEOUT_S", 0.01)
    response = anon_client.post("/api/auth/login", json={"password": login_passwords["viewer"]})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "login_busy"
    assert session.execute(select(ATTEMPTS.c.id)).all() == []


def test_verify_slots_are_released_after_each_login(
    anon_client: TestClient, login_passwords: dict[Role, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    slots = threading.BoundedSemaphore(4)
    monkeypatch.setattr(auth_routes, "_VERIFY_SLOTS", slots)
    anon_client.post("/api/auth/login", json=WRONG)
    anon_client.post("/api/auth/login", json={"password": login_passwords["viewer"]})
    taken = [slots.acquire(blocking=False) for _ in range(4)]
    assert taken == [True, True, True, True]


def test_logout_clears_cookie(anon_client: TestClient, login_passwords: dict[Role, str]) -> None:
    anon_client.post("/api/auth/login", json={"password": login_passwords["viewer"]})
    response = anon_client.post("/api/auth/logout")
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert anon_client.get("/api/auth/me").status_code == 401


def test_expired_admin_token_rejected_regardless_of_cookie_max_age(
    anon_client: TestClient, auth_env: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    thirteen_hours_ago = int(time.time()) - 13 * 3600
    with monkeypatch.context() as m:
        m.setattr(TimestampSigner, "get_timestamp", lambda self: thirteen_hours_ago)
        old_admin = issue_session(auth_env, "admin")
        old_viewer = issue_session(auth_env, "viewer")
    anon_client.cookies.set(COOKIE_NAME, old_admin)
    assert anon_client.get("/api/auth/me").status_code == 401
    anon_client.cookies.set(COOKIE_NAME, old_viewer)
    assert anon_client.get("/api/auth/me").json() == {"role": "viewer"}


def test_cross_site_upload_with_admin_cookie_is_blocked(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/api/admin/imports",
        files={"file": ("scores.xlsx", b"PK\x03\x04", "application/octet-stream")},
        headers={"Origin": "https://shop.claysmasher.com", "Host": "sundayclays.claysmasher.com"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf"
