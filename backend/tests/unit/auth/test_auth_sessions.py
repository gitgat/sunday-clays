from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from itsdangerous import URLSafeTimedSerializer
from pydantic import SecretStr

from sunday_clays.auth.sessions import Role, issue_session, load_session
from sunday_clays.config import Settings

ROTATED_HASH = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("rotated")


def _forge(settings: Settings, payload: object) -> str:
    secret = settings.session_secret.get_secret_value()
    return URLSafeTimedSerializer(secret, salt="sc-session").dumps(payload)


@pytest.mark.parametrize("role", ["viewer", "admin"])
def test_issued_token_loads_as_its_role(auth_env: Settings, role: Role) -> None:
    assert load_session(auth_env, issue_session(auth_env, role)) == role


def test_rotating_admin_hash_revokes_admin_sessions_only(auth_env: Settings) -> None:
    viewer_token = issue_session(auth_env, "viewer")
    admin_token = issue_session(auth_env, "admin")
    rotated = auth_env.model_copy(update={"admin_password_hash": SecretStr(ROTATED_HASH)})
    assert load_session(rotated, admin_token) is None
    assert load_session(rotated, viewer_token) == "viewer"


def test_rotating_viewer_hash_revokes_viewer_sessions_only(auth_env: Settings) -> None:
    viewer_token = issue_session(auth_env, "viewer")
    admin_token = issue_session(auth_env, "admin")
    rotated = auth_env.model_copy(update={"viewer_password_hash": SecretStr(ROTATED_HASH)})
    assert load_session(rotated, viewer_token) is None
    assert load_session(rotated, admin_token) == "admin"


@pytest.mark.parametrize(
    ("role", "ttl"), [("viewer", timedelta(days=30)), ("admin", timedelta(hours=12))]
)
def test_token_expires_after_its_role_ttl(auth_env: Settings, role: Role, ttl: timedelta) -> None:
    token = issue_session(auth_env, role)
    issued = datetime.now(UTC)
    assert load_session(auth_env, token, now=issued + ttl - timedelta(minutes=1)) == role
    assert load_session(auth_env, token, now=issued + ttl + timedelta(minutes=1)) is None


def test_token_signed_with_another_secret_is_rejected(auth_env: Settings) -> None:
    other = auth_env.model_copy(update={"session_secret": SecretStr("another-secret-" + "y" * 32)})
    assert load_session(auth_env, issue_session(other, "admin")) is None


@pytest.mark.parametrize("token", ["", "not-a-token", "eyJyIjoiYWRtaW4ifQ.bad.sig"])
def test_garbage_token_is_rejected(auth_env: Settings, token: str) -> None:
    assert load_session(auth_env, token) is None


@pytest.mark.parametrize(
    "payload",
    [["admin"], {"r": "root", "k": "0123456789abcdef"}, {"r": 1, "k": "x"}, {"r": "admin", "k": 7}],
)
def test_signed_but_malformed_payload_is_rejected(auth_env: Settings, payload: object) -> None:
    assert load_session(auth_env, _forge(auth_env, payload)) is None
