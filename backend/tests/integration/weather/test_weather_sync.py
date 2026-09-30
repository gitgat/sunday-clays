"""weather_sync: which dates are fetched, from which API, what is stored, recompute."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from sqlalchemy import Row, Table, func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.models import Base
from sunday_clays.weather import sync
from sunday_clays.weather.client import HourlyObs, WeatherApiError
from sunday_clays.weather.sync import (
    SyncResult,
    dates_needing_weather,
    sync_weather,
    upsert_hourly,
    weather_sync_handler,
)

LA = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 9, 27, 15, 0, tzinfo=LA)  # a Sunday afternoon
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
RECORDED = Path(__file__).parents[2] / "fixtures" / "open_meteo" / "archive_2026-09-13.json"
ARGON2_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$zAaUsgjT4w79Q1k1Gfv6xA"
    "$8hnJDkRbYWn07p0LLDJamRY8+s/GuMmthqmaBq6Aris"
)


def table(name: str) -> Table:
    return Base.metadata.tables[name]


def add_event(session: Session, event_date: date) -> None:
    session.execute(
        insert(table("events")).values(
            event_date=event_date,
            round_type="sporting",
            round_type_source="none",
            head_count=None,
            n_rounds=0,
            n_shooters=0,
            has_scores=False,
            has_stations=False,
            results_complete=False,
        )
    )


def obs(ts_local: datetime, temp_f: float | None = 60.0) -> HourlyObs:
    return HourlyObs(
        ts_local=ts_local,
        temp_f=temp_f,
        apparent_f=58.0,
        precip_in=0.0,
        rain_in=0.0,
        wind_mph=5.0,
        gust_mph=9.0,
        wind_dir_deg=180.0,
        cloud_pct=50.0,
        humidity_pct=70.0,
        pressure_hpa=1015.0,
        weather_code=3,
    )


def day(event_date: date, temp_f: float | None = 60.0) -> list[HourlyObs]:
    return [obs(datetime.combine(event_date, time(h)), temp_f) for h in range(24)]


def add_hourly(session: Session, ts_local: datetime, source: str, temp_f: float) -> None:
    session.execute(
        insert(table("weather_hourly")).values(
            ts_local=ts_local,
            temp_f=temp_f,
            apparent_f=58.0,
            precip_in=0.0,
            rain_in=0.0,
            wind_mph=5.0,
            gust_mph=9.0,
            wind_dir_deg=180.0,
            cloud_pct=50.0,
            humidity_pct=70.0,
            pressure_hpa=1015.0,
            weather_code=3,
            source=source,
            fetched_at=datetime(2026, 9, 1, tzinfo=LA),
        )
    )


def add_window(session: Session, event_date: date, source: str, temp_f: float = 50.0) -> None:
    for hour in (10, 11, 12):
        add_hourly(session, datetime.combine(event_date, time(hour)), source, temp_f)


def stored(session: Session) -> dict[datetime, tuple[float, str]]:
    hourly = table("weather_hourly")
    rows = session.execute(select(hourly.c.ts_local, hourly.c.temp_f, hourly.c.source))
    return {ts: (temp, source) for ts, temp, source in rows}


def queued(session: Session, kind: str) -> list[Row[Any]]:
    jobs = table("jobs")
    query = select(jobs).where(jobs.c.kind == kind, jobs.c.status == "queued")
    return list(session.execute(query).all())


class FrozenClock(datetime):
    """``datetime`` whose ``now()`` is 2026-09-20 03:00 UTC (2026-09-19 20:00 in Los Angeles)."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:  # type: ignore[override]
        return datetime(2026, 9, 20, 3, 0, tzinfo=UTC).astimezone(tz)


