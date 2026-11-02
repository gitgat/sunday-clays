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
from tests.integration.mcp.test_commit import (
    AFTER,
    KEY,
    LATER,
    FakeDump,
    _correction,
    _week,
)

from sunday_clays.domain.imports import active_scores_import
from sunday_clays.mcp import approve, server, writes
from sunday_clays.mcp.writes import Refusal
from sunday_clays.models import AuditLog, Job, McpOperation

Factory = Callable[[], AbstractContextManager[Session]]
STALE = LATER - dt.timedelta(hours=2)


@pytest.fixture
def fac(base_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Factory]:
    monkeypatch.setenv("DATABASE_URL", base_engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("MCP_COMMIT_ENABLED", "true")
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
    fac: Factory, base_engine: Engine
) -> None:
    pid = _week_preview(fac)
    code, out = _run([pid], Stdin("yes\n"))
    assert code == 0, out
    op = _op(base_engine, pid)
    assert op.status == "committed"
    assert op.commit_path == "cli-approve"
    assert (op.idempotency_key or "").startswith("cli-")
    assert f"get_job with the job id {op.job_id}" in out
    assert "pre-import-x.dump" in out
    assert "get_job" in out
    assert pid in out
    with Session(base_engine) as s:
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
    fac: Factory, base_engine: Engine, answer: str
) -> None:
    pid = _week_preview(fac)
    base = _active(base_engine)
    dump = FakeDump()
    code, out = _run([pid], Stdin(answer), dump=dump)
    assert code == 1
    assert dump.calls == []
    assert _op(base_engine, pid).status == "previewed"
    assert _active(base_engine) == base
    assert "Not committed" in out


def test_no_tty_without_yes_is_a_usage_error_with_no_change(
    fac: Factory, base_engine: Engine
) -> None:
    pid = _week_preview(fac)
    dump = FakeDump()
    code, out = _run([pid], Stdin("yes\n", tty=False), dump=dump)
    assert code == 2
    assert "--yes" in out
    assert dump.calls == []
    assert _op(base_engine, pid).status == "previewed"


def test_yes_flag_commits_without_a_prompt(fac: Factory, base_engine: Engine) -> None:
    pid = _week_preview(fac)
    code, out = _run([pid, "--yes"], Stdin("", tty=False))
    assert code == 0, out
    assert _op(base_engine, pid).status == "committed"


