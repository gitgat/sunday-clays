"""Fist-bump store (Plan 15 Task 1): idempotent writes, per-device state and durability."""

import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import Engine, insert
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import run_pipeline
from sunday_clays.domain.bumps import (
    BumpState,
    add_bump,
    bump_state,
    bump_states,
    remove_bump,
)
from sunday_clays.domain.rebuild import LIVE_TABLES, rebuild_live
from sunday_clays.models import FistBump

A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")


def test_add_is_idempotent_per_device(session: Session) -> None:
    add_bump(session, "k1", A)
    add_bump(session, "k1", A)
    add_bump(session, "k1", B)
    assert bump_state(session, "k1", A) == BumpState(2, True)
    assert bump_state(session, "k1", None) == BumpState(2, False)


def test_add_over_a_row_another_writer_stored_never_raises(session: Session) -> None:
    session.execute(insert(FistBump).values(insight_key="k1", device_id=A))
    add_bump(session, "k1", A)
    assert bump_state(session, "k1", A) == BumpState(1, True)


def test_concurrent_identical_bumps_store_one_row(committed_engine: Engine) -> None:
    with Session(committed_engine) as first, Session(committed_engine) as second:
        add_bump(first, "k1", A)  # holds the key's index entry until it commits

        def racer() -> None:
            add_bump(second, "k1", A)  # waits for `first`, then does nothing
            second.commit()

        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(racer)
            first.commit()
            waiting.result(timeout=10)
    with Session(committed_engine) as check:
        assert bump_state(check, "k1", A) == BumpState(1, True)


def test_remove_is_idempotent_and_never_goes_negative(session: Session) -> None:
    add_bump(session, "k1", A)
    remove_bump(session, "k1", A)
    remove_bump(session, "k1", A)
    remove_bump(session, "k2", B)
    assert bump_state(session, "k1", A) == BumpState(0, False)


def test_states_zero_fill_asked_keys_and_ignore_the_rest(session: Session) -> None:
    add_bump(session, "k1", A)
    add_bump(session, "stale", A)
    assert bump_states(session, ["k1", "k2", "k1"], A) == {
        "k1": BumpState(1, True),
        "k2": BumpState(0, False),
    }
    assert bump_states(session, [], A) == {}


def test_bump_tables_are_not_live_tables() -> None:
    assert "fist_bumps" not in LIVE_TABLES
    assert "bump_attempts" not in LIVE_TABLES


def test_bumps_survive_a_rebuild_and_a_recompute(fx_session: Session) -> None:
    add_bump(fx_session, "k1", A)
    rebuild_live(fx_session)
    run_pipeline(fx_session)
    assert bump_state(fx_session, "k1", A) == BumpState(1, True)


def test_remove_takes_back_one_device_on_one_insight_only(session: Session) -> None:
    add_bump(session, "k1", A)
    add_bump(session, "k2", A)
    add_bump(session, "k1", B)
    remove_bump(session, "k1", A)
    assert bump_state(session, "k2", A) == BumpState(1, True)
    assert bump_state(session, "k1", B) == BumpState(1, True)
    assert bump_state(session, "k1", A) == BumpState(1, False)
