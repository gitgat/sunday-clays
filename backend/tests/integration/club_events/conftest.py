"""Fixtures for the club-event tests (Plan 20); the seed helpers are in seed.py."""

import pytest
from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.domain.features import set_switch


@pytest.fixture
def events_on(session: Session, test_settings: Settings) -> None:
    """The `events` launch switch on, in the test's own transaction."""
    set_switch(session, test_settings, "events", True)
