"""rebuild_live against concurrent readers on real connections (C4: live tables swap atomically).

Every connection sets a short lock_timeout, so a rebuild that blocks readers (or is blocked by
them) fails fast with LockNotAvailable instead of hanging the run.
"""

import threading
import time
from collections.abc import Callable
from datetime import date

from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from sunday_clays.domain.imports import stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.models import Event, Round

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)
OLD = [("Hadley, Ike", 35, D1), ("Devlin, Sid", 30, D1)]
NEW = [("Hadley, Ike", 34, D1), ("Devlin, Sid", 30, D1), ("Hadley, Ike", 33, D2)]
OLD_EVENTS, NEW_EVENTS = [(D1, 2)], [(D1, 2), (D2, 1)]
OLD_ROUNDS, NEW_ROUNDS = [(D1, 30), (D1, 35)], [(D1, 30), (D1, 34), (D2, 33)]


def _seed(
    engine: Engine,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    """Commit live tables built from OLD, with NEW already the active scores import."""
    with Session(engine) as setup:
        mark_committed(setup, stage_import(setup, scores_workbook(OLD), "old.xlsx").import_id)
        rebuild_live(setup)
        mark_committed(setup, stage_import(setup, scores_workbook(NEW), "new.xlsx").import_id)
        setup.commit()


def _lock_timeout(session: Session) -> None:
    session.execute(text("SET LOCAL lock_timeout = '2s'"))


def _events(session: Session) -> list[tuple[date, int]]:
    rows = session.execute(select(Event.event_date, Event.n_rounds).order_by(Event.event_date))
    return [(d, n) for d, n in rows]


def _rounds(session: Session) -> list[tuple[date, int]]:
    rows = session.execute(
        select(Round.event_date, Round.score).order_by(Round.event_date, Round.score)
    )
    return [(d, score) for d, score in rows]


def test_reader_sees_old_rows_during_rebuild(
    committed_engine: Engine,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    _seed(committed_engine, scores_workbook, mark_committed)
    with Session(committed_engine) as rebuilder, Session(committed_engine) as reader:
        rebuild_live(rebuilder)  # not committed yet
        _lock_timeout(reader)
        # neither read waits for the rebuild; both see the committed pre-rebuild rows
        assert (_events(reader), _rounds(reader)) == (OLD_EVENTS, OLD_ROUNDS)
        reader.commit()
        rebuilder.commit()
        # the reader's next transaction sees the whole new state at once
        assert (_events(reader), _rounds(reader)) == (NEW_EVENTS, NEW_ROUNDS)


def test_reader_holding_a_live_table_does_not_block_rebuild(
    committed_engine: Engine,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    _seed(committed_engine, scores_workbook, mark_committed)
    with Session(committed_engine) as reader, Session(committed_engine) as rebuilder:
        _lock_timeout(reader)
        assert _events(reader) == OLD_EVENTS  # its lock on events lasts until the reader commits
        _lock_timeout(rebuilder)
        rebuild_live(rebuilder)  # must not wait for the reader's lock on events
        # the reader goes on to another live table: no wait, and no deadlock with the rebuild
        assert _rounds(reader) == OLD_ROUNDS
        rebuilder.commit()
        reader.commit()
        assert (_events(reader), _rounds(reader)) == (NEW_EVENTS, NEW_ROUNDS)


def test_concurrent_rebuilds_run_one_after_the_other(
    committed_engine: Engine,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    # TRUNCATE's ACCESS EXCLUSIVE used to queue a second rebuild behind the first; DELETE alone
    # would let it clear only the rows it can see and then collide with the first one's inserts
    _seed(committed_engine, scores_workbook, mark_committed)
    raised: list[Exception] = []
    first, second = Session(committed_engine), Session(committed_engine)
    probe = committed_engine.connect()
    pid = second.scalar(select(func.pg_backend_pid()))
    # the transaction the worker thread continues: bounded, so no regression can hang the test
    second.execute(text("SET LOCAL lock_timeout = '20s'"))

    def rebuild_second() -> None:
        try:
            rebuild_live(second)
            second.commit()
        except Exception as exc:  # asserted below
            raised.append(exc)

    worker = threading.Thread(target=rebuild_second)
    waited_on: str | None = None
    try:
        rebuild_live(first)  # not committed yet
        worker.start()
        deadline = time.monotonic() + 10
        while waited_on is None and worker.is_alive() and time.monotonic() < deadline:
            waited_on = probe.scalar(
                text("SELECT min(locktype) FROM pg_locks WHERE pid = :pid AND NOT granted"),
                {"pid": pid},
            )
            time.sleep(0.02)
        first.commit()
        worker.join(timeout=30)
        assert not worker.is_alive()
    finally:
        first.close()  # rolls back if the commit was never reached, releasing its locks
        worker.join(timeout=30)
        second.close()
        probe.close()
    assert (waited_on, raised) == ("advisory", [])
    with Session(committed_engine) as check:
        assert (_events(check), _rounds(check)) == (NEW_EVENTS, NEW_ROUNDS)
