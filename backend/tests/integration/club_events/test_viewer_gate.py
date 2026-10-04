"""The `events` switch gates every viewer route (Plan 20 D1, D23): while off, a viewer gets the
body of an unknown /api path and nothing is written; an admin is served."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.domain.features import set_switch
from sunday_clays.models import ClubEventAttempt, ClubEventRegistration

from .seed import IP, seed_event, seed_registration, seed_shooter

NOT_FOUND = {"detail": "Not Found"}


def _calls(session: Session) -> list[tuple[str, str, dict[str, Any] | None, int]]:
    """(method, url, body, the admin's status) for every viewer route."""
    event_id = seed_event(session)
    shooter_id = seed_shooter(session, "Hadley, Ike")
    rid = seed_registration(session, event_id, name="Dana Quill", email="dana.quill@example.com")
    base = f"/api/club-events/{event_id}"
    signup = {"shooter_id": None, "name": "Pat Kim", "email": "pat.kim@example.com", "guests": 0}
    return [
        ("GET", "/api/club-events", None, 200),
        ("GET", base, None, 200),
        ("GET", f"{base}/signup-check?shooter_id={shooter_id}", None, 200),
        ("POST", f"{base}/registrations", signup, 201),
        ("POST", f"{base}/registrations/{rid}/cancel", {"email": "wrong@example.com"}, 403),
    ]


def _attempts(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(ClubEventAttempt)) or 0)


def test_every_viewer_route_is_the_unknown_path_404_while_off(
    session: Session, viewer_client: TestClient, test_settings: Settings
) -> None:
    assert viewer_client.get("/api/no-such-path").json() == NOT_FOUND
    calls = _calls(session)
    for method, url, body, _ in calls:
        response = viewer_client.request(method, url, json=body, headers=IP)
        assert (response.status_code, response.json()) == (404, NOT_FOUND), url
    # The same calls are real routes: switched on, each is served. Without this half the test
    # would pass on a base with no route at all.
    set_switch(session, test_settings, "events", True)
    for method, url, body, status in calls:
        assert viewer_client.request(method, url, json=body, headers=IP).status_code == status, url


def test_gated_signup_leaves_no_attempt_row(
    session: Session, viewer_client: TestClient, test_settings: Settings
) -> None:
    calls = _calls(session)
    for method, url, body, _ in calls:
        viewer_client.request(method, url, json=body, headers=IP)
    assert _attempts(session) == 0
    assert session.scalar(select(func.count()).select_from(ClubEventRegistration)) == 1
    # Switched on, the same calls write attempt rows (check, sign-up, failed cancel), so the zero
    # above is the gate's doing, not a missing route's.
    set_switch(session, test_settings, "events", True)
    for method, url, body, _ in calls:
        viewer_client.request(method, url, json=body, headers=IP)
    assert _attempts(session) > 0
    assert session.scalar(select(func.count()).select_from(ClubEventRegistration)) == 2


def test_admins_are_served_while_off(session: Session, admin_client: TestClient) -> None:
    for method, url, body, status in _calls(session):
        assert admin_client.request(method, url, json=body, headers=IP).status_code == status, url


def test_the_switch_on_serves_viewers(
    session: Session, viewer_client: TestClient, events_on: None
) -> None:
    for method, url, body, status in _calls(session):
        assert viewer_client.request(method, url, json=body, headers=IP).status_code == status, url
