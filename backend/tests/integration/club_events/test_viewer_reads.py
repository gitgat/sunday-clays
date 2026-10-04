"""Reading club events (Plan 20 §5.4, D20, D21, §4 display names and live shooters)."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from sunday_clays.models import ShooterProfile

from .seed import (
    DEADLINE,
    IP,
    STARTS,
    add_rule,
    seed_contact,
    seed_event,
    seed_registration,
    seed_shooter,
)

pytestmark = pytest.mark.usefixtures("events_on")
LATE = datetime(2026, 10, 18, 6, 30, tzinfo=UTC)  # Sat Oct 17, 23:30 in Los Angeles


def _list(client: TestClient) -> dict[str, list[dict[str, Any]]]:
    response = client.get("/api/club-events")
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


def test_upcoming_ascending_with_cancelled_ones_and_past_descending(
    session: Session, viewer_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    clock(datetime(2026, 10, 2, 18, 0, tzinfo=UTC))
    later = seed_event(
        session,
        title="Banquet",
        starts_at=STARTS + timedelta(days=7),
        deadline=DEADLINE + timedelta(days=7),
    )
    soon = seed_event(session, title="Fall Fun Shoot")
    off = seed_event(session, title="Work party", cancelled_at=datetime(2026, 9, 1, tzinfo=UTC))
    old = seed_event(
        session,
        title="Lesson day",
        starts_at=datetime(2026, 9, 5, 16, tzinfo=UTC),
        deadline=datetime(2026, 9, 5, 3, tzinfo=UTC),
    )
    older = seed_event(
        session,
        title="Spring social",
        starts_at=datetime(2026, 4, 5, 16, tzinfo=UTC),
        deadline=datetime(2026, 4, 5, 3, tzinfo=UTC),
    )
    body = _list(viewer_client)
    assert [e["id"] for e in body["upcoming"]] == [soon, off, later]
    assert [e["id"] for e in body["past"]] == [old, older]
    assert {e["id"]: e["state"] for e in body["upcoming"]} == {
        soon: "open",
        off: "cancelled",
        later: "open",
    }


def test_a_summary_carries_club_time_parts_and_counts(
    session: Session, viewer_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    clock(datetime(2026, 10, 2, 18, 0, tzinfo=UTC))
    event_id = seed_event(
        session,
        starts_at=LATE,
        deadline=datetime(2026, 10, 17, 3, 0, tzinfo=UTC),
        capacity=4,
        allow_guests=True,
        max_guests=2,
    )
    seed_registration(session, event_id, name="Amy Ace", guests=2)
    seed_registration(session, event_id, name="Bob Bee")
    seed_registration(session, event_id, name="Cal Cy", guests=1, status="waitlist")
    seed_registration(session, event_id, name="Pat Kim", status="cancelled", cancelled_via="device")
    [summary] = _list(viewer_client)["upcoming"]
    assert summary == {
        "id": event_id,
        "title": "Fall Fun Shoot",
        "starts_at": "2026-10-18T06:30:00Z",
        "local_date": "2026-10-17",
        "local_time": "23:30",
        "signup_deadline": "2026-10-17T03:00:00Z",
        "deadline_local_date": "2026-10-16",
        "deadline_local_time": "20:00",
        "state": "open",
        "capacity": 4,
        "spots_taken": 4,
        "waitlist_count": 1,
        "allow_guests": True,
        "max_guests": 2,
        "signups": 2,
        "purged": False,
        "upcoming": True,
    }


def test_the_upcoming_flag_matches_the_list_it_is_in_on_list_and_detail(
    session: Session, viewer_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    clock(datetime(2026, 10, 2, 18, 0, tzinfo=UTC))
    soon = seed_event(session, title="Fall Fun Shoot")
    old = seed_event(
        session,
        title="Lesson day",
        starts_at=datetime(2026, 9, 5, 16, tzinfo=UTC),
        deadline=datetime(2026, 9, 5, 3, tzinfo=UTC),
    )
    body = _list(viewer_client)
    assert [e["upcoming"] for e in body["upcoming"]] == [True]
    assert [e["upcoming"] for e in body["past"]] == [False]
    assert viewer_client.get(f"/api/club-events/{soon}").json()["upcoming"] is True
    assert viewer_client.get(f"/api/club-events/{old}").json()["upcoming"] is False


def test_late_evening_event_stays_upcoming(
    session: Session, viewer_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, starts_at=LATE, deadline=LATE - timedelta(hours=1))
    clock(datetime(2026, 10, 18, 6, 45, tzinfo=UTC))  # 23:45 in Los Angeles, Sunday in UTC
    body = _list(viewer_client)
    assert [(e["id"], e["state"]) for e in body["upcoming"]] == [(event_id, "started")]
    clock(datetime(2026, 10, 18, 7, 1, tzinfo=UTC))  # 00:01 on Sunday in Los Angeles
    body = _list(viewer_client)
    assert body["upcoming"] == []
    assert [e["id"] for e in body["past"]] == [event_id]


def test_a_purged_event_reports_its_final_counts_and_no_roster(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(
        session,
        starts_at=datetime(2026, 8, 1, 16, tzinfo=UTC),
        deadline=datetime(2026, 8, 1, 3, tzinfo=UTC),
        roster_purged_at=datetime(2026, 9, 1, tzinfo=UTC),
        final_signups=28,
        final_spots=31,
    )
    detail = viewer_client.get(f"/api/club-events/{event_id}").json()
    assert (detail["purged"], detail["signups"], detail["spots_taken"], detail["roster"]) == (
        True,
        28,
        31,
        [],
    )


def test_the_roster_lists_going_then_the_waitlist_by_display_name(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(
        session,
        capacity=2,
        allow_guests=True,
        max_guests=2,
        notes="Bring <b>gloves</b>\nand a chair",
    )
    renamed = seed_shooter(session, "Hadley, Ike", profile_name="Hadley, Isaac")
    profile_gone = seed_shooter(session, "Bee, Bob")
    target = seed_shooter(session, "Ace, Amy")
    source = seed_shooter(session, "Ace, Aimee", profile=False)
    add_rule(session, "merge_shooter", {"source_shooter_id": source, "target_shooter_id": target})
    b = seed_registration(session, event_id, name="Dana Quill", status="waitlist", guests=2)
    a = seed_registration(session, event_id, shooter_id=renamed, guests=1)  # going, later id
    c = seed_registration(session, event_id, shooter_id=source, status="waitlist")
    d = seed_registration(session, event_id, shooter_id=profile_gone, status="waitlist")
    seed_registration(
        session, event_id, name="Pat Kim", status="removed", cancelled_via="organizer"
    )
    session.execute(delete(ShooterProfile).where(ShooterProfile.shooter_id == profile_gone))
    detail = viewer_client.get(f"/api/club-events/{event_id}").json()
    assert detail["notes"] == "Bring <b>gloves</b>\nand a chair"
    assert detail["roster"] == [
        {
            "registration_id": a,
            "name": "Hadley, Isaac",
            "shooter_id": renamed,
            "guests": 1,
            "status": "going",
            "waitlist_position": None,
        },
        {
            "registration_id": b,
            "name": "Dana Quill",
            "shooter_id": None,
            "guests": 2,
            "status": "waitlist",
            "waitlist_position": 1,
        },
        {
            "registration_id": c,
            "name": "Ace, Amy",
            "shooter_id": target,
            "guests": 0,
            "status": "waitlist",
            "waitlist_position": 2,
        },
        {
            "registration_id": d,
            "name": "Bee, Bob",
            "shooter_id": profile_gone,
            "guests": 0,
            "status": "waitlist",
            "waitlist_position": 3,
        },
    ]


def test_an_unknown_event_is_404(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/club-events/999999")
    assert (response.status_code, response.json()["error"]["code"]) == (404, "club_event_not_found")


def test_no_viewer_response_contains_an_email(session: Session, viewer_client: TestClient) -> None:
    event_id = seed_event(session, capacity=1)
    sid = seed_shooter(session, "Hadley, Ike")
    seed_contact(session, sid, "ike.hadley@example.com")
    seed_registration(session, event_id, shooter_id=sid)
    seed_registration(
        session, event_id, name="Dana Quill", email="dana.quill@example.com", status="waitlist"
    )
    signup = viewer_client.post(
        f"/api/club-events/{event_id}/registrations",
        json={"name": "Pat Kim", "email": "pat.kim@example.com"},
        headers=IP,
    )
    cancel = viewer_client.post(
        f"/api/club-events/{event_id}/registrations/{signup.json()['registration_id']}/cancel",
        json={"token": signup.json()["token"]},
        headers=IP,
    )
    reads = [
        viewer_client.get("/api/club-events"),
        viewer_client.get(f"/api/club-events/{event_id}"),
        viewer_client.get(f"/api/club-events/{event_id}/signup-check?shooter_id={sid}", headers=IP),
    ]
    for response in [*reads, signup, cancel]:
        assert response.status_code in (200, 201)
        assert "@" not in response.text, response.url
        for key in ('"email"', '"registrant_email"', '"token_hash"', '"queue_at"', '"created_at"'):
            assert key not in response.text, (key, response.url)


def test_viewer_responses_are_never_tagged_or_stored(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike")
    for url in (
        "/api/club-events",
        f"/api/club-events/{event_id}",
        f"/api/club-events/{event_id}/signup-check?shooter_id={sid}",
    ):
        response = viewer_client.get(url, headers=IP)
        assert response.status_code == 200, url
        assert response.headers["cache-control"] == "no-store", url
        assert "etag" not in response.headers, url


def test_the_local_parts_never_use_the_server_zone_of_the_date(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    detail = viewer_client.get(f"/api/club-events/{event_id}").json()
    assert (detail["local_date"], detail["local_time"]) == (str(date(2030, 10, 19)), "09:00")
    assert (detail["deadline_local_date"], detail["deadline_local_time"]) == ("2030-10-18", "20:00")
