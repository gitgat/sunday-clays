from datetime import timedelta

import pytest
from sqlalchemy import Engine, func, select, text, update
from sqlalchemy.orm import Session

from sunday_clays.db import SessionFactory
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.jobs import queue
from sunday_clays.jobs.queue import (
    claim_next,
    complete,
    enqueue,
    fail,
    get_job,
    recover_orphans,
)
from sunday_clays.models import Job


def _job(session: Session, job_id: int) -> Job:
    session.expire_all()
    job = session.get(Job, job_id)
    assert job is not None
    return job


def _set(session: Session, job_id: int, **values: object) -> None:
    session.execute(update(Job).where(Job.id == job_id).values(**values))


def test_same_dedupe_key_coalesces_to_one_queued_job(session: Session) -> None:
    first = enqueue(session, "rebuild", dedupe_key="rebuild")
    second = enqueue(session, "rebuild", {"ignored": True}, dedupe_key="rebuild")
    assert second == first
    assert session.scalar(select(func.count()).select_from(Job)) == 1


def test_jobs_without_a_key_are_never_coalesced(session: Session) -> None:
    assert enqueue(session, "noop") != enqueue(session, "noop")


def test_enqueue_while_same_key_is_running_creates_a_new_job(session: Session) -> None:
    running = enqueue(session, "rebuild", dedupe_key="rebuild")
    _set(session, running, status="running")
    queued = enqueue(session, "rebuild", dedupe_key="rebuild")
    assert queued != running
    assert _job(session, queued).status == "queued"


def test_enqueue_conflict_leaves_the_outer_transaction_usable(session: Session) -> None:
    enqueue(session, "rebuild", dedupe_key="rebuild")
    enqueue(session, "rebuild", dedupe_key="rebuild")
    assert session.execute(text("SELECT 1")).scalar_one() == 1


