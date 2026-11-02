"""Staging tools: a validated week or correction becomes pending imports plus a preview.

Nothing here commits. Every refusal discards what it staged and records an ``mcp_operations``
row (status ``refused``) plus an ``mcp.refuse`` audit row; ``run_write`` lets the session commit
those before the refusal is raised to the caller. Names and arguments are never logged.
"""

import datetime as dt
import hashlib
import os
import re
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import exists, func, select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import record_audit
from sunday_clays.config import database_url_from_env
from sunday_clays.domain.errors import ConflictError
from sunday_clays.domain.imports import (
    IMPORT_LIFECYCLE_LOCK_KEY,
    active_scores_import,
    active_station_sources,
    commit_import,
    discard_import,
    load_staged_scores,
    rollback_import,
    stage_import,
)
from sunday_clays.domain.schemas import FindingOut, ImportPreview, ScoresDiff, StationsDiff
from sunday_clays.ingest.names import name_key
from sunday_clays.ingest.types import ParseError
from sunday_clays.jobs.queue import enqueue
from sunday_clays.mcp import backup
from sunday_clays.mcp.build import (
    BuildError,
    CorrectionInput,
    WeekInput,
    build_correction,
    build_scores,
    build_stations,
)
from sunday_clays.models import Event, Import, ImportStationSheet, McpOperation, Round

DEFAULT_PREVIEW_TTL_SECONDS = 3600
# pg_advisory_xact_lock key serializing previews. Taken elsewhere: 7263001 migrations,
# 7263002 import lifecycle, 7263003 rebuild, 7263004 page views.
MCP_PREVIEW_LOCK_KEY = 7263005
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
MAX_WEEK_AGE_DAYS = 14
MANY_NEW_NAMES = 3
SUNDAY = 6

T = TypeVar("T")


