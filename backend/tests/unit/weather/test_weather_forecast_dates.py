"""Which Sunday the forecast job targets."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from sunday_clays.weather.forecast import next_event_sunday

LA = ZoneInfo("America/Los_Angeles")


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        pytest.param(datetime(2026, 9, 26, 9, 0, tzinfo=LA), date(2026, 9, 27), id="sat"),
        pytest.param(
            datetime(2026, 9, 27, 11, 59, tzinfo=LA),
            date(2026, 9, 27),
            id="sun-event-on",
        ),
        pytest.param(
            datetime(2026, 9, 27, 12, 0, tzinfo=LA),
            date(2026, 10, 4),
            id="sun-event-over",
        ),
        pytest.param(datetime(2026, 9, 28, 6, 0, tzinfo=LA), date(2026, 10, 4), id="mon"),
        pytest.param(datetime(2026, 10, 3, 23, 59, tzinfo=LA), date(2026, 10, 4), id="sat-23:59"),
        pytest.param(datetime(2026, 10, 4, 0, 0, tzinfo=LA), date(2026, 10, 4), id="sun-00:00"),
        # 2026-11-01: clocks fall back at 02:00 PDT, so 01:00-01:59 happens twice
        pytest.param(
            datetime(2026, 11, 1, 1, 30, fold=1, tzinfo=LA),
            date(2026, 11, 1),
            id="fall-back-repeated-hour",
        ),
        pytest.param(
            datetime(2026, 11, 1, 11, 59, tzinfo=LA), date(2026, 11, 1), id="fall-back-11:59"
        ),
        pytest.param(
            datetime(2026, 11, 1, 12, 0, tzinfo=LA), date(2026, 11, 8), id="fall-back-12:00"
        ),
        # 2027-03-14: clocks spring forward at 02:00 PST, so 02:00-02:59 never happens
        pytest.param(
            datetime(2027, 3, 14, 3, 0, tzinfo=LA), date(2027, 3, 14), id="spring-fwd-03:00"
        ),
        pytest.param(
            datetime(2027, 3, 14, 11, 59, tzinfo=LA), date(2027, 3, 14), id="spring-fwd-11:59"
        ),
        pytest.param(
            datetime(2027, 3, 14, 12, 0, tzinfo=LA), date(2027, 3, 21), id="spring-fwd-12:00"
        ),
    ],
)
def test_next_event_sunday(now: datetime, expected: date) -> None:
    assert next_event_sunday(now) == expected
