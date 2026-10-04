"""Signing up and the sign-up check (Plan 20 §5.4, D4, D5, D6, D8, D9, D14, §5.3.7)."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import fingerprint
from sunday_clays.domain import club_events as rules
from sunday_clays.models import ClubEventAttempt, ClubEventRegistration, ShooterContact

from .seed import (
    DEADLINE,
    IP,
    add_alias,
    add_rule,
    seed_attempts,
    seed_contact,
    seed_event,
    seed_registration,
    seed_shooter,
)

R = ClubEventRegistration
pytestmark = pytest.mark.usefixtures("events_on")


def _post(client: TestClient, event_id: int, **body: Any) -> Any:
    payload = {"shooter_id": None, "name": None, "email": None, "guests": 0} | body
    return client.post(f"/api/club-events/{event_id}/registrations", json=payload, headers=IP)


def _error(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def _registrations(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(R)) or 0)


def _contact(session: Session, shooter_id: int) -> tuple[str, str, datetime | None] | None:
    row = session.execute(
        select(ShooterContact.email, ShooterContact.source, ShooterContact.last_used_at).where(
            ShooterContact.shooter_id == shooter_id
        )
    ).one_or_none()
    return None if row is None else (row[0], row[1], row[2])


# --- the three sign-up paths (D4, D5) ------------------------------------------------------------


def test_a_picked_shooter_with_an_email_on_file_is_never_asked_again(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike")
    seed_contact(session, sid, "ike.hadley@example.com")
    response = _post(viewer_client, event_id, shooter_id=sid)
    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["email_used"], body["waitlist_position"]) == (
        "going",
        "on_file",
        None,
    )
    row = session.execute(
        select(R.shooter_id, R.registrant_email).where(R.id == body["registration_id"])
    ).one()
    assert tuple(row) == (sid, None)
    contact = _contact(session, sid)
    assert contact is not None
    assert contact[2] is not None


def test_a_picked_shooter_without_an_email_saves_one_with_source_signup(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike")
    response = _post(viewer_client, event_id, shooter_id=sid, email=" Ike.Hadley@Example.com ")
    assert response.status_code == 201
    assert response.json()["email_used"] == "given"
    contact = _contact(session, sid)
    assert contact is not None
    assert contact[:2] == ("ike.hadley@example.com", "signup")


def test_an_email_is_required_whenever_it_is_asked(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike")
    assert _error(_post(viewer_client, event_id, shooter_id=sid)) == (400, "email_required")
    assert _error(_post(viewer_client, event_id, name="Dana Quill", email="  ")) == (
        400,
        "email_required",
    )
    assert _registrations(session) == 0


def test_a_typed_name_keeps_its_email_on_the_registration(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    response = _post(
        viewer_client, event_id, name="  Dana   Quill ", email="Dana.Quill@example.com"
    )
    assert response.status_code == 201
    assert response.json()["email_used"] == "given"
    row = session.execute(
        select(R.shooter_id, R.registrant_name, R.name_key, R.registrant_email).where(
            R.id == response.json()["registration_id"]
        )
    ).one()
    assert tuple(row) == (None, "Dana Quill", "dana quill", "dana.quill@example.com")


def test_the_token_is_returned_once_and_only_its_hash_is_stored(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    body = _post(viewer_client, event_id, name="Dana Quill", email="dana.quill@example.com").json()
    stored = session.scalar(select(R.token_hash).where(R.id == body["registration_id"]))
    assert len(body["token"]) >= 40
    assert stored == hashlib.sha256(body["token"].encode()).hexdigest() != body["token"]


# --- bodies (§5.3.6) -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [{}, {"shooter_id": 1, "name": "Dana Quill", "email": "dana.quill@example.com"}],
    ids=["neither", "both"],
)
def test_pick_or_type_is_a_400_not_a_422(
    session: Session, viewer_client: TestClient, body: dict[str, Any]
) -> None:
    event_id = seed_event(session)
    response = _post(viewer_client, event_id, **body)
    assert _error(response) == (400, "pick_or_type")
    assert (
        response.json()["error"]["message"]
        == "Pick a name from the list, or choose I'm not listed."
    )


def test_a_long_email_is_bad_email_and_never_echoed(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    long_email = "a" * 290 + "@example.com"
    response = _post(viewer_client, event_id, name="Dana Quill", email=long_email)
    assert _error(response) == (400, "bad_email")
    assert long_email not in response.text
    assert "input" not in response.text


# --- duplicates (D14) ----------------------------------------------------------------------------


def test_one_sign_up_per_shooter_per_event(session: Session, viewer_client: TestClient) -> None:
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike")
    seed_contact(session, sid, "ike.hadley@example.com")
    assert _post(viewer_client, event_id, shooter_id=sid).status_code == 201
    response = _post(viewer_client, event_id, shooter_id=sid)
    assert _error(response) == (409, "already_signed_up")
    assert response.json()["error"]["message"] == "Hadley, Ike is already on the list."


def test_a_typed_name_in_the_other_order_is_a_duplicate(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    assert (
        _post(
            viewer_client, event_id, name="Dana Quill", email="dana.quill@example.com"
        ).status_code
        == 201
    )
    response = _post(viewer_client, event_id, name="Quill, Dana", email="dq@example.com")
    assert _error(response) == (409, "already_signed_up")


@pytest.mark.parametrize(
    "typed",
    ["Ike Hadley", "Isaac Hadley", "Hadley Ikey", "Ike Hadlee"],
    ids=["display name", "renamed display name", "alias in the other order", "alias_name rule"],
)
def test_a_typed_name_that_is_on_the_list_is_refused(
    session: Session, viewer_client: TestClient, typed: str
) -> None:
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike", profile_name="Hadley, Isaac")  # renamed
    add_alias(session, "ikey hadley", sid)
    add_rule(session, "alias_name", {"name_key": "ike hadlee", "shooter_id": sid})
    response = _post(viewer_client, event_id, name=typed, email="x.y@example.com")
    assert _error(response) == (409, "name_on_list")
    assert response.json()["error"]["message"] == (
        "That name is already on the shooter list. Pick it from the list instead."
    )


def test_a_merge_source_and_its_target_are_one_shooter(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    target = seed_shooter(session, "Hadley, Ike")
    source = seed_shooter(session, "Hadly, Ike", profile=False)
    add_rule(session, "merge_shooter", {"source_shooter_id": source, "target_shooter_id": target})
    seed_contact(session, target, "ike.hadley@example.com")
    seed_registration(session, event_id, shooter_id=source)  # signed up before the merge
    assert _error(_post(viewer_client, event_id, shooter_id=target)) == (409, "already_signed_up")
    other = seed_event(session, title="Banquet")
    assert _post(viewer_client, other, shooter_id=source).status_code == 201  # picked as the target
    assert _error(_post(viewer_client, other, shooter_id=target)) == (409, "already_signed_up")


def test_profileless_shooter_name_can_be_typed(session: Session, viewer_client: TestClient) -> None:
    event_id = seed_event(session)
    hidden = seed_shooter(session, "Bee, Bob", profile=False)
    deceased = seed_shooter(session, "Cy, Cal", status="deceased")
    assert _error(_post(viewer_client, event_id, shooter_id=hidden, email="b@example.com")) == (
        404,
        "shooter_not_found",
    )
    assert _error(_post(viewer_client, event_id, shooter_id=deceased, email="c@example.com")) == (
        404,
        "shooter_not_found",
    )
    assert (
        _post(viewer_client, event_id, name="Bob Bee", email="bob.bee@example.com").status_code
        == 201
    )
    assert (
        _post(viewer_client, event_id, name="Cal Cy", email="cal.cy@example.com").status_code == 201
    )


# --- guests, capacity and refusals (D8, D9, §5.3.4) ----------------------------------------------


def test_guests_follow_the_event_rule(session: Session, viewer_client: TestClient) -> None:
    members_only = seed_event(session)
    two_each = seed_event(session, title="Banquet", allow_guests=True, max_guests=2)
    assert _error(
        _post(viewer_client, members_only, name="Dana Quill", email="d@example.com", guests=1)
    ) == (400, "bad_guests")
    assert _error(
        _post(viewer_client, two_each, name="Dana Quill", email="d@example.com", guests=3)
    ) == (400, "bad_guests")
    assert (
        _post(
            viewer_client, two_each, name="Dana Quill", email="d@example.com", guests=2
        ).status_code
        == 201
    )


def test_capacity_counts_guests_and_the_waitlist_keeps_its_order(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session, capacity=3, allow_guests=True, max_guests=2)
    first = _post(viewer_client, event_id, name="Amy Ace", email="amy@example.com", guests=1).json()
    second = _post(
        viewer_client, event_id, name="Bob Bee", email="bob@example.com", guests=1
    ).json()
    third = _post(viewer_client, event_id, name="Cal Cy", email="cal@example.com").json()
    assert (first["status"], first["waitlist_position"]) == ("going", None)
    assert (second["status"], second["waitlist_position"]) == ("waitlist", 1)
    assert (third["status"], third["waitlist_position"]) == ("waitlist", 2)  # never jumps Bob


def test_no_capacity_never_waitlists(session: Session, viewer_client: TestClient) -> None:
    event_id = seed_event(session)
    for n, name in enumerate(["Amy Ace", "Bob Bee", "Cal Cy"]):
        assert (
            _post(viewer_client, event_id, name=name, email=f"{n}@example.com").json()["status"]
            == "going"
        )


def test_closed_cancelled_full_and_unknown_events_refuse(
    session: Session,
    viewer_client: TestClient,
    clock: Callable[[datetime], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    open_event = seed_event(session)
    cancelled = seed_event(session, title="Banquet", cancelled_at=DEADLINE - timedelta(days=30))
    assert _error(_post(viewer_client, cancelled, name="Dana Quill", email="d@example.com")) == (
        409,
        "event_cancelled",
    )
    assert _error(_post(viewer_client, 999_999, name="Dana Quill", email="d@example.com")) == (
        404,
        "club_event_not_found",
    )
    monkeypatch.setattr(rules, "MAX_ACTIVE_PER_EVENT", 1)
    assert (
        _post(viewer_client, open_event, name="Amy Ace", email="a@example.com").status_code == 201
    )
    response = _post(viewer_client, open_event, name="Bob Bee", email="b@example.com")
    assert _error(response) == (409, "signups_full")
    monkeypatch.setattr(rules, "MAX_ACTIVE_PER_EVENT", 200)
    clock(DEADLINE)
    response = _post(viewer_client, open_event, name="Cal Cy", email="c@example.com")
    assert _error(response) == (409, "signups_closed")
    assert response.json()["error"]["message"] == "Sign-ups for this event have closed."


# --- limits (§5.3.7) -----------------------------------------------------------------------------


def test_every_signup_post_counts_even_a_refused_one(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    assert _post(viewer_client, event_id).status_code == 400  # pick_or_type
    actions = session.scalars(
        select(ClubEventAttempt.action).where(ClubEventAttempt.ip == fingerprint("203.0.113.7"))
    ).all()
    assert actions == ["signup"]


def test_the_signup_limit_is_100_an_hour_per_fingerprint(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    seed_attempts(session, fingerprint("203.0.113.7"), "signup", 99)
    assert _post(viewer_client, event_id, name="Amy Ace", email="a@example.com").status_code == 201
    response = _post(viewer_client, event_id, name="Bob Bee", email="b@example.com")
    assert _error(response) == (429, "rate_limited")
    assert (
        response.json()["error"]["message"] == "Too many tries from here. Wait a bit and try again."
    )
    other = viewer_client.post(
        f"/api/club-events/{event_id}/registrations",
        json={"name": "Cal Cy", "email": "c@example.com"},
        headers={"X-Real-IP": "198.51.100.9"},
    )
    assert other.status_code == 201  # another client has its own budget


def test_the_check_limit_is_60_per_10_minutes(session: Session, viewer_client: TestClient) -> None:
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike")
    seed_attempts(session, fingerprint("203.0.113.7"), "check", 59)
    url = f"/api/club-events/{event_id}/signup-check?shooter_id={sid}"
    assert viewer_client.get(url, headers=IP).status_code == 200
    assert _error(viewer_client.get(url, headers=IP)) == (429, "rate_limited")


def test_signup_check_says_only_whether_an_email_is_on_file_and_who_is_on(
    session: Session, viewer_client: TestClient
) -> None:
    event_id = seed_event(session)
    with_email = seed_shooter(session, "Hadley, Ike")
    without = seed_shooter(session, "Ace, Amy")
    seed_contact(session, with_email, "ike.hadley@example.com")
    seed_registration(session, event_id, shooter_id=with_email)
    base = f"/api/club-events/{event_id}/signup-check"
    assert viewer_client.get(f"{base}?shooter_id={with_email}", headers=IP).json() == {
        "has_email": True,
        "already_signed_up": True,
    }
    assert viewer_client.get(f"{base}?shooter_id={without}", headers=IP).json() == {
        "has_email": False,
        "already_signed_up": False,
    }
    assert _error(viewer_client.get(f"{base}?shooter_id=999999", headers=IP)) == (
        404,
        "shooter_not_found",
    )


# --- contact timestamps (the retention job reads them) -------------------------------------------

LONG_AGO = datetime(2024, 1, 1, tzinfo=UTC)
FROZEN = datetime(2026, 10, 2, 18, 0, tzinfo=UTC)


def _stamps(session: Session, shooter_id: int) -> tuple[datetime | None, datetime]:
    row = session.execute(
        select(ShooterContact.last_used_at, ShooterContact.updated_at).where(
            ShooterContact.shooter_id == shooter_id
        )
    ).one()
    return row[0], row[1]


def test_reusing_a_contact_refreshes_both_timestamps(
    session: Session, viewer_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    clock(FROZEN)
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike")
    seed_contact(session, sid, "ike.hadley@example.com", updated_at=LONG_AGO, last_used_at=LONG_AGO)
    assert _post(viewer_client, event_id, shooter_id=sid).status_code == 201
    assert _stamps(session, sid) == (FROZEN, FROZEN)


def test_a_new_contact_is_stamped_with_the_stores_clock(
    session: Session, viewer_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    clock(FROZEN)
    event_id = seed_event(session)
    sid = seed_shooter(session, "Hadley, Ike")
    response = _post(viewer_client, event_id, shooter_id=sid, email="ike.hadley@example.com")
    assert response.status_code == 201
    assert _stamps(session, sid)[0] == FROZEN
