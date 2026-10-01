"""Fist-bump routes on the fx world (Plan 14 Task 3): idempotent, refused, rate-limited, never
cached, and wiped by an admin with an audit entry."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import event, insert, select
from sqlalchemy.orm import Session

from sunday_clays.api.routes.admin_sheet import list_bumped_posts
from sunday_clays.auth.ratelimit import BUMP_LIMIT
from sunday_clays.domain.bumps import BumpState, add_bump, bump_state
from sunday_clays.models import Base

A = "00000000-0000-4000-8000-00000000000a"
B = "00000000-0000-4000-8000-00000000000b"
IP = {"X-Real-IP": "203.0.113.7"}
LATEST = "2026-09-27"
ATTEMPTS = Base.metadata.tables["bump_attempts"]
AUDIT = Base.metadata.tables["audit_log"]


def _key(client: TestClient, index: int = 0) -> str:
    return str(client.get("/api/sheet/latest").json()["posts"][index]["post_key"])


def _post(client: TestClient, key: str, device: str, headers: dict[str, str] = IP):
    return client.post(
        "/api/sheet/bumps", json={"post_key": key, "device_id": device}, headers=headers
    )


def _delete(client: TestClient, key: str, device: str, headers: dict[str, str] = IP):
    return client.request(
        "DELETE", "/api/sheet/bumps", json={"post_key": key, "device_id": device}, headers=headers
    )


def test_bumping_is_idempotent_per_device_and_taking_back_too(
    fx_viewer_client: TestClient,
) -> None:
    key = _key(fx_viewer_client)
    assert _post(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": True}
    assert _post(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": True}
    assert _post(fx_viewer_client, key, B).json() == {"bumps": 2, "bumped": True}
    assert _delete(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": False}
    assert _delete(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": False}
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps", params={"device_id": B}).json()
    assert counts[key] == {"bumps": 1, "bumped": True}
    mine = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps", params={"device_id": A}).json()
    assert mine[key] == {"bumps": 1, "bumped": False}


def test_counts_cover_every_post_on_the_issue_with_zeros(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    keys = {p["post_key"] for p in body["posts"]} | {
        p["post_key"] for g in body["more"] for p in g["posts"]
    }
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps").json()
    assert set(counts) == keys
    assert set(map(str, counts.values())) == {str({"bumps": 0, "bumped": False})}


def test_a_device_id_that_is_not_a_uuid_is_400(fx_viewer_client: TestClient) -> None:
    key = _key(fx_viewer_client)
    for bad in ("not-a-uuid", "00000000000040008000000000000000a", "{" + A + "}", A + "x"):
        for response in (_post(fx_viewer_client, key, bad), _delete(fx_viewer_client, key, bad)):
            assert response.status_code == 400, bad
            assert response.json()["error"]["code"] == "bad_device_id"
    response = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps", params={"device_id": "nope"})
    assert response.status_code == 400
    assert _post(fx_viewer_client, key, A.upper()).status_code == 200


def test_an_unknown_post_key_is_404(fx_viewer_client: TestClient) -> None:
    for key in ("deadbeefdeadbeefdead", "trophy:no_such_trophy:2026-09-27", "otd:2026-09-27:9"):
        response = _post(fx_viewer_client, key, A)
        assert response.status_code == 404, key
        assert response.json()["error"]["code"] == "post_not_found"
    assert fx_viewer_client.get("/api/sheet/2026-09-26/bumps").status_code == 404


def test_stale_bumps_are_kept_hidden_and_wipeable(
    fx_viewer_client: TestClient, fx_admin_client: TestClient, fx_session: Session
) -> None:
    stale = "trophy:retired_trophy:2026-09-27"
    add_bump(fx_session, stale, uuid.UUID(A))
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps").json()
    assert stale not in counts
    assert _post(fx_viewer_client, stale, B).status_code == 404
    assert bump_state(fx_session, stale, None) == BumpState(1, False)
    listed = {row["post_key"]: row for row in fx_admin_client.get("/api/admin/sheet/bumps").json()}
    assert listed[stale]["current"] is False
    assert listed[stale]["label"] == "Trophy retired_trophy, 2026-09-27"
    response = fx_admin_client.delete(f"/api/admin/sheet/bumps/{stale}")
    assert response.json() == {"post_key": stale, "wiped": 1}


def test_the_120th_action_in_10_minutes_is_the_last(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    key = _key(fx_viewer_client)
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


def test_refused_requests_still_count_toward_the_limit(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    before = len(fx_session.execute(select(ATTEMPTS.c.id)).all())
    _post(fx_viewer_client, "deadbeefdeadbeefdead", A)
    _post(fx_viewer_client, _key(fx_viewer_client), "nope")
    assert len(fx_session.execute(select(ATTEMPTS.c.id)).all()) == before + 2


def test_counts_are_never_cached_and_never_in_the_issue_body(fx_viewer_client: TestClient) -> None:
    before = fx_viewer_client.get("/api/sheet/latest")
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps")
    assert counts.headers["cache-control"] == "no-store"
    assert "etag" not in counts.headers
    _post(fx_viewer_client, _key(fx_viewer_client), A)
    again = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps", headers={"If-None-Match": "*"})
    assert again.status_code == 200
    assert again.json() != counts.json()
    after = fx_viewer_client.get("/api/sheet/latest")
    assert after.json() == before.json()
    assert after.headers["etag"] == before.headers["etag"]


def test_an_admin_wipe_clears_one_post_and_is_audited(
    fx_viewer_client: TestClient, fx_admin_client: TestClient, fx_session: Session
) -> None:
    posts = fx_viewer_client.get("/api/sheet/latest").json()["posts"]
    first = next(p for p in posts if p["insight"] is not None)
    key, other = first["post_key"], next(p["post_key"] for p in posts if p is not first)
    for device in (A, B):
        _post(fx_viewer_client, key, device)
    _post(fx_viewer_client, other, A)
    listed = fx_admin_client.get("/api/admin/sheet/bumps").json()
    row = next(r for r in listed if r["post_key"] == key)
    assert (row["bumps"], row["current"], row["issue_date"]) == (2, True, LATEST)
    assert row["label"] == first["insight"]["headline_text"]
    assert fx_viewer_client.delete(f"/api/admin/sheet/bumps/{key}").status_code == 403
    assert fx_admin_client.delete(f"/api/admin/sheet/bumps/{key}").json() == {
        "post_key": key,
        "wiped": 2,
    }
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps").json()
    assert counts[key] == {"bumps": 0, "bumped": False}
    assert counts[other]["bumps"] == 1
    action, details = fx_session.execute(
        select(AUDIT.c.action, AUDIT.c.details).order_by(AUDIT.c.id.desc()).limit(1)
    ).one()
    assert (action, details) == ("sheet.wipe_bumps", {"post_key": key, "wiped": 2})


def _statements_for(session: Session, count: int) -> int:
    """SQL statements `list_bumped_posts` sends for `count` bumped posts (a mix of kinds)."""
    session.execute(Base.metadata.tables["fist_bumps"].delete())
    live = [f"otd:{LATEST}:{i}" for i in range(count)]
    stale = [f"fedcba98765432{i:06d}" for i in range(count)]
    for key in (*live, *stale)[:count]:
        add_bump(session, key, uuid.UUID(A))
    statements: list[str] = []

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        statements.append(statement)

    connection = session.connection()
    event.listen(connection, "before_cursor_execute", record)
    try:
        listed = list_bumped_posts(session)
    finally:
        event.remove(connection, "before_cursor_execute", record)
    assert len(listed) == count
    return len(statements)


def test_the_admin_list_does_not_query_per_row(fx_viewer_client: TestClient, fx_session: Session):
    _key(fx_viewer_client)  # warm the per-data_version issue cache
    _statements_for(fx_session, 5)
    small = _statements_for(fx_session, 5)
    large = _statements_for(fx_session, 50)
    assert small == large
    assert large < 10
