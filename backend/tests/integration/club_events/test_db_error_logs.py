"""No log line ever carries an email (Plan 20 D22, §6.3): the ordinary flows, every domain error,
and a real CHECK and a real unique violation forced past the domain checks."""

import logging
import traceback
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sunday_clays.domain import club_event_store as store

from .seed import IP, seed_event, seed_shooter

EMAILS = ("ike.hadley@example.com", "dana.quill@example.com", "pat.kim@example.com")


def _logged(caplog: pytest.LogCaptureFixture) -> str:
    parts = [caplog.text]
    for record in caplog.records:
        parts.append(record.getMessage())
        if record.exc_info:
            parts.append("".join(traceback.format_exception(*record.exc_info)))
    return "\n".join(parts)


def _post(client: TestClient, url: str, body: dict[str, Any]) -> Any:
    return client.post(url, json=body, headers=IP)


def test_db_errors_never_log_an_email(
    session: Session,
    viewer_client: TestClient,
    events_on: None,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.DEBUG)
    event_id = seed_event(session, capacity=1)
    sid = seed_shooter(session, "Hadley, Ike")
    other = seed_shooter(session, "Ace, Amy")
    signups = f"/api/club-events/{event_id}/registrations"
    ike = _post(viewer_client, signups, {"shooter_id": sid, "email": EMAILS[0]})
    dana = _post(viewer_client, signups, {"name": "Dana Quill", "email": EMAILS[1]})
    assert (ike.status_code, dana.status_code) == (201, 201)
    cancel = f"{signups}/{dana.json()['registration_id']}/cancel"
    assert _post(viewer_client, cancel, {"email": EMAILS[1]}).status_code == 200
    for body, status in [
        ({"name": "Pat Kim", "email": "pat.kim@"}, 400),  # bad_email
        ({"shooter_id": other}, 400),  # email_required
        ({"name": "Ike Hadley", "email": EMAILS[2]}, 409),  # name_on_list
        ({"shooter_id": sid, "email": EMAILS[0]}, 409),  # already_signed_up
        ({"shooter_id": sid, "name": "Pat Kim", "email": EMAILS[2]}, 400),  # pick_or_type
    ]:
        assert _post(viewer_client, signups, body).status_code == status, body
    ike_cancel = f"{signups}/{ike.json()['registration_id']}/cancel"
    assert _post(viewer_client, ike_cancel, {"email": "wrong@example.com"}).status_code == 403
    assert _post(viewer_client, ike_cancel, {"email": EMAILS[0], "token": "x"}).status_code == 400

    # a real unique violation: the duplicate pre-check is bypassed
    monkeypatch.setattr(store, "name_key_is_active", lambda *args, **kwargs: False)
    pat = _post(viewer_client, signups, {"name": "Pat Kim", "email": EMAILS[2]})
    assert pat.status_code == 201
    again = _post(viewer_client, signups, {"name": "Kim, Pat", "email": EMAILS[2]})
    assert (again.status_code, again.json()["error"]["code"]) == (409, "already_signed_up")
    # the spec's "{name} is already on the list." with the typed name, never the generic fallback
    assert again.json()["error"]["message"] == "Kim, Pat is already on the list."

    # a real CHECK violation: cancelling no longer scrubs the email and the token
    monkeypatch.setattr(
        store,
        "inactive_values",
        lambda status, via, now: {"status": status, "cancelled_at": now, "cancelled_via": via},
    )
    pat_cancel = f"{signups}/{pat.json()['registration_id']}/cancel"
    broken = _post(viewer_client, pat_cancel, {"token": pat.json()["token"]})
    assert broken.status_code == 500
    assert broken.json() == {"error": {"code": "internal", "message": "Internal server error"}}

    text = _logged(caplog)
    assert "ck_club_event_registrations_inactive_scrubbed" in text
    assert "uq_club_event_registrations_name" in text
    for email in EMAILS:
        assert email not in text
    assert "@example.com" not in text
