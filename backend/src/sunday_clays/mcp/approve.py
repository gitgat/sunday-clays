"""The human approve command: ``python -m sunday_clays.mcp.approve <preview_id> [--yes]``.

During the preview-only period this is how a previewed Sunday is committed, and it is the only way
a correction is. It bypasses ``MCP_COMMIT_ENABLED`` on purpose (a human is approving) and passes
``allow_correction=True``. It is run by the owner inside the mcp container and is deliberately not
importable from, nor reachable through, any MCP tool.

The summary names shooters: it goes to the owner's terminal only and is never logged. The database
URL and the bearer token are never printed.
"""

import argparse
import datetime as dt
import sys
import uuid
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, TextIO

from sqlalchemy.orm import Session

from sunday_clays.mcp import backup, server, writes
from sunday_clays.models import McpOperation

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
Factory = Callable[[], AbstractContextManager[Session]]


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Any:  # never echo the offending argument
        raise _UsageError("bad arguments")


def _parser() -> argparse.ArgumentParser:
    p = _Parser(
        prog="python -m sunday_clays.mcp.approve",
        description="Commit a previewed Sunday or correction after a verified backup.",
        add_help=True,
    )
    p.add_argument("preview_id", help="the preview_id returned by preview_week/preview_correction")
    p.add_argument(
        "--yes", action="store_true", help="skip the confirmation prompt (needed without a TTY)"
    )
    return p


def _summary(session: Session, preview_id: uuid.UUID, now: dt.datetime) -> dict[str, Any] | None:
    op = session.get(McpOperation, preview_id)
    if op is None:
        return None
    session.refresh(op)
    return {
        "kind": op.kind,
        "date": op.event_date,
        "status": op.status,
        "created_at": op.created_at,
        "expires_at": op.created_at + writes.preview_ttl(),
        "preview": (op.result or {}).get("preview") or {},
        "now": now,
    }


