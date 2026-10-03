"""Page-cache behaviour against real Postgres (Plan 19 §5.2)."""

import asyncio
import logging
import threading
import time
from collections.abc import Iterator
from datetime import date
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import bump_data_version
from sunday_clays.api import page_cache as pc
from sunday_clays.api.app import create_app
from sunday_clays.api.routes import _filters
from sunday_clays.api.routes import insights as insights_routes
from sunday_clays.auth.sessions import COOKIE_NAME, issue_session
from sunday_clays.config import Settings, get_settings

#: At least one real URL per ALLOWLIST template (the meta-test below enforces it).
SAMPLE_URLS: tuple[str, ...] = (
    "/api/insights/home",
    "/api/insights/club",
    "/api/insights/leaderboards",
    "/api/insights/records",
    "/api/insights/stations",
    "/api/insights/sundays/2026-09-27",
    "/api/insights/shooters/3",
    "/api/events",
    "/api/events?year=2026",
    "/api/events/2026-09-27",
    "/api/events/2026-09-27/achievements",
    "/api/leaderboards",
    "/api/leaderboards/movers",
    "/api/leaderboards/history?from=2025-09-28&to=2026-09-27",
    "/api/stations",
    "/api/stations/4",
    "/api/shooters/3/stations",
    "/api/club/summary?since=2026-08-03&as_of=2026-09-27",
    "/api/club/attendance",
    "/api/club/cohorts",
    "/api/club/distribution?by=year",
    "/api/club/first-rounds",
    "/api/club/regulars",
    "/api/club/conversion",
    "/api/club/parity?by=year",
    "/api/club/trends",
    "/api/records",
    "/api/achievements",
    "/api/achievements/doubleheader",
    "/api/shooters/3/achievements",
    "/api/shooters",
    "/api/shooters/3",
    "/api/shooters/3/rounds",
    "/api/shooters/3/special",
    "/api/shooters/3/rating",
    "/api/shooters/3/splits?by=year",
    "/api/shooters/3/insights",
    "/api/yir/2026",
    "/api/yir/2026/shooters/3",
    "/api/on-this-day",
)
SAME = ("content-type", "content-length", "cache-control", "etag")


@pytest.fixture
def cache_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _cache_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "false")
    get_settings.cache_clear()


def _rows(session: Session) -> list[Any]:
    return list(session.execute(text("SELECT key, role, local_date FROM response_cache")).all())


def test_every_template_has_a_sample() -> None:
    routes = [pc.CachedRoute(t, pc.compile_template(t), frozenset()) for t in pc.ALLOWLIST]
    covered = {pc.match_route(routes, url.split("?")[0]).template for url in SAMPLE_URLS}  # type: ignore[union-attr]
    assert covered == set(pc.ALLOWLIST)


@pytest.mark.parametrize("world", ["fx", "fx_special"])
def test_byte_identical_for_every_allowlisted_route(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, world: str
) -> None:
    client = cast(TestClient, request.getfixturevalue(f"{world}_viewer_client"))
    for url in SAMPLE_URLS:
        _cache_off(monkeypatch)
        a = client.get(url)
        assert a.status_code == 200, url
        monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
        get_settings.cache_clear()
        b, c = client.get(url), client.get(url)
        assert (b.headers["x-page-cache"], c.headers["x-page-cache"]) == ("miss", "hit"), url
        assert a.status_code == b.status_code == c.status_code
        assert a.content == b.content == c.content, url
        for name in SAME:
            assert a.headers.get(name) == b.headers.get(name) == c.headers.get(name), (url, name)
        revalidated = client.get(url, headers={"If-None-Match": c.headers["etag"]})
        assert revalidated.status_code == 304, url


