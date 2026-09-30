"""Admin import workflow (C8): upload → preview → commit / discard / rollback, and job status."""

import logging
from pathlib import PurePosixPath
from typing import Annotated, ClassVar, Final

from fastapi import APIRouter, Depends, File, Path, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sunday_clays.api.routes._admin import JobRefOut
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.imports import (
    commit_import,
    discard_import,
    get_import_preview,
    rollback_import,
    stage_import,
)
from sunday_clays.domain.imports import list_imports as list_import_summaries
from sunday_clays.domain.schemas import ImportPreview, ImportSummary
from sunday_clays.ingest.types import ParseError
from sunday_clays.jobs.queue import JobOut, enqueue, get_job

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES: Final = (".xlsx", ".xlsm")
MAX_FILENAME_CHARS: Final = 255

ActorDep = Annotated[Actor, Depends(admin_actor)]
ImportId = Annotated[int, Path(alias="id")]
JobId = Annotated[int, Path(alias="id")]


class PayloadTooLargeError(DomainError):
    status_code: ClassVar[int] = 413


class CommitIn(BaseModel):
    confirm_removals: bool = False


def clean_filename(raw: str | None) -> str:
    """Printable basename, at most the last 255 characters; "" when nothing printable is left.

    Every non-printable character (``str.isprintable()`` is False: Cc/Cf/Zl/Zp and non-ASCII
    spaces, e.g. NUL, ESC, newline, U+202E) is dropped before the basename is taken and stripped,
    so none reaches the DB, the audit log or the imports UI. The basename is the last `/`- or
    `\\`-separated segment. "" fails the caller's suffix check (400 ``unsupported_file_type``).
    """
    printable = "".join(ch for ch in raw or "" if ch.isprintable())
    name = PurePosixPath(printable.replace("\\", "/")).name.strip()
    return name[-MAX_FILENAME_CHARS:]


def _stage(session: Session, data: bytes, filename: str, actor: Actor) -> ImportPreview:
    preview = stage_import(session, data, filename)
    record_audit(
        session,
        actor.ip,
        actor.role,
        "imports.stage",
        {
            "import_id": preview.import_id,
            "kind": preview.kind,
            "filename": filename,
            "duplicate_of": preview.duplicate_of,
        },
    )
    return preview


@router.post("/imports")
async def upload_import(
    file: Annotated[UploadFile, File()],
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    actor: ActorDep,
) -> ImportPreview:
    filename = clean_filename(file.filename)
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        raise DomainError("unsupported_file_type", "Upload the Excel workbook (.xlsx or .xlsm)")
    limit = settings.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLargeError("payload_too_large", f"The file is larger than {limit} bytes")
    try:
        return await run_in_threadpool(_stage, session, data, filename, actor)
    except ParseError as exc:
        # parse_upload chains the original exception but never logs it;
        # the client gets str(exc) only.
        logger.warning("Upload %r could not be parsed", filename, exc_info=exc)
        raise DomainError("unreadable_file", str(exc)) from exc


@router.get("/imports")
def list_imports(session: SessionDep) -> list[ImportSummary]:
    """Every import, newest first (Plan 03 T6)."""
    return list_import_summaries(session)


@router.get("/imports/{id}")
def get_import(import_id: ImportId, session: SessionDep) -> ImportPreview:
    """The preview stored at staging time (Plan 03 T3; Decision D15); 404 ``import_not_found``."""
    return get_import_preview(session, import_id)


@router.post("/imports/{id}/commit")
def commit(
    import_id: ImportId, session: SessionDep, actor: ActorDep, body: CommitIn | None = None
) -> JobRefOut:
    confirm = body.confirm_removals if body is not None else False
    commit_import(session, import_id, confirm_removals=confirm)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session,
        actor.ip,
        actor.role,
        "imports.commit",
        {"import_id": import_id, "confirm_removals": confirm, "job_id": job_id},
    )
    return JobRefOut(job_id=job_id)


@router.post("/imports/{id}/discard", status_code=204)
def discard(import_id: ImportId, session: SessionDep, actor: ActorDep) -> None:
    discard_import(session, import_id)
    record_audit(session, actor.ip, actor.role, "imports.discard", {"import_id": import_id})


@router.post("/imports/{id}/rollback")
def rollback(import_id: ImportId, session: SessionDep, actor: ActorDep) -> JobRefOut:
    rollback_import(session, import_id)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session,
        actor.ip,
        actor.role,
        "imports.rollback",
        {"import_id": import_id, "job_id": job_id},
    )
    return JobRefOut(job_id=job_id)


@router.get("/jobs/{id}")
def job_status(job_id: JobId, session: SessionDep) -> JobOut:
    return get_job(session, job_id)
