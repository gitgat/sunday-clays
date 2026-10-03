"""page_warm (Plan 19 §3.7.5, D34, D35; §5.1, §5.2)."""

import logging
import time
from datetime import date
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.api import page_cache as pc
from sunday_clays.api.routes import _filters
from sunday_clays.config import get_settings
from sunday_clays.domain.features import LAST_WARM_KEY
from sunday_clays.jobs import page_warm


@pytest.fixture
def cache_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
    get_settings.cache_clear()


def _put(session: Session, key: str, data_version: int, local_date: str) -> None:
    session.execute(
        text(
            "INSERT INTO response_cache"
            " (key, data_version, local_date, app_version, role, route, body)"
            " VALUES (:k, :dv, CAST(:ld AS date), 'dev', 'viewer', '/api/meta', '{}')"
        ),
        {"k": key, "dv": data_version, "ld": local_date},
    )


def _count(session: Session) -> int:
    return int(session.execute(text("SELECT count(*) FROM response_cache")).scalar_one())


def test_targets_follow_the_spa_defaults(fx_session: Session, test_settings: Any) -> None:
    targets = page_warm.warm_targets(fx_session, get_settings())
    assert targets[0] == "/api/insights/home"
    assert "/api/events/2026-09-27" in targets[:4]
    assert "/api/records?as_of=2026-09-27&since=2026-08-03" in targets
    assert "/api/stations?as_of=2026-09-27&era=current&since=2026-08-03" in targets
    assert "/api/leaderboards?metric=avg_score&period=season" in targets
    assert "/api/leaderboards/movers?period=season" in targets
    assert "/api/insights/leaderboards" in targets  # no season= at the default URL state
    assert (
        "/api/leaderboards/history?from=2025-09-28&metric=season_points&period=rolling_12"
        "&to=2026-09-27&top=10"
    ) in targets
    routes = pc.resolve_allowlist(cast(FastAPI, _app()), pc.ALLOWLIST)
    for target in targets:
        assert pc.match_route(routes, urlsplit(target).path) is not None, target
    assert len(targets) == len(set(targets))


def test_months_back_matches_the_spa() -> None:
    assert page_warm._months_back(date(2026, 9, 27), 12) == date(2025, 9, 28)
    assert page_warm._months_back(date(2026, 3, 31), 1) == date(2026, 3, 1)  # Feb 28 + 1 day


def test_prune_drops_other_versions_and_dates_then_the_oldest(
    fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pc, "PRUNE_TO_ROWS", 2)
    _put(fx_session, "old-version", 1, "2026-10-02")
    _put(fx_session, "old-date", 7, "2026-10-01")
    for i in range(3):
        _put(fx_session, f"keep-{i}", 7, "2026-10-02")
        fx_session.execute(
            text(
                "UPDATE response_cache SET created_at = now() + make_interval(secs => :s)"
                " WHERE key = :k"
            ),
            {"s": i, "k": f"keep-{i}"},
        )
    deleted = page_warm.prune(fx_session, 7, date(2026, 10, 2))
    assert deleted == 3
    keys = set(fx_session.execute(text("SELECT key FROM response_cache")).scalars())
    assert keys == {"keep-1", "keep-2"}  # the oldest current row went last


def _app() -> FastAPI:
    from sunday_clays.api.app import create_app

    return create_app()


def test_warm_stores_every_target_then_each_is_a_hit_with_the_same_body(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = cast(FastAPI, fx_viewer_client.app)
    report = page_warm.run_page_warm(fx_session, get_settings(), app)
    targets = page_warm.warm_targets(fx_session, get_settings())
    assert (report.warmed, report.skipped, report.failed) == (len(targets), 0, 0)
    assert _count(fx_session) == len(targets)
    for target in targets:
        hit = fx_viewer_client.get(target)
        assert hit.headers["x-page-cache"] == "hit", target
        monkeypatch.setenv("PAGE_CACHE_ENABLED", "false")
        get_settings.cache_clear()
        assert fx_viewer_client.get(target).content == hit.content, target
        monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
        get_settings.cache_clear()
    last = fx_session.execute(
        text("SELECT value FROM app_state WHERE key = :k"), {"k": LAST_WARM_KEY}
    ).scalar_one()
    assert last["data_version"] == get_data_version(fx_session)
    assert last["local_date"] == _filters.today_local(get_settings().timezone).isoformat()
    assert last["warmed"] == len(targets)
    assert last["failed"] == 0


def test_a_zero_budget_skips_everything_and_still_completes(
    cache_on: None, fx_viewer_client: TestClient, fx_session: Session
) -> None:
    report = page_warm.run_page_warm(
        fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app), budget_s=0
    )
    assert report.warmed == 0
    assert report.skipped == len(page_warm.warm_targets(fx_session, get_settings()))
    assert _count(fx_session) == 0


