"""Club-event pages are members-only (Plan 20 D24): a crawler on any club-events path gets the
generic club preview, with no title, date, count or name, whatever the switches say."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sunday_clays.og.facts import facts_for_path

from .seed import seed_event, seed_registration


@pytest.mark.parametrize("switch_on", [True, False])
@pytest.mark.parametrize("path", ["club-events", "club-events/1", "club-events/1/anything"])
def test_every_club_events_path_is_the_generic_preview(
    session: Session, path: str, switch_on: bool
) -> None:
    assert facts_for_path(session, path, switch_on).kind == "generic"


def test_the_preview_page_never_names_the_event_or_anyone(
    session: Session, anon_client: TestClient
) -> None:
    event_id = seed_event(session, title="Fall Fun Shoot")
    seed_registration(session, event_id, name="Dana Quill", email="dana.quill@example.com")
    for prefix in ("", "l/"):
        response = anon_client.get(f"/api/og/page/{prefix}club-events/{event_id}")
        assert response.status_code == 200
        for secret in ("Fall Fun Shoot", "Dana", "Quill", "@example.com", "2030"):
            assert secret not in response.text, (prefix, secret)
