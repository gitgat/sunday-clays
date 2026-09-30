import pytest
from starlette.requests import Request

from sunday_clays.auth.deps import client_ip


def _request(headers: dict[str, str], peer: str | None) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 50000) if peer is not None else None,
    }
    return Request(scope)


@pytest.mark.parametrize(
    ("headers", "peer", "expected"),
    [
        ({"X-Real-IP": "203.0.113.7"}, "172.18.0.5", "203.0.113.7"),
        ({}, "172.18.0.5", "172.18.0.5"),
        ({"X-Forwarded-For": "198.51.100.1"}, "172.18.0.5", "172.18.0.5"),
        ({"X-Real-IP": "2001:db8:1:2:3:4:5:6"}, "172.18.0.5", "2001:db8:1:2::/64"),
        ({"X-Real-IP": "::ffff:198.51.100.9"}, "172.18.0.5", "198.51.100.9"),
        ({"X-Real-IP": "not-an-ip"}, "172.18.0.5", "172.18.0.5"),
        ({}, "testclient", "testclient"),
        ({}, None, "unknown"),
    ],
)
def test_client_ip(headers: dict[str, str], peer: str | None, expected: str) -> None:
    assert client_ip(_request(headers, peer)) == expected
