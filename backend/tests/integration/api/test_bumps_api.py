"""/api/bumps on the fx world (Plan 15 Task 1): keyed by insight, idempotent, refused,
rate-limited and never cached."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.api.routes.bumps import MAX_KEYS
from sunday_clays.auth.ratelimit import BUMP_LIMIT
from sunday_clays.domain.bumps import BumpState, add_bump, bump_state
from sunday_clays.models import Base

A = "00000000-0000-4000-8000-00000000000a"
B = "00000000-0000-4000-8000-00000000000b"
IP = {"X-Real-IP": "203.0.113.7"}
ATTEMPTS = Base.metadata.tables["bump_attempts"]
GONE = "fedcba9876543210fedc"  # insight-shaped, in no insights row


def _keys(client: TestClient, n: int = 2) -> list[str]:
    feed = client.get("/api/insights/home").json()
    keys = [row["key"] for row in feed["top"]] + [row["key"] for row in feed["more"]]
    assert len(keys) >= n, "the fx world's home feed has enough insights"
    return keys[:n]


def _post(client: TestClient, key: str, device: str, headers: dict[str, str] = IP):
    return client.post("/api/bumps", json={"key": key, "device_id": device}, headers=headers)


def _delete(client: TestClient, key: str, device: str, headers: dict[str, str] = IP):
    return client.request(
        "DELETE", "/api/bumps", json={"key": key, "device_id": device}, headers=headers
    )


def _counts(client: TestClient, keys: list[str], device: str | None = None, **headers: str):
    params = {"keys": ",".join(keys)} | ({} if device is None else {"device_id": device})
    return client.get("/api/bumps", params=params, headers=headers)


def test_bumping_is_idempotent_per_device_and_taking_back_too(
    fx_viewer_client: TestClient,
) -> None:
    key = _keys(fx_viewer_client)[0]
    assert _post(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": True}
    assert _post(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": True}
    assert _post(fx_viewer_client, key, B).json() == {"bumps": 2, "bumped": True}
    assert _delete(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": False}
    assert _delete(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": False}
    assert _counts(fx_viewer_client, [key], B).json() == {key: {"bumps": 1, "bumped": True}}
    assert _counts(fx_viewer_client, [key], A).json() == {key: {"bumps": 1, "bumped": False}}


def test_counts_cover_every_asked_insight_with_zeros(fx_viewer_client: TestClient) -> None:
    keys = _keys(fx_viewer_client)
    counts = _counts(fx_viewer_client, keys).json()
    assert set(counts) == set(keys)
    assert all(state == {"bumps": 0, "bumped": False} for state in counts.values())
    assert fx_viewer_client.get("/api/bumps").json() == {}


def test_an_insight_that_is_gone_keeps_its_bumps_but_never_shows(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    key = _keys(fx_viewer_client)[0]
    add_bump(fx_session, GONE, uuid.UUID(A))
    assert set(_counts(fx_viewer_client, [key, GONE]).json()) == {key}
    response = _post(fx_viewer_client, GONE, B)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "insight_not_found"
    assert bump_state(fx_session, GONE, None) == BumpState(1, False)


def test_an_unknown_key_is_404(fx_viewer_client: TestClient) -> None:
    for key in (GONE, "trophy:no_such_trophy:2026-09-27"):
        for response in (_post(fx_viewer_client, key, A), _delete(fx_viewer_client, key, A)):
            assert response.status_code == 404, key
            assert response.json()["error"]["code"] == "insight_not_found"


def test_a_device_id_that_is_not_a_uuid_is_400(fx_viewer_client: TestClient) -> None:
    key = _keys(fx_viewer_client)[0]
    bad_ids = ("not-a-uuid", "00000000000040008000000000000000a", "{" + A + "}", A + "x", "0" * 65)
    for bad in bad_ids:
        for response in (
            _post(fx_viewer_client, key, bad),
            _delete(fx_viewer_client, key, bad),
            _counts(fx_viewer_client, [key], bad),
        ):
            assert response.status_code == 400, bad
            assert response.json()["error"]["code"] == "bad_device_id"
    assert _post(fx_viewer_client, key, A.upper()).status_code == 200


def test_at_most_100_keys_per_ask_and_duplicates_count_once(
    fx_viewer_client: TestClient,
) -> None:
    key = _keys(fx_viewer_client)[0]
    too_many = [f"{i:020x}" for i in range(MAX_KEYS + 1)]
    response = _counts(fx_viewer_client, too_many)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "too_many_keys"
    assert _counts(fx_viewer_client, too_many[:MAX_KEYS]).status_code == 200
    assert _counts(fx_viewer_client, [key] * (MAX_KEYS + 50)).json() == {
        key: {"bumps": 0, "bumped": False}
    }
    spaced = fx_viewer_client.get("/api/bumps", params={"keys": f" {key} ,, "}).json()
    assert spaced == {key: {"bumps": 0, "bumped": False}}


def test_the_600th_action_in_10_minutes_is_the_last(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    key = _keys(fx_viewer_client)[0]
    now = datetime.now(UTC)
    fx_session.execute(insert(ATTEMPTS), [{"ip": "203.0.113.7", "at": now}] * (BUMP_LIMIT - 1))
    assert _post(fx_viewer_client, key, A).status_code == 200
    refused = _delete(fx_viewer_client, key, A)
    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "rate_limited"
    other = {"X-Real-IP": "198.51.100.1"}
    assert _delete(fx_viewer_client, key, A, headers=other).json() == {
        "bumps": 0,
        "bumped": False,
    }
    assert _counts(fx_viewer_client, [key]).status_code == 200  # reading is never limited


def test_refused_requests_still_count_toward_the_limit(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    before = len(fx_session.execute(select(ATTEMPTS.c.id)).all())
    _post(fx_viewer_client, GONE, A)
    _post(fx_viewer_client, _keys(fx_viewer_client)[0], "nope")
    assert len(fx_session.execute(select(ATTEMPTS.c.id)).all()) == before + 2


def test_counts_are_never_cached_and_never_in_a_feed(fx_viewer_client: TestClient) -> None:
    key = _keys(fx_viewer_client)[0]
    before = fx_viewer_client.get("/api/insights/home")
    counts = _counts(fx_viewer_client, [key])
    assert counts.headers["cache-control"] == "no-store"
    assert "etag" not in counts.headers
    _post(fx_viewer_client, key, A)
    again = _counts(fx_viewer_client, [key], **{"If-None-Match": "*"})
    assert again.status_code == 200
    assert again.json() != counts.json()
    after = fx_viewer_client.get("/api/insights/home")
    assert after.json() == before.json()
    assert after.headers["etag"] == before.headers["etag"]


def test_a_bad_device_id_is_refused_before_an_unknown_key(fx_viewer_client: TestClient) -> None:
    for response in (
        _post(fx_viewer_client, GONE, "nope"),
        _delete(fx_viewer_client, GONE, "nope"),
    ):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "bad_device_id"


def test_an_empty_or_over_long_key_is_400_bad_key_and_counts_toward_the_limit(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    before = len(fx_session.execute(select(ATTEMPTS.c.id)).all())
    for key in ("", "k" * 201):
        for response in (_post(fx_viewer_client, key, A), _delete(fx_viewer_client, key, A)):
            assert response.status_code == 400, len(key)
            assert response.json()["error"]["code"] == "bad_key"
    assert len(fx_session.execute(select(ATTEMPTS.c.id)).all()) == before + 4
    assert _post(fx_viewer_client, "k" * 200, A).status_code == 404  # 200 is the longest allowed


def test_asking_for_a_key_over_200_chars_is_400_bad_key(fx_viewer_client: TestClient) -> None:
    response = _counts(fx_viewer_client, ["k" * 201])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_key"
    assert _counts(fx_viewer_client, ["k" * 200]).status_code == 200


def test_cross_site_writes_are_403_csrf(fx_viewer_client: TestClient) -> None:
    key = _keys(fx_viewer_client)[0]
    cross = {**IP, "Sec-Fetch-Site": "cross-site"}
    for response in (
        _post(fx_viewer_client, key, A, cross),
        _delete(fx_viewer_client, key, A, cross),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf"