def test_a_failing_target_is_counted_and_the_rest_still_warm(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        page_warm,
        "warm_targets",
        lambda _s, _settings: ["/api/events", "/api/events/2026-13-45", "/api/records"],
    )
    report = page_warm.run_page_warm(
        fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app)
    )
    assert (report.warmed, report.failed) == (2, 1)
    assert "/api/events/{date}" in caplog.text
    assert "2026-13-45" not in caplog.text


@pytest.mark.slow
def test_loose_ceilings(cache_on: None, fx_viewer_client: TestClient, fx_session: Session) -> None:
    """Memory: perf tests only catch gross regressions on any runner."""
    started = time.monotonic()
    page_warm.run_page_warm(fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app))
    assert time.monotonic() - started < 120
    for target in page_warm.warm_targets(fx_session, get_settings()):
        hit_started = time.monotonic()
        fx_viewer_client.get(target)
        assert time.monotonic() - hit_started < 2, target


def test_last_warm_row_validates_as_the_admin_status_shape(
    cache_on: None, fx_viewer_client: TestClient, fx_session: Session
) -> None:
    from sunday_clays.api.routes.admin_page_cache import LastWarmOut

    page_warm.run_page_warm(fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app))
    raw = fx_session.execute(
        text("SELECT value FROM app_state WHERE key = :k"), {"k": LAST_WARM_KEY}
    ).scalar_one()
    assert LastWarmOut.model_validate(raw).failed == 0


def test_a_switched_off_cache_is_a_clean_no_op(
    cache_on: None, fx_viewer_client: TestClient, fx_session: Session
) -> None:
    """Kills: warming (and storing rows) after the page_cache switch was turned off while a
    page_warm job sat in the queue."""
    from sunday_clays.domain.features import set_switch

    set_switch(fx_session, get_settings(), "page_cache", False)
    report = page_warm.run_page_warm(
        fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app)
    )
    assert (report.warmed, report.skipped, report.failed) == (0, 0, 0)
    assert _count(fx_session) == 0
    assert (
        fx_session.execute(
            text("SELECT count(*) FROM app_state WHERE key = :k"), {"k": LAST_WARM_KEY}
        ).scalar_one()
        == 0
    )


def test_the_setting_false_is_a_clean_no_op(
    fx_viewer_client: TestClient, fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "false")
    get_settings.cache_clear()
    report = page_warm.run_page_warm(
        fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app)
    )
    assert (report.warmed, report.skipped, report.failed) == (0, 0, 0)
    assert _count(fx_session) == 0


def test_warming_stores_only_viewer_rows(
    cache_on: None, fx_viewer_client: TestClient, fx_session: Session
) -> None:
    """Kills: warming as admin, which would store admin-role bodies (or none for viewers)."""
    page_warm.run_page_warm(fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app))
    roles = set(fx_session.execute(text("SELECT DISTINCT role FROM response_cache")).scalars())
    assert roles == {"viewer"}


class _Flaky(TestClient):
    """A client whose `/api/events` request raises and whose `/api/club/trends` answers 500."""

    def get(self, url: Any, *args: Any, **kwargs: Any) -> Any:
        if str(url) == "/api/events":
            raise RuntimeError("boom /api/events")
        if str(url) == "/api/club/trends":
            return httpx.Response(500)
        return super().get(url, *args, **kwargs)


def test_a_raising_or_500_target_counts_as_failed_and_logs_no_path(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills: aborting the job on the first exception, counting a 500 as warmed, and logging the
    exception message (which can carry a path); the route template is logged, never the path."""
    monkeypatch.setattr(page_warm, "TestClient", _Flaky)
    monkeypatch.setattr(
        page_warm,
        "warm_targets",
        lambda _s, _settings: ["/api/events", "/api/club/trends", "/api/records"],
    )
    with caplog.at_level(logging.WARNING, logger="sunday_clays.jobs.page_warm"):
        report = page_warm.run_page_warm(
            fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app)
        )
    assert (report.warmed, report.failed) == (1, 2)
    assert "RuntimeError" in caplog.text
    assert "status 500" in caplog.text
    assert "boom" not in caplog.text