def test_a_week_commits_with_mcp_commit_enabled_unset(
    fac: Factory, base_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _week_preview(fac)
    monkeypatch.delenv("MCP_COMMIT_ENABLED")
    with pytest.raises(Refusal) as gated:  # the tool path is shut ...
        writes.commit_week_tool(fac, pid, idempotency_key=KEY, now=LATER, dump=FakeDump())
    assert gated.value.code == "commits_disabled"
    code, out = _run([pid, "--yes"], Stdin(tty=False))  # ... the human path is not
    assert code == 0, out
    assert _op(base_engine, pid).status == "committed"


# --- corrections -------------------------------------------------------------------------------
def test_a_correction_commits_and_shows_old_and_new_scores(
    fac: Factory, base_engine: Engine
) -> None:
    pid = _correction_preview(fac)
    with pytest.raises(Refusal) as tool:
        writes.commit_week_tool(fac, pid, idempotency_key=KEY, now=LATER, dump=FakeDump())
    assert tool.value.code == "correction_needs_human"  # the tool still refuses this preview
    code, out = _run([pid], Stdin("yes\n"))
    assert code == 0, out
    assert "correction" in out
    assert " -> " in out
    assert "station_score_mismatch" in out
    stored = _op(base_engine, pid).result["preview"]["changes"][0]
    assert stored["name"] in out
    assert f"{stored['old_score']} -> {stored['new_score']}" in out
    op = _op(base_engine, pid)
    assert (op.status, op.commit_path) == ("committed", "cli-approve")


# --- refusals ----------------------------------------------------------------------------------
def test_a_stale_base_is_refused_base_changed(fac: Factory, base_engine: Engine) -> None:
    a = _week_preview(fac)
    b = _week_preview(fac, _week(AFTER, 40))
    writes.commit_week_tool(fac, b, idempotency_key="key-bbbbbbb", now=LATER, dump=FakeDump())
    moved = _active(base_engine)
    code, out = _run([a, "--yes"], Stdin(tty=False))
    assert code == 1
    assert "base_changed" in out
    assert _active(base_engine) == moved
    assert _op(base_engine, a).status == "expired"


def test_an_expired_preview_is_refused_expired(fac: Factory, base_engine: Engine) -> None:
    pid = _week_preview(fac, now=STALE)
    code, out = _run([pid, "--yes"], Stdin(tty=False))
    assert code == 1
    assert "expired" in out
    assert _op(base_engine, pid).status == "expired"


def test_an_unknown_preview_exits_1_without_a_change(fac: Factory) -> None:
    code, out = _run(["00000000-0000-4000-8000-000000000000", "--yes"], Stdin(tty=False))
    assert code == 1
    assert "unknown_preview" in out
    assert "Refused: unknown_preview" in out


def test_an_already_committed_preview_is_refused(fac: Factory) -> None:
    pid = _week_preview(fac)
    assert _run([pid, "--yes"], Stdin(tty=False))[0] == 0
    code, out = _run([pid, "--yes"], Stdin(tty=False))
    assert code == 1
    assert "already_committed" in out


def test_a_backup_failure_exits_1_and_commits_nothing(fac: Factory, base_engine: Engine) -> None:
    pid = _week_preview(fac)
    base = _active(base_engine)
    code, out = _run([pid, "--yes"], Stdin(tty=False), dump=FakeDump(fail=True))
    assert code == 1
    assert "backup_failed" in out
    assert _op(base_engine, pid).status == "previewed"
    assert _active(base_engine) == base


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
def test_the_database_url_and_audit_are_clean(fac: Factory, base_engine: Engine) -> None:
    pid = _week_preview(fac)
    code, out = _run([pid, "--yes"], Stdin(tty=False))
    assert code == 0
    assert "postgresql" not in out
    with Session(base_engine) as s:
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


# --- fix round 1 -------------------------------------------------------------------------------
class HookIn(Stdin):
    """A stdin that runs a hook between the summary and the answer."""

    def __init__(self, hook: Callable[[], None], text: str = "yes\n") -> None:
        super().__init__(text)
        self.hook = hook

    def readline(self, *_a: Any) -> str:
        self.hook()
        return super().readline()


def _audits(engine: Engine, action: str = "mcp.refuse") -> list[dict[str, Any]]:
    with Session(engine) as s:
        return [a.details for a in s.scalars(select(AuditLog).where(AuditLog.action == action))]


def test_the_cli_sweeps_stale_previews_first(fac: Factory, base_engine: Engine) -> None:
    stale = _week_preview(fac, _week(AFTER, 40), now=STALE)
    pid = _week_preview(fac)
    assert _run([pid, "--yes"], Stdin(tty=False))[0] == 0
    assert _op(base_engine, stale).status == "expired"  # swept, not merely left behind


def test_a_leading_space_is_not_yes(fac: Factory, base_engine: Engine) -> None:
    pid = _week_preview(fac)
    code, _out = _run([pid], Stdin(" yes\n"))
    assert code == 1
    assert _op(base_engine, pid).status == "previewed"


def test_the_summary_numbers_messages_and_clock(fac: Factory) -> None:
    pid = _week_preview(fac)
    stored = writes.run_write(
        fac,
        lambda s: dict(s.get(McpOperation, UUID(pid)).result["preview"]),  # type: ignore[union-attr]
    )
    now = LATER + dt.timedelta(minutes=25)
    out = io.StringIO()
    approve.main([pid], Stdin("no\n"), out, dump=FakeDump(), now=lambda: now)
    text = out.getvalue()
    n = len(stored["findings_for_date"])
    assert f"findings for this date: {n} (+{stored['historical_findings']} older)" in text
    for f in stored["findings_for_date"]:
        assert f["message"] in text
    assert "staged 25 min ago" in text
    assert "expires 2026-10-13T19:00" in text  # created 18:00 + the one-hour default


def test_duplicates_and_note_are_printed(fac: Factory) -> None:
    def many(s: Session) -> str:
        week = _week()
        extra = [{"name": f"Newname{c}, Person", "score": 20, "status": "Guest"} for c in "ABCDE"]
        data = week.model_dump(mode="json", by_alias=True)
        data["shooters"] = data["shooters"] + extra
        from sunday_clays.mcp.build import WeekInput

        return writes.preview_week(s, WeekInput.model_validate(data), now=LATER).preview_id

    pid = writes.run_write(fac, many)
    out = io.StringIO()
    approve.main([pid], Stdin("no\n"), out, dump=FakeDump(), now=lambda: LATER)
    assert "check each against find_shooters" in out.getvalue()


def test_a_near_miss_of_a_known_name_prints_a_possible_duplicate_line(
    fac: Factory, base_engine: Engine
) -> None:
    from sunday_clays.mcp.build import WeekInput
    from sunday_clays.models import Shooter

    with Session(base_engine) as s:
        known = s.scalars(select(Shooter.display_name).order_by(Shooter.display_name)).first()
    assert known is not None
    assert "," in known
    surname, given = (part.strip() for part in known.split(",", 1))
    near = f"{surname}x, {given}"  # one letter off a shooter who is not here that day
    data = _week().model_dump(mode="json", by_alias=True)
    data["shooters"][1]["name"] = near

    pid = writes.run_write(
        fac, lambda s: writes.preview_week(s, WeekInput.model_validate(data), now=LATER).preview_id
    )
    out = io.StringIO()
    approve.main([pid], Stdin("no\n"), out, dump=FakeDump(), now=lambda: LATER)

    line = next(ln for ln in out.getvalue().splitlines() if "possible duplicate:" in ln)
    assert near in line
    assert known in line


def test_a_busy_database_says_nothing_changed_and_to_re_run(
    fac: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _week_preview(fac)

    def busy(*_a: object, **_k: object) -> dict[str, Any]:
        raise Refusal("busy", "the database was busy")

    monkeypatch.setattr(writes, "commit_operation", busy)
    code, out = _run([pid, "--yes"], Stdin(tty=False))

    assert code == 1
    assert "Busy: the database was busy and nothing was changed; re-run this command." in out
    assert "Refused:" not in out


def test_a_correction_summary_has_counts(fac: Factory) -> None:
    pid = _correction_preview(fac)
    out = io.StringIO()
    approve.main([pid], Stdin("no\n"), out, dump=FakeDump(), now=lambda: LATER)
    text = out.getvalue()
    assert "shooters, score sum" in text
    assert "average" in text
    assert "station detail stays" in text


def test_a_non_previewed_status_goes_straight_to_the_refusal(fac: Factory) -> None:
    pid = _week_preview(fac, now=STALE)
    code, out = _run([pid], Stdin("yes\n"))  # a TTY and no --yes
    assert code == 1
    assert "Refused: expired" in out
    assert "Type yes" not in out


@pytest.mark.parametrize("how", ["superseded", "base_moved"])
def test_state_changing_between_summary_and_yes_refuses_with_no_dump(
    fac: Factory, base_engine: Engine, how: str
) -> None:
    a = _week_preview(fac)
    b = _week_preview(fac, _week(AFTER, 40))

    def change() -> None:
        if how == "superseded":
            writes.run_write(fac, lambda s: writes.preview_week(s, _week(score=44), now=LATER))
        else:
            writes.commit_week_tool(
                fac, b, idempotency_key="key-bbbbbbb", now=LATER, dump=FakeDump()
            )

    dump = FakeDump()
    base = _active(base_engine) if how == "superseded" else None
    code, out = _run([a], HookIn(change), dump=dump)
    assert code == 1
    assert "Refused:" in out
    if how == "base_moved":
        assert "base_changed" in out
        assert dump.calls == []
    else:
        assert dump.calls == []
        assert _active(base_engine) == base
    assert _op(base_engine, a).status == "expired"


def test_a_cli_refusal_writes_the_audit_row(fac: Factory, base_engine: Engine) -> None:
    pid = _week_preview(fac, now=STALE)
    _run([pid, "--yes"], Stdin(tty=False))
    assert {"action": "commit", "code": "expired", "preview_id": pid} in _audits(base_engine)
    _run(["00000000-0000-4000-8000-000000000000", "--yes"], Stdin(tty=False))
    assert any(d.get("code") == "unknown_preview" for d in _audits(base_engine))


def test_a_commit_prints_both_import_ids_and_both_ways_to_check(
    fac: Factory, base_engine: Engine
) -> None:
    pid = _week_preview(fac)
    code, out = _run([pid, "--yes"], Stdin(tty=False))
    assert code == 0
    op = _op(base_engine, pid)
    assert f"scores import {op.scores_import_id}" in out
    assert f"stations import {op.stations_import_id}" in out
    assert f"get_job with the job id {op.job_id}" in out
    assert f"preview id {pid}" in out
    assert out.index("Taking the backup") < out.index("Committing") < out.index("Committed ")


def test_a_database_error_is_uncertain_and_mentions_no_key(
    fac: Factory, base_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import text

    pid = _week_preview(fac)

    def bad(*_a: object, **_k: object) -> int:
        raise_sql(base_engine)
        return 0

    def raise_sql(engine: Engine) -> None:
        with Session(engine) as s:
            s.execute(text("SELECT secret_col FROM no_such_table"))

    monkeypatch.setattr(writes, "enqueue", bad)
    code, out = _run([pid, "--yes"], Stdin(tty=False))
    assert code == 1
    assert "re-run this command (a committed preview" in out
    assert "42P01" in out
    assert "ProgrammingError" in out
    assert "idempotency" not in out
    assert "Refused: db_error" not in out
    assert "secret_col" not in out


def test_closed_stdin_exits_2_without_yes_and_works_with_it(
    fac: Factory, base_engine: Engine
) -> None:
    pid = _week_preview(fac)
    import sys  # sys.stdin is None when the process was started with stdin closed

    real = sys.stdin
    sys.stdin = None  # type: ignore[assignment]
    try:
        out = io.StringIO()
        assert approve.main([pid], None, out, dump=FakeDump(), now=lambda: LATER) == 2
        assert "--yes" in out.getvalue()
        assert _op(base_engine, pid).status == "previewed"
        out = io.StringIO()
        assert approve.main([pid, "--yes"], None, out, dump=FakeDump(), now=lambda: LATER) == 0
    finally:
        sys.stdin = real
    assert _op(base_engine, pid).status == "committed"


def test_ctrl_c_at_the_prompt_is_not_committed(fac: Factory, base_engine: Engine) -> None:
    def interrupt() -> None:
        raise KeyboardInterrupt

    pid = _week_preview(fac)
    dump = FakeDump()
    code, out = _run([pid], HookIn(interrupt), dump=dump)
    assert code == 1
    assert "Not committed." in out
    assert dump.calls == []
    assert _op(base_engine, pid).status == "previewed"


def test_ctrl_c_during_the_backup_is_not_committed(fac: Factory, base_engine: Engine) -> None:
    def interrupt() -> None:
        raise KeyboardInterrupt

    pid = _week_preview(fac)
    code, out = _run([pid, "--yes"], Stdin(tty=False), dump=FakeDump(hook=interrupt))
    assert code == 1
    assert "Not committed." in out
    assert _op(base_engine, pid).status == "previewed"


def test_ctrl_c_during_the_commit_step_is_ambiguous(
    fac: Factory, base_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: object, **_k: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(writes, "enqueue", boom)
    pid = _week_preview(fac)
    code, out = _run([pid, "--yes"], Stdin(tty=False))
    assert code == 1
    assert "may or may not have committed" in out
    assert "Traceback" not in out


def test_help_prints_usage_and_exits_zero_without_touching_anything() -> None:
    out = io.StringIO()
    code = approve.main(["--help"], Stdin(), out, dump=FakeDump(), now=lambda: LATER)
    assert code == 0


def test_a_correction_summary_without_day_totals_omits_that_line() -> None:
    lines = approve._render(
        {
            "kind": "correction",
            "date": dt.date(2026, 9, 27),
            "status": "previewed",
            "created_at": LATER,
            "expires_at": LATER + dt.timedelta(hours=1),
            "now": LATER,
            "preview": {
                "changes": [{"name": "Testshooter, Alpha", "old_score": 40, "new_score": 41}]
            },
        }
    )
    text = "\n".join(lines)
    assert "Testshooter, Alpha: 40 -> 41" in text
    assert "the day then has" not in text
    assert "station detail stays" in text
