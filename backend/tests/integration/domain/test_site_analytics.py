"""Admin analytics reads (Plan 16 Task 2): rollups and raw rows merged, local days, zero-filled."""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.templates import plain
from sunday_clays.domain.site_analytics import (
    BumpDay,
    MeStates,
    PageKindViews,
    Span,
    TopInsight,
    VisitorDay,
    VisitorWeek,
    WeekMeStates,
    bumps,
    monday,
    page_kinds,
    uptake,
    visitors,
)
from sunday_clays.models import FistBump, Insight, PageKindRollup, PageView, PageViewRollup

TZ = "America/Los_Angeles"
PT = ZoneInfo(TZ)
A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
C = uuid.UUID("00000000-0000-4000-8000-00000000000c")
WEEK = Span(date(2026, 9, 14), date(2026, 9, 20))  # Monday to Sunday
GONE = "fedcba9876543210fedc"


def _view(session: Session, device: uuid.UUID, kind: str, state: str, at: datetime) -> None:
    session.execute(
        insert(PageView).values(device_id=device, page_kind=kind, me_state=state, at=at)
    )


def _seed(session: Session) -> None:
    session.execute(
        insert(PageViewRollup),
        [
            {
                "period": "day",
                "start_day": date(2026, 6, 23),
                "devices": 2,
                "me_picked": 1,
                "me_skipped": 0,
                "me_none": 1,
            },
            {
                "period": "day",
                "start_day": date(2026, 6, 25),
                "devices": 1,
                "me_picked": 0,
                "me_skipped": 1,
                "me_none": 0,
            },
            {
                "period": "week",
                "start_day": date(2026, 6, 22),
                "devices": 3,
                "me_picked": 0,
                "me_skipped": 1,
                "me_none": 2,
            },
        ],
    )
    session.execute(
        insert(PageKindRollup),
        [
            {"day": date(2026, 6, 23), "page_kind": "home", "views": 2},
            {"day": date(2026, 6, 23), "page_kind": "leaderboards", "views": 1},
        ],
    )
    # A's later answer goes in first: "last by id" would call A "none" on Sep 14.
    _view(session, A, "records", "picked", datetime(2026, 9, 14, 15, 0, tzinfo=PT))
    _view(session, A, "home", "none", datetime(2026, 9, 14, 10, 0, tzinfo=PT))
    _view(session, B, "home", "skipped", datetime(2026, 9, 14, 11, 0, tzinfo=PT))
    _view(session, A, "home", "picked", datetime(2026, 9, 16, 9, 0, tzinfo=PT))
    # Sunday 23:30 local is Monday in UTC: it stays on Sunday Sep 20.
    _view(session, C, "leaderboards", "none", datetime(2026, 9, 20, 23, 30, tzinfo=PT))


def test_monday_and_span() -> None:
    assert monday(date(2026, 9, 20)) == date(2026, 9, 14)
    assert monday(date(2026, 9, 14)) == date(2026, 9, 14)
    assert WEEK.has(date(2026, 9, 14))
    assert WEEK.has(date(2026, 9, 20))
    assert not WEEK.has(date(2026, 9, 13))
    assert not WEEK.has(date(2026, 9, 21))
    assert Span(None, date(2026, 9, 20)).has(date(2001, 1, 1))


def test_visitors_merge_rollups_and_raw_and_zero_fill(session: Session) -> None:
    _seed(session)
    result = visitors(session, TZ, WEEK)
    assert result.days == [
        VisitorDay(date(2026, 9, 14), 2),
        VisitorDay(date(2026, 9, 15), 0),
        VisitorDay(date(2026, 9, 16), 1),
        VisitorDay(date(2026, 9, 17), 0),
        VisitorDay(date(2026, 9, 18), 0),
        VisitorDay(date(2026, 9, 19), 0),
        VisitorDay(date(2026, 9, 20), 1),
    ]
    assert result.weeks == [VisitorWeek(date(2026, 9, 14), 3)]  # A, B and C once each
    # Most devices first, then the later day.
    assert result.busiest == [
        VisitorDay(date(2026, 9, 14), 2),
        VisitorDay(date(2026, 9, 20), 1),
        VisitorDay(date(2026, 9, 16), 1),
    ]


