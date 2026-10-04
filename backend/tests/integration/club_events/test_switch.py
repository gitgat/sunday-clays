"""The `events` switch starts off and turns on (Plan 20 D1 on Plan 19's mechanism)."""

from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.domain.features import read_switches, set_switch


def test_events_is_off_until_an_admin_turns_it_on(
    session: Session, test_settings: Settings
) -> None:
    assert read_switches(session, test_settings).get("events", False) is False
    set_switch(session, test_settings, "events", True)
    assert read_switches(session, test_settings)["events"] is True
