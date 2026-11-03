"""Commit/rollback through REAL committed sessions and several connections.

The fixture-world tests share one rolled-back session, so they cannot see what ``run_write``
really commits, nor any lock behaviour. These run on the committed-engine database.
"""

import datetime as dt
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session
from tests.integration.mcp.test_commit import AFTER, KEY, KEY2, LATER, FakeDump, _week

from sunday_clays.domain.errors import ConflictError
from sunday_clays.domain.imports import (
    IMPORT_LIFECYCLE_LOCK_KEY,
    active_scores_import,
)
from sunday_clays.mcp import server, writes
from sunday_clays.mcp.writes import Refusal
from sunday_clays.models import Import, McpOperation

Factory = Callable[[], AbstractContextManager[Session]]
STALE = LATER - dt.timedelta(hours=2)


@pytest.fixture
def fac(base_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Factory]:
    monkeypatch.setenv("DATABASE_URL", base_engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("MCP_COMMIT_ENABLED", "true")
    try:
        yield server.write_session_factory
    finally:
        # The factory caches an engine per URL; close its pool so no connection is garbage
        # collected while open (a ResourceWarning that would fail an unrelated later test).
        for maker in server._write_sessionmakers.values():
            maker.kw["bind"].dispose()
        server._write_sessionmakers.clear()


class Slow:
    """A dump that waits for the test to release it."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def __call__(self, *_a: object, **_k: object) -> Path:
        self.entered.set()
        self.release.wait(30)
        return Path("/x/pre-import-slow.dump")


def _preview(fac: Factory, week: Any = None, now: dt.datetime = LATER) -> str:
    return writes.run_write(
        fac,
        lambda s: writes.preview_week(s, week or _week(), now=now).preview_id,
    )


def _state(engine: Engine, pid: str) -> dict[str, Any]:
    with Session(engine) as s:
        op = s.get(McpOperation, UUID(pid))
        assert op is not None
        return {
            "status": op.status,
            "imports": [
                s.scalar(select(Import.status).where(Import.id == i))
                for i in (op.scores_import_id, op.stations_import_id)
                if i is not None
            ],
            "active": active_scores_import(s),
        }


def _active(engine: Engine) -> int | None:
    with Session(engine) as s:
        return active_scores_import(s)


def _thread(fn: Callable[[], Any], out: dict[str, Any], name: str) -> threading.Thread:
    def go() -> None:
        try:
            out[name] = ("ok", fn())
        except BaseException as exc:
            out[name] = ("err", exc)

    t = threading.Thread(target=go)
    t.start()
    return t


def _wait_for(pred: Callable[[], bool], what: str, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while not pred():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.05)


def _lock_waiters(engine: Engine) -> int:
    with engine.connect() as c:
        return int(
            c.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                )
            ).scalar_one()
        )


def _lifecycle_lock_granted(engine: Engine) -> int:
    with engine.connect() as c:
        return int(
            c.execute(
                text(
                    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                    "AND objid = :k AND granted"
                ),
                {"k": IMPORT_LIFECYCLE_LOCK_KEY},
            ).scalar_one()
        )


def _commit(fac: Factory, pid: str, key: str = KEY, dump: Any = None) -> dict[str, Any]:
    return writes.commit_week_tool(
        fac, pid, idempotency_key=key, now=LATER, dump=dump or FakeDump()
    )


# --- savepoints: nothing half-committed survives run_write's commit ----------------------------
def test_a_conflict_on_the_second_commit_leaves_both_imports_pending(
    fac: Factory, base_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _preview(fac)
    base = _active(base_engine)
    real, calls = writes.commit_import, []

    def flaky(session: Session, import_id: int, **kw: Any) -> None:
        calls.append(import_id)
        if len(calls) == 2:
            raise ConflictError("not_pending", "changed under us")
        real(session, import_id, **kw)

    monkeypatch.setattr(writes, "commit_import", flaky)
    with pytest.raises(Refusal) as exc:
        _commit(fac, pid)
    assert exc.value.code == "import_not_pending"
    assert len(calls) == 2  # the first commit really ran, then was undone
    state = _state(base_engine, pid)
    assert state["imports"] == ["pending", "pending"]
    assert state["status"] == "previewed"
    assert state["active"] == base


def test_a_conflict_on_the_second_rollback_leaves_the_commit_in_place(
    fac: Factory, base_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _preview(fac)
    _commit(fac, pid)
    committed = _state(base_engine, pid)
    assert committed["imports"] == ["committed", "committed"]
    real, calls = writes.rollback_import, []

    def flaky(session: Session, import_id: int) -> None:
        calls.append(import_id)
        if len(calls) == 2:
            raise ConflictError("not_committed", "changed under us")
        real(session, import_id)

    monkeypatch.setattr(writes, "rollback_import", flaky)
    with pytest.raises(Refusal) as exc:
        writes.rollback_week_tool(fac, pid, idempotency_key=KEY2, now=LATER, dump=FakeDump())
    assert exc.value.code == "import_not_committed"
    assert len(calls) == 2
    assert _state(base_engine, pid) == committed


def test_an_enqueue_failure_undoes_the_commit(
    fac: Factory, base_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _preview(fac)
    base = _active(base_engine)

    def boom(*_a: object, **_k: object) -> int:
        raise RuntimeError("queue is down")

    monkeypatch.setattr(writes, "enqueue", boom)
    with pytest.raises(RuntimeError):
        _commit(fac, pid)
    state = _state(base_engine, pid)
    assert state["imports"] == ["pending", "pending"]
    assert (state["status"], state["active"]) == ("previewed", base)


# --- I1: a preview must not expire an operation that is committing -----------------------------
def test_a_preview_cannot_expire_an_operation_that_commits_mid_dump(
    fac: Factory, base_engine: Engine
) -> None:
    a = _preview(fac)
    out: dict[str, Any] = {}
    slow = Slow()
    committing = _thread(lambda: _commit(fac, a, dump=slow), out, "commit")
    assert slow.entered.wait(15)
    other = _week(score=44)
    previewing = _thread(lambda: writes.preview_week_tool(fac, other, now=LATER), out, "preview")
    _wait_for(lambda: _lock_waiters(base_engine) >= 1, "the preview to block on the row")
    assert "preview" not in out
    slow.release.set()
    committing.join(60)
    previewing.join(60)
    assert out["commit"][0] == "ok"
    state = _state(base_engine, a)
    assert state["status"] == "committed"  # not overwritten with 'expired'
    assert state["imports"] == ["committed", "committed"]
    # The newcomer saw the moved base and was refused rather than recorded on a stale one.
    assert out["preview"][0] == "err"
    assert isinstance(out["preview"][1], Refusal)
    assert out["preview"][1].code == "base_changed"
    # ... and the undo path still works.
    rolled = writes.rollback_week_tool(fac, a, idempotency_key=KEY2, now=LATER, dump=FakeDump())
    assert rolled["status"] == "rolled_back"


# --- I2: no lifecycle lock held across a dump ---------------------------------------------------
def test_the_lifecycle_lock_is_not_held_during_a_slow_dump_with_a_stale_op(
    fac: Factory, base_engine: Engine
) -> None:
    stale = _preview(fac, _week(AFTER, 40), now=STALE)
    a = _preview(fac)
    out: dict[str, Any] = {}
    slow = Slow()
    committing = _thread(lambda: _commit(fac, a, dump=slow), out, "commit")
    assert slow.entered.wait(15)
    try:
        assert _lifecycle_lock_granted(base_engine) == 0
        # The sweep already expired the stale op in its own short transaction.
        assert _state(base_engine, stale)["status"] == "expired"
    finally:
        slow.release.set()
        committing.join(60)
    assert out["commit"][0] == "ok"
    assert _state(base_engine, a)["status"] == "committed"


def test_commit_itself_never_sweeps_so_it_holds_no_lifecycle_lock_over_the_dump(
    fac: Factory, base_engine: Engine
) -> None:
    """Calls the transaction body directly, so only an in-transaction sweep could take the lock."""
    stale = _preview(fac, _week(AFTER, 40), now=STALE)
    a = _preview(fac)
    out: dict[str, Any] = {}
    slow = Slow()
    committing = _thread(
        lambda: writes.run_write(
            fac,
            lambda s: writes.commit_week(s, a, idempotency_key=KEY, now=LATER, dump=slow),
        ),
        out,
        "commit",
    )
    assert slow.entered.wait(15)
    try:
        assert _lifecycle_lock_granted(base_engine) == 0
    finally:
        slow.release.set()
        committing.join(60)
    assert out["commit"][0] == "ok"
    assert _state(base_engine, stale)["status"] == "previewed"  # not its job


def test_the_sweep_does_not_deadlock_with_a_commit_holding_a_row(
    fac: Factory, base_engine: Engine
) -> None:
    stale = _preview(fac, _week(AFTER, 40), now=STALE)
    a = _preview(fac)
    out: dict[str, Any] = {}
    slow = Slow()
    t0 = _thread(lambda: _commit(fac, a, dump=slow), out, "t0")
    assert slow.entered.wait(15)
    # A second caller sweeps (and finds the stale op) while t0 holds its row mid-dump.
    t1 = _thread(lambda: writes.sweep_expired(fac, LATER), out, "t1")
    t1.join(30)
    assert not t1.is_alive()
    slow.release.set()
    t0.join(60)
    assert out["t0"][0] == "ok", out
    assert out["t1"][0] == "ok", out
    assert _state(base_engine, stale)["status"] == "expired"


def test_the_sweep_skips_a_row_another_transaction_holds(fac: Factory, base_engine: Engine) -> None:
    stale = _preview(fac, _week(AFTER, 40), now=STALE)
    holder = base_engine.connect()
    tx = holder.begin()
    try:
        holder.execute(text("SELECT id FROM mcp_operations WHERE id = :i FOR UPDATE"), {"i": stale})
        out: dict[str, Any] = {}
        t = _thread(lambda: writes.sweep_expired(fac, LATER), out, "sweep")
        t.join(10)
        assert not t.is_alive(), "the sweep blocked on a row it should have skipped"
        assert out["sweep"][0] == "ok"
        assert _state(base_engine, stale)["status"] == "previewed"
    finally:
        tx.rollback()
        holder.close()
    writes.sweep_expired(fac, LATER)
    assert _state(base_engine, stale)["status"] == "expired"  # picked up once free


# --- the lifecycle lock is held when the base is re-checked ------------------------------------
def test_the_lifecycle_lock_is_held_at_the_locked_recheck(
    fac: Factory, base_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _preview(fac)
    real = writes._stale_base
    held: list[int] = []

    def watching(session: Session, op: McpOperation) -> None:
        held.append(
            int(
                session.execute(
                    text(
                        "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = :k "
                        "AND pid = pg_backend_pid() AND granted"
                    ),
                    {"k": IMPORT_LIFECYCLE_LOCK_KEY},
                ).scalar_one()
            )
        )
        real(session, op)

    monkeypatch.setattr(writes, "_stale_base", watching)
    _commit(fac, pid)
    assert len(held) == 2
    assert held[0] == 0  # the early check runs before the dump, without the lock
    assert held[1] == 1  # the re-check runs under it
    assert _state(base_engine, pid)["status"] == "committed"


def test_the_stale_base_is_refused_when_it_moves_during_a_real_dump(
    fac: Factory, base_engine: Engine
) -> None:
    """Two real transactions: the base moves while the first is in its dump."""
    a = _preview(fac)
    other = _preview(fac, _week(AFTER, 40))
    slow = Slow()
    out: dict[str, Any] = {}
    t = _thread(lambda: _commit(fac, a, dump=slow), out, "a")
    assert slow.entered.wait(15)
    moved = writes.run_write(
        fac,
        lambda s: writes.commit_operation(
            s,
            other,
            idempotency_key=KEY2,
            commit_path="cli-approve",
            allow_correction=False,
            now=LATER,
            dump=FakeDump(),
        ),
    )
    assert moved["status"] == "committed"
    after_move = _active(base_engine)
    slow.release.set()
    t.join(60)
    assert out["a"][0] == "err"
    assert isinstance(out["a"][1], Refusal)
    assert out["a"][1].code == "base_changed"
    assert _active(base_engine) == after_move
    assert _state(base_engine, a)["status"] == "expired"


# --- R1: an identical preview must not expire an operation that committed meanwhile -----------
def test_an_identical_preview_never_expires_an_operation_that_commits_meanwhile(
    fac: Factory, base_engine: Engine
) -> None:
    wk = _week(AFTER, 40)
    a = _preview(fac, wk)
    b = _preview(fac)
    slow = Slow()
    out: dict[str, Any] = {}
    committing = _thread(lambda: _commit(fac, a, dump=slow), out, "a")
    assert slow.entered.wait(15)
    # B commits (the base moves, so A would be stale) and an identical preview of A queues up
    # behind A's row lock ...
    writes.commit_week_tool(fac, b, idempotency_key="key-bbbbbbb", now=LATER, dump=FakeDump())
    previewing = _thread(lambda: writes.preview_week_tool(fac, wk, now=LATER), out, "p")
    _wait_for(lambda: _lock_waiters(base_engine) >= 1, "the preview to block on A's row")
    # ... B is rolled back (the base is A's again) and A commits, then the preview resumes.
    writes.rollback_week_tool(fac, b, idempotency_key="key-rrrrrrr", now=LATER, dump=FakeDump())
    slow.release.set()
    committing.join(60)
    previewing.join(60)
    assert out["a"][0] == "ok", out
    state = _state(base_engine, a)
    assert state["status"] == "committed"  # not overwritten with 'expired'
    assert state["imports"] == ["committed", "committed"]
