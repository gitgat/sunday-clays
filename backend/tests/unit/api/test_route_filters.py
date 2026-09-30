from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sunday_clays.api.routes import _filters
from sunday_clays.domain.round_type import RoundType


def test_today_local_is_the_date_in_the_given_zone() -> None:
    today = _filters.today_local("America/Los_Angeles")
    now = datetime.now(UTC)
    zone = ZoneInfo("America/Los_Angeles")
    # the call may straddle midnight: accept the zone's date just before or just after it
    assert today in {
        (now - timedelta(seconds=5)).astimezone(zone).date(),
        (now + timedelta(seconds=5)).astimezone(zone).date(),
    }


def test_resolve_as_of_keeps_an_explicit_date() -> None:
    assert _filters.resolve_as_of(date(2024, 2, 29), "America/Los_Angeles") == date(2024, 2, 29)


def test_resolve_as_of_none_is_today_in_the_club_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_today(tz: str) -> date:
        seen.append(tz)
        return date(2026, 9, 27)

    monkeypatch.setattr(_filters, "today_local", fake_today)

    assert _filters.resolve_as_of(None, "America/Los_Angeles") == date(2026, 9, 27)
    assert seen == ["America/Los_Angeles"]


def test_round_type_param_reads_repeated_round_type_values() -> None:
    app = FastAPI()

    @app.get("/probe")
    def probe(round_types: list[RoundType] = _filters.round_type_param) -> list[str]:
        return [rt.value for rt in round_types]

    client = TestClient(app)

    assert client.get("/probe").json() == []
    assert client.get("/probe?round_type=sporting&round_type=super_sporting").json() == [
        "sporting",
        "super_sporting",
    ]
    assert client.get("/probe?round_type=trap").status_code == 422
