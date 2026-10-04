"""Races on real connections (Plan 20 D9, D13): the event row lock serialises the writes of one
event, and the queue follows the lock order. Without `FOR UPDATE` these fail every time, not
sometimes: the second session never waits."""

import threading
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import Connection, Engine, func, select, text
from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.domain import club_event_store as store
from sunday_clays.domain import club_events as rules
from sunday_clays.models import ClubEventRegistration

from .seed import NOW, seed_event, seed_registration

R = ClubEventRegistration


def _seed(engine: Engine, **event: Any) -> int:
    with Session(engine) as setup:
        event_id = seed_event(setup, **event)
        setup.commit()
        return event_id


def _wait_until_blocked(probe: Connection, pid: int, worker: threading.Thread) -> str | None:
    deadline = time.monotonic() + 10
    while worker.is_alive() and time.monotonic() < deadline:
        waited = probe.scalar(
            text("SELECT min(locktype) FROM pg_locks WHERE pid = :pid AND NOT granted"),
            {"pid": pid},
        )
        if waited is not None:
            return str(waited)
        time.sleep(0.02)
    return None


def _race(
    engine: Engine, hold: Callable[[Session], Any], then: Callable[[Session], Any]
) -> tuple[Any, Any, str | None]:
    """`hold` runs in the first session and keeps its transaction open; `then` runs in a second
    session on a thread; the first commits only once the second waits on a lock."""
    first, second = Session(engine), Session(engine)
    probe = engine.connect()
    results: list[Any] = []
    raised: list[Exception] = []
    pid = int(second.scalar(select(func.pg_backend_pid())) or 0)
    second.execute(text("SET LOCAL lock_timeout = '20s'"))

    def run_second() -> None:
        try:
            results.append(then(second))
            second.commit()
        except Exception as exc:  # asserted below
            raised.append(exc)

    worker = threading.Thread(target=run_second)
    try:
        held = hold(first)
        worker.start()
        waited_on = _wait_until_blocked(probe, pid, worker)
        first.commit()
        worker.join(20)
    finally:
        first.close()
        second.close()
        probe.close()
    assert raised == []
    return held, results[0], waited_on


def _typed(event_id: int, name: str) -> Callable[[Session], store.SignupResult]:
    email = name.lower().replace(" ", ".") + "@example.com"

    def sign_up(session: Session) -> store.SignupResult:
        return store.sign_up(
            session, event_id, shooter_id=None, name=name, email=email, guests=0, now=NOW
        )

    return sign_up


def test_last_spot_race_never_overbooks(committed_engine: Engine, test_settings: Settings) -> None:
    event_id = _seed(committed_engine, capacity=1)
    held, second, waited_on = _race(
        committed_engine, _typed(event_id, "Pat Kim"), _typed(event_id, "Dana Quill")
    )
    assert waited_on is not None, "the second sign-up never waited for the event lock"
    assert (held.status, second.status) == ("going", "waitlist")


def test_cancel_and_signup_race(committed_engine: Engine, test_settings: Settings) -> None:
    event_id = _seed(committed_engine, capacity=1)
    with Session(committed_engine) as setup:
        rid = seed_registration(
            setup,
            event_id,
            name="Amy Ace",
            email="amy@example.com",
            token_hash=rules.token_hash("amy-token"),
        )
        setup.commit()

    def cancel(session: Session) -> int | None:
        return store.cancel(
            session, event_id, rid, proof="amy-token", via="device", ip="fp-test", now=NOW
        )

    held, second, waited_on = _race(committed_engine, cancel, _typed(event_id, "Dana Quill"))
    assert waited_on is not None
    assert (held, second.status) == (0, "going")  # the sign-up saw the committed cancel


def test_queue_order_follows_lock_order(committed_engine: Engine, test_settings: Settings) -> None:
    event_id = _seed(committed_engine, capacity=1)
    a, b = Session(committed_engine), Session(committed_engine)
    try:
        a.execute(text("SELECT 1"))  # A's transaction starts first, so its now() is earlier
        time.sleep(0.01)
        b_result = _typed(event_id, "Pat Kim")(b)
        b.commit()
        a_result = _typed(event_id, "Dana Quill")(a)
        a.commit()
        queue_at = dict(a.execute(select(R.id, R.queue_at)).all())  # type: ignore[arg-type]
    finally:
        a.close()
        b.close()
    assert (b_result.status, a_result.status) == ("going", "waitlist")
    assert a_result.registration_id > b_result.registration_id
    assert queue_at[a_result.registration_id] > queue_at[b_result.registration_id]
