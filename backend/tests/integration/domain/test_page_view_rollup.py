"""Page-view rollup (Plan 16 Task 1): raw visits older than about 90 days become daily and
weekly totals in whole weeks of the club's local time, and the raw rows go."""

import random
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, Engine, delete, func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.domain.page_views import RollupReport, rollup_cutoff, rollup_page_views
from sunday_clays.domain.site_analytics import Span, page_kinds, uptake, visitors
from sunday_clays.models import PageKindRollup, PageView, PageViewRollup

TZ = "America/Los_Angeles"
PT = ZoneInfo(TZ)
TODAY = date(2026, 10, 1)  # 90 days back is Fri 2026-07-03, so the cutoff is Mon 2026-06-29
A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
C = uuid.UUID("00000000-0000-4000-8000-00000000000c")
D = uuid.UUID("00000000-0000-4000-8000-00000000000d")
KINDS = ("home", "leaderboards", "records", "profile")


def _view(session: Session, device: uuid.UUID, kind: str, state: str, at: datetime) -> None:
    session.execute(
        insert(PageView).values(device_id=device, page_kind=kind, me_state=state, at=at)
    )


def _seed(session: Session) -> None:
    # The later visit goes in first: a rollup that took the last *id* instead of the last *time*
    # would call A "none" on Jun 23.
    _view(session, A, "leaderboards", "picked", datetime(2026, 6, 23, 12, 0, tzinfo=PT))
    _view(session, A, "home", "none", datetime(2026, 6, 23, 10, 0, tzinfo=PT))
    _view(session, A, "home", "skipped", datetime(2026, 6, 25, 9, 0, tzinfo=PT))
    _view(session, B, "home", "none", datetime(2026, 6, 23, 11, 0, tzinfo=PT))
    # Sunday 23:30 local is Monday 06:30 UTC: still Sunday, still the week of Jun 22.
    _view(session, D, "home", "none", datetime(2026, 6, 28, 23, 30, tzinfo=PT))
    # From local midnight of the cutoff on, rows stay raw.
    _view(session, D, "records", "picked", datetime(2026, 6, 29, 0, 30, tzinfo=PT))
    _view(session, C, "home", "picked", datetime(2026, 6, 30, 9, 0, tzinfo=PT))


def _rollups(session: Session) -> list[tuple[str, date, int, int, int, int]]:
    rows = session.execute(
        select(
            PageViewRollup.period,
            PageViewRollup.start_day,
            PageViewRollup.devices,
            PageViewRollup.me_picked,
            PageViewRollup.me_skipped,
            PageViewRollup.me_none,
        )
    )
    return sorted((p, s, n, a, b, c) for p, s, n, a, b, c in rows)


def _kinds(session: Session) -> list[tuple[date, str, int]]:
    rows = session.execute(
        select(PageKindRollup.day, PageKindRollup.page_kind, PageKindRollup.views)
    )
    return sorted((d, k, v) for d, k, v in rows)


def _raw(session: Session) -> list[tuple[uuid.UUID, str]]:
    return sorted(
        (d, k) for d, k in session.execute(select(PageView.device_id, PageView.page_kind))
    )


def test_the_cutoff_is_the_monday_on_or_before_90_days_back() -> None:
    assert rollup_cutoff(TODAY) == date(2026, 6, 29)
    assert rollup_cutoff(date(2026, 9, 27)) == date(2026, 6, 29)  # 90 back is that Monday
    assert rollup_cutoff(date(2026, 10, 5)) == date(2026, 7, 6)  # 90 back is Tue Jul 7


def test_rollup_counts_old_visits_by_local_day_and_week(session: Session) -> None:
    _seed(session)
    assert rollup_page_views(session, TODAY, TZ) == RollupReport(date(2026, 6, 29), 5)
    # (period, start, devices, picked, skipped, none): a week counts A once, not twice.
    assert _rollups(session) == [
        ("day", date(2026, 6, 23), 2, 1, 0, 1),
        ("day", date(2026, 6, 25), 1, 0, 1, 0),
        ("day", date(2026, 6, 28), 1, 0, 0, 1),
        ("week", date(2026, 6, 22), 3, 0, 1, 2),
    ]
    assert _kinds(session) == [
        (date(2026, 6, 23), "home", 2),
        (date(2026, 6, 23), "leaderboards", 1),
        (date(2026, 6, 25), "home", 1),
        (date(2026, 6, 28), "home", 1),
    ]
    assert _raw(session) == sorted([(D, "records"), (C, "home")])


