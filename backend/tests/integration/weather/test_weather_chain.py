"""rebuild -> weather_sync (mocked Open-Meteo) -> recompute writes event_weather."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import Table, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.ingest.names import identity_key, name_key
from sunday_clays.jobs.handlers import load_handlers
from sunday_clays.models import Base
from sunday_clays.weather.client import HOURLY_VARIABLES

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
EVENTS = (date(2026, 9, 6), date(2026, 9, 13))
ARGON2_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$zAaUsgjT4w79Q1k1Gfv6xA"
    "$8hnJDkRbYWn07p0LLDJamRY8+s/GuMmthqmaBq6Aris"
)
UNITS = {
    "time": "unixtime",
    "temperature_2m": "°F",
    "apparent_temperature": "°F",
    "precipitation": "inch",
    "rain": "inch",
    "wind_speed_10m": "mp/h",
    "wind_gusts_10m": "mp/h",
    "wind_direction_10m": "°",
    "cloud_cover": "%",
    "relative_humidity_2m": "%",
    "pressure_msl": "hPa",
    "weather_code": "wmo code",
}
CONSTANT = {
    "temperature_2m": 60.0,
    "apparent_temperature": 58.0,
    "precipitation": 0.01,
    "rain": 0.01,
    "wind_speed_10m": 5.0,
    "wind_gusts_10m": 12.0,
    "wind_direction_10m": 180,
    "cloud_cover": 80,
    "relative_humidity_2m": 70,
    "pressure_msl": 1015.0,
    "weather_code": 61,
}
# Run in a fresh interpreter: in this pytest process other test modules have already
# imported the weather modules (registering their handlers), which would hide a
# load_handlers() that no longer looks in sunday_clays.weather.
DISCOVER_HANDLERS = """
import json, sys
from sunday_clays.jobs.handlers import load_handlers
preloaded = sorted(m for m in sys.modules if m.startswith("sunday_clays.weather"))
handlers = {kind: f"{fn.__module__}.{fn.__qualname__}" for kind, fn in load_handlers().items()}
print(json.dumps({"preloaded": preloaded, "handlers": handlers}))
"""


def table(name: str) -> Table:
    return Base.metadata.tables[name]


def archive_response(request: httpx.Request) -> httpx.Response:
    """Constant weather for every hour of the requested UTC days."""
    start = date.fromisoformat(request.url.params["start_date"])
    end = date.fromisoformat(request.url.params["end_date"])
    first = int(datetime.combine(start, time(0), tzinfo=UTC).timestamp())
    stamps = [first + 3600 * i for i in range(24 * ((end - start).days + 1))]
    hourly: dict[str, list[Any]] = {"time": stamps}
    hourly.update({name: [CONSTANT[name]] * len(stamps) for name in HOURLY_VARIABLES})
    body = {
        "latitude": 45.377853,
        "longitude": -122.816895,
        "generationtime_ms": 0.3,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 79.0,
        "hourly_units": UNITS,
        "hourly": hourly,
    }
    return httpx.Response(200, json=body)


def commit_scores(session: Session) -> None:
    """A committed scores import: three shooters at each of two Sundays."""
    imports = table("imports")
    import_id: int = session.execute(
        insert(imports)
        .values(
            kind="scores",
            filename="weather-chain.xlsx",
            sha256="c" * 64,
            file_bytes=b"synthetic",
            status="committed",
            committed_at=datetime.now(UTC) - timedelta(minutes=1),
            summary={},
            findings=[],
        )
        .returning(imports.c.id)
    ).scalar_one()
    rows: list[dict[str, Any]] = []
    for event_date in EVENTS:
        for offset, raw in enumerate(("Doe, Jane", "Roe, Rick", "Poe, Pat")):
            rows.append(
                {
                    "import_id": import_id,
                    "row_number": len(rows) + 2,
                    "raw_name": raw,
                    "name_key": identity_key(name_key(raw), event_date),
                    "score": 40 - offset,
                    "event_date": event_date,
                    "status": "member",
                    "gauge_class": None,
                }
            )
    session.execute(insert(table("import_score_rows")), rows)


def queued_kinds(session: Session) -> list[str]:
    jobs = table("jobs")
    return list(session.scalars(select(jobs.c.kind).where(jobs.c.status == "queued")))


@pytest.fixture
def weather_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
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
    monkeypatch.setenv("OPEN_METEO_ARCHIVE_URL", ARCHIVE_URL)
    monkeypatch.setenv("OPEN_METEO_FORECAST_URL", FORECAST_URL)
    monkeypatch.setenv("TIMEZONE", "America/Los_Angeles")
    monkeypatch.setenv("WEATHER_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_rebuild_weather_sync_recompute_chain_writes_event_weather(
    session: Session, weather_env: None
) -> None:
    # the worker's own discovery function (Plan 03 T7), so a broken discovery fails here too
    handlers = load_handlers()
    commit_scores(session)

    handlers["rebuild"](session, {})
    assert "weather_sync" in queued_kinds(session)

    with respx.mock() as router:
        router.get(ARCHIVE_URL).mock(side_effect=archive_response)
        handlers["weather_sync"](session, {})
    assert "recompute" in queued_kinds(session)

    handlers["recompute"](session, {})
    event_weather = table("event_weather")
    rows = session.execute(
        select(
            event_weather.c.event_date,
            event_weather.c.temp_f,
            event_weather.c.condition,
        )
    ).all()
    # 0.01 in/h at 11:00 and 12:00 -> 0.02 in over the window -> "rain" (C7)
    assert sorted(rows) == [(EVENTS[0], 60.0, "rain"), (EVENTS[1], 60.0, "rain")]


def test_worker_discovery_finds_the_weather_handlers_in_a_fresh_interpreter() -> None:
    result = subprocess.run(
        [sys.executable, "-c", DISCOVER_HANDLERS],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr  # show the child's traceback on failure
    found = json.loads(result.stdout)
    assert found["preloaded"] == []  # only load_handlers() imports the weather package
    expected = {
        "forecast_refresh": "sunday_clays.weather.forecast.forecast_refresh_handler",
        "rebuild": "sunday_clays.jobs.rebuild_handler.handle_rebuild",
        "recompute": "sunday_clays.jobs.handlers.handle_recompute",
        "weather_sync": "sunday_clays.weather.sync.weather_sync_handler",
    }
    # other plans may register more kinds; these are the ones the weather chain relies on
    assert {kind: found["handlers"].get(kind) for kind in expected} == expected
