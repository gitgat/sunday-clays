"""Postgres-backed job queue: coalescing enqueue, SKIP LOCKED claim, retry with backoff (C6)."""

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sunday_clays.domain.errors import NotFoundError
from sunday_clays.models import Job

MAX_ATTEMPTS = 3
FIRST_RETRY_DELAY = timedelta(minutes=1)
LATER_RETRY_DELAY = timedelta(minutes=5)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    attempts: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def _queued_id(session: Session, dedupe_key: str) -> int | None:
    return session.scalar(
        select(Job.id).where(Job.dedupe_key == dedupe_key, Job.status == "queued")
    )


def enqueue(
    session: Session,
    kind: str,
    payload: dict[str, Any] | None = None,
    *,
    run_after: datetime | None = None,
    dedupe_key: str | None = None,
) -> int:
    """Queue a job, or return the id of the queued job with the same dedupe_key.

    Never raises on a duplicate; raises RuntimeError only if a queued twin is claimed between the
    INSERT and the lookup twice in a row.
    """
    values: dict[str, Any] = {"kind": kind, "payload": payload or {}, "dedupe_key": dedupe_key}
    if run_after is not None:
        values["run_after"] = run_after
    if dedupe_key is None:
        return session.execute(insert(Job).values(**values).returning(Job.id)).scalar_one()
    stmt = (
        insert(Job)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=[Job.dedupe_key], index_where=text("status = 'queued'")
        )
        .returning(Job.id)
    )
    for _ in range(2):  # a queued twin can be claimed between our INSERT and SELECT: retry once
        new_id = session.scalar(stmt)
        if new_id is not None:
            return new_id
        existing = _queued_id(session, dedupe_key)
        if existing is not None:
            return existing
    raise RuntimeError(f"could not enqueue {kind!r} with dedupe_key {dedupe_key!r}")


def claim_next(session: Session) -> Job | None:
    """Claim the oldest runnable queued job in its own committed transaction."""
    job = session.scalars(
        select(Job)
        .where(Job.status == "queued", Job.run_after <= func.now())
        .order_by(Job.run_after, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if job is not None:
        job.status = "running"
        job.started_at = func.now()
        job.attempts = Job.attempts + 1
    session.commit()
    return job


def complete(session: Session, job_id: int) -> None:
    session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="done", finished_at=func.now(), error=None)
    )


def fail_permanently(session: Session, job_id: int, error: str) -> None:
    session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="failed", finished_at=func.now(), error=error)
    )


def fail(session: Session, job_id: int, error: str) -> None:
    """Requeue with backoff (1 min, then 5 min) while attempts < 3, else mark failed.

    A queued job with the same dedupe_key supersedes this one instead of it being requeued (C6).
    """
    # populate_existing: a copy already in the identity map may predate the lock (stale attempts)
    job = session.get(Job, job_id, with_for_update=True, populate_existing=True)
    if job is None:
        raise NotFoundError("job_not_found", f"Job {job_id} does not exist")
    if job.attempts >= MAX_ATTEMPTS:
        fail_permanently(session, job_id, error)
        return
    delay = FIRST_RETRY_DELAY if job.attempts <= 1 else LATER_RETRY_DELAY
    requeue = (
        update(Job)
        .where(Job.id == job_id)
        .values(status="queued", error=error, run_after=func.now() + delay)
    )
    key = job.dedupe_key
    if key is None:  # no dedupe key: nothing can supersede this job
        session.execute(requeue)
        return
    duplicate = _queued_id(session, key)
    if duplicate is None:
        # An API request can commit a same-key enqueue between that check and this requeue; the
        # requeue then trips uq_jobs_dedupe_key_queued and the new job supersedes this one.
        try:
            with session.begin_nested():
                session.execute(requeue)
            return
        except IntegrityError:
            duplicate = _queued_id(session, key)
    fail_permanently(session, job_id, f"superseded by job {duplicate}")


def recover_orphans(session: Session) -> list[int]:
    """Send every job left 'running' by a dead worker through fail(); returns their ids."""
    orphan_ids = list(
        session.scalars(select(Job.id).where(Job.status == "running").order_by(Job.id))
    )
    for job_id in orphan_ids:
        fail(session, job_id, "worker restarted")
    return orphan_ids


def get_job(session: Session, job_id: int) -> JobOut:
    job = session.get(Job, job_id)
    if job is None:
        raise NotFoundError("job_not_found", f"Job {job_id} does not exist")
    return JobOut.model_validate(job)