def test_a_data_version_bump_serves_fresh_data(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both URLs are stored before the bump and their rows poisoned with a sentinel, so a "miss"
    after the bump proves the key moved (§5.2). Kills: a key without data_version."""
    urls = ("/api/shooters/3", "/api/insights/home")
    first = {url: fx_viewer_client.get(url) for url in urls}
    assert {r.headers["x-page-cache"] for r in first.values()} == {"miss"}
    assert "Abernathy, Winston" in first["/api/shooters/3"].text
    assert len(_rows(fx_session)) == 2
    fx_session.execute(text("UPDATE response_cache SET body = '{\"sentinel\": 1}'"))
    for url in urls:  # control: before the bump, a hit serves the stored (poisoned) row
        poisoned = fx_viewer_client.get(url)
        assert poisoned.headers["x-page-cache"] == "hit", url
        assert "sentinel" in poisoned.text, url
    fx_session.execute(
        text("UPDATE shooter_profiles SET display_name = 'Abernathy, Wendell' WHERE shooter_id = 3")
    )
    bump_data_version(fx_session)
    after = {url: fx_viewer_client.get(url) for url in urls}
    _cache_off(monkeypatch)
    for url, response in after.items():
        assert response.headers["x-page-cache"] == "miss", url
        assert "sentinel" not in response.text, url
        assert response.content == fx_viewer_client.get(url).content, url  # the uncached answer
    assert "Abernathy, Wendell" in after["/api/shooters/3"].text


def test_the_local_date_rolling_over_serves_fresh_data(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls = ("/api/club/trends", "/api/on-this-day", "/api/shooters/3")
    for day in (date(2026, 10, 2), date(2026, 10, 3)):
        monkeypatch.setattr(_filters, "today_local", lambda _tz, d=day: d)
        for url in urls:
            response = fx_viewer_client.get(url)
            assert response.headers["x-page-cache"] == "miss", (day, url)
            monkeypatch.setenv("PAGE_CACHE_ENABLED", "false")
            get_settings.cache_clear()
            assert fx_viewer_client.get(url).content == response.content, (day, url)
            monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
            get_settings.cache_clear()
    assert {r.local_date for r in _rows(fx_session)} == {date(2026, 10, 2), date(2026, 10, 3)}


def test_viewer_and_admin_bodies_never_cross(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_admin_client: TestClient,
    fx_session: Session,
) -> None:
    url = "/api/shooters/3"
    assert fx_viewer_client.get(url).headers["x-page-cache"] == "miss"
    assert fx_admin_client.get(url).headers["x-page-cache"] == "miss"
    assert sorted(r.role for r in _rows(fx_session)) == ["admin", "viewer"]
    fx_session.execute(
        text("UPDATE response_cache SET body = '{\"admin_only\": 1}' WHERE role = 'admin'")
    )
    assert "admin_only" not in fx_viewer_client.get(url).text
    fx_session.execute(
        text("UPDATE response_cache SET body = '{\"viewer_only\": 1}' WHERE role = 'viewer'")
    )
    assert "viewer_only" not in fx_admin_client.get(url).text


def test_excluded_routes_are_never_stored(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_admin_client: TestClient,
    fx_session: Session,
) -> None:
    device = "0b6d3a8e-2f40-4c55-9a51-6b1f3e1f0a11"
    gated = ("/api/club/milestones", "/api/shooters/3/summary?to=2026-09-27")
    calls: list[tuple[TestClient, str, str]] = [
        (fx_viewer_client, "GET", f"/api/bumps?keys=x&device_id={device}"),
        (fx_viewer_client, "GET", "/api/features"),
        (fx_viewer_client, "GET", "/api/meta"),
        (fx_viewer_client, "GET", "/api/health"),
        (fx_viewer_client, "GET", "/api/auth/me"),
        (fx_viewer_client, "GET", "/api/predictions/next"),
        (fx_viewer_client, "GET", "/api/weather/events"),
        (fx_viewer_client, "GET", "/api/og/page/events/2026-09-27"),
        (fx_admin_client, "GET", "/api/admin/features"),
        (fx_viewer_client, "GET", "/api/events/1999-01-03"),  # 404
        (fx_viewer_client, "GET", "/api/shooters/abc"),  # 422
        (fx_viewer_client, "GET", "/api/shooters/3?since=2026-09-27&as_of=2026-09-01"),  # 400
        (fx_viewer_client, "GET", "/api/events?_=1"),  # undeclared parameter
        (fx_viewer_client, "HEAD", "/api/events"),
        *[(c, "GET", url) for c in (fx_viewer_client, fx_admin_client) for url in gated],
    ]
    for client, method, url in calls:
        response = client.request(method, url)
        assert response.headers.get("x-page-cache") != "hit", url
    for key in ("club_milestones", "summary_card"):
        fx_admin_client.put(f"/api/admin/features/{key}", json={"enabled": True})
    for client, method, url in [
        (c, "GET", url) for c in (fx_viewer_client, fx_admin_client) for url in gated
    ]:
        client.request(method, url)
    assert _rows(fx_session) == []
    bypassed = fx_viewer_client.get("/api/events?_=1")
    assert bypassed.headers["x-page-cache"] == "bypass"
    assert "x-page-cache" not in fx_viewer_client.get("/api/features").headers


def test_fail_open_with_one_warning_per_request_naming_only_the_template(
    cache_on: None,
    fx_viewer_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(app: FastAPI) -> Any:
        raise RuntimeError("database is gone")

    monkeypatch.setattr(pc, "_open_session", broken)
    for url in ("/api/shooters/3", "/api/events/2026-09-27"):
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="sunday_clays.api.page_cache"):
            response = fx_viewer_client.get(url)
        assert response.status_code == 200
        assert response.headers["x-page-cache"] == "bypass"
        (record,) = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert "{" in record.getMessage()  # the template, e.g. /api/shooters/{id}
        assert url not in record.getMessage()


def test_the_row_cap_serves_but_does_not_store(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pc, "MAX_ROWS", 2)
    for url in ("/api/events", "/api/records"):
        fx_viewer_client.get(url)
    third = fx_viewer_client.get("/api/achievements")
    assert third.status_code == 200
    assert third.headers["x-page-cache"] == "miss"
    assert len(_rows(fx_session)) == 2
    assert fx_viewer_client.get("/api/achievements").headers["x-page-cache"] == "miss"


def test_the_kill_switch(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_admin_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx_viewer_client.get("/api/events")
    assert len(_rows(fx_session)) == 1
    assert (
        fx_admin_client.put("/api/admin/features/page_cache", json={"enabled": False}).status_code
        == 200
    )
    assert _rows(fx_session) == []
    audits = (
        fx_session.execute(text("SELECT details FROM audit_log WHERE action = 'feature_switch'"))
        .scalars()
        .all()
    )
    assert audits == [{"key": "page_cache", "enabled": False}]
    assert fx_viewer_client.get("/api/events").headers["x-page-cache"] == "bypass"
    assert _rows(fx_session) == []
    fx_admin_client.put("/api/admin/features/page_cache", json={"enabled": True})
    assert fx_viewer_client.get("/api/events").headers["x-page-cache"] == "miss"
    _cache_off(monkeypatch)
    assert fx_viewer_client.get("/api/events").headers["x-page-cache"] == "bypass"


@pytest.fixture
def live_app_cookie(committed_engine: Engine, auth_env: Settings, cache_on: None) -> str:
    return issue_session(get_settings(), "viewer")


async def _hit_many(apps: list[FastAPI], cookie: str, url: str, n: int) -> list[httpx.Response]:
    clients = [
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies={COOKIE_NAME: cookie},
        )
        for app in apps
    ]
    try:
        return await asyncio.gather(*[clients[i % len(clients)].get(url) for i in range(n)])
    finally:
        for client in clients:
            await client.aclose()


def _count_calls(monkeypatch: pytest.MonkeyPatch, module: Any, name: str) -> list[int]:
    calls: list[int] = []
    lock = threading.Lock()
    real = getattr(module, name)

    def counted(*args: Any, **kwargs: Any) -> Any:
        with lock:
            calls.append(1)
        time.sleep(0.3)  # long enough for every follower to arrive while the leader computes
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, counted)
    return calls


def test_stampede_computes_once_per_process(
    live_app_cookie: str, committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _count_calls(monkeypatch, insights_routes, "held_dates")
    responses = asyncio.run(_hit_many([create_app()], live_app_cookie, "/api/insights/home", 10))
    assert len(calls) == 1
    assert len({r.content for r in responses}) == 1
    assert {r.status_code for r in responses} == {200}
    with Session(committed_engine) as s:
        assert s.execute(text("SELECT count(*) FROM response_cache")).scalar_one() == 1


def test_followers_that_time_out_compute_alone_and_store_nothing(
    live_app_cookie: str, committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D33 fallback: a follower waits FOLLOW_TIMEOUT_S for a slow leader, then answers from its
    own computation and stores nothing (the leader stores the one row). The timeout is patched to
    50 ms; the leader takes 300 ms. Kills: a follower that raises or hangs on the timeout, one
    that stores a second row, or one that answers with an empty body."""
    monkeypatch.setattr(pc, "FOLLOW_TIMEOUT_S", 0.05)
    calls = _count_calls(monkeypatch, insights_routes, "held_dates")
    responses = asyncio.run(_hit_many([create_app()], live_app_cookie, "/api/insights/home", 4))
    assert {r.status_code for r in responses} == {200}
    assert len({r.content for r in responses}) == 1
    assert responses[0].content != b""
    assert {r.headers["x-page-cache"] for r in responses} == {"miss"}  # nobody got a hit
    assert len(calls) == 4  # the leader and the 3 followers that gave up each ran the route
    with Session(committed_engine) as s:
        assert s.execute(text("SELECT count(*) FROM response_cache")).scalar_one() == 1


def test_two_replicas_compute_at_most_twice_and_keep_one_row(
    live_app_cookie: str, committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _count_calls(monkeypatch, insights_routes, "held_dates")
    apps = [create_app(), create_app()]
    responses = asyncio.run(_hit_many(apps, live_app_cookie, "/api/insights/home", 10))
    assert len(calls) <= 2
    assert len({r.content for r in responses}) == 1
    with Session(committed_engine) as s:
        assert s.execute(text("SELECT count(*) FROM response_cache")).scalar_one() == 1


def test_a_leaders_404_is_not_shared_and_not_stored(
    live_app_cookie: str, committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sunday_clays.analytics import frames

    calls = _count_calls(monkeypatch, frames, "load_calendar")
    responses = asyncio.run(_hit_many([create_app()], live_app_cookie, "/api/events/1999-01-03", 4))
    assert {r.status_code for r in responses} == {404}
    # D33: the leader's 404 is not storable, so each of the 3 followers runs the route itself
    # (one load_calendar per run). Kills sharing the leader's response with the followers.
    assert len(calls) == 4
    with Session(committed_engine) as s:
        assert s.execute(text("SELECT count(*) FROM response_cache")).scalar_one() == 0


def test_repeated_parameters_are_never_stored_or_cross_served(
    cache_on: None, fx_viewer_client: TestClient, fx_session: Session
) -> None:
    """FastAPI answers with the last value; a key that sorts values would merge both orders."""
    first = fx_viewer_client.get("/api/events?year=2025&year=2026")
    second = fx_viewer_client.get("/api/events?year=2026&year=2025")
    assert first.headers["x-page-cache"] == second.headers["x-page-cache"] == "bypass"
    assert _rows(fx_session) == []
    assert first.content != second.content  # 2026 vs 2025 answers differ


def test_a_stored_row_is_never_served_without_a_valid_session(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    from sunday_clays.auth import sessions

    url = "/api/shooters/3"
    valid = fx_viewer_client.cookies.get(COOKIE_NAME)
    assert valid is not None
    assert fx_viewer_client.get(url).headers["x-page-cache"] == "miss"
    assert len(_rows(fx_session)) == 1
    assert fx_viewer_client.get(url).headers["x-page-cache"] == "hit"

    fx_viewer_client.cookies.clear()
    no_cookie = fx_viewer_client.get(url)
    assert no_cookie.status_code == 401
    assert no_cookie.headers.get("x-page-cache") != "hit"

    fx_viewer_client.cookies.set(COOKIE_NAME, valid + "x")
    forged = fx_viewer_client.get(url)
    assert forged.status_code == 401
    assert forged.headers.get("x-page-cache") != "hit"

    class Later(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> "Later":
            return cls.fromtimestamp((datetime.now(UTC) + timedelta(days=31)).timestamp(), tz)

    monkeypatch.setattr(sessions, "datetime", Later)
    fx_viewer_client.cookies.set(COOKIE_NAME, valid)
    expired = fx_viewer_client.get(url)
    assert expired.status_code == 401
    assert expired.headers.get("x-page-cache") != "hit"


def test_a_failed_store_still_serves_the_body_with_one_warning(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(pc, "_write", broken)
    with caplog.at_level(logging.WARNING, logger="sunday_clays.api.page_cache"):
        response = fx_viewer_client.get("/api/shooters/3")
    assert response.status_code == 200
    assert response.headers["x-page-cache"] == "miss"
    (record,) = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert "/api/shooters/{id}" in record.getMessage()
    assert _rows(fx_session) == []
