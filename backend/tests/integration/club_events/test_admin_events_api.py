"""Organizers create and edit club events (Plan 20 §5.3.3, §5.3.4, §5.3.11, §5.5). Served
whether the switch is on or off (D1): no test here turns it on."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.models import ClubEventRegistration

from .seed import DEADLINE, NOW, STARTS, seed_event, seed_registration

R = ClubEventRegistration
BASE = "/api/admin/club-events"
NEW = {
    "title": "Fall Fun Shoot",
    "starts_local": "2026-10-17T10:00",
    "deadline_local": "2026-10-16T20:00",
    "notes": "Bring eye and ear protection.",
    "capacity": 20,
    "allow_guests": True,
    "max_guests": 2,
}


def _error(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def _statuses(session: Session, event_id: int) -> list[tuple[str, str]]:
    rows = session.execute(
        select(R.registrant_name, R.status).where(R.event_id == event_id).order_by(R.id)
    )
    return [(str(name), str(status)) for name, status in rows]


def test_create_returns_the_event_in_club_time(
    admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    clock(NOW)
    response = admin_client.post(BASE, json=NEW)
    assert response.status_code == 201
    body = response.json()
    assert (body["title"], body["local_date"], body["local_time"]) == (
        "Fall Fun Shoot",
        "2026-10-17",
        "10:00",
    )
    assert (body["deadline_local_date"], body["deadline_local_time"], body["state"]) == (
        "2026-10-16",
        "20:00",
        "open",
    )
    assert (body["capacity"], body["allow_guests"], body["max_guests"]) == (20, True, 2)
    assert body["notes"] == "Bring eye and ear protection."
    assert body["starts_at"] == "2026-10-17T17:00:00Z"


def test_create_refusals(admin_client: TestClient, clock: Callable[[datetime], None]) -> None:
    clock(NOW)
    cases = [
        (
            {"starts_local": "2026-09-01T10:00", "deadline_local": "2026-08-31T20:00"},
            "starts_in_past",
        ),
        ({"deadline_local": "2026-10-17T10:01"}, "deadline_after_start"),
        (
            {"starts_local": "2027-03-14T02:30", "deadline_local": "2027-03-13T20:00"},
            "bad_local_time",
        ),
        ({"title": "   "}, "bad_title"),
        ({"title": "T" * 81}, "bad_title"),
        ({"notes": "n" * 2001}, "notes_too_long"),
        ({"capacity": 0}, "bad_capacity"),
        ({"capacity": 501}, "bad_capacity"),
        ({"max_guests": 11}, "bad_max_guests"),
        ({"max_guests": 0}, "bad_max_guests"),
    ]
    for change, code in cases:
        assert _error(admin_client.post(BASE, json=NEW | change)) == (400, code), change


def test_guests_off_stores_no_guests(
    admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    clock(NOW)
    body = admin_client.post(BASE, json=NEW | {"allow_guests": False, "max_guests": 4}).json()
    assert (body["allow_guests"], body["max_guests"]) == (False, 0)


def test_the_list_is_newest_first(session: Session, admin_client: TestClient) -> None:
    older = seed_event(
        session,
        title="Lesson day",
        starts_at=STARTS - timedelta(days=30),
        deadline=DEADLINE - timedelta(days=30),
    )
    newer = seed_event(session, title="Banquet")
    assert [e["id"] for e in admin_client.get(BASE).json()] == [newer, older]


def test_notes_on_a_past_event_can_change(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session)
    clock(STARTS + timedelta(days=3))
    response = admin_client.patch(f"{BASE}/{event_id}", json={"notes": "Thanks for coming!"})
    assert response.status_code == 200
    assert response.json()["notes"] == "Thanks for coming!"


def test_the_start_of_a_started_or_purged_event_cannot_move(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    started = seed_event(session)
    purged = seed_event(session, title="Banquet", roster_purged_at=STARTS)
    clock(STARTS + timedelta(minutes=1))
    move = {"starts_local": "2030-11-02T10:00", "deadline_local": "2030-11-01T20:00"}
    response = admin_client.patch(f"{BASE}/{started}", json=move)
    assert _error(response) == (409, "event_started")
    assert (
        response.json()["error"]["message"]
        == "This event has already started, so its date can't change."
    )
    clock(NOW)
    assert _error(admin_client.patch(f"{BASE}/{purged}", json=move)) == (409, "event_started")


def test_a_deadline_moved_into_the_past_closes_sign_ups_at_once(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session)
    clock(NOW)
    body = admin_client.patch(
        f"{BASE}/{event_id}", json={"deadline_local": "2026-10-01T20:00"}
    ).json()
    assert body["state"] == "closed"


def test_a_start_moved_before_the_deadline_is_refused(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session)
    clock(NOW)
    response = admin_client.patch(f"{BASE}/{event_id}", json={"starts_local": "2030-10-18T19:00"})
    assert _error(response) == (400, "deadline_after_start")


def test_moving_the_start_keeps_the_queue(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, capacity=1)
    seed_registration(session, event_id, name="Amy Ace")
    seed_registration(session, event_id, name="Bob Bee", status="waitlist")
    seed_registration(session, event_id, name="Cal Cy", status="waitlist")
    clock(NOW)
    move = {"starts_local": "2030-11-02T10:00", "deadline_local": "2030-11-01T20:00"}
    assert admin_client.patch(f"{BASE}/{event_id}", json=move).status_code == 200
    assert _statuses(session, event_id) == [
        ("Amy Ace", "going"),
        ("Bob Bee", "waitlist"),
        ("Cal Cy", "waitlist"),
    ]


def test_capacity_can_equal_going_but_not_less(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, capacity=10, allow_guests=True, max_guests=2)
    seed_registration(session, event_id, name="Amy Ace", guests=2)
    seed_registration(session, event_id, name="Bob Bee")
    clock(NOW)
    response = admin_client.patch(f"{BASE}/{event_id}", json={"capacity": 3})
    assert _error(response) == (409, "capacity_below_going")
    assert (
        response.json()["error"]["message"]
        == "4 spots are already taken. Remove people first, or set at least 4."
    )
    assert admin_client.patch(f"{BASE}/{event_id}", json={"capacity": 4}).json()["capacity"] == 4


def test_raising_or_clearing_capacity_promotes(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, capacity=1)
    seed_registration(session, event_id, name="Amy Ace")
    seed_registration(session, event_id, name="Bob Bee", status="waitlist")
    seed_registration(session, event_id, name="Cal Cy", status="waitlist")
    clock(NOW)
    admin_client.patch(f"{BASE}/{event_id}", json={"capacity": 2})
    assert [s for _, s in _statuses(session, event_id)] == ["going", "going", "waitlist"]
    admin_client.patch(f"{BASE}/{event_id}", json={"capacity": None})
    assert [s for _, s in _statuses(session, event_id)] == ["going", "going", "going"]


def test_turning_guests_off_keeps_existing_guests(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, capacity=5, allow_guests=True, max_guests=2)
    seed_registration(session, event_id, name="Amy Ace", guests=2)
    clock(NOW)
    body = admin_client.patch(
        f"{BASE}/{event_id}", json={"allow_guests": False, "max_guests": 0}
    ).json()
    assert (body["allow_guests"], body["max_guests"], body["spots_taken"]) == (False, 0, 3)
    assert session.scalar(select(R.guests).where(R.event_id == event_id)) == 2


def test_cancel_keeps_everyone_and_restore_promotes(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, capacity=2)
    seed_registration(session, event_id, name="Amy Ace")
    seed_registration(session, event_id, name="Bob Bee", status="waitlist")
    clock(NOW)
    assert admin_client.post(f"{BASE}/{event_id}/cancel").json()["state"] == "cancelled"
    admin_client.patch(f"{BASE}/{event_id}", json={"capacity": 3})  # no promotion while cancelled
    assert _statuses(session, event_id) == [("Amy Ace", "going"), ("Bob Bee", "waitlist")]
    assert admin_client.post(f"{BASE}/{event_id}/restore").json()["state"] == "open"
    assert _statuses(session, event_id) == [("Amy Ace", "going"), ("Bob Bee", "going")]


def test_a_started_event_cannot_be_restored(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, cancelled_at=NOW)
    clock(STARTS)
    response = admin_client.post(f"{BASE}/{event_id}/restore")
    assert _error(response) == (409, "event_started")
    assert response.json()["error"]["message"] == "This event has started, so it can't be restored."


def test_delete_removes_the_event_and_its_sign_ups(
    session: Session, admin_client: TestClient
) -> None:
    event_id = seed_event(session)
    seed_registration(session, event_id, name="Amy Ace")
    assert admin_client.delete(f"{BASE}/{event_id}").status_code == 204
    assert session.scalar(select(func.count()).select_from(R)) == 0
    assert _error(admin_client.get(f"{BASE}/{event_id}/roster")) == (404, "club_event_not_found")


def test_viewers_cannot_reach_the_admin_routes(session: Session, viewer_client: TestClient) -> None:
    event_id = seed_event(session)
    assert viewer_client.get(BASE).status_code == 403
    assert viewer_client.get(f"{BASE}/{event_id}/roster").status_code == 403
    assert viewer_client.get("/api/admin/shooter-contacts").status_code == 403


def test_promotion_uses_the_store_clock(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, capacity=1)
    seed_registration(session, event_id, name="Amy Ace")
    waiting = seed_registration(session, event_id, name="Bob Bee", status="waitlist")
    frozen = datetime(2026, 10, 2, 18, 30, tzinfo=UTC)
    clock(frozen)
    admin_client.patch(f"{BASE}/{event_id}", json={"capacity": 2})
    assert session.scalar(select(R.promoted_at).where(R.id == waiting)) == frozen


def test_lowering_the_guest_limit_never_alters_existing_registrations(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, capacity=10, allow_guests=True, max_guests=3)
    seed_registration(session, event_id, name="Amy Ace", guests=3)
    seed_registration(session, event_id, name="Bob Bee", guests=2)
    clock(NOW)
    body = admin_client.patch(f"{BASE}/{event_id}", json={"max_guests": 1}).json()
    assert (body["max_guests"], body["spots_taken"]) == (1, 4 + 3)
    rows = session.execute(select(R.registrant_name, R.guests, R.status).order_by(R.id)).all()
    assert [tuple(r) for r in rows] == [("Amy Ace", 3, "going"), ("Bob Bee", 2, "going")]


def test_a_capacity_raise_never_promotes_on_a_started_event(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, capacity=1)
    seed_registration(session, event_id, name="Amy Ace")
    seed_registration(session, event_id, name="Bob Bee", status="waitlist")
    clock(STARTS + timedelta(minutes=1))
    assert admin_client.patch(f"{BASE}/{event_id}", json={"capacity": 5}).status_code == 200
    assert [s for _, s in _statuses(session, event_id)] == ["going", "waitlist"]
