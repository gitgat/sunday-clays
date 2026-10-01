"""Fist-bump store (Plan 14 Task 1): idempotent writes, per-device state, wipe and durability."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, insert
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import run_pipeline
from sunday_clays.domain.bumps import (
    BumpState,
    add_bump,
    bump_state,
    bump_states,
    bump_totals,
    remove_bump,
    wipe_bumps,
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
    session.execute(insert(FistBump).values(post_key="k1", device_id=A))
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


def test_wipe_removes_every_device_on_one_post_only(session: Session) -> None:
    add_bump(session, "k1", A)
    add_bump(session, "k1", B)
    add_bump(session, "k2", A)
    assert wipe_bumps(session, "k1") == 2
    assert wipe_bumps(session, "k1") == 0
    assert bump_states(session, ["k1", "k2"], None) == {
        "k1": BumpState(0, False),
        "k2": BumpState(1, False),
    }


def test_totals_list_the_most_recently_bumped_first(session: Session) -> None:
    now = datetime.now(UTC)
    session.execute(
        insert(FistBump),
        [
            {"post_key": "old", "device_id": A, "created_at": now - timedelta(days=2)},
            {"post_key": "new", "device_id": A, "created_at": now - timedelta(hours=1)},
            {"post_key": "new", "device_id": B, "created_at": now},
        ],
    )
    totals = bump_totals(session, 10)
    assert [(t.post_key, t.bumps) for t in totals] == [("new", 2), ("old", 1)]
    assert totals[0].last_at == now
    assert [t.post_key for t in bump_totals(session, 1)] == ["new"]


def test_bump_tables_are_not_live_tables() -> None:
    assert "fist_bumps" not in LIVE_TABLES
    assert "bump_attempts" not in LIVE_TABLES


def test_bumps_survive_a_rebuild_and_a_recompute(fx_session: Session) -> None:
    add_bump(fx_session, "k1", A)
    rebuild_live(fx_session)
    run_pipeline(fx_session)
    assert bump_state(fx_session, "k1", A) == BumpState(1, True)
