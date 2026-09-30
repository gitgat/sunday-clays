"""Recompute step 20 writes event_weather from weather_hourly."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Table, insert, select, update
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import discover_steps, get_data_version, run_pipeline
from sunday_clays.analytics.steps import s20_event_weather
from sunday_clays.models import Base

LA = ZoneInfo("America/Los_Angeles")


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


def add_hour(
    session: Session, ts_local: datetime, source: str = "archive", **fields: float
) -> None:
    values: dict[str, Any] = {
        "ts_local": ts_local,
        "temp_f": 60.0,
        "apparent_f": 58.0,
        "precip_in": 0.0,
        "rain_in": 0.0,
        "wind_mph": 5.0,
        "gust_mph": 9.0,
        "wind_dir_deg": 180.0,
        "cloud_pct": 80.0,
        "humidity_pct": 70.0,
        "pressure_hpa": 1015.0,
        "weather_code": 3,
        "source": source,
        "fetched_at": datetime(2026, 9, 27, 12, 0, tzinfo=LA),
    }
    values.update(fields)
    session.execute(insert(table("weather_hourly")).values(**values))


def event_weather(session: Session) -> dict[date, dict[str, Any]]:
    rows = session.execute(select(table("event_weather"))).mappings()
    return {row["event_date"]: dict(row) for row in rows}


def test_s20_writes_event_weather_from_window_rows(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    add_hour(session, datetime.combine(date(2026, 9, 13), time(10)), temp_f=57.0, gust_mph=30.0)
    add_hour(session, datetime.combine(date(2026, 9, 13), time(11)), temp_f=60.0, precip_in=0.01)
    add_hour(session, datetime.combine(date(2026, 9, 13), time(12)), temp_f=63.0, precip_in=0.01)
    # 13:00 is outside the window
    add_hour(session, datetime.combine(date(2026, 9, 13), time(13)), temp_f=90.0)
    s20_event_weather.run(session)
    row = event_weather(session)[date(2026, 9, 13)]
    assert row["temp_f"] == pytest.approx(60.0)
    assert row["precip_in"] == pytest.approx(0.02)
    assert row["gust_mph"] == pytest.approx(9.0)
    assert (row["condition"], row["source"]) == ("rain", "archive")


def test_s20_skips_event_with_missing_window_row(session: Session) -> None:
    add_event(session, date(2026, 9, 20))
    add_hour(session, datetime.combine(date(2026, 9, 20), time(10)))
    add_hour(session, datetime.combine(date(2026, 9, 20), time(11)))
    s20_event_weather.run(session)
    assert event_weather(session) == {}


def test_s20_skips_event_with_a_null_needed_value(session: Session) -> None:
    # weather_sync never stores such a row (Decisions §6), but the step must not write zeros
    add_event(session, date(2026, 9, 20))
    add_hour(session, datetime.combine(date(2026, 9, 20), time(10)))
    add_hour(session, datetime.combine(date(2026, 9, 20), time(11)), precip_in=None)
    add_hour(session, datetime.combine(date(2026, 9, 20), time(12)))
    s20_event_weather.run(session)
    assert event_weather(session) == {}


def test_s20_marks_forecast_source(session: Session) -> None:
    add_event(session, date(2026, 9, 27))
    add_hour(session, datetime.combine(date(2026, 9, 27), time(10)))
    add_hour(session, datetime.combine(date(2026, 9, 27), time(11)), source="forecast")
    add_hour(session, datetime.combine(date(2026, 9, 27), time(12)))
    s20_event_weather.run(session)
    row = event_weather(session)[date(2026, 9, 27)]
    assert (row["source"], row["condition"]) == ("forecast", "overcast")


def test_s20_writes_a_calm_window_with_no_wind_direction(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    for h in (10, 11, 12):
        add_hour(session, datetime.combine(date(2026, 9, 13), time(h)), wind_mph=0.0)
    s20_event_weather.run(session)
    row = event_weather(session)[date(2026, 9, 13)]
    assert (row["wind_mph"], row["wind_dir_deg"]) == (0.0, None)


def test_s20_ignores_hours_of_non_event_dates(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    for h in (10, 11, 12):
        add_hour(session, datetime.combine(date(2026, 9, 12), time(h)))
    s20_event_weather.run(session)
    assert event_weather(session) == {}


def test_s20_replaces_rows_from_the_previous_run(session: Session) -> None:
    session.execute(
        insert(table("event_weather")).values(
            event_date=date(2026, 1, 4),
            temp_f=40.0,
            apparent_f=35.0,
            precip_in=0.0,
            wind_mph=3.0,
            gust_mph=5.0,
            wind_dir_deg=90.0,
            cloud_pct=10.0,
            humidity_pct=80.0,
            pressure_hpa=1020.0,
            condition="clear",
            source="archive",
        )
    )
    add_event(session, date(2026, 9, 13))
    for h in (10, 11, 12):
        add_hour(session, datetime.combine(date(2026, 9, 13), time(h)))
    s20_event_weather.run(session)
    assert sorted(event_weather(session)) == [date(2026, 9, 13)]


def test_s20_rewrites_an_event_row_when_its_window_weather_changes(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    for h in (10, 11, 12):
        source = "forecast" if h == 11 else "archive"
        add_hour(session, datetime.combine(date(2026, 9, 13), time(h)), source=source)
    s20_event_weather.run(session)
    first = event_weather(session)
    s20_event_weather.run(session)
    assert event_weather(session) == first  # unchanged weather -> identical rows
    before = first[date(2026, 9, 13)]
    assert (before["condition"], before["source"]) == ("overcast", "forecast")
    # weather_sync upgrades the forecast hour to archive, and the archive saw rain
    hourly = table("weather_hourly")
    session.execute(
        update(hourly)
        .where(hourly.c.ts_local == datetime.combine(date(2026, 9, 13), time(11)))
        .values(precip_in=0.03, source="archive")
    )
    s20_event_weather.run(session)
    assert event_weather(session) == {
        date(2026, 9, 13): {
            **before,
            "precip_in": 0.03,
            "condition": "rain",
            "source": "archive",
        }
    }


def test_s20_is_discovered_as_pipeline_step_20() -> None:
    step = next(s for s in discover_steps() if s.name == "event_weather")
    assert (step.order, step.run) == (20, s20_event_weather.run)


def test_run_pipeline_runs_step_20_then_bumps_data_version(session: Session) -> None:
    add_event(session, date(2026, 9, 13))
    for h in (10, 11, 12):
        add_hour(session, datetime.combine(date(2026, 9, 13), time(h)))
    before = get_data_version(session)
    assert "event_weather" in run_pipeline(session)
    assert sorted(event_weather(session)) == [date(2026, 9, 13)]
    assert get_data_version(session) == before + 1
