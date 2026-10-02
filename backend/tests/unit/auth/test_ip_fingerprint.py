"""ip_fingerprint: the keyed hash of the client-IP bucket that rate-limit tables store instead of
the address itself (Plan 16 final fixes)."""

import hashlib

import pytest

from sunday_clays.auth.deps import ip_fingerprint
from sunday_clays.config import Settings

from .test_auth_client_ip import _request


def _fp(headers: dict[str, str], peer: str | None = "172.18.0.5") -> str:
    return ip_fingerprint(_request(headers, peer))


def test_the_fingerprint_is_32_hex_chars_and_never_the_address(auth_env: Settings) -> None:
    value = _fp({"X-Real-IP": "203.0.113.7"})

    assert len(value) == 32
    int(value, 16)
    assert "203.0.113.7" not in value


def test_the_same_ip_gives_the_same_bucket_and_two_ips_give_two(auth_env: Settings) -> None:
    a = _fp({"X-Real-IP": "203.0.113.7"})

    assert _fp({"X-Real-IP": "203.0.113.7"}) == a
    assert _fp({"X-Real-IP": "203.0.113.8"}) != a


def test_ipv6_in_one_slash_64_shares_a_bucket(auth_env: Settings) -> None:
    a = _fp({"X-Real-IP": "2001:db8:1:2:3:4:5:6"})

    assert _fp({"X-Real-IP": "2001:db8:1:2:ffff::1"}) == a
    assert _fp({"X-Real-IP": "2001:db8:1:3::1"}) != a


def test_the_key_is_the_session_secret(auth_env: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    from sunday_clays.config import get_settings

    first = _fp({"X-Real-IP": "203.0.113.7"})
    monkeypatch.setenv("SESSION_SECRET", "another-secret-" + "x" * 40)
    get_settings.cache_clear()

    assert _fp({"X-Real-IP": "203.0.113.7"}) != first
    assert first != hashlib.sha256(b"203.0.113.7").hexdigest()[:32]
