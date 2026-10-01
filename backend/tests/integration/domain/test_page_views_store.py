"""Page-view store (Plan 16 Task 1): one count per device and page kind every 30 minutes."""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from sunday_clays.domain.page_views import ME_STATES, PAGE_KINDS, record_page_view
from sunday_clays.domain.rebuild import LIVE_TABLES
from sunday_clays.models import PageView

A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
NOW = datetime(2026, 10, 1, 18, 0, tzinfo=UTC)


def _rows(session: Session) -> list[tuple[uuid.UUID, str, str, datetime]]:
    rows = session.execute(
        select(PageView.device_id, PageView.page_kind, PageView.me_state, PageView.at).order_by(
            PageView.id
        )
    )
    return [(d, k, s, at) for d, k, s, at in rows]


def test_the_kinds_and_states_are_exactly_the_approved_lists() -> None:
    assert PAGE_KINDS == (
        "home",
        "profile",
        "event",
        "leaderboards",
        "records",
        "club",
        "stations",
        "weather",
        "yir",
        "explorer",
        "achievements",
        "race",
        "compare",
        "events-list",
        "admin",
        "other",
    )
    assert ME_STATES == ("picked", "skipped", "none")


def test_a_device_counts_once_per_page_kind_every_30_minutes(session: Session) -> None:
    assert record_page_view(session, A, "home", "none", NOW) is True
    almost = NOW + timedelta(minutes=29, seconds=59)
    assert record_page_view(session, A, "home", "picked", almost) is False
    later = NOW + timedelta(minutes=30)
    assert record_page_view(session, A, "home", "picked", later) is True
    assert _rows(session) == [(A, "home", "none", NOW), (A, "home", "picked", later)]


def test_other_kinds_and_other_devices_count_on_their_own(session: Session) -> None:
    record_page_view(session, A, "home", "none", NOW)
    soon = NOW + timedelta(minutes=1)
    assert record_page_view(session, A, "leaderboards", "none", soon) is True
    assert record_page_view(session, B, "home", "skipped", soon) is True
    assert [(d, k) for d, k, _, _ in _rows(session)] == [
        (A, "home"),
        (A, "leaderboards"),
        (B, "home"),
    ]


def _someone_waits_on_an_advisory_lock(engine: Engine) -> bool:
    with engine.connect() as conn:
        waiting = conn.scalar(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted")
        )
    return bool(waiting)


def test_two_identical_beacons_at_once_count_once(committed_engine: Engine) -> None:
    """Kills "no lock": the second session must block until the first commits, then see it."""
    with Session(committed_engine) as first, Session(committed_engine) as second:
        assert record_page_view(first, A, "home", "none", NOW) is True  # holds the lock

        def racer() -> bool:
            # A lock that is never released must fail the test, not hang it.
            second.execute(text("SET LOCAL lock_timeout = '5s'"))
            counted = record_page_view(second, A, "home", "none", NOW + timedelta(seconds=1))
            second.commit()
            return counted

        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(racer)
            deadline = time.monotonic() + 10
            while not _someone_waits_on_an_advisory_lock(committed_engine):
                assert time.monotonic() < deadline, "the second beacon never waited for the first"
                time.sleep(0.01)
            first.commit()
            assert waiting.result(timeout=10) is False
    with Session(committed_engine) as check:
        assert check.scalar(select(func.count()).select_from(PageView)) == 1


def test_page_view_tables_are_not_live_tables() -> None:
    for table in ("page_views", "page_view_attempts", "page_view_rollups", "page_kind_rollups"):
        assert table not in LIVE_TABLES


def test_a_view_stores_only_a_device_a_kind_a_state_and_a_time() -> None:
    assert set(PageView.__table__.columns.keys()) == {
        "id",
        "device_id",
        "page_kind",
        "me_state",
        "at",
    }
