"""Fixtures for the club-event tests (Plan 20); the seed helpers are in seed.py."""

from collections.abc import Callable
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.domain import club_event_store as store
from sunday_clays.domain.features import set_switch


@pytest.fixture
def events_on(session: Session, test_settings: Settings) -> None:
    """The `events` launch switch on, in the test's own transaction."""
    set_switch(session, test_settings, "events", True)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[datetime], None]:
    """`clock(dt)` freezes the store's clock (the routes' "now") at `dt`."""

    def freeze(now: datetime) -> None:
        monkeypatch.setattr(store, "utcnow", lambda: now)

    return freeze
