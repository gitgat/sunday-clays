"""POST /api/pageviews (Plan 16 Task 1): counted for viewers, dropped for admins, deduped,
validated and rate-limited, with nothing that identifies a person stored with a view."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.models import Base

A = "00000000-0000-4000-8000-00000000000a"
IP = {"X-Real-IP": "203.0.113.7"}
VIEWS = Base.metadata.tables["page_views"]
ATTEMPTS = Base.metadata.tables["page_view_attempts"]


def _beacon(
    client: TestClient,
    device: str = A,
    kind: str = "home",
    state: str = "none",
    headers: dict[str, str] = IP,
    **extra: object,
):
    body = {"device_id": device, "page_kind": kind, "me_state": state, **extra}
    return client.post("/api/pageviews", json=body, headers=headers)


def _views(session: Session) -> list[tuple[str, str, str]]:
    rows = session.execute(
        select(VIEWS.c.device_id, VIEWS.c.page_kind, VIEWS.c.me_state).order_by(VIEWS.c.id)
    )
    return [(str(d), k, s) for d, k, s in rows]


def _attempt_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(ATTEMPTS)) or 0


def test_a_viewer_beacon_is_counted_once_per_kind_every_30_minutes(
    viewer_client: TestClient, session: Session
) -> None:
    first = _beacon(viewer_client)
    assert first.status_code == 204
    assert first.content == b""
    assert _beacon(viewer_client, state="picked").status_code == 204  # deduped, still 204
    assert _beacon(viewer_client, kind="profile", state="picked").status_code == 204
    assert _views(session) == [(A, "home", "none"), (A, "profile", "picked")]


def test_an_admin_beacon_is_dropped_and_leaves_no_trace(
    admin_client: TestClient, session: Session
) -> None:
    assert _beacon(admin_client).status_code == 204
    assert _beacon(admin_client, device="not-a-uuid").status_code == 204  # dropped before checks
    assert _views(session) == []
    assert _attempt_count(session) == 0


def test_the_browser_clock_is_accepted_but_never_stored(
    viewer_client: TestClient, session: Session
) -> None:
    before = datetime.now(UTC)
    assert _beacon(viewer_client, at="2001-01-01T00:00:00Z").status_code == 204
    stored = session.scalar(select(VIEWS.c.at))
    assert stored is not None
    assert stored >= before - timedelta(seconds=5)


def test_a_device_id_that_is_not_a_uuid_is_400_and_still_counts_toward_the_limit(
    viewer_client: TestClient, session: Session
) -> None:
    for bad in ("not-a-uuid", "{" + A + "}", A + "x"):
        response = _beacon(viewer_client, device=bad)
        assert response.status_code == 400, bad
        assert response.json()["error"]["code"] == "bad_device_id"
    assert _views(session) == []
    assert _attempt_count(session) == 3


def test_a_kind_or_state_outside_the_lists_is_422(
    viewer_client: TestClient, session: Session
) -> None:
    assert _beacon(viewer_client, kind="/shooters/3").status_code == 422
    assert _beacon(viewer_client, state="Hadley, Ike").status_code == 422
    assert _views(session) == []
    assert _attempt_count(session) == 0  # refused before the handler runs


def test_the_limitth_beacon_in_10_minutes_is_the_last(
    viewer_client: TestClient, session: Session
) -> None:
    now = datetime.now(UTC)
    limit = get_settings().page_view_limit  # 600: viewer_client's auth_env leaves it unset
    session.execute(insert(ATTEMPTS), [{"ip": "203.0.113.7", "at": now}] * (limit - 1))
    assert _beacon(viewer_client).status_code == 204
    refused = _beacon(viewer_client, kind="records")
    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "rate_limited"
    other = {"X-Real-IP": "198.51.100.1"}
    assert _beacon(viewer_client, kind="records", headers=other).status_code == 204
    assert _views(session) == [(A, "home", "none"), (A, "records", "none")]