class FakeSource:
    """Stands in for Open-Meteo (external) and records every request the sync makes.

    Like the real API it returns more hours than asked for (neighbouring days)."""

    def __init__(self, hours: list[HourlyObs], fail_on_archive_call: int = 0) -> None:
        self.hours = hours
        self.fail_on_archive_call = fail_on_archive_call
        self.archive_calls: list[tuple[date, date]] = []
        self.forecast_calls: list[tuple[int, int]] = []

    def archive(self, start: date, end: date) -> list[HourlyObs]:
        self.archive_calls.append((start, end))
        if len(self.archive_calls) == self.fail_on_archive_call:
            raise WeatherApiError("Open-Meteo HTTP 503: busy")
        return list(self.hours)

    def forecast(self, *, past_days: int, forecast_days: int) -> list[HourlyObs]:
        self.forecast_calls.append((past_days, forecast_days))
        return list(self.hours)


@pytest.fixture
def weather_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Real Settings from env vars (C2 names), weather enabled, cache cleared."""
    for name in (
        "DATABASE_URL_FILE",
        "SESSION_SECRET_FILE",
        "VIEWER_PASSWORD_HASH_FILE",
        "ADMIN_PASSWORD_HASH_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    monkeypatch.setenv("SESSION_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("VIEWER_PASSWORD_HASH", ARGON2_HASH)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", ARGON2_HASH)
    monkeypatch.setenv("APP_VERSION", "test")
    monkeypatch.setenv("CLUB_LAT", "45.3525")
    monkeypatch.setenv("CLUB_LON", "-122.8082")
    monkeypatch.setenv("TIMEZONE", "America/Los_Angeles")
    monkeypatch.setenv("OPEN_METEO_ARCHIVE_URL", ARCHIVE_URL)
    monkeypatch.setenv("OPEN_METEO_FORECAST_URL", FORECAST_URL)
    monkeypatch.setenv("WEATHER_ENABLED", "true")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_weather_sync_enqueues_recompute_when_new_rows(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    source = FakeSource(day(date(2026, 9, 12)) + day(date(2026, 9, 13)))
    result = sync_weather(session, source, now_local=NOW)
    assert source.archive_calls == [(date(2026, 9, 13), date(2026, 9, 14))]
    assert source.forecast_calls == []
    rows = stored(session)
    assert sorted(rows) == [datetime.combine(date(2026, 9, 13), time(h)) for h in range(24)]
    assert {src for _, src in rows.values()} == {"archive"}
    jobs = queued(session, "recompute")
    assert [job.dedupe_key for job in jobs] == ["recompute"]
    assert result == SyncResult(
        fetched_dates=(date(2026, 9, 13),),
        rows_upserted=24,
        window_rows_upserted=3,
        recompute_job_id=jobs[0].id,
    )


def test_weather_sync_no_recompute_when_nothing_new(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    add_window(session, date(2026, 9, 13), "archive")
    source = FakeSource(day(date(2026, 9, 13)))
    result = sync_weather(session, source, now_local=NOW)
    assert (source.archive_calls, source.forecast_calls) == ([], [])
    assert queued(session, "recompute") == []
    assert result == SyncResult((), 0, 0, None)


def test_archive_requests_are_chunked_by_calendar_year(session: Session) -> None:
    for event_date in (date(2019, 1, 6), date(2019, 12, 29), date(2020, 1, 5)):
        add_event(session, event_date)
    source = FakeSource(day(date(2019, 1, 6)) + day(date(2019, 12, 29)) + day(date(2020, 1, 5)))
    sync_weather(session, source, now_local=NOW)
    assert source.archive_calls == [
        (date(2019, 1, 6), date(2019, 12, 30)),
        (date(2020, 1, 5), date(2020, 1, 6)),
    ]
    assert len(stored(session)) == 72


def test_recent_dates_use_forecast_past_days(session: Session) -> None:
    # on 2026-09-27: 09-20 is 7 days old (archive), 09-21 is 6 days old, 09-27 is today
    for event_date in (date(2026, 9, 20), date(2026, 9, 21), date(2026, 9, 27)):
        add_event(session, event_date)
    hours = day(date(2026, 9, 20)) + day(date(2026, 9, 21)) + day(date(2026, 9, 27))
    source = FakeSource(hours)
    sync_weather(session, source, now_local=NOW)
    assert source.archive_calls == [(date(2026, 9, 20), date(2026, 9, 21))]
    assert source.forecast_calls == [(7, 1)]
    rows = stored(session)
    assert rows[datetime.combine(date(2026, 9, 20), time(10))][1] == "archive"
    assert rows[datetime.combine(date(2026, 9, 21), time(10))][1] == "forecast"
    assert rows[datetime.combine(date(2026, 9, 27), time(10))][1] == "forecast"


def test_event_is_fetched_only_after_its_window_closes(session: Session) -> None:
    add_event(session, date(2026, 9, 27))
    assert dates_needing_weather(session, datetime(2026, 9, 27, 12, 59, tzinfo=LA)) == []
    assert dates_needing_weather(session, datetime(2026, 9, 27, 13, 0, tzinfo=LA)) == [
        date(2026, 9, 27)
    ]


def test_utc_aware_now_is_read_as_club_wall_clock(session: Session) -> None:
    add_event(session, date(2026, 9, 27))
    # 19:59 UTC is 12:59 PDT (window still open); 20:00 UTC is 13:00 PDT
    assert dates_needing_weather(session, datetime(2026, 9, 27, 19, 59, tzinfo=UTC)) == []
    assert dates_needing_weather(session, datetime(2026, 9, 27, 20, 0, tzinfo=UTC)) == [
        date(2026, 9, 27)
    ]


def test_utc_aware_now_keeps_the_six_day_split_local(session: Session) -> None:
    # 2026-09-28 02:00 UTC is 2026-09-27 19:00 PDT: 09-21 is 6 days old (forecast), not 7
    add_event(session, date(2026, 9, 21))
    source = FakeSource(day(date(2026, 9, 21)))
    sync_weather(session, source, now_local=datetime(2026, 9, 28, 2, 0, tzinfo=UTC))
    assert (source.archive_calls, source.forecast_calls) == ([], [(7, 1)])


def test_the_timezone_argument_sets_the_wall_clock(session: Session) -> None:
    add_event(session, date(2026, 9, 27))
    now = datetime(2026, 9, 27, 13, 0, tzinfo=UTC)  # 06:00 PDT
    assert dates_needing_weather(session, now) == []
    assert dates_needing_weather(session, now, timezone="UTC") == [date(2026, 9, 27)]


def test_naive_now_is_rejected(session: Session) -> None:
    naive = datetime.combine(date(2026, 9, 27), time(15))
    with pytest.raises(ValueError, match="timezone-aware"):
        dates_needing_weather(session, naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        sync_weather(session, FakeSource([]), now_local=naive)


def test_forecast_rows_upgraded_to_archive_after_six_days(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    add_window(session, date(2026, 9, 13), "forecast", temp_f=50.0)
    add_event(session, date(2026, 9, 21))
    add_window(session, date(2026, 9, 21), "forecast", temp_f=50.0)
    source = FakeSource(day(date(2026, 9, 13), temp_f=61.0))
    result = sync_weather(session, source, now_local=NOW)
    assert source.archive_calls == [(date(2026, 9, 13), date(2026, 9, 14))]
    assert source.forecast_calls == []
    rows = stored(session)
    assert rows[datetime.combine(date(2026, 9, 13), time(10))] == (61.0, "archive")
    assert rows[datetime.combine(date(2026, 9, 21), time(10))] == (50.0, "forecast")
    assert result.recompute_job_id is not None


def test_rows_with_missing_values_are_not_stored(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    source = FakeSource(day(date(2026, 9, 13), temp_f=None))
    result = sync_weather(session, source, now_local=NOW)
    assert stored(session) == {}
    assert queued(session, "recompute") == []
    assert result == SyncResult((date(2026, 9, 13),), 0, 0, None)
    assert dates_needing_weather(session, NOW) == [date(2026, 9, 13)]


def test_partial_window_is_fetched_again(session: Session) -> None:
    # an earlier sync stored 10:00 and 11:00 but 12:00 was still null in the archive
    add_event(session, date(2026, 9, 13))
    for hour in (10, 11):
        add_hourly(session, datetime.combine(date(2026, 9, 13), time(hour)), "archive", 60.0)
    assert dates_needing_weather(session, NOW) == [date(2026, 9, 13)]
    source = FakeSource(day(date(2026, 9, 13)))
    result = sync_weather(session, source, now_local=NOW)
    assert source.archive_calls == [(date(2026, 9, 13), date(2026, 9, 14))]
    assert stored(session)[datetime.combine(date(2026, 9, 13), time(12))] == (60.0, "archive")
    assert [job.id for job in queued(session, "recompute")] == [result.recompute_job_id]


def test_hours_outside_the_window_alone_enqueue_no_recompute(session: Session) -> None:
    # archive still catching up: 00:00-09:00 are complete, 10:00 onwards still null
    add_event(session, date(2026, 9, 13))
    hours = [
        obs(datetime.combine(date(2026, 9, 13), time(h)), 60.0 if h < 10 else None)
        for h in range(24)
    ]
    result = sync_weather(session, FakeSource(hours), now_local=NOW)
    assert result == SyncResult((date(2026, 9, 13),), 10, 0, None)
    assert len(stored(session)) == 10
    assert queued(session, "recompute") == []


def test_open_meteo_failure_writes_nothing(session: Session) -> None:
    add_event(session, date(2019, 1, 6))
    add_event(session, date(2020, 1, 5))
    source = FakeSource(day(date(2019, 1, 6)) + day(date(2020, 1, 5)), fail_on_archive_call=2)
    with pytest.raises(WeatherApiError):
        sync_weather(session, source, now_local=NOW)
    assert stored(session) == {}
    assert queued(session, "recompute") == []


def test_upsert_overwrites_an_existing_hour(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    add_hourly(session, datetime.combine(date(2026, 9, 13), time(3)), "archive", temp_f=40.0)
    sync_weather(session, FakeSource(day(date(2026, 9, 13), temp_f=61.0)), now_local=NOW)
    hourly = table("weather_hourly")
    temp, fetched_at = session.execute(
        select(hourly.c.temp_f, hourly.c.fetched_at).where(
            hourly.c.ts_local == datetime.combine(date(2026, 9, 13), time(3))
        )
    ).one()
    assert (temp, fetched_at) == (61.0, NOW)


def test_unchanged_window_rewrite_enqueues_no_recompute(session: Session) -> None:
    # 10:00 and 11:00 are stored; the archive returns them unchanged and 12:00 still null
    add_event(session, date(2026, 9, 13))
    for hour in (10, 11):
        add_hourly(session, datetime.combine(date(2026, 9, 13), time(hour)), "archive", 60.0)
    hours = [
        obs(datetime.combine(date(2026, 9, 13), time(h)), None if h == 12 else 60.0)
        for h in range(24)
    ]
    source = FakeSource(hours)
    result = sync_weather(session, source, now_local=NOW)
    assert source.archive_calls == [(date(2026, 9, 13), date(2026, 9, 14))]
    assert result == SyncResult((date(2026, 9, 13),), 21, 0, None)
    assert queued(session, "recompute") == []
    hourly = table("weather_hourly")
    ten = datetime.combine(date(2026, 9, 13), time(10))
    fetched_at = session.scalar(select(hourly.c.fetched_at).where(hourly.c.ts_local == ten))
    assert fetched_at == datetime(2026, 9, 1, tzinfo=LA)  # untouched: nothing changed


def test_upsert_hourly_writes_only_new_or_changed_rows(session: Session) -> None:
    first = datetime.combine(date(2026, 9, 13), time(3))
    at = [first + timedelta(hours=i) for i in range(5)]
    no_rain = replace(obs(at[3]), rain_in=None)
    original = [
        (obs(at[0], temp_f=57.1), "archive"),  # not exact in float4
        (obs(at[1]), "archive"),
        (obs(at[2]), "forecast"),
        (no_rain, "archive"),
        (replace(obs(at[4]), rain_in=None), "archive"),
    ]
    assert upsert_hourly(session, original, fetched_at=NOW) == 5
    later = NOW + timedelta(days=1)
    again = [
        (obs(at[0], temp_f=57.1), "archive"),  # identical: skipped
        (obs(at[1], temp_f=61.0), "archive"),  # value changed
        (obs(at[2]), "archive"),  # only the source changed
        (replace(no_rain, rain_in=0.02), "archive"),  # NULL -> value is a change
        (replace(obs(at[4]), rain_in=None), "archive"),  # NULL -> NULL is not
    ]
    assert upsert_hourly(session, again, fetched_at=later) == 3
    hourly = table("weather_hourly")
    rows = session.execute(select(hourly.c.ts_local, hourly.c.fetched_at)).all()
    assert dict(rows) == {at[0]: NOW, at[1]: later, at[2]: later, at[3]: later, at[4]: NOW}


def test_upsert_hourly_writes_more_rows_than_one_statement_can_bind(session: Session) -> None:
    # 360 event dates x 24 h (the fixture's first full sync): one multi-row INSERT would
    # need 8,640 x 14 = 120,960 bind parameters, above Postgres' 65,535 cap
    start = datetime.combine(date(2019, 1, 1), time(0))
    rows = [(obs(start + timedelta(hours=i)), "archive") for i in range(8640)]
    assert upsert_hourly(session, rows, fetched_at=NOW) == 8640
    hourly = table("weather_hourly")
    assert session.scalar(select(func.count()).select_from(hourly)) == 8640


def test_weather_sync_handler_fetches_recorded_archive(
    session: Session, weather_env: pytest.MonkeyPatch
) -> None:
    add_event(session, date(2026, 9, 13))
    body = json.loads(RECORDED.read_text(encoding="utf-8"))
    with respx.mock() as router:
        route = router.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=body))
        weather_sync_handler(session, {})
    params = route.calls.last.request.url.params
    assert (params["start_date"], params["end_date"]) == ("2026-09-13", "2026-09-14")
    assert (params["latitude"], params["longitude"]) == ("45.3525", "-122.8082")
    rows = stored(session)
    assert sorted(rows) == [datetime.combine(date(2026, 9, 13), time(h)) for h in range(24)]
    assert rows[datetime.combine(date(2026, 9, 13), time(10))][0] == pytest.approx(57.1, abs=1e-4)
    assert len(queued(session, "recompute")) == 1


def test_weather_sync_handler_noop_when_disabled(
    session: Session, weather_env: pytest.MonkeyPatch
) -> None:
    weather_env.setenv("WEATHER_ENABLED", "false")
    get_settings.cache_clear()
    add_event(session, date(2026, 9, 13))
    with respx.mock(assert_all_called=False) as router:
        route = router.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json={}))
        weather_sync_handler(session, {})
    assert not route.called
    assert stored(session) == {}
    assert queued(session, "recompute") == []


def test_weather_sync_handler_reads_the_clock_in_the_configured_timezone(
    session: Session, weather_env: pytest.MonkeyPatch
) -> None:
    # at 2026-09-20 03:00 UTC, 09-13 is 7 days old on a UTC wall clock (archive API) but only
    # 6 days old in Los Angeles, where it is still 09-19 20:00 (forecast API)
    weather_env.setenv("TIMEZONE", "UTC")
    get_settings.cache_clear()
    weather_env.setattr(sync, "datetime", FrozenClock)
    add_event(session, date(2026, 9, 13))
    body = json.loads(RECORDED.read_text(encoding="utf-8"))
    with respx.mock(assert_all_called=False) as router:
        archive = router.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=body))
        forecast = router.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=body))
        weather_sync_handler(session, {})
    assert not forecast.called
    params = archive.calls.last.request.url.params
    assert (params["start_date"], params["end_date"]) == ("2026-09-13", "2026-09-14")
    rows = stored(session)  # the client reads the stamps on the same UTC wall clock
    assert sorted(rows) == [datetime.combine(date(2026, 9, 13), time(h)) for h in range(24)]
    assert {src for _, src in rows.values()} == {"archive"}
    assert len(queued(session, "recompute")) == 1