def test_enqueue_retries_once_when_the_queued_twin_is_claimed_meanwhile(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    twin = enqueue(session, "rebuild", dedupe_key="rebuild")
    real_lookup = queue._queued_id

    def claimed_in_between(s: Session, key: str) -> int | None:
        _set(s, twin, status="running")  # a worker claims the twin after our INSERT conflicted
        monkeypatch.setattr(queue, "_queued_id", real_lookup)
        return real_lookup(s, key)

    monkeypatch.setattr(queue, "_queued_id", claimed_in_between)
    new_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    assert new_id != twin
    assert _job(session, new_id).status == "queued"


def test_enqueue_gives_up_after_one_retry(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    enqueue(session, "rebuild", dedupe_key="rebuild")
    monkeypatch.setattr(queue, "_queued_id", lambda s, key: None)
    with pytest.raises(RuntimeError, match="could not enqueue"):
        enqueue(session, "rebuild", dedupe_key="rebuild")


def test_claim_next_takes_the_oldest_runnable_job(session: Session) -> None:
    later = enqueue(session, "b")
    earlier = enqueue(session, "a")
    _set(session, earlier, run_after=func.now() - timedelta(minutes=1))
    enqueue(session, "future", run_after=session.scalar(select(func.now() + timedelta(hours=1))))
    job = claim_next(session)
    assert job is not None
    assert job.id == earlier
    claimed = _job(session, earlier)
    assert (claimed.status, claimed.attempts) == ("running", 1)
    assert claimed.started_at is not None
    job = claim_next(session)
    assert job is not None
    assert job.id == later
    assert claim_next(session) is None  # only the future job is left


def test_two_concurrent_claims_never_share_a_job(committed_engine: Engine) -> None:
    with SessionFactory() as setup:
        first = enqueue(setup, "a")
        second = enqueue(setup, "b")
        setup.commit()
    with committed_engine.connect() as locker:
        locker.begin()
        locker.execute(text("SELECT id FROM jobs WHERE id = :id FOR UPDATE"), {"id": first})
        with SessionFactory() as other:
            other.execute(text("SET LOCAL lock_timeout = '2s'"))
            job = claim_next(other)  # skips the locked row instead of waiting on it
            assert job is not None
            assert job.id == second
        locker.rollback()


def test_complete_marks_done(session: Session) -> None:
    job_id = enqueue(session, "a")
    claim_next(session)
    complete(session, job_id)
    job = _job(session, job_id)
    assert (job.status, job.error) == ("done", None)
    assert job.finished_at is not None


def test_fail_requeues_with_backoff_then_gives_up(session: Session) -> None:
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    for attempts, minutes in ((1, 1), (2, 5)):
        _set(session, job_id, status="running", attempts=attempts)
        fail(session, job_id, "boom")
        job = _job(session, job_id)
        delay = session.scalar(select(Job.run_after - func.now()).where(Job.id == job_id))
        assert (job.status, job.error) == ("queued", "boom")
        assert delay == timedelta(minutes=minutes)
    _set(session, job_id, status="running", attempts=3)
    fail(session, job_id, "boom")
    job = _job(session, job_id)
    assert (job.status, job.error) == ("failed", "boom")
    assert job.finished_at is not None


def test_fail_reads_the_current_row_not_a_stale_cached_copy(session: Session) -> None:
    job_id = enqueue(session, "a")
    cached = session.get(Job, job_id)  # held, so it stays in the (weak) identity map
    assert cached is not None
    assert cached.attempts == 0
    session.execute(
        text("UPDATE jobs SET status = 'running', attempts = 3 WHERE id = :id"), {"id": job_id}
    )
    fail(session, job_id, "boom")  # must see attempts=3 and give up, not requeue
    job = _job(session, job_id)
    assert job is cached
    assert (job.status, job.error) == ("failed", "boom")


def test_fail_with_a_queued_duplicate_marks_the_job_superseded(session: Session) -> None:
    running = enqueue(session, "rebuild", dedupe_key="rebuild")
    _set(session, running, status="running", attempts=1)
    newer = enqueue(session, "rebuild", dedupe_key="rebuild")
    fail(session, running, "boom")
    job = _job(session, running)
    assert (job.status, job.error) == ("failed", f"superseded by job {newer}")
    assert _job(session, newer).status == "queued"


def test_fail_supersedes_when_a_twin_appears_after_the_check(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = enqueue(session, "rebuild", dedupe_key="rebuild")
    _set(session, running, status="running", attempts=1)
    newer = enqueue(session, "rebuild", dedupe_key="rebuild")
    real_lookup = queue._queued_id

    def twin_not_yet_committed(s: Session, key: str) -> int | None:
        monkeypatch.setattr(queue, "_queued_id", real_lookup)  # later lookups see the twin
        return None  # an API request commits its same-key enqueue just after this check

    monkeypatch.setattr(queue, "_queued_id", twin_not_yet_committed)
    fail(session, running, "boom")  # the requeue trips uq_jobs_dedupe_key_queued; no raise
    job = _job(session, running)
    assert (job.status, job.error) == ("failed", f"superseded by job {newer}")
    assert _job(session, newer).status == "queued"
    assert session.execute(text("SELECT 1")).scalar_one() == 1  # the transaction is usable


def test_recover_orphans_requeues_or_fails_running_jobs(session: Session) -> None:
    retry = enqueue(session, "a")
    exhausted = enqueue(session, "b")
    untouched = enqueue(session, "c")
    _set(session, retry, status="running", attempts=1)
    _set(session, exhausted, status="running", attempts=3)
    assert recover_orphans(session) == [retry, exhausted]
    assert (_job(session, retry).status, _job(session, retry).error) == (
        "queued",
        "worker restarted",
    )
    assert (_job(session, exhausted).status, _job(session, exhausted).error) == (
        "failed",
        "worker restarted",
    )
    assert _job(session, untouched).status == "queued"


def test_get_job_and_unknown_ids(session: Session) -> None:
    job_id = enqueue(session, "rebuild", {"x": 1}, dedupe_key="rebuild")
    out = get_job(session, job_id)
    assert (out.id, out.kind, out.status, out.attempts, out.error) == (
        job_id,
        "rebuild",
        "queued",
        0,
        None,
    )
    for call in (lambda: get_job(session, 999_999), lambda: fail(session, 999_999, "x")):
        with pytest.raises(NotFoundError) as excinfo:
            call()
        assert excinfo.value.code == "job_not_found"