def test_all_time_visitors_start_at_the_first_rolled_day(session: Session) -> None:
    _seed(session)
    result = visitors(session, TZ, Span(None, date(2026, 9, 20)))
    assert result.days[0] == VisitorDay(date(2026, 6, 23), 2)
    assert len(result.days) == 90  # Jun 23 to Sep 20, zero-filled
    assert result.weeks[0] == VisitorWeek(date(2026, 6, 22), 3)
    assert result.weeks[-1] == VisitorWeek(date(2026, 9, 14), 3)
    assert len(result.weeks) == 13


def test_no_data_and_no_since_is_empty_not_an_error(session: Session) -> None:
    result = visitors(session, TZ, Span(None, date(2026, 9, 20)))
    assert (result.days, result.weeks, result.busiest) == ([], [], [])


def test_busiest_keeps_the_top_five_days_with_visits(session: Session) -> None:
    for day in range(1, 8):
        for n in range(day):
            _view(
                session,
                uuid.UUID(int=day * 100 + n),
                "home",
                "none",
                datetime(2026, 9, day, 12, 0, tzinfo=PT),
            )
    busiest = visitors(session, TZ, Span(date(2026, 9, 1), date(2026, 9, 10))).busiest
    assert [d.devices for d in busiest] == [7, 6, 5, 4, 3]


def test_page_kinds_merge_rollups_and_raw_in_the_span(session: Session) -> None:
    _seed(session)
    assert page_kinds(session, TZ, WEEK) == [
        PageKindViews("home", 3),
        PageKindViews("leaderboards", 1),
        PageKindViews("records", 1),
    ]
    assert page_kinds(session, TZ, Span(None, date(2026, 9, 20))) == [
        PageKindViews("home", 5),
        PageKindViews("leaderboards", 2),
        PageKindViews("records", 1),
    ]


def test_uptake_uses_each_devices_last_answer(session: Session) -> None:
    _seed(session)
    result = uptake(session, TZ, WEEK)
    assert result.weeks == [WeekMeStates(date(2026, 9, 14), 1, 1, 1)]
    assert result.latest == MeStates(picked=1, skipped=1, none=1)
    assert result.latest_since == date(2026, 9, 14)


def test_uptake_weeks_include_rollups_and_detail_starts_at_the_first_raw_day(
    session: Session,
) -> None:
    _seed(session)
    result = uptake(session, TZ, Span(date(2026, 6, 1), date(2026, 9, 20)))
    assert result.weeks[0] == WeekMeStates(date(2026, 6, 1), 0, 0, 0)
    assert WeekMeStates(date(2026, 6, 22), 0, 1, 2) in result.weeks
    assert result.latest_since == date(2026, 9, 14)
    assert result.latest == MeStates(picked=1, skipped=1, none=1)


def test_uptake_without_raw_rows_has_no_detail(session: Session) -> None:
    result = uptake(session, TZ, WEEK)
    assert result.latest == MeStates(0, 0, 0)
    assert result.latest_since is None
    assert result.weeks == [WeekMeStates(date(2026, 9, 14), 0, 0, 0)]


def test_uptake_with_raw_rows_only_after_the_span_has_no_detail(session: Session) -> None:
    _view(session, A, "home", "picked", datetime(2026, 9, 25, 9, 0, tzinfo=PT))
    assert uptake(session, TZ, WEEK).latest_since is None


def test_bumps_per_day_top_insights_and_devices(fx_session: Session) -> None:
    key, headline = fx_session.execute(select(Insight.key, Insight.headline).limit(1)).one()

    def bump(insight: str, device: uuid.UUID, at: datetime) -> None:
        fx_session.execute(
            insert(FistBump).values(insight_key=insight, device_id=device, created_at=at)
        )

    bump(key, A, datetime(2026, 9, 14, 12, 0, tzinfo=PT))
    bump(key, B, datetime(2026, 9, 16, 12, 0, tzinfo=PT))
    bump(GONE, A, datetime(2026, 9, 16, 13, 0, tzinfo=PT))
    bump(GONE, C, datetime(2026, 8, 1, 12, 0, tzinfo=PT))  # outside the week
    result = bumps(fx_session, TZ, WEEK)
    assert result.days[:3] == [
        BumpDay(date(2026, 9, 14), 1),
        BumpDay(date(2026, 9, 15), 0),
        BumpDay(date(2026, 9, 16), 2),
    ]
    assert len(result.days) == 7
    assert result.top == [TopInsight(key, plain(headline), 2), TopInsight(GONE, None, 1)]
    assert result.devices == 2
    assert result.devices_all_time == 3
