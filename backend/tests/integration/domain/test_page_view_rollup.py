"""Page-view rollup (Plan 16 Task 1): raw visits older than about 90 days become daily and
weekly totals in whole weeks of the club's local time, and the raw rows go."""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.domain.page_views import RollupReport, rollup_cutoff, rollup_page_views
from sunday_clays.models import PageKindRollup, PageView, PageViewRollup

TZ = "America/Los_Angeles"
PT = ZoneInfo(TZ)
TODAY = date(2026, 10, 1)  # 90 days back is Fri 2026-07-03, so the cutoff is Mon 2026-06-29
A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
C = uuid.UUID("00000000-0000-4000-8000-00000000000c")
D = uuid.UUID("00000000-0000-4000-8000-00000000000d")


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
