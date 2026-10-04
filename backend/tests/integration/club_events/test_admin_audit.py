"""Every organizer action writes exactly one audit row, and no audit row ever holds a name or an
email (Plan 20 §5.5); no admin flow logs an email (D22)."""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.models import AuditLog

from .seed import NOW, seed_contact, seed_registration, seed_shooter

BASE = "/api/admin/club-events"
NAMES = ("Hadley", "Ike", "Dana", "Quill", "Hadly", "Amy", "Ace")


def _audit(session: Session) -> list[tuple[str, dict[str, Any]]]:
    rows = session.execute(
        select(AuditLog.action, AuditLog.details)
        .where(AuditLog.action != "auth.login")  # the admin_client fixture logs in first
        .order_by(AuditLog.id)
    )
    return [(str(action), dict(details)) for action, details in rows]


def test_audit_details_never_hold_a_name_or_email(
    session: Session,
    admin_client: TestClient,
    clock: Callable[[datetime], None],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    clock(NOW)
    ike = seed_shooter(session, "Hadley, Ike")
    amy = seed_shooter(session, "Ace, Amy")
    seed_contact(session, ike, "ike.hadley@example.com")
    created = admin_client.post(
        BASE,
        json={
            "title": "Fall Fun Shoot",
            "starts_local": "2026-10-17T10:00",
            "deadline_local": "2026-10-16T20:00",
            "capacity": 4,
            "allow_guests": True,
            "max_guests": 2,
        },
    ).json()
    event_id = created["id"]
    picked = seed_registration(session, event_id, shooter_id=ike)
    typed = seed_registration(session, event_id, name="Dana Quill", email="dana.quill@example.com")
    typo = seed_registration(session, event_id, name="Ike Hadly", email="ike.typo@example.com")
    calls = [
        ("PATCH", f"{BASE}/{event_id}", {"notes": "Bring a chair."}, "club_events.update"),
        ("GET", f"{BASE}/{event_id}/roster", None, "club_events.roster_view"),
        ("GET", f"{BASE}/{event_id}/roster.csv", None, "club_events.roster_export"),
        ("GET", f"{BASE}/{event_id}/emails?status=going", None, "club_events.emails_copy"),
        (
            "PATCH",
            f"{BASE}/{event_id}/registrations/{picked}",
            {"guests": 1},
            "club_events.registration.guests",
        ),
        (
            "POST",
            f"{BASE}/{event_id}/registrations/{typed}/reset-cancel-limit",
            None,
            "club_events.registration.reset_cancel_limit",
        ),
        (
            "POST",
            f"{BASE}/{event_id}/registrations/{typo}/link",
            {"shooter_id": amy},
            "club_events.registration.link",
        ),
        (
            "DELETE",
            f"{BASE}/{event_id}/registrations/{typed}",
            None,
            "club_events.registration.remove",
        ),
        ("POST", f"{BASE}/{event_id}/cancel", None, "club_events.cancel"),
        ("POST", f"{BASE}/{event_id}/restore", None, "club_events.restore"),
        ("GET", "/api/admin/shooter-contacts", None, "shooter_contacts.view"),
        (
            "PUT",
            f"/api/admin/shooter-contacts/{ike}",
            {"email": "ike@example.com"},
            "shooter_contacts.set",
        ),
        ("DELETE", f"/api/admin/shooter-contacts/{amy}", None, "shooter_contacts.delete"),
        ("DELETE", f"{BASE}/{event_id}", None, "club_events.delete"),
    ]
    for method, url, body, _ in calls:
        assert admin_client.request(method, url, json=body).status_code < 300, url
    actions = [action for action, _ in _audit(session)]
    assert actions == ["club_events.create", *(action for *_, action in calls)]
    for action, details in _audit(session):
        text = json.dumps(details)
        assert "@" not in text, action
        assert "name" not in details, action
        for name in NAMES:
            assert name not in text, (action, name)
    by_action = dict(_audit(session))
    assert by_action["club_events.create"] == {
        "id": event_id,
        "title": "Fall Fun Shoot",
        "starts_at": "2026-10-17T17:00:00+00:00",
    }
    assert by_action["club_events.update"] == {"id": event_id, "changed": ["notes"]}
    assert by_action["shooter_contacts.set"] == {"shooter_id": ike, "email_changed": True}
    assert by_action["club_events.registration.link"] == {
        "id": event_id,
        "registration_id": typo,
        "shooter_id": amy,
        "email_moved": True,
        "email_discarded": False,
    }
    for email in (
        "ike.hadley@example.com",
        "dana.quill@example.com",
        "ike.typo@example.com",
        "ike@example.com",
    ):
        assert email not in caplog.text
