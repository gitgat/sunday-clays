"""Every organizer write that can change who holds a spot takes the event lock first (Plan 20 D13,
Task 3 ruling): with the lock held by another transaction, the write waits instead of racing."""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from sunday_clays.domain import club_event_admin as admin
from sunday_clays.domain import club_event_store as store

from .seed import NOW, seed_event, seed_registration, seed_shooter
from .test_concurrency import _race

Action = Callable[[Session, dict[str, int]], Any]
ACTIONS: dict[str, Action] = {
    "update": lambda s, w: admin.update_event(
        s, w["event"], admin.EventPatch(notes="x"), now=NOW, tz="America/Los_Angeles"
    ),
    "cancel": lambda s, w: admin.cancel_event(s, w["event"], NOW),
    "restore": lambda s, w: admin.restore_event(s, w["event"], NOW),
    "delete": lambda s, w: admin.delete_event(s, w["event"]),
    "remove": lambda s, w: admin.remove_registration(s, w["event"], w["reg"], NOW),
    "guests": lambda s, w: admin.set_guests(s, w["event"], w["reg"], 1, NOW),
    "link": lambda s, w: admin.link_registration(s, w["event"], w["typed"], w["shooter"], NOW),
}


@pytest.mark.parametrize("name", sorted(ACTIONS))
def test_the_write_waits_for_the_event_lock(committed_engine: Engine, name: str) -> None:
    with Session(committed_engine) as setup:
        event = seed_event(setup, capacity=5, allow_guests=True, max_guests=2)
        world = {
            "event": event,
            "reg": seed_registration(setup, event, name="Amy Ace", email="amy@example.com"),
            "typed": seed_registration(setup, event, name="Ike Hadly", email="ike@example.com"),
            "shooter": seed_shooter(setup, "Hadley, Ike"),
        }
        setup.commit()
    _, _, waited_on = _race(
        committed_engine,
        lambda first: store.lock_event(first, world["event"]),
        lambda second: ACTIONS[name](second, world),
    )
    assert waited_on is not None, f"{name} did not wait for the event lock"
