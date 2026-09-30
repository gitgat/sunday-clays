"""The default Settings point the client at Open-Meteo for the club's location."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from sunday_clays.config import Settings
from sunday_clays.weather.client import OpenMeteoClient

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
RECORDED = Path(__file__).parents[2] / "fixtures" / "open_meteo" / "archive_2026-09-13.json"
ARGON2_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$zAaUsgjT4w79Q1k1Gfv6xA"
    "$8hnJDkRbYWn07p0LLDJamRY8+s/GuMmthqmaBq6Aris"
)
DEFAULTED_ENV = frozenset(
    {
        "DATABASE_URL_FILE",
        "SESSION_SECRET_FILE",
        "VIEWER_PASSWORD_HASH_FILE",
        "ADMIN_PASSWORD_HASH_FILE",
        "CLUB_LAT",
        "CLUB_LON",
        "TIMEZONE",
        "OPEN_METEO_ARCHIVE_URL",
        "OPEN_METEO_FORECAST_URL",
    }
)


def recorded() -> dict[str, Any]:
    body: dict[str, Any] = json.loads(RECORDED.read_text(encoding="utf-8"))
    return body


def test_default_settings_query_open_meteo_at_the_club(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Settings reads env vars even through model_validate, and matches their names in any
    # case: clear every spelling of each one this test relies on, so an exported shell or
    # CI variable cannot change the outcome
    for key in list(os.environ):
        if key.upper() in DEFAULTED_ENV:
            monkeypatch.delenv(key)
    settings = Settings.model_validate(
        {
            "database_url": "postgresql+psycopg://unused:unused@localhost:5432/unused",
            "session_secret": "0123456789abcdef0123456789abcdef",
            "viewer_password_hash": ARGON2_HASH,
            "admin_password_hash": ARGON2_HASH,
            "app_version": "test",
        }
    )
    with respx.mock() as router:
        archive = router.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=recorded()))
        forecast = router.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=recorded()))
        with OpenMeteoClient.from_settings(settings) as client:
            rows = client.archive(date(2026, 9, 13), date(2026, 9, 14))
            client.forecast(past_days=0, forecast_days=1)
    for route in (archive, forecast):
        params = route.calls.last.request.url.params
        assert (params["latitude"], params["longitude"]) == ("45.3525", "-122.8082")
    # the default timezone is America/Los_Angeles
    assert rows[0].ts_local == datetime.combine(date(2026, 9, 12), time(17))