def _age(delta: dt.timedelta) -> str:
    minutes = max(int(delta.total_seconds() // 60), 0)
    return f"{minutes} min" if minutes < 120 else f"{minutes // 60} h"


def _render(info: dict[str, Any]) -> list[str]:
    p = info["preview"]
    now: dt.datetime = info["now"]
    correction = info["kind"] == "correction"
    lines = [
        f"Preview of a {'CORRECTION' if correction else info['kind']} for {info['date']}"
        f" (status: {info['status']})",
    ]
    if correction:
        changes = p.get("changes", [])
        lines.append(f"  {len(changes)} score(s) change:")
        lines += [f"    {c['name']}: {c['old_score']} -> {c['new_score']}" for c in changes]
        if p.get("head_count") is not None:
            lines.append(
                f"  the day then has {p['head_count']} shooters, score sum {p['score_sum']}, "
                f"average {p['average']}"
            )
        lines.append(
            "  A corrected shooter's station detail stays, and will be flagged as not matching "
            "the score (station_score_mismatch)."
        )
    else:
        lines.append(
            f"  {p.get('head_count', '?')} shooters, score sum {p.get('score_sum', '?')}, "
            f"average {p.get('average', '?')}"
        )
        new = p.get("new_names", [])
        lines.append(f"  new names ({len(new)}): {'; '.join(new) if new else 'none'}")
        for first, second in p.get("possible_duplicates", []):
            lines.append(f"  possible duplicate: {first} / {second}")
    mine = p.get("findings_for_date", [])
    lines.append(
        f"  findings for this date: {len(mine)} (+{int(p.get('historical_findings', 0))} older)"
    )
    lines += [f"    - {f['message']}" for f in mine]
    if p.get("note"):
        lines.append(f"  note: {p['note']}")
    lines.append(
        f"  staged {_age(now - info['created_at'])} ago; "
        f"expires {info['expires_at'].isoformat(timespec='minutes')}"
    )
    return lines


def _default_dump(
    base: Callable[..., Path], say: Callable[[str], None], phase: dict[str, str]
) -> Callable[..., Path]:
    """The normal dump, but with its own (long) lock wait: a human can wait out the nightly job."""

    def dump(preview_id: uuid.UUID, **kw: Any) -> Path:
        kw.pop("lock_timeout_s", None)  # the tools' short wait; pre_import_dump has its default
        phase["at"] = "backup"
        say("Taking the backup...")
        path = base(preview_id, **kw)
        phase["at"] = "commit"
        say("Committing...")
        return path

    return dump


def _uncertain(say: Callable[[str], None], exc: writes.Refusal) -> None:
    say(
        "The outcome is uncertain: the database returned an error and the scores may or may not "
        "have changed."
    )
    say("  the outcome is uncertain; re-run this command (a committed preview won't commit twice)")
    say("  or check get_job with the preview id.")
    say(f"  sqlstate {exc.sqlstate or 'unknown'}, error class {exc.error_class or 'unknown'}")


def main(
    argv: Sequence[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    *,
    session_factory: Factory | None = None,
    dump: Callable[..., Path] | None = None,
    now: Callable[[], dt.datetime] | None = None,
) -> int:
    stdin = stdin if stdin is not None else sys.stdin  # None when the process has no stdin
    out = stdout or sys.stdout

    def say(text: str = "") -> None:
        out.write(text + "\n")

    try:
        args = _parser().parse_args(list(argv) if argv is not None else None)
        preview_id = uuid.UUID(args.preview_id)
    except (_UsageError, ValueError):
        say("usage: python -m sunday_clays.mcp.approve <preview_id> [--yes]")
        say("error: preview_id must be the UUID returned by preview_week or preview_correction")
        return EXIT_USAGE
    except SystemExit:  # --help
        return EXIT_OK
    if (stdin is None or not stdin.isatty()) and not args.yes:
        say("error: stdin is not a terminal, so there is no way to confirm.")
        say("Re-run with --yes to commit without a prompt.")
        return EXIT_USAGE

    factory = session_factory or server.write_session_factory
    clock = now or (lambda: dt.datetime.now(dt.UTC))
    phase = {"at": "before"}  # before -> backup -> commit: what an interrupt can have left behind
    take = _default_dump(dump or backup.pre_import_dump, say, phase)
    stamp = clock()
    try:
        writes.sweep_expired(factory, stamp)  # commit_operation never sweeps
        info = writes.run_write(factory, lambda s: _summary(s, preview_id, stamp))
        if info is not None:
            for line in _render(info):
                say(line)
        # An unknown id and a preview that is no longer pending go straight to the real refusal
        # (which also writes the audit row): there is nothing to confirm.
        if info is not None and info["status"] == "previewed" and not args.yes and stdin:
            out.write("Type yes to commit this (anything else cancels): ")
            out.flush()
            if stdin.readline().rstrip("\r\n") != "yes":
                say()
                say("Not committed. Nothing was changed.")
                return EXIT_REFUSED
        key = f"cli-{uuid.uuid4()}"
        result = writes.run_write(
            factory,
            lambda s: writes.commit_operation(
                s,
                str(preview_id),
                idempotency_key=key,
                commit_path="cli-approve",
                allow_correction=True,
                now=clock(),
                dump=take,
            ),
        )
    except KeyboardInterrupt:
        say()
        if phase["at"] == "commit":
            say(
                "Interrupted while committing: it may or may not have committed; run approve "
                "again or check get_job with the preview id."
            )
        else:
            say("Not committed. Nothing was changed.")
        return EXIT_REFUSED
    except writes.Refusal as exc:
        if exc.code == "db_error":
            _uncertain(say, exc)
        elif exc.code == "busy":
            say("Busy: the database was busy and nothing was changed; re-run this command.")
        else:
            say(f"Refused: {exc.code}: {exc.message}")
        return EXIT_REFUSED
    say(f"Committed {result['kind']} for {result['date']}.")
    say(
        f"  scores import {result['scores_import_id']}"
        + (
            f", stations import {result['stations_import_id']}"
            if result["stations_import_id"] is not None
            else ""
        )
        + f"; backup file {result['backup_file']}"
    )
    say(f"  rebuild progress: get_job with the job id {result['job_id']}")
    say(f"  the commit record: get_job with the preview id {result['preview_id']}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