class Refusal(Exception):
    """A stable-coded refusal; the message may name the offending shooter (owner-only caller)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.sqlstate: str | None = None  # set for db_error, for the log only
        self.error_class: str | None = None  # likewise: the exception class name, never its text


class WeekPreview(BaseModel):
    date: dt.date
    head_count: int
    score_sum: int
    average: float
    new_names: list[str]
    possible_duplicates: list[tuple[str, str]]
    findings_for_date: list[FindingOut]
    historical_findings: int
    preview_id: str
    expires_at: dt.datetime
    note: str | None = None


class CorrectionChange(BaseModel):
    name: str
    old_score: int
    new_score: int


class CorrectionPreview(BaseModel):
    date: dt.date
    changes: list[CorrectionChange]
    findings_for_date: list[FindingOut]
    historical_findings: int
    preview_id: str
    expires_at: dt.datetime
    needs_human_approval: bool = True


def preview_ttl() -> dt.timedelta:
    raw = os.environ.get("MCP_PREVIEW_TTL")
    seconds = int(raw) if raw and raw.isdigit() and int(raw) > 0 else DEFAULT_PREVIEW_TTL_SECONDS
    return dt.timedelta(seconds=seconds)


# A failure at COMMIT may already have been applied, so this never says "unchanged".
DB_ERROR_MESSAGE = (
    "the database returned an error; the scores may or may not have changed; "
    "check get_job, or retry with the same idempotency key"
)
BUSY_SQLSTATES = frozenset({"40P01", "57014", "55P03"})  # deadlock, canceled, lock not available


def run_write[T](
    factory: Callable[[], AbstractContextManager[Session]], fn: Callable[[Session], T]
) -> T:
    """Run ``fn`` in a write session; a Refusal is raised only after the session has committed.

    A deadlock, statement timeout or lock-wait timeout becomes the coded, retryable refusal
    ``busy``; the SQL text is never returned to the caller.
    """
    refusal: Refusal | None = None
    try:
        with factory() as session:
            try:
                result = fn(session)
            except Refusal as exc:
                refusal = exc
    except SQLAlchemyError as exc:
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if isinstance(exc, DBAPIError) and sqlstate in BUSY_SQLSTATES:
            raise Refusal(
                "busy",
                "the database was busy; the scores were not changed; "
                "retry with the same idempotency key",
            ) from None
        # Anything else is a bug or an outage; the text (SQL, parameters) never reaches the caller.
        db_refusal = Refusal("db_error", DB_ERROR_MESSAGE)
        db_refusal.sqlstate = sqlstate
        db_refusal.error_class = type(exc).__name__
        raise db_refusal from None
    if refusal is not None:
        raise refusal
    return result


# --- shared steps ----------------------------------------------------------------------------
def _discard_if_pending(session: Session, import_id: int | None) -> None:
    """Discard a pending import; one an admin already discarded or committed is left alone."""
    if import_id is None:
        return
    if session.scalar(select(Import.status).where(Import.id == import_id)) != "pending":
        return
    try:
        discard_import(session, import_id)
    except ConflictError:  # not_pending: it changed between the read and the lifecycle lock
        return


def _expire(session: Session, op: McpOperation) -> None:
    op.status = "expired"
    _discard_if_pending(session, op.scores_import_id)
    _discard_if_pending(session, op.stations_import_id)


def _sweep(session: Session, now: dt.datetime, ttl: dt.timedelta) -> None:
    stale = session.scalars(
        select(McpOperation)
        .where(McpOperation.status == "previewed", McpOperation.created_at < now - ttl)
        # A row another transaction holds (a commit mid-dump) is not ours to expire.
        .with_for_update(skip_locked=True)
    ).all()
    for op in stale:
        _expire(session, op)
    session.flush()


def _supersede(session: Session, event_date: dt.date) -> None:
    """A newer preview for a Sunday replaces any earlier one, so two never both commit."""
    # FOR UPDATE: a row another transaction is committing mid-dump is waited for, and the WHERE
    # is re-evaluated afterwards, so a just-committed operation drops out and is never expired.
    older = session.scalars(
        select(McpOperation)
        .where(McpOperation.status == "previewed", McpOperation.event_date == event_date)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    for op in older:
        _expire(session, op)


def _refuse(
    session: Session,
    kind: str,
    event_date: dt.date,
    now: dt.datetime,
    exc: Refusal,
    staged: list[int],
) -> None:
    for import_id in staged:
        _discard_if_pending(session, import_id)
    session.add(
        McpOperation(
            kind=kind,
            event_date=event_date,
            status="refused",
            created_at=now,
            result={"code": exc.code, "message": exc.message},
        )
    )
    record_audit(
        session, None, "mcp", "mcp.refuse", {"kind": kind, "date": event_date, "code": exc.code}
    )
    session.flush()


def _stage(session: Session, data: bytes, filename: str, staged: list[int]) -> ImportPreview:
    try:
        preview = stage_import(session, data, filename)
    except ParseError as exc:
        raise Refusal("invalid_input", f"the built workbook did not parse: {exc}") from exc
    if preview.duplicate_of is not None:
        raise Refusal("duplicate", "an identical file is already staged or committed")
    staged.append(preview.import_id)
    return preview


def _base_bytes(session: Session) -> tuple[int, bytes]:
    """The active scores import's id and bytes, read together so the id is the one built on."""
    base_id = active_scores_import(session)
    if base_id is None:
        raise Refusal("no_base", "no committed scores import to build on")
    data = session.scalars(select(Import.file_bytes).where(Import.id == base_id)).one()
    return base_id, data


def _require_base(session: Session, base_id: int) -> None:
    if active_scores_import(session) != base_id:
        raise Refusal("base_changed", "the stored scores changed while this was being built")


def _split_findings(
    date: dt.date, previews: list[ImportPreview], new_names: list[str]
) -> tuple[list[FindingOut], int]:
    """Only findings about the previewed Sunday are listed; the rest are an old-data count."""
    fresh = {name_key(n) for n in new_names}
    mine: list[FindingOut] = []
    other = 0
    for preview in previews:
        for finding in preview.findings:
            # Spurious: the scores are not committed yet when the stations are staged.
            if (
                finding.code == "station_name_unmatched"
                and finding.name is not None
                and name_key(finding.name) in fresh
            ):
                continue
            if finding.event_date == date:
                mine.append(finding)
            else:
                other += 1
    return mine, other


def _existing_preview(
    session: Session, kind: str, date: dt.date, digest: str
) -> McpOperation | None:
    return session.scalars(
        select(McpOperation)
        .where(
            McpOperation.status == "previewed",
            McpOperation.kind == kind,
            McpOperation.event_date == date,
            McpOperation.result["input_sha256"].astext == digest,
        )
        .limit(1)
    ).first()