def test_a_second_run_changes_nothing(session: Session) -> None:
    _seed(session)
    rollup_page_views(session, TODAY, TZ)
    before = (_rollups(session), _kinds(session), _raw(session))
    assert rollup_page_views(session, TODAY, TZ) == RollupReport(date(2026, 6, 29), 0)
    assert (_rollups(session), _kinds(session), _raw(session)) == before


def test_nothing_from_the_cutoff_on_is_touched(session: Session) -> None:
    _view(session, C, "home", "picked", datetime(2026, 6, 29, 0, 0, tzinfo=PT))
    assert rollup_page_views(session, TODAY, TZ).rolled == 0
    assert _rollups(session) == []
    assert _kinds(session) == []
    assert _raw(session) == [(C, "home")]


def test_a_concurrent_reader_sees_the_rollup_and_the_deletion_together_or_neither(
    engine: Engine,
) -> None:
    """One transaction: until it commits another connection still sees the raw rows and no
    rollups; after, the rollups and no raw rows. Never raw rows gone with rollups missing."""

    def snapshot(conn: Connection) -> tuple[int, int, int]:
        return (
            conn.scalar(select(func.count()).select_from(PageView)) or 0,
            conn.scalar(select(func.count()).select_from(PageViewRollup)) or 0,
            conn.scalar(select(func.count()).select_from(PageKindRollup)) or 0,
        )

    cleanup = (PageKindRollup, PageViewRollup, PageView)
    try:
        with Session(engine) as seed:
            _seed(seed)
            seed.commit()
        with Session(engine) as writer, engine.connect() as reader:
            before = snapshot(reader)
            assert before[0] == 7
            rollup_page_views(writer, TODAY, TZ)  # not committed yet
            assert snapshot(reader) == before
            reader.rollback()
            writer.commit()
            after = snapshot(reader)
            assert after[0] == 2
            assert after[1] > 0
            assert after[2] > 0
    finally:
        with engine.begin() as conn:
            for table in cleanup:
                conn.execute(delete(table))


def test_reads_are_unchanged_by_the_rollup(session: Session) -> None:
    """The rollup's buckets and the reads' buckets agree: the charts read the same before and
    after, across both DST changes, for any run date (the second and third runs roll more)."""
    rng = random.Random(165)  # noqa: S311 - a seeded fixture, not security
    devices = [uuid.UUID(int=n + 1) for n in range(12)]
    hours = [0, 1, 6, 12, 18, 22, 23]
    first = datetime(2026, 7, 1, tzinfo=PT)
    views = []
    for _ in range(1000):
        day = first + timedelta(days=rng.randrange(0, 273))  # to 2027-03-31, past both DST days
        at = day.replace(hour=rng.choice(hours), minute=rng.randrange(60))
        views.append(
            (rng.choice(devices), rng.choice(KINDS), rng.choice(("none", "picked", "skipped")), at)
        )
    rng.shuffle(views)
    for device, kind, state, at in views:
        _view(session, device, kind, state, at)
    today = date(2027, 4, 1)
    spans = [
        Span(None, today),  # open
        Span(date(2026, 10, 26), date(2026, 11, 15)),  # across the fall DST change
        Span(date(2027, 3, 1), today),  # recent, across the spring one
    ]

    def snapshot() -> list[object]:
        out: list[object] = []
        for span in spans:
            out += [visitors(session, TZ, span), page_kinds(session, TZ, span)]
            # Only the weekly series: ``latest`` is each device's last answer from the raw rows
            # still kept, which the rollup shrinks on purpose.
            out.append(uptake(session, TZ, span).weeks)
        return out

    before = snapshot()
    for run_day in (today, today + timedelta(days=7), today + timedelta(days=14)):
        assert rollup_page_views(session, run_day, TZ).rolled >= 0
        assert snapshot() == before, run_day
    assert session.scalar(select(func.count()).select_from(PageViewRollup)) > 0
