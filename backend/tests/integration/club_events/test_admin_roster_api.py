"""The organizer's roster (Plan 20 §5.5, D15): emails, CSV, the email list, remove, guests,
the cancel-limit reset and linking a typed name to a shooter."""

import csv
import io
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import fingerprint
from sunday_clays.domain import club_events as rules
from sunday_clays.models import ClubEventRegistration, ShooterContact

from .seed import (
    IP,
    NOW,
    STARTS,
    add_rule,
    seed_attempts,
    seed_contact,
    seed_event,
    seed_registration,
    seed_shooter,
)

R = ClubEventRegistration
BASE = "/api/admin/club-events"


def _error(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


@pytest.fixture
def world(session: Session) -> dict[str, int]:
    event_id = seed_event(session, capacity=3, allow_guests=True, max_guests=2)
    ike = seed_shooter(session, "Hadley, Ike")
    seed_contact(session, ike, "ike.hadley@example.com")
    return {
        "event": event_id,
        "ike": ike,
        "ike_reg": seed_registration(session, event_id, shooter_id=ike, guests=1),
        "dana": seed_registration(
            session, event_id, name="Dana Quill", email="dana.quill@example.com"
        ),
        "typo": seed_registration(
            session, event_id, name="Ike Hadly", email="ike.typo@example.com", status="waitlist"
        ),
        "gone": seed_registration(
            session, event_id, name="Pat Kim", status="cancelled", cancelled_via="device"
        ),
    }


def test_the_roster_shows_every_row_with_emails_and_sources(
    session: Session, admin_client: TestClient, world: dict[str, int]
) -> None:
    seed_attempts(session, "fp-x", "cancel_fail", 2, registration_id=world["dana"])
    rows = {row["id"]: row for row in admin_client.get(f"{BASE}/{world['event']}/roster").json()}
    ike, dana, typo, gone = (rows[world[k]] for k in ("ike_reg", "dana", "typo", "gone"))
    assert (
        ike["name"],
        ike["typed_name"],
        ike["shooter_id"],
        ike["email"],
        ike["email_source"],
    ) == ("Hadley, Ike", None, world["ike"], "ike.hadley@example.com", "contact")
    assert (dana["email"], dana["email_source"], dana["cancel_fail_count"]) == (
        "dana.quill@example.com",
        "registration",
        2,
    )
    assert (typo["status"], typo["waitlist_position"]) == ("waitlist", 1)
    assert typo["suggested_shooter"] == {
        "id": world["ike"],
        "name": "Hadley, Ike",
        "has_email": True,
    }
    assert dana["suggested_shooter"] is None
    assert len(dana["signed_up_local"]) == len("2026-10-02 11:00")
    assert (gone["status"], gone["cancelled_via"], gone["email"]) == ("cancelled", "device", None)
    assert [r["id"] for r in admin_client.get(f"{BASE}/{world['event']}/roster").json()] == [
        world["ike_reg"],
        world["dana"],
        world["typo"],
        world["gone"],
    ]


def test_the_csv_has_the_header_filename_order_and_escaping(
    session: Session, admin_client: TestClient, world: dict[str, int]
) -> None:
    seed_registration(
        session,
        world["event"],
        name="=HYPERLINK(1) Amy",
        email="amy@example.com",
        status="waitlist",
    )
    response = admin_client.get(f"{BASE}/{world['event']}/roster.csv")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="club-event-{world["event"]}-2030-10-19-roster.csv"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.text.startswith(
        "status,waitlist_position,name,shooter_id,email,guests,spots,signed_up_local\r\n"
    )
    rows = list(csv.reader(io.StringIO(response.text)))[1:]
    assert [r[:3] for r in rows] == [
        ["going", "", "Hadley, Ike"],
        ["going", "", "Dana Quill"],
        ["waitlist", "1", "Ike Hadly"],
        ["waitlist", "2", "'=HYPERLINK(1) Amy"],
    ]
    assert rows[0][3:7] == [str(world["ike"]), "ike.hadley@example.com", "1", "2"]


def test_the_email_list_is_distinct_in_queue_order(
    admin_client: TestClient, world: dict[str, int]
) -> None:
    url = f"{BASE}/{world['event']}/emails"
    assert admin_client.get(url).json() == {
        "emails": ["ike.hadley@example.com", "dana.quill@example.com"]
    }
    assert admin_client.get(f"{url}?status=waitlist").json() == {"emails": ["ike.typo@example.com"]}
    assert len(admin_client.get(f"{url}?status=active").json()["emails"]) == 3


def test_remove_scrubs_promotes_and_ignores_every_limit(
    session: Session,
    admin_client: TestClient,
    world: dict[str, int],
    clock: Callable[[datetime], None],
) -> None:
    clock(NOW)
    seed_attempts(
        session, fingerprint("testclient"), "cancel_fail", 50, registration_id=world["dana"]
    )
    assert (
        admin_client.delete(f"{BASE}/{world['event']}/registrations/{world['dana']}").status_code
        == 204
    )
    row = session.execute(
        select(R.status, R.cancelled_via, R.registrant_email, R.token_hash).where(
            R.id == world["dana"]
        )
    ).one()
    assert tuple(row) == ("removed", "organizer", None, None)
    assert session.scalar(select(R.status).where(R.id == world["typo"])) == "going"  # 2 + 1 fits 3
    again = admin_client.delete(f"{BASE}/{world['event']}/registrations/{world['dana']}")
    assert _error(again) == (404, "registration_not_found")


def test_no_promotion_after_start(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    # §5.3.2 "never once started" and §5.9 "Event started": the organizer can still remove a row,
    # and nobody moves up from the waitlist.
    event_id = seed_event(session, capacity=1)
    going = seed_registration(session, event_id, name="Amy Ace")
    waiting = seed_registration(session, event_id, name="Bob Bee", status="waitlist")
    clock(STARTS + timedelta(minutes=1))
    assert admin_client.delete(f"{BASE}/{event_id}/registrations/{going}").status_code == 204
    assert session.scalar(select(R.status).where(R.id == going)) == "removed"
    assert session.scalar(select(R.status).where(R.id == waiting)) == "waitlist"
    assert session.scalar(select(R.promoted_at).where(R.id == waiting)) is None


def test_guests_change_within_capacity_and_a_decrease_promotes(
    session: Session,
    admin_client: TestClient,
    world: dict[str, int],
    clock: Callable[[datetime], None],
) -> None:
    clock(NOW)
    url = f"{BASE}/{world['event']}/registrations/{world['ike_reg']}"
    over = admin_client.patch(url, json={"guests": 2})
    assert _error(over) == (409, "over_capacity")
    assert over.json()["error"]["message"] == "That would go over capacity by 1."
    assert _error(admin_client.patch(url, json={"guests": 11})) == (400, "bad_guests")
    assert admin_client.patch(url, json={"guests": 0}).json() == {"guests": 0}
    assert session.scalar(select(R.status).where(R.id == world["typo"])) == "going"


def test_a_reset_lets_the_right_email_cancel_again(
    session: Session,
    admin_client: TestClient,
    viewer_client: TestClient,
    world: dict[str, int],
    events_on: None,
) -> None:
    for n in range(rules.CANCEL_FAIL_PER_REGISTRATION):
        seed_attempts(session, f"fp-{n}", "cancel_fail", 1, registration_id=world["dana"])
    cancel = f"/api/club-events/{world['event']}/registrations/{world['dana']}/cancel"
    assert (
        viewer_client.post(cancel, json={"email": "dana.quill@example.com"}, headers=IP).status_code
        == 429
    )
    reset = admin_client.post(
        f"{BASE}/{world['event']}/registrations/{world['dana']}/reset-cancel-limit"
    )
    assert reset.json() == {"cleared": 5}
    assert (
        viewer_client.post(cancel, json={"email": "dana.quill@example.com"}, headers=IP).status_code
        == 200
    )


def test_link_moves_the_email_when_the_shooter_has_none(
    session: Session, admin_client: TestClient, world: dict[str, int]
) -> None:
    amy = seed_shooter(session, "Ace, Amy")
    url = f"{BASE}/{world['event']}/registrations/{world['typo']}/link"
    assert admin_client.post(url, json={"shooter_id": amy}).json() == {
        "shooter_id": amy,
        "email_moved": True,
        "email_discarded": False,
    }
    row = session.execute(
        select(R.shooter_id, R.registrant_name, R.registrant_email).where(R.id == world["typo"])
    ).one()
    assert tuple(row) == (amy, "Ike Hadly", None)
    contact = session.execute(
        select(ShooterContact.email, ShooterContact.source).where(ShooterContact.shooter_id == amy)
    ).one()
    assert tuple(contact) == ("ike.typo@example.com", "link")
    assert _error(admin_client.post(url, json={"shooter_id": amy})) == (409, "already_linked")


def test_link_discards_the_email_when_the_shooter_has_one(
    session: Session, admin_client: TestClient, world: dict[str, int]
) -> None:
    other = seed_event(session, title="Banquet")
    typed = seed_registration(session, other, name="Ike Hadly", email="ike.typo@example.com")
    body = admin_client.post(
        f"{BASE}/{other}/registrations/{typed}/link", json={"shooter_id": world["ike"]}
    ).json()
    assert (body["email_moved"], body["email_discarded"]) == (False, True)
    contact = session.scalar(
        select(ShooterContact.email).where(ShooterContact.shooter_id == world["ike"])
    )
    assert contact == "ike.hadley@example.com"


def test_link_refuses_a_shooter_already_on_the_event(
    admin_client: TestClient, world: dict[str, int]
) -> None:
    url = f"{BASE}/{world['event']}/registrations/{world['typo']}/link"
    assert _error(admin_client.post(url, json={"shooter_id": world["ike"]})) == (
        409,
        "already_signed_up",
    )
    assert _error(admin_client.post(url, json={"shooter_id": 999_999})) == (
        404,
        "shooter_not_found",
    )


def test_a_purged_event_has_an_empty_roster_and_csv(
    session: Session, admin_client: TestClient
) -> None:
    event_id = seed_event(session, roster_purged_at=NOW, final_signups=3, final_spots=4)
    assert admin_client.get(f"{BASE}/{event_id}/roster").json() == []
    text = admin_client.get(f"{BASE}/{event_id}/roster.csv").text
    assert text == "status,waitlist_position,name,shooter_id,email,guests,spots,signed_up_local\r\n"


def test_a_guest_decrease_never_promotes_on_a_started_event(
    session: Session, admin_client: TestClient, clock: Callable[[datetime], None]
) -> None:
    event_id = seed_event(session, capacity=3, allow_guests=True, max_guests=2)
    big = seed_registration(session, event_id, name="Amy Ace", guests=2)
    waiting = seed_registration(session, event_id, name="Bob Bee", status="waitlist")
    clock(STARTS + timedelta(minutes=1))
    response = admin_client.patch(f"{BASE}/{event_id}/registrations/{big}", json={"guests": 0})
    assert response.json() == {"guests": 0}
    assert session.scalar(select(R.status).where(R.id == waiting)) == "waitlist"


def test_a_link_that_moves_an_email_stamps_the_contact_clock(
    session: Session,
    admin_client: TestClient,
    world: dict[str, int],
    clock: Callable[[datetime], None],
) -> None:
    clock(NOW)
    amy = seed_shooter(session, "Ace, Amy")
    url = f"{BASE}/{world['event']}/registrations/{world['typo']}/link"
    assert admin_client.post(url, json={"shooter_id": amy}).status_code == 200
    stamps = session.execute(
        select(ShooterContact.updated_at, ShooterContact.last_used_at).where(
            ShooterContact.shooter_id == amy
        )
    ).one()
    assert tuple(stamps) == (NOW, NOW)


def test_a_link_that_discards_stamps_last_used_and_keeps_updated_at(
    session: Session,
    admin_client: TestClient,
    world: dict[str, int],
    clock: Callable[[datetime], None],
) -> None:
    old = NOW - timedelta(days=100)
    session.execute(
        ShooterContact.__table__.update()
        .where(ShooterContact.shooter_id == world["ike"])
        .values(updated_at=old, last_used_at=None)
    )
    clock(NOW)
    other = seed_event(session, title="Banquet")
    typed = seed_registration(session, other, name="Ike Hadly", email="ike.typo@example.com")
    response = admin_client.post(
        f"{BASE}/{other}/registrations/{typed}/link", json={"shooter_id": world["ike"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["email_discarded"], body["email_moved"]) == (True, False)
    stamps = session.execute(
        select(ShooterContact.updated_at, ShooterContact.last_used_at).where(
            ShooterContact.shooter_id == world["ike"]
        )
    ).one()
    assert tuple(stamps) == (old, NOW)


def test_the_link_race_message_names_the_resolved_shooter(
    session: Session,
    admin_client: TestClient,
    world: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = seed_shooter(session, "Hadly, Ike", profile=False)
    add_rule(
        session, "merge_shooter", {"source_shooter_id": old, "target_shooter_id": world["ike"]}
    )

    class Diag:
        constraint_name = "uq_club_event_registrations_shooter"

    class Orig(Exception):
        diag = Diag()

    def race(*_args: Any, **_kwargs: Any) -> None:
        raise DBAPIError("INSERT", {}, Orig())

    monkeypatch.setattr("sunday_clays.domain.club_event_admin.link_registration", race)
    url = f"{BASE}/{world['event']}/registrations/{world['typo']}/link"
    response = admin_client.post(url, json={"shooter_id": old})
    assert _error(response) == (409, "already_signed_up")
    assert response.json()["error"]["message"] == "Hadley, Ike is already on the list."
