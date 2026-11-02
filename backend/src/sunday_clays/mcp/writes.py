"""Staging tools: a validated week or correction becomes pending imports plus a preview.

Nothing here commits. Every refusal discards what it staged and records an ``mcp_operations``
row (status ``refused``) plus an ``mcp.refuse`` audit row; ``run_write`` lets the session commit
those before the refusal is raised to the caller. Names and arguments are never logged.
"""

import datetime as dt
import hashlib
import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import record_audit
from sunday_clays.domain.imports import (
    active_scores_import,
    discard_import,
    load_staged_scores,
    stage_import,
)
from sunday_clays.domain.schemas import FindingOut, ImportPreview, ScoresDiff
from sunday_clays.ingest.names import name_key
from sunday_clays.ingest.types import ParseError
from sunday_clays.mcp.build import (
    BuildError,
    CorrectionInput,
    WeekInput,
    build_correction,
    build_scores,
    build_stations,
)
from sunday_clays.models import Event, Import, McpOperation, Round

DEFAULT_PREVIEW_TTL_SECONDS = 3600
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


def run_write[T](
    factory: Callable[[], AbstractContextManager[Session]], fn: Callable[[Session], T]
) -> T:
    """Run ``fn`` in a write session; a Refusal is raised only after the session has committed."""
    refusal: Refusal | None = None
    with factory() as session:
        try:
            result = fn(session)
        except Refusal as exc:
            refusal = exc
    if refusal is not None:
        raise refusal
    return result


# --- shared steps ----------------------------------------------------------------------------
def _discard_if_pending(session: Session, import_id: int | None) -> None:
    if import_id is None:
        return
    if session.scalar(select(Import.status).where(Import.id == import_id)) == "pending":
        discard_import(session, import_id)


def _expire(session: Session, op: McpOperation) -> None:
    op.status = "expired"
    _discard_if_pending(session, op.scores_import_id)
    _discard_if_pending(session, op.stations_import_id)


def _sweep(session: Session, now: dt.datetime, ttl: dt.timedelta) -> None:
    stale = session.scalars(
        select(McpOperation).where(
            McpOperation.status == "previewed", McpOperation.created_at < now - ttl
        )
    ).all()
    for op in stale:
        _expire(session, op)
    session.flush()


def _supersede(session: Session, event_date: dt.date) -> None:
    """A newer preview for a Sunday replaces any earlier one, so two never both commit."""
    older = session.scalars(
        select(McpOperation).where(
            McpOperation.status == "previewed", McpOperation.event_date == event_date
        )
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


def _base_bytes(session: Session) -> bytes:
    base_id = active_scores_import(session)
    if base_id is None:
        raise Refusal("no_base", "no committed scores import to build on")
    return session.scalars(select(Import.file_bytes).where(Import.id == base_id)).one()


def _split_findings(date: dt.date, previews: list[ImportPreview]) -> tuple[list[FindingOut], int]:
    """Only findings about the previewed Sunday are listed; the rest are an old-data count."""
    mine: list[FindingOut] = []
    other = 0
    for preview in previews:
        for finding in preview.findings:
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


def _last_event(session: Session) -> dt.date | None:
    return session.scalar(select(func.max(Event.event_date)))


def _record_preview(
    session: Session,
    kind: str,
    date: dt.date,
    now: dt.datetime,
    ttl: dt.timedelta,
    scores_id: int,
    stations_id: int | None,
    digest: str,
) -> McpOperation:
    _supersede(session, date)
    op = McpOperation(
        kind=kind,
        event_date=date,
        status="previewed",
        created_at=now,
        scores_import_id=scores_id,
        stations_import_id=stations_id,
        result={"input_sha256": digest},
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
    last = _last_event(session)
    if last is not None and date <= last:
        raise Refusal(
            "not_after_last_event",
            f"the latest stored Sunday is {last.isoformat()}; a new week must come after it",
        )
    today = now.astimezone(LOCAL_TZ).date()
    if (today - date).days > MAX_WEEK_AGE_DAYS:
        raise Refusal("too_old", f"{date.isoformat()} is more than {MAX_WEEK_AGE_DAYS} days ago")
    if session.scalar(select(exists().where(Round.event_date == date))):
        raise Refusal("date_has_rounds", f"{date.isoformat()} already has stored rounds")


def _week_preview(
    session: Session, week: WeekInput, now: dt.datetime, ttl: dt.timedelta, staged: list[int]
) -> WeekPreview:
    _check_week_date(session, week.date, now)
    digest = _digest(week)
    same = _existing_preview(session, "week", week.date, digest)
    if same is not None:
        return WeekPreview.model_validate(same.result["preview"])
    base = _base_bytes(session)
    try:
        scores_bytes = build_scores(base, week)
    except BuildError as exc:
        raise Refusal("invalid_input", f"could not build the scores workbook: {exc.code}") from exc
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
        and diff.rows_removed == 0
        and diff.rows_changed == 0
    ):
        raise Refusal("not_append_only", "the week would change or remove stored scores")
    op = _record_preview(
        session, "week", week.date, now, ttl, scores.import_id,
        stations.import_id if stations else None, digest,
    )  # fmt: skip
    mine, other = _split_findings(week.date, [p for p in (scores, stations) if p is not None])
    total = sum(s.score for s in week.shooters)
    n_new = len(diff.new_names)
    preview = WeekPreview(
        date=week.date,
        head_count=len(week.shooters),
        score_sum=total,
        average=round(total / len(week.shooters), 2),
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
    session: Session, week: WeekInput, *, now: dt.datetime, ttl: dt.timedelta | None = None
) -> WeekPreview:
    ttl = ttl or preview_ttl()
    _sweep(session, now, ttl)
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
    last = _last_event(session)
    if last != c.date:
        raise Refusal("not_latest_event", "only the latest stored Sunday can be corrected")
    digest = _digest(c)
    same = _existing_preview(session, "correction", c.date, digest)
    if same is not None:
        return CorrectionPreview.model_validate(same.result["preview"])
    base = _base_bytes(session)
    old = {
        r.name_key: r.score
        for r in load_staged_scores(session, active_scores_import(session))
        if r.event_date == c.date
    }
    try:
        data = build_correction(base, c)
    except BuildError as exc:
        if exc.code == "name_not_on_date":
            raise Refusal(
                "name_not_on_date", "a corrected name is not on that Sunday's scores"
            ) from exc
        raise Refusal("invalid_input", f"could not build the correction: {exc.code}") from exc
    scores = _stage(session, data, f"mcp-correction-{c.date.isoformat()}.xlsx", staged)
    diff = scores.diff
    if not (
        isinstance(diff, ScoresDiff)
        and not diff.events_added
        and not diff.events_removed
        and diff.rows_added == 0
        and diff.rows_removed == 0
        and diff.rows_changed == len(c.rows)
    ):
        raise Refusal(
            "invalid_input",
            f"expected {len(c.rows)} changed scores and nothing else; a score may equal the "
            "stored one",
        )
    op = _record_preview(session, "correction", c.date, now, ttl, scores.import_id, None, digest)
    mine, other = _split_findings(c.date, [scores])
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
    session: Session, c: CorrectionInput, *, now: dt.datetime, ttl: dt.timedelta | None = None
) -> CorrectionPreview:
    ttl = ttl or preview_ttl()
    _sweep(session, now, ttl)
    staged: list[int] = []
    try:
        return _correction_preview(session, c, now, ttl, staged)
    except Refusal as exc:
        _refuse(session, "correction", c.date, now, exc, staged)
        raise
