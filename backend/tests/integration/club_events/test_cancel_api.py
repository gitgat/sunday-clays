"""Cancelling (Plan 20 D10, D11, §5.3.7, §5.4): by device token, by email, constant and quiet."""

from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import fingerprint
from sunday_clays.domain import club_events as rules
from sunday_clays.models import ClubEventAttempt, ClubEventRegistration

from .seed import (
    STARTS,
    seed_attempts,
    seed_contact,
    seed_event,
    seed_registration,
    seed_shooter,
)

R = ClubEventRegistration
pytestmark = pytest.mark.usefixtures("events_on")
TOKEN = "device-token-for-dana"
MISMATCH = {
    "error": {
        "code": "cancel_not_matched",
        "message": "That email doesn't match this sign-up. Check it and try again.",
    }
}


def _cancel(
    client: TestClient, event_id: int, rid: int, ip: str = "203.0.113.7", **body: Any
) -> Any:
    return client.post(
        f"/api/club-events/{event_id}/registrations/{rid}/cancel",
        json=body,
        headers={"X-Real-IP": ip},
    )


def _dana(session: Session, event_id: int, **extra: Any) -> int:
    return seed_registration(
        session,
        event_id,
        name="Dana Quill",
        email="dana.quill@example.com",
        token_hash=rules.token_hash(TOKEN),
        **extra,
    )


def _state(session: Session, rid: int) -> tuple[Any, ...]:
    row = session.execute(
        select(R.status, R.cancelled_via, R.registrant_email, R.token_hash).where(R.id == rid)
    ).one()
    return tuple(row)


def test_the_device_token_cancels_and_scrubs(session: Session, viewer_client: TestClient) -> None:
    event_id = seed_event(session)
    rid = _dana(session, event_id)
    response = _cancel(viewer_client, event_id, rid, token=TOKEN)
    assert (response.status_code, response.json()) == (200, {"status": "cancelled", "promoted": 0})
    assert _state(session, rid) == ("cancelled", "device", None, None)


def test_the_registration_email_cancels_in_any_case(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    rid = _dana(session, event_id)
    assert (
        _cancel(viewer_client, event_id, rid, email="  DANA.Quill@Example.com").status_code == 200
    )
    assert _state(session, rid) == ("cancelled", "email", None, None)


def test_a_picked_shooter_cancels_with_the_email_on_file(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike")
    seed_contact(session, sid, "ike.hadley@example.com")
    rid = seed_registration(session, event_id, shooter_id=sid)
    assert _cancel(viewer_client, event_id, rid, email="Ike.Hadley@example.com").status_code == 200


def test_a_non_ascii_stored_email_cancels_with_its_typed_form(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    rid = seed_registration(session, event_id, name="Pat Kim", email="ü@x.de")
    assert _cancel(viewer_client, event_id, rid, email="Ü@X.DE").status_code == 200


def test_cancel_failures_are_indistinguishable(session: Session, viewer_client: TestClient) -> None:
    event_id = seed_event(session)
    typed = _dana(session, event_id)
    no_contact = seed_registration(session, event_id, shooter_id=seed_shooter(session, "Ace, Amy"))
    answers = [
        _cancel(viewer_client, event_id, typed, token="not-the-token"),
        _cancel(viewer_client, event_id, typed, email="wrong@example.com"),
        _cancel(viewer_client, event_id, typed, email="not an email"),
        _cancel(viewer_client, event_id, no_contact, email="amy.ace@example.com"),
    ]
    assert {(a.status_code, a.text) for a in answers} == {(403, answers[0].text)}
    assert answers[0].json() == MISMATCH
    rows = Counter(
        tuple(row)
        for row in session.execute(
            select(ClubEventAttempt.action, ClubEventAttempt.registration_id)
        )
    )
    # every failure counts for this client; only email failures count against the registration
    assert rows == Counter(
        {("cancel_fail", None): 1, ("cancel_fail", typed): 2, ("cancel_fail", no_contact): 1}
    )


@pytest.mark.parametrize("body", [{}, {"token": TOKEN, "email": "dana.quill@example.com"}])
def test_token_or_email_not_both(
    session: Session, viewer_client: TestClient, body: dict[str, str]
) -> None:
    event_id = seed_event(session)
    rid = _dana(session, event_id)
    response = _cancel(viewer_client, event_id, rid, **body)
    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "token_or_email",
        "message": "Send the sign-up's token or an email, not both.",
    }


def test_only_an_active_registration_of_this_event_can_be_cancelled(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    other = seed_event(session, title="Banquet")
    rid = _dana(session, other)
    gone = seed_registration(
        session, event_id, name="Pat Kim", status="cancelled", cancelled_via="device"
    )
    for target in (rid, gone):
        response = _cancel(viewer_client, event_id, target, token=TOKEN)
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "registration_not_found",
        )


def test_members_cannot_cancel_once_the_event_has_started(
    session: Session, viewer_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session)
    rid = _dana(session, event_id)
    clock(STARTS)
    response = _cancel(viewer_client, event_id, rid, token=TOKEN)
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "event_started",
        "message": "This event has started. Ask an organizer to change the list.",
    }


def test_a_cancel_promotes_the_waitlist(session: Session, viewer_client: TestClient) -> None:
    event_id = seed_event(session, capacity=1)
    rid = _dana(session, event_id)
    waiting = seed_registration(
        session, event_id, name="Pat Kim", email="pat.kim@example.com", status="waitlist"
    )
    assert _cancel(viewer_client, event_id, rid, token=TOKEN).json() == {
        "status": "cancelled",
        "promoted": 1,
    }
    row = session.execute(select(R.status, R.promoted_at).where(R.id == waiting)).one()
    assert row[0] == "going"
    assert row[1] is not None


def test_a_cancelled_event_still_takes_cancels_but_promotes_nobody(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session, capacity=1, cancelled_at=STARTS - timedelta(days=60))
    rid = _dana(session, event_id)
    waiting = seed_registration(
        session, event_id, name="Pat Kim", email="pat.kim@example.com", status="waitlist"
    )
    assert _cancel(viewer_client, event_id, rid, token=TOKEN).json() == {
        "status": "cancelled",
        "promoted": 0,
    }
    assert session.scalar(select(R.status).where(R.id == waiting)) == "waitlist"


def test_ten_failures_lock_this_client_out_of_both_paths(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    rid = _dana(session, event_id)
    seed_attempts(session, fingerprint("203.0.113.7"), "cancel_fail", 10)
    assert _cancel(viewer_client, event_id, rid, token=TOKEN).status_code == 429
    assert _cancel(viewer_client, event_id, rid, ip="198.51.100.9", token=TOKEN).status_code == 200


def test_a_registration_at_its_limit_refuses_even_the_right_email(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    rid = _dana(session, event_id)
    for n in range(rules.CANCEL_FAIL_PER_REGISTRATION):
        _cancel(viewer_client, event_id, rid, ip=f"198.51.100.{n + 1}", email="wrong@example.com")
    response = _cancel(
        viewer_client, event_id, rid, ip="198.51.100.77", email="dana.quill@example.com"
    )
    assert (response.status_code, response.json()["error"]["code"]) == (429, "rate_limited")


def test_token_cancel_ignores_registration_fail_limit(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    rid = _dana(session, event_id)
    for n in range(5):
        _cancel(viewer_client, event_id, rid, ip=f"198.51.100.{n + 1}", email="wrong@example.com")
    assert _cancel(viewer_client, event_id, rid, ip="198.51.100.77", token=TOKEN).status_code == 200