def _digest(model: BaseModel) -> str:
    return hashlib.sha256(model.model_dump_json(by_alias=True).encode()).hexdigest()


def _lock_previews(session: Session) -> None:
    """Held to the end of the transaction: a second preview waits, then sees the first."""
    session.execute(select(func.pg_advisory_xact_lock(MCP_PREVIEW_LOCK_KEY)))


def _active_last(session: Session) -> dt.date | None:
    """Latest Sunday in the active scores import (live events may lag behind a fresh commit)."""
    rows = load_staged_scores(session, active_scores_import(session))
    return max((r.event_date for r in rows), default=None)


def _last_event(session: Session) -> dt.date | None:
    """Latest Sunday known anywhere: the active import's rows or the rebuilt events table."""
    stored = session.scalar(select(func.max(Event.event_date)))
    active = _active_last(session)
    return max((d for d in (stored, active) if d is not None), default=None)


def _reusable(session: Session, op: McpOperation | None) -> McpOperation | None:
    """A previous identical preview, only while it can still be committed as previewed."""
    if op is None:
        return None
    # Re-read under a row lock: the unlocked load may be stale (the row can have been committed
    # while we waited), and an expire must never overwrite a committed or rolled-back operation.
    held = session.scalars(
        select(McpOperation)
        .where(McpOperation.id == op.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    if held.status != "previewed":
        return None
    op = held
    live = all(
        i is None or session.scalar(select(Import.status).where(Import.id == i)) == "pending"
        for i in (op.scores_import_id, op.stations_import_id)
    )
    if live and op.result.get("base_import_id") == active_scores_import(session):
        return op
    _expire(session, op)
    session.flush()
    return None


def _record_preview(
    session: Session,
    kind: str,
    date: dt.date,
    now: dt.datetime,
    ttl: dt.timedelta,
    scores_id: int,
    stations_id: int | None,
    digest: str,
    base_id: int,
) -> McpOperation:
    _supersede(session, date)
    session.flush()  # the old row leaves 'previewed' before the new one enters it
    _require_base(session, base_id)  # after any wait on a committing row: the base may have moved
    op = McpOperation(
        kind=kind,
        event_date=date,
        status="previewed",
        created_at=now,
        scores_import_id=scores_id,
        stations_import_id=stations_id,
        result={"input_sha256": digest, "base_import_id": base_id},
    )
    session.add(op)
    session.flush()
    record_audit(
        session,
        None,
        "mcp",
        "mcp.preview",
        {"kind": kind, "date": date, "preview_id": str(op.id), "expires_at": now + ttl},
    )
    return op


# --- preview_week ----------------------------------------------------------------------------
def _check_week_date(session: Session, date: dt.date, now: dt.datetime) -> None:
    if date.weekday() != SUNDAY:
        raise Refusal("not_sunday", f"{date.isoformat()} is not a Sunday")
    today = now.astimezone(LOCAL_TZ).date()
    if date > today:
        raise Refusal("future_date", f"{date.isoformat()} is in the future (today is {today})")
    last = _last_event(session)
    if last is not None and date <= last:
        raise Refusal(
            "not_after_last_event",
            f"the latest stored Sunday is {last.isoformat()}; a new week must come after it",
        )
    if (today - date).days > MAX_WEEK_AGE_DAYS:
        raise Refusal("too_old", f"{date.isoformat()} is more than {MAX_WEEK_AGE_DAYS} days ago")
    if session.scalar(select(exists().where(Round.event_date == date))):
        raise Refusal("date_has_rounds", f"{date.isoformat()} already has stored rounds")


def _week_preview(
    session: Session, week: WeekInput, now: dt.datetime, ttl: dt.timedelta, staged: list[int]
) -> WeekPreview:
    _check_week_date(session, week.date, now)
    digest = _digest(week)
    same = _reusable(session, _existing_preview(session, "week", week.date, digest))
    if same is not None:
        return WeekPreview.model_validate(same.result["preview"])
    base_id, base = _base_bytes(session)
    try:
        scores_bytes = build_scores(base, week)
    except BuildError as exc:
        raise Refusal("invalid_input", f"could not build the scores workbook: {exc.code}") from exc
    _require_base(session, base_id)  # before staging: the diff must be against this base
    stations_bytes = build_stations(week)
    scores = _stage(session, scores_bytes, f"mcp-scores-{week.date.isoformat()}.xlsx", staged)
    stations = None
    if stations_bytes is not None:
        stations = _stage(
            session, stations_bytes, f"mcp-stations-{week.date.isoformat()}.xlsx", staged
        )
    diff = scores.diff
    if not (
        isinstance(diff, ScoresDiff)
        and diff.events_added == [week.date]
        and not diff.events_removed
        and diff.rows_added == len(week.shooters)
        and diff.rows_removed == 0
        and diff.rows_changed == 0
        and diff.attendance_changed <= 1
    ):
        raise Refusal("not_append_only", "the week would change or remove stored scores")
    if stations is not None:
        sdiff = stations.diff
        if not (
            isinstance(sdiff, StationsDiff)
            and sdiff.events_added == [week.date]
            and not sdiff.events_replaced
            and not sdiff.sheets_skipped
        ):
            raise Refusal(
                "not_append_only", "the station sheet would replace or skip stored station data"
            )
    staged_rows = [
        r for r in load_staged_scores(session, scores.import_id) if r.event_date == week.date
    ]
    total = sum(r.score for r in staged_rows)
    if len(staged_rows) != len(week.shooters) or total != sum(s.score for s in week.shooters):
        raise Refusal("not_append_only", "the staged rows do not match the submitted scores")
    op = _record_preview(
        session, "week", week.date, now, ttl, scores.import_id,
        stations.import_id if stations else None, digest, base_id,
    )  # fmt: skip
    mine, other = _split_findings(
        week.date, [p for p in (scores, stations) if p is not None], diff.new_names
    )
    n_new = len(diff.new_names)
    preview = WeekPreview(
        date=week.date,
        head_count=len(staged_rows),
        score_sum=total,
        average=round(total / len(staged_rows), 2),
        new_names=diff.new_names,
        possible_duplicates=diff.possible_duplicates,
        findings_for_date=mine,
        historical_findings=other,
        preview_id=str(op.id),
        expires_at=now + ttl,
        note=(
            f"{n_new} new names: check each against find_shooters for an existing spelling"
            if n_new > MANY_NEW_NAMES
            else None
        ),
    )
    op.result = {**op.result, "preview": preview.model_dump(mode="json")}
    session.flush()
    return preview


def preview_week(
    session: Session,
    week: WeekInput,
    *,
    now: dt.datetime,
    ttl: dt.timedelta | None = None,
) -> WeekPreview:
    ttl = ttl or preview_ttl()
    _lock_previews(session)  # never sweeps: preview_week_tool sweeps in its own transaction
    staged: list[int] = []
    try:
        return _week_preview(session, week, now, ttl, staged)
    except Refusal as exc:
        _refuse(session, "week", week.date, now, exc, staged)
        raise


# --- preview_correction ----------------------------------------------------------------------
def _correction_preview(
    session: Session, c: CorrectionInput, now: dt.datetime, ttl: dt.timedelta, staged: list[int]
) -> CorrectionPreview:
    if _active_last(session) != c.date:
        raise Refusal("not_latest_event", "only the latest stored Sunday can be corrected")
    digest = _digest(c)
    same = _reusable(session, _existing_preview(session, "correction", c.date, digest))
    if same is not None:
        return CorrectionPreview.model_validate(same.result["preview"])
    base_id, base = _base_bytes(session)
    old = {
        r.name_key: r.score for r in load_staged_scores(session, base_id) if r.event_date == c.date
    }
    try:
        data = build_correction(base, c)
    except BuildError as exc:
        if exc.code == "name_not_on_date":
            raise Refusal(
                "name_not_on_date", "a corrected name is not on that Sunday's scores"
            ) from exc
        raise Refusal("invalid_input", f"could not build the correction: {exc.code}") from exc
    _require_base(session, base_id)
    scores = _stage(session, data, f"mcp-correction-{c.date.isoformat()}.xlsx", staged)
    diff = scores.diff
    if not (
        isinstance(diff, ScoresDiff)
        and not diff.events_added
        and not diff.events_removed
        and diff.rows_added == 0
        and diff.rows_removed == 0
        and diff.rows_changed == len(c.rows)
        and diff.attendance_changed == 0
    ):
        raise Refusal(
            "invalid_input",
            f"expected {len(c.rows)} changed scores and nothing else; a score may equal the "
            "stored one",
        )
    op = _record_preview(
        session, "correction", c.date, now, ttl, scores.import_id, None, digest, base_id
    )
    mine, other = _split_findings(c.date, [scores], [])
    preview = CorrectionPreview(
        date=c.date,
        changes=[
            CorrectionChange(name=r.name, old_score=old[name_key(r.name)], new_score=r.score)
            for r in c.rows
        ],
        findings_for_date=mine,
        historical_findings=other,
        preview_id=str(op.id),
        expires_at=now + ttl,
    )
    op.result = {**op.result, "preview": preview.model_dump(mode="json")}
    session.flush()
    return preview


def preview_correction(
    session: Session,
    c: CorrectionInput,
    *,
    now: dt.datetime,
    ttl: dt.timedelta | None = None,
) -> CorrectionPreview:
    ttl = ttl or preview_ttl()
    _lock_previews(session)  # never sweeps: preview_correction_tool sweeps first
    staged: list[int] = []
    try:
        return _correction_preview(session, c, now, ttl, staged)
    except Refusal as exc:
        _refuse(session, "correction", c.date, now, exc, staged)
        raise


# --- commit_week / rollback_week -------------------------------------------------------------
DEFAULT_BACKUP_DIR = "/backups"
TOOL_DUMP_LOCK_TIMEOUT_S = 30.0
KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,100}$")
APPROVE_COMMAND = "python -m sunday_clays.mcp.approve"
DumpFn = Callable[..., Path]


def commits_enabled() -> bool:
    """``MCP_COMMIT_ENABLED``: only "true" or "1" turn it on; anything else (or unset) is off."""
    return os.environ.get("MCP_COMMIT_ENABLED") in {"true", "1"}


def backup_dir() -> Path:
    return Path(os.environ.get("MCP_BACKUP_DIR") or DEFAULT_BACKUP_DIR)


def _parse_id(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _audit_refusal(session: Session, action: str, preview_id: uuid.UUID | None, code: str) -> None:
    """An audit row only: the operation (if any) keeps its status so it stays retryable."""
    details: dict[str, Any] = {"action": action, "code": code}
    if preview_id is not None:
        details["preview_id"] = str(preview_id)
    record_audit(session, None, "mcp", "mcp.refuse", details)
    session.flush()


def _find_by_key(session: Session, key: str) -> tuple[McpOperation, str] | None:
    """The operation that already used ``key``, and whether as its commit or rollback key."""
    committed = session.scalars(
        select(McpOperation).where(McpOperation.idempotency_key == key).limit(1)
    ).first()
    if committed is not None:
        return committed, "commit"
    rolled = session.scalars(
        select(McpOperation)
        .where(McpOperation.result["rollback"]["idempotency_key"].astext == key)
        .limit(1)
    ).first()
    return (rolled, "rollback") if rolled is not None else None


def _check_key(key: str) -> None:
    if not KEY_PATTERN.fullmatch(key):
        raise Refusal(
            "invalid_idempotency_key",
            "the idempotency key must be 8-100 characters of A-Za-z0-9._-",
        )


def _lock_op(session: Session, preview_id: str) -> McpOperation:
    parsed = _parse_id(preview_id)
    op = (
        session.get(McpOperation, parsed, with_for_update=True, populate_existing=True)
        if parsed is not None
        else None
    )
    if op is None:
        raise Refusal("unknown_preview", "no such preview")
    return op


def _linked(op: McpOperation) -> list[int]:
    return [i for i in (op.scores_import_id, op.stations_import_id) if i is not None]


def _require_status(session: Session, op: McpOperation, import_ids: list[int], status: str) -> None:
    code = "import_not_pending" if status == "pending" else "import_not_committed"
    for import_id in import_ids:
        if session.scalar(select(Import.status).where(Import.id == import_id)) != status:
            raise Refusal(code, f"a staged import is no longer {status} (an admin changed it)")


def _stale_base(session: Session, op: McpOperation) -> None:
    """The preview's workbook is a full history built on ``base_import_id``; it must still be live.

    Committing it over a newer base would silently revert whatever changed since. The preview
    can never become committable again, so it is expired and its staged imports discarded.
    """
    if active_scores_import(session) != op.result.get("base_import_id"):
        _expire(session, op)
        op.result = {**op.result, "expired_reason": "base_changed"}
        session.flush()
        raise Refusal(
            "base_changed", "the stored scores changed since this preview; stage it again"
        )


def _lifecycle_lock(session: Session) -> None:
    session.execute(select(func.pg_advisory_xact_lock(IMPORT_LIFECYCLE_LOCK_KEY)))


def _take_dump(session: Session, op: McpOperation, dump: DumpFn | None) -> str:
    """The verified pre-write dump's file name; a failure refuses and changes nothing."""
    take = dump or backup.pre_import_dump
    try:
        path = take(
            op.id,
            backup_dir=backup_dir(),
            database_url=database_url_from_env(),
            lock_timeout_s=TOOL_DUMP_LOCK_TIMEOUT_S,
        )
    except backup.BackupError as exc:
        raise Refusal(
            "backup_failed", f"the pre-import backup failed, nothing changed: {exc}"
        ) from exc
    return Path(path).name


def _translate(exc: ConflictError) -> Refusal:
    if exc.code == "not_pending":
        return Refusal("import_not_pending", "a staged import is no longer pending")
    if exc.code == "not_committed":
        return Refusal("import_not_committed", "a staged import is no longer committed")
    return Refusal(exc.code, exc.message)


def _replay(op: McpOperation, owner: tuple[McpOperation, str] | None, which: str) -> dict[str, Any]:
    """The stored result for a repeated key on the same operation; any other use is reuse."""
    if owner is None or owner[0].id != op.id or owner[1] != which:
        raise Refusal("key_reused", "that idempotency key was already used for something else")
    stored = {k: v for k, v in op.result[which].items() if k != "idempotency_key"}
    return {**stored, "current_status": op.status}  # the stored result itself is unchanged


def commit_operation(
    session: Session,
    preview_id: str,
    *,
    idempotency_key: str,
    commit_path: str,
    allow_correction: bool,
    now: dt.datetime,
    dump: DumpFn | None = None,
) -> dict[str, Any]:
    """Commit a previewed operation (scores then stations) after a verified dump; fail closed."""
    parsed = _parse_id(preview_id)
    try:
        _check_key(idempotency_key)
        return _commit(
            session, preview_id, idempotency_key, commit_path, allow_correction, now, dump
        )
    except Refusal as exc:
        _audit_refusal(session, "commit", parsed, exc.code)
        raise


def _commit(
    session: Session,
    preview_id: str,
    key: str,
    commit_path: str,
    allow_correction: bool,
    now: dt.datetime,
    dump: DumpFn | None,
) -> dict[str, Any]:
    op = _lock_op(session, preview_id)
    owner = _find_by_key(session, key)
    if owner is not None:
        return _replay(op, owner, "commit")
    if op.status == "expired":
        raise Refusal("expired", "this preview expired; stage it again")
    if op.status != "previewed":
        code = "already_committed" if op.status in {"committed", "rolled_back"} else "not_previewed"
        raise Refusal(code, f"this preview is {op.status}")
    if op.created_at < now - preview_ttl():
        _expire(session, op)  # nothing is held across a dump yet: this refuses straight away
        session.flush()
        raise Refusal("expired", "this preview expired; stage it again")
    if op.kind == "correction" and not allow_correction:
        raise Refusal(
            "correction_needs_human",
            f"a human must approve a correction: {APPROVE_COMMAND} {op.id}",
        )
    _require_status(session, op, _linked(op), "pending")
    _stale_base(session, op)  # early, so a stale preview does not waste a dump
    backup_file = _take_dump(session, op, dump)
    _lifecycle_lock(session)
    _require_status(session, op, _linked(op), "pending")
    _stale_base(session, op)
    if _find_by_key(session, key) is not None:
        raise Refusal("key_reused", "that idempotency key was already used for something else")
    try:
        with session.begin_nested():  # all or nothing: never scores without stations
            for import_id in _linked(op):  # scores first, then stations
                commit_import(session, import_id)
            job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    except ConflictError as exc:
        raise _translate(exc) from exc
    result = {
        "preview_id": str(op.id),
        "kind": op.kind,
        "date": op.event_date.isoformat(),
        "status": "committed",
        "scores_import_id": op.scores_import_id,
        "stations_import_id": op.stations_import_id,
        "job_id": job_id,
        "backup_file": backup_file,
        "commit_path": commit_path,
        "committed_at": now.isoformat(),
    }
    op.status = "committed"
    op.commit_path = commit_path
    op.idempotency_key = key
    op.backup_file = backup_file
    op.job_id = job_id
    op.committed_at = now
    op.result = {**op.result, "commit": result}
    session.flush()
    record_audit(
        session,
        None,
        "mcp",
        "mcp.commit",
        {
            "preview_id": str(op.id),
            "kind": op.kind,
            "date": op.event_date,
            "commit_path": commit_path,
            "job_id": job_id,
            "backup_file": backup_file,
        },
    )
    session.flush()
    return result


def _station_import_is_live(session: Session, op: McpOperation) -> bool:
    """True while the station sheet for this date still comes from this operation's import."""
    if op.stations_import_id is None:
        return False
    live = active_station_sources(session).get(op.event_date)
    mine = session.scalars(
        select(ImportStationSheet.id).where(
            ImportStationSheet.import_id == op.stations_import_id,
            ImportStationSheet.event_date == op.event_date,
        )
    ).all()
    return live is not None and live in mine


def _require_latest(session: Session, op: McpOperation) -> None:
    if (
        active_scores_import(session) != op.scores_import_id
        or _active_last(session) != op.event_date
    ):
        raise Refusal("not_latest", "only the most recent committed import can be rolled back")


def rollback_operation(
    session: Session,
    preview_id: str,
    *,
    idempotency_key: str,
    now: dt.datetime,
    dump: DumpFn | None = None,
) -> dict[str, Any]:
    """Undo the latest committed operation (after a verified dump); fail closed."""
    parsed = _parse_id(preview_id)
    try:
        _check_key(idempotency_key)
        return _rollback(session, preview_id, idempotency_key, now, dump)
    except Refusal as exc:
        _audit_refusal(session, "rollback", parsed, exc.code)
        raise


def _rollback(
    session: Session, preview_id: str, key: str, now: dt.datetime, dump: DumpFn | None
) -> dict[str, Any]:
    op = _lock_op(session, preview_id)
    owner = _find_by_key(session, key)
    if owner is not None:
        return _replay(op, owner, "rollback")
    if op.status == "rolled_back":
        raise Refusal("already_rolled_back", "this operation was already rolled back")
    if op.status != "committed":
        raise Refusal("not_committed", f"this preview is {op.status}, not committed")
    _require_latest(session, op)
    backup_file = _take_dump(session, op, dump)
    _lifecycle_lock(session)
    _require_latest(session, op)
    _require_status(session, op, [i for i in [op.scores_import_id] if i is not None], "committed")
    if _find_by_key(session, key) is not None:
        raise Refusal("key_reused", "that idempotency key was already used for something else")
    stations_rolled_back = _station_import_is_live(session, op)
    try:
        with session.begin_nested():
            targets = [op.scores_import_id, op.stations_import_id if stations_rolled_back else None]
            for import_id in targets:
                if import_id is not None:
                    rollback_import(session, import_id)
            job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    except ConflictError as exc:
        raise _translate(exc) from exc
    result: dict[str, Any] = {
        "preview_id": str(op.id),
        "kind": op.kind,
        "date": op.event_date.isoformat(),
        "status": "rolled_back",
        "scores_import_id": op.scores_import_id,
        "stations_import_id": op.stations_import_id,
        "stations_rolled_back": stations_rolled_back,
        "job_id": job_id,
        "backup_file": backup_file,
        "rolled_back_at": now.isoformat(),
        "idempotency_key": key,
    }
    if op.stations_import_id is not None and not stations_rolled_back:
        result["note"] = (
            "the station sheet for this date no longer comes from this operation, so it was left"
        )
    op.status = "rolled_back"
    op.rolled_back_at = now
    op.result = {**op.result, "rollback": result}
    session.flush()
    record_audit(
        session,
        None,
        "mcp",
        "mcp.rollback",
        {
            "preview_id": str(op.id),
            "kind": op.kind,
            "date": op.event_date,
            "job_id": job_id,
            "backup_file": backup_file,
            "stations_rolled_back": stations_rolled_back,
        },
    )
    session.flush()
    return {k: v for k, v in result.items() if k != "idempotency_key"}


# --- the tool-facing wrappers ----------------------------------------------------------------
def _gate(session: Session, action: str, preview_id: str) -> None:
    if not commits_enabled():
        _audit_refusal(session, action, _parse_id(preview_id), "commits_disabled")
        parsed = _parse_id(preview_id)
        how = (
            f"{APPROVE_COMMAND} {parsed}"
            if parsed is not None
            else "the approve command with the preview_id returned by preview_week"
        )  # only a parsed UUID is ever echoed back
        raise Refusal(
            "commits_disabled",
            f"commits through this server are off; a human commits during the preview-only "
            f"period with: {how}",
        )


def commit_week(
    session: Session,
    preview_id: str,
    *,
    idempotency_key: str,
    now: dt.datetime,
    dump: DumpFn | None = None,
) -> dict[str, Any]:
    """The ``commit_week`` tool: gated, never a correction."""
    _gate(session, "commit", preview_id)
    return commit_operation(
        session,
        preview_id,
        idempotency_key=idempotency_key,
        commit_path="mcp-auto",
        allow_correction=False,
        now=now,
        dump=dump,
    )


def rollback_week(
    session: Session,
    preview_id: str,
    *,
    idempotency_key: str,
    now: dt.datetime,
    dump: DumpFn | None = None,
) -> dict[str, Any]:
    """The ``rollback_week`` tool: gated, and a correction needs a human here too."""
    _gate(session, "rollback", preview_id)
    parsed = _parse_id(preview_id)
    op = session.get(McpOperation, parsed) if parsed is not None else None
    if op is not None and op.kind == "correction":
        _audit_refusal(session, "rollback", parsed, "correction_needs_human")
        raise Refusal(
            "correction_needs_human",
            f"a human must roll back a correction: use the imports page or {APPROVE_COMMAND}",
        )
    return rollback_operation(
        session, preview_id, idempotency_key=idempotency_key, now=now, dump=dump
    )


# --- tool entry points: gate, then a short sweep transaction, then the real work ---------------
def sweep_expired(factory: Callable[[], AbstractContextManager[Session]], now: dt.datetime) -> None:
    """Expire stale previews in their own short transaction.

    Never inside a commit's transaction: discarding takes the import lifecycle lock, which would
    then be held across the dump and invert lock order against the row locks held there.
    """
    run_write(factory, lambda session: _sweep(session, now, preview_ttl()))


def preview_week_tool(
    factory: Callable[[], AbstractContextManager[Session]], week: WeekInput, *, now: dt.datetime
) -> WeekPreview:
    sweep_expired(factory, now)
    return run_write(factory, lambda s: preview_week(s, week, now=now))


def preview_correction_tool(
    factory: Callable[[], AbstractContextManager[Session]],
    correction: CorrectionInput,
    *,
    now: dt.datetime,
) -> CorrectionPreview:
    sweep_expired(factory, now)
    return run_write(factory, lambda s: preview_correction(s, correction, now=now))


def commit_week_tool(
    factory: Callable[[], AbstractContextManager[Session]],
    preview_id: str,
    *,
    idempotency_key: str,
    now: dt.datetime,
    dump: DumpFn | None = None,
) -> dict[str, Any]:
    run_write(factory, lambda s: _gate(s, "commit", preview_id))  # disabled: no sweep, no state
    sweep_expired(factory, now)
    return run_write(
        factory,
        lambda s: commit_week(s, preview_id, idempotency_key=idempotency_key, now=now, dump=dump),
    )


def rollback_week_tool(
    factory: Callable[[], AbstractContextManager[Session]],
    preview_id: str,
    *,
    idempotency_key: str,
    now: dt.datetime,
    dump: DumpFn | None = None,
) -> dict[str, Any]:
    run_write(factory, lambda s: _gate(s, "rollback", preview_id))
    sweep_expired(factory, now)
    return run_write(
        factory,
        lambda s: rollback_week(s, preview_id, idempotency_key=idempotency_key, now=now, dump=dump),
    )
