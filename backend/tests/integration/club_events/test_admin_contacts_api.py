"""Shooters' emails on file (Plan 20 §5.5): organizers list, set and remove them."""

from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.models import ShooterContact

from .seed import NOW, seed_contact, seed_shooter

BASE = "/api/admin/shooter-contacts"


def test_list_set_and_delete(session: Session, admin_client: TestClient) -> None:
    ike = seed_shooter(session, "Hadley, Ike")
    amy = seed_shooter(session, "Ace, Amy")
    seed_contact(session, ike, "ike.hadley@example.com")
    listed = admin_client.get(BASE).json()
    assert [(c["shooter_id"], c["name"], c["email"], c["source"]) for c in listed] == [
        (ike, "Hadley, Ike", "ike.hadley@example.com", "signup")
    ]
    put = admin_client.put(f"{BASE}/{amy}", json={"email": " Amy.Ace@Example.com "})
    assert (put.status_code, put.json()["email"], put.json()["source"]) == (
        200,
        "amy.ace@example.com",
        "organizer",
    )
    changed = admin_client.put(f"{BASE}/{ike}", json={"email": "ike@example.com"}).json()
    assert (changed["email"], changed["source"]) == ("ike@example.com", "organizer")
    assert [c["name"] for c in admin_client.get(BASE).json()] == ["Ace, Amy", "Hadley, Ike"]
    assert admin_client.delete(f"{BASE}/{amy}").status_code == 204
    assert (
        session.scalar(select(ShooterContact.shooter_id).where(ShooterContact.shooter_id == amy))
        is None
    )


def test_refusals(session: Session, admin_client: TestClient) -> None:
    ike = seed_shooter(session, "Hadley, Ike")
    bad = admin_client.put(f"{BASE}/{ike}", json={"email": "not-an-email"})
    assert (bad.status_code, bad.json()["error"]["code"]) == (400, "bad_email")
    unknown = admin_client.put(f"{BASE}/999999", json={"email": "x@example.com"})
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (404, "shooter_not_found")
    missing = admin_client.delete(f"{BASE}/{ike}")
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "contact_not_found")


def test_an_organizer_edit_sets_updated_at_to_the_store_clock_and_leaves_last_used(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    ike = seed_shooter(session, "Hadley, Ike")
    old = NOW - timedelta(days=400)
    used = NOW - timedelta(days=30)
    seed_contact(session, ike, "ike.hadley@example.com", updated_at=old, last_used_at=used)
    clock(NOW)
    body = admin_client.put(f"{BASE}/{ike}", json={"email": "ike@example.com"}).json()
    assert body["updated_at"] == "2026-10-02T18:00:00Z"
    assert body["last_used_at"] == "2026-09-02T18:00:00Z"
    assert body["last_used_on"] == "2026-09-02"
