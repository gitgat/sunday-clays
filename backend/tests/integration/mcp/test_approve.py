"""The human approve command, end to end on the committed-engine database (real commits)."""

import asyncio
import datetime as dt
import io
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from tests.conftest import FIXTURES_DIR
from tests.integration.mcp.test_commit import (
    AFTER,
    KEY,
    LATER,
    FakeDump,
    _correction,
    _week,
)

from sunday_clays.domain.imports import active_scores_import, commit_import, stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.mcp import approve, server, writes
from sunday_clays.mcp.writes import Refusal
from sunday_clays.models import AuditLog, Job, McpOperation

Factory = Callable[[], AbstractContextManager[Session]]
STALE = LATER - dt.timedelta(hours=2)


@pytest.fixture
def fac(committed_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Factory]:
    monkeypatch.setenv("DATABASE_URL", committed_engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("MCP_COMMIT_ENABLED", "true")
    with Session(committed_engine) as s:
        base = stage_import(s, (FIXTURES_DIR / "scores_2026-09-27.xlsx").read_bytes(), "base.xlsx")
        commit_import(s, base.import_id)
        rebuild_live(s)
        s.commit()
    try:
        yield server.write_session_factory
    finally:
        for maker in server._write_sessionmakers.values():
            maker.kw["bind"].dispose()
        server._write_sessionmakers.clear()


class Stdin(io.StringIO):
    def __init__(self, text: str = "", tty: bool = True) -> None:
        super().__init__(text)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def _week_preview(fac: Factory, week: Any = None, now: dt.datetime = LATER) -> str:
    return writes.run_write(
        fac, lambda s: writes.preview_week(s, week or _week(), now=now).preview_id
    )


def _correction_preview(fac: Factory, now: dt.datetime = LATER) -> str:
    return writes.run_write(fac, lambda s: _correction(s, now=now))


def _run(
    argv: list[str], stdin: Stdin, dump: Any = None, now: dt.datetime = LATER
) -> tuple[int, str]:
    out = io.StringIO()
    code = approve.main(argv, stdin, out, dump=dump or FakeDump(), now=lambda: now)
    return code, out.getvalue()


def _op(engine: Engine, pid: str) -> McpOperation:
    with Session(engine) as s:
        op = s.get(McpOperation, UUID(pid))
        assert op is not None
        s.expunge(op)
        return op


def _active(engine: Engine) -> int | None:
    with Session(engine) as s:
        return active_scores_import(s)


# --- confirmation ------------------------------------------------------------------------------
def test_typing_yes_commits_and_reports_the_job_and_backup(
    fac: Factory, committed_engine: Engine
) -> None:
    pid = _week_preview(fac)
    code, out = _run([pid], Stdin("yes\n"))
    assert code == 0, out
    op = _op(committed_engine, pid)
    assert op.status == "committed"
    assert op.commit_path == "cli-approve"
    assert (op.idempotency_key or "").startswith("cli-")
    assert f"job {op.job_id};" in out
    assert "pre-import-x.dump" in out
    assert "get_job" in out
    assert pid in out
    with Session(committed_engine) as s:
        assert s.get(Job, op.job_id) is not None


def test_the_summary_is_shown_before_the_prompt(fac: Factory) -> None:
    pid = _week_preview(fac)
    code, out = _run([pid], Stdin("no\n"))
    assert code == 1
    for expected in (
        "week",
        "2026-10-04",
        "2 shooters",
        "75",  # 45 + 30
        "37.5",
        "Testshooter, Alpha",  # a new name; owner's terminal only
        "expires",
        "finding",
    ):
        assert expected in out, expected
    assert out.index("2026-10-04") < out.index("yes")


@pytest.mark.parametrize("answer", ["y\n", "YES\n", "Yes\n", "yes please\n", "\n", "", "no\n"])
def test_anything_but_yes_declines_with_no_change(
    fac: Factory, committed_engine: Engine, answer: str
) -> None:
    pid = _week_preview(fac)
    base = _active(committed_engine)
    dump = FakeDump()
    code, out = _run([pid], Stdin(answer), dump=dump)
    assert code == 1
    assert dump.calls == []
    assert _op(committed_engine, pid).status == "previewed"
    assert _active(committed_engine) == base
    assert "Not committed" in out


def test_no_tty_without_yes_is_a_usage_error_with_no_change(
    fac: Factory, committed_engine: Engine
) -> None:
    pid = _week_preview(fac)
    dump = FakeDump()
    code, out = _run([pid], Stdin("yes\n", tty=False), dump=dump)
    assert code == 2
    assert "--yes" in out
    assert dump.calls == []
    assert _op(committed_engine, pid).status == "previewed"


def test_yes_flag_commits_without_a_prompt(fac: Factory, committed_engine: Engine) -> None:
    pid = _week_preview(fac)
    code, out = _run([pid, "--yes"], Stdin("", tty=False))
    assert code == 0, out
    assert _op(committed_engine, pid).status == "committed"


def test_a_week_commits_with_mcp_commit_enabled_unset(
    fac: Factory, committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _week_preview(fac)
    monkeypatch.delenv("MCP_COMMIT_ENABLED")
    with pytest.raises(Refusal) as gated:  # the tool path is shut ...
        writes.commit_week_tool(fac, pid, idempotency_key=KEY, now=LATER, dump=FakeDump())
    assert gated.value.code == "commits_disabled"
    code, out = _run([pid, "--yes"], Stdin(tty=False))  # ... the human path is not
    assert code == 0, out
    assert _op(committed_engine, pid).status == "committed"


# --- corrections -------------------------------------------------------------------------------
def test_a_correction_commits_and_shows_old_and_new_scores(
    fac: Factory, committed_engine: Engine
) -> None:
    pid = _correction_preview(fac)
    with pytest.raises(Refusal) as tool:
        writes.commit_week_tool(fac, pid, idempotency_key=KEY, now=LATER, dump=FakeDump())
    assert tool.value.code == "correction_needs_human"  # the tool still refuses this preview
    code, out = _run([pid], Stdin("yes\n"))
    assert code == 0, out
    assert "correction" in out
    assert " -> " in out
    stored = _op(committed_engine, pid).result["preview"]["changes"][0]
    assert stored["name"] in out
    assert f"{stored['old_score']} -> {stored['new_score']}" in out
    op = _op(committed_engine, pid)
    assert (op.status, op.commit_path) == ("committed", "cli-approve")


# --- refusals ----------------------------------------------------------------------------------
def test_a_stale_base_is_refused_base_changed(fac: Factory, committed_engine: Engine) -> None:
    a = _week_preview(fac)
    b = _week_preview(fac, _week(AFTER, 40))
    writes.commit_week_tool(fac, b, idempotency_key="key-bbbbbbb", now=LATER, dump=FakeDump())
    moved = _active(committed_engine)
    code, out = _run([a, "--yes"], Stdin(tty=False))
    assert code == 1
    assert "base_changed" in out
    assert _active(committed_engine) == moved
    assert _op(committed_engine, a).status == "expired"


def test_an_expired_preview_is_refused_expired(fac: Factory, committed_engine: Engine) -> None:
    pid = _week_preview(fac, now=STALE)
    code, out = _run([pid, "--yes"], Stdin(tty=False))
    assert code == 1
    assert "expired" in out
    assert _op(committed_engine, pid).status == "expired"


def test_an_unknown_preview_exits_1_without_a_change(fac: Factory) -> None:
    code, out = _run(["00000000-0000-4000-8000-000000000000", "--yes"], Stdin(tty=False))
    assert code == 1
    assert "no preview" in out.lower()


def test_an_already_committed_preview_is_refused(fac: Factory) -> None:
    pid = _week_preview(fac)
    assert _run([pid, "--yes"], Stdin(tty=False))[0] == 0
    code, out = _run([pid, "--yes"], Stdin(tty=False))
    assert code == 1
    assert "already_committed" in out


def test_a_backup_failure_exits_1_and_commits_nothing(
    fac: Factory, committed_engine: Engine
) -> None:
    pid = _week_preview(fac)
    base = _active(committed_engine)
    code, out = _run([pid, "--yes"], Stdin(tty=False), dump=FakeDump(fail=True))
    assert code == 1
    assert "backup_failed" in out
    assert _op(committed_engine, pid).status == "previewed"
    assert _active(committed_engine) == base


# --- bad arguments -----------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["not-a-uuid", "$(rm -rf /)", "1; ls", ""])
def test_an_unparsable_preview_id_exits_2_and_is_not_echoed(bad: str) -> None:
    code, out = _run([bad, "--yes"], Stdin(tty=False))
    assert code == 2
    if bad:
        assert bad not in out


def test_missing_and_extra_arguments_exit_2() -> None:
    assert _run([], Stdin())[0] == 2
    assert _run(["00000000-0000-4000-8000-000000000000", "--bogus"], Stdin())[0] == 2


# --- hygiene -----------------------------------------------------------------------------------
def test_the_database_url_and_audit_are_clean(fac: Factory, committed_engine: Engine) -> None:
    pid = _week_preview(fac)
    code, out = _run([pid, "--yes"], Stdin(tty=False))
    assert code == 0
    assert "postgresql" not in out
    with Session(committed_engine) as s:
        details = s.scalars(select(AuditLog.details).where(AuditLog.action == "mcp.commit")).all()
    assert any(d.get("commit_path") == "cli-approve" for d in details)


def test_the_default_backup_is_the_normal_dump_with_the_long_lock_timeout(
    fac: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}

    def fake_pre_import_dump(preview_id: UUID, **kw: Any) -> Path:
        seen.update(kw)
        return tmp_path / "pre-import-real.dump"

    monkeypatch.setattr(approve.backup, "pre_import_dump", fake_pre_import_dump)
    monkeypatch.setenv("MCP_BACKUP_DIR", str(tmp_path))
    pid = _week_preview(fac)
    out = io.StringIO()
    code = approve.main([pid, "--yes"], Stdin(tty=False), out, now=lambda: LATER)
    assert code == 0, out.getvalue()
    assert "lock_timeout_s" not in seen  # pre_import_dump's own default (10 minutes) applies
    assert seen["backup_dir"] == tmp_path
    assert "pre-import-real.dump" in out.getvalue()


# --- the approve path is unreachable from any tool --------------------------------------------
def test_no_mcp_tool_exposes_the_approve_path() -> None:
    mcp = server.build_mcp(lambda: None, lambda: None)  # type: ignore[arg-type,return-value]
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {
        "find_shooters",
        "get_event",
        "get_job",
        "preview_week",
        "preview_correction",
        "commit_week",
        "rollback_week",
    }
    assert not any("approve" in n for n in names)


def test_the_server_module_never_allows_corrections_or_imports_approve() -> None:
    src = Path(server.__file__).read_text()
    assert "allow_correction=True" not in src
    assert "allow_correction = True" not in src
    assert "mcp.approve" not in src
    assert "import approve" not in src
    assert "cli-approve" not in src
    assert "commit_operation" not in src
