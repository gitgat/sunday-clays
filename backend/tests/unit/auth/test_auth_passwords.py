import pytest
from argon2 import PasswordHasher, Type, extract_parameters

from sunday_clays.auth.passwords import hash_password, match_role, verify_password
from sunday_clays.auth.sessions import Role
from sunday_clays.config import Settings


def test_hash_password_uses_owasp_argon2id_profile() -> None:
    params = extract_parameters(hash_password("correct horse"))
    assert (params.type, params.memory_cost, params.time_cost, params.parallelism) == (
        Type.ID,
        19_456,
        2,
        1,
    )


def test_verify_accepts_right_password_and_rejects_wrong_one() -> None:
    stored = hash_password("correct horse")
    assert verify_password(stored, "correct horse") is True
    assert verify_password(stored, "battery staple") is False


def test_verify_rejects_a_hash_that_is_not_argon2() -> None:
    assert verify_password("plain-text-not-a-hash", "plain-text-not-a-hash") is False


def test_verify_refuses_hash_above_memory_cap() -> None:
    costly = PasswordHasher(time_cost=1, memory_cost=19_457, parallelism=1).hash("pw")
    assert verify_password(costly, "pw") is False


def test_verify_accepts_hash_at_memory_cap() -> None:
    at_cap = PasswordHasher(time_cost=1, memory_cost=19_456, parallelism=1).hash("pw")
    assert verify_password(at_cap, "pw") is True


@pytest.mark.parametrize("role", ["viewer", "admin"])
def test_match_role_returns_the_role_whose_password_matches(
    auth_env: Settings, login_passwords: dict[Role, str], role: Role
) -> None:
    assert match_role(auth_env, login_passwords[role]) == role


def test_match_role_returns_none_for_unknown_password(auth_env: Settings) -> None:
    assert match_role(auth_env, "not-a-configured-password") is None
