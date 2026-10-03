"""Public link-preview routes (Plan 19 §3.1, D6; §5.1, §5.2)."""

import io
import re
from datetime import date
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.pipeline import bump_data_version
from sunday_clays.config import get_settings
from sunday_clays.domain.features import set_switch

LATEST = "2026-09-27"
SCORE_NEAR_WORD = re.compile(r"\b(score|of)\s+([0-5]?\d|60)\b|\b([0-5]?\d|60)\s+(of|score)\b", re.I)


def _on(session: Session) -> None:
    set_switch(session, get_settings(), "link_previews", True)


def test_every_og_route_is_get_or_head_under_api_og(fx_client: TestClient) -> None:
    found = []
    for context in iter_route_contexts(cast(FastAPI, fx_client.app).routes):
        route = context.original_route
        if isinstance(route, APIRoute) and route.endpoint.__module__.endswith(".routes.og"):
            found.append(context.path_format)
            assert str(context.path_format).startswith("/api/og/")
            assert set(context.methods or ()) <= {"GET", "HEAD"}
    assert len(found) == 4


@pytest.mark.parametrize(
    "path", ["/api/og/page/", f"/api/og/page/events/{LATEST}", "/api/og/image/generic.png"]
)
def test_no_cookie_needed_and_head_mirrors_get(fx_client: TestClient, path: str) -> None:
    fx_client.cookies.clear()
    get = fx_client.get(path)
    head = fx_client.head(path)
    assert get.status_code == head.status_code == 200
    assert head.content == b""
    for name in ("content-type", "content-length", "cache-control", "x-robots-tag"):
        assert head.headers.get(name) == get.headers.get(name), name


def test_page_headers(fx_client: TestClient) -> None:
    response = fx_client.get(f"/api/og/page/events/{LATEST}")
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["cache-control"] == "private, no-cache"
    assert response.headers["vary"] == "User-Agent"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "etag" not in response.headers


def test_switch_off_every_path_is_generic(fx_client: TestClient) -> None:
    page = fx_client.get(f"/api/og/page/events/{LATEST}").text
    assert "Scores, trophies and stats" in page
    assert fx_client.get(f"/api/og/image/sunday/{LATEST}.png").status_code == 404


def test_switch_on_a_sunday_previews_its_facts(fx_client: TestClient, fx_session: Session) -> None:
    _on(fx_session)
    n, round_type = fx_session.execute(
        text("SELECT n_shooters, round_type FROM events WHERE event_date = :d"),
        {"d": date(2026, 9, 27)},
    ).one()
    label = {"sporting": "Sporting", "super_sporting": "Super Sporting"}[round_type]
    page = fx_client.get(f"/api/og/page/l/events/{LATEST}").text
    assert f"Sunday, Sep 27, 2026 · {n} shooters · {label}" in page
    assert f'content="https://sundayclays.claysmasher.com/l/events/{LATEST}"' in page


def test_unknown_and_existing_dates_answer_the_same_status(
    fx_client: TestClient, fx_session: Session
) -> None:
    _on(fx_session)
    assert fx_client.get("/api/og/page/events/1999-01-03").status_code == 200
    assert fx_client.get(f"/api/og/page/events/{LATEST}").status_code == 200
    assert fx_client.get("/api/og/page/events/2026-13-45").status_code == 200


def test_sunday_png_on_off_and_deterministic(fx_client: TestClient, fx_session: Session) -> None:
    _on(fx_session)
    first = fx_client.get(f"/api/og/image/sunday/{LATEST}.png?v=1")
    assert first.status_code == 200
    assert first.headers["content-type"] == "image/png"
    assert first.headers["cache-control"] == "public, max-age=3600"
    assert Image.open(io.BytesIO(first.content)).size == (1200, 630)
    bump_data_version(fx_session)  # facts unchanged, so the bytes are too
    clear_cache()
    assert fx_client.get(f"/api/og/image/sunday/{LATEST}.png?v=2").content == first.content
    assert fx_client.get("/api/og/image/sunday/1999-01-03.png").status_code == 404
    assert fx_client.get("/api/og/image/sunday/nope.png").status_code == 404


def test_generic_png_is_cached_for_a_day(fx_client: TestClient) -> None:
    response = fx_client.get("/api/og/image/generic.png")
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_a_session_cookie_changes_nothing(
    fx_client: TestClient, fx_viewer_client: TestClient, fx_session: Session
) -> None:
    _on(fx_session)
    fx_client.cookies.clear()
    path = f"/api/og/page/events/{LATEST}"
    assert fx_viewer_client.get(path).content == fx_client.get(path).content


def _assert_name_free(page: str, names: list[str]) -> None:
    for display_name in names:
        for part in {display_name, *[p.strip() for p in display_name.split(",")]}:
            if part:
                assert not re.search(rf"\b{re.escape(part)}\b", page), part
    assert not SCORE_NEAR_WORD.search(page)


@pytest.mark.parametrize("world", ["fx", "fx_special"])
def test_name_scan_every_sunday_and_every_shooter(
    request: pytest.FixtureRequest, world: str
) -> None:
    client = cast(TestClient, request.getfixturevalue(f"{world}_client"))
    session = cast(Session, request.getfixturevalue(f"{world}_session"))
    clear_cache()
    _on(session)
    names = [
        str(n) for n in session.execute(text("SELECT display_name FROM shooter_profiles")).scalars()
    ]
    days = session.execute(text("SELECT event_date FROM events ORDER BY event_date")).scalars()
    ids = session.execute(text("SELECT shooter_id FROM shooter_profiles")).scalars()
    for day in days:
        _assert_name_free(client.get(f"/api/og/page/events/{day.isoformat()}").text, names)
    for shooter_id in ids:
        page = client.get(f"/api/og/page/shooters/{shooter_id}").text
        assert "Scores, trophies and stats" in page  # profiles are always generic
        _assert_name_free(page, names)
