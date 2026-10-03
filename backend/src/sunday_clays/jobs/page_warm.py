"""The ``page_warm`` job (Plan 19 §3.7.5, D34, D35): prune the page cache, then request the busiest
default pages through the real app, in process, as a viewer, so their bodies are stored before
the first visitor arrives. Counts are logged, never paths."""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final, cast
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import CursorResult, text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.api import page_cache as pc
from sunday_clays.api.routes._filters import latest_scored_day, today_local
from sunday_clays.auth.sessions import COOKIE_NAME, issue_session
from sunday_clays.config import Settings, get_settings
from sunday_clays.domain.features import LAST_WARM_KEY, page_cache_on
from sunday_clays.jobs.handlers import handler

logger = logging.getLogger(__name__)

WARM_BUDGET_S: Final = 180.0
RETRY_AFTER: Final = timedelta(minutes=5)
WARM_BASE_URL: Final = "http://page-warm.internal"
EIGHT_WEEK_DAYS: Final = 56  # lib/timeWindowChoice.ts
RACE_TOP: Final = 10  # features/race/labels.ts


def _months_back(anchor: date, months: int) -> date:
    """The SPA's monthsBack: anchor minus `months` calendar months (day clamped), plus one day."""
    index = anchor.year * 12 + (anchor.month - 1) - months
    year, month = divmod(index, 12)
    first_next = date(year + (month + 1) // 12, (month + 1) % 12 + 1, 1)
    last_day = (first_next - timedelta(days=1)).day
    return date(year, month + 1, min(anchor.day, last_day)) + timedelta(days=1)


def _url(path: str, **query: Any) -> str:
    """``path?sorted query``: the string the ETag and the page-cache key hash (sorted_query)."""
    items = sorted((k, str(v)) for k, v in query.items() if v is not None)
    return f"{path}?{urlencode(items)}" if items else path


def warm_targets(session: Session, settings: Settings) -> list[str]:
    """The default-page requests in order of cost x visits (§3.7.5). Each entry is read from the SPA
    code that sends it at default URL state (no `w`, no filters, so no `round_type`); the e2e pin
    test (page-cache.spec.ts) guards that they stay equal."""
    anchor = latest_scored_day(session, settings.timezone)
    latest = anchor.isoformat()
    since = (anchor - timedelta(days=EIGHT_WEEK_DAYS - 1)).isoformat()
    window = {"since": since, "as_of": latest}
    return [
        # 1 Home
        "/api/insights/home",  # insights/homeWidget -> FeedSections.HomeInsights
        f"/api/events/{latest}",  # home/api.ts (LatestEventCard)
        "/api/events",  # TurnoutChart's fullscreen/CSV fetch (no year, no window)
        _url("/api/events", **{"from": since, "to": latest}),  # lib/windowEvents.ts (ClubPulse)
        # 2 Latest Sunday
        f"/api/insights/sundays/{latest}",  # insights/api.ts
        f"/api/events/{latest}/achievements",  # achievements/api.ts
        # 3 Sundays list (the latest year)
        _url("/api/events", year=anchor.year),  # events/api.ts useEvents(year)
        # 4 Stations: stations/api.ts sends era (page default 'current') plus the window
        _url("/api/stations", era="current", **window),
        "/api/insights/stations",
        # 5 Club: features/club/api.ts
        "/api/club/trends",
        _url("/api/club/summary", **window),  # useClubSummary(range)
        "/api/club/summary",  # useClubStatusByYear (ignores the window)
        _url("/api/club/first-rounds", **{"from": since, "to": latest}),
        "/api/club/attendance",
        "/api/club/cohorts",
        _url("/api/club/distribution", by="year"),
        "/api/club/regulars",
        "/api/club/conversion",
        _url("/api/club/parity", by="year"),
        "/api/insights/club",
        # 6 Leaderboards: at the default window the board and the movers send the period only
        # (boardWindow gives since = as_of = null; LeaderboardsPage.test "'/leaderboards' asks for
        # period season and since null"), and PageInsights sends no `season` without an `as_of`.
        _url("/api/leaderboards", metric="avg_score", period="season"),
        _url("/api/leaderboards/movers", period="season"),
        "/api/insights/leaderboards",
        # 7 Race (rolling 12 months): race/api.ts historyQuery, RACE_TOP, the 12M window
        _url(
            "/api/leaderboards/history",
            period="rolling_12",
            metric="season_points",
            top=RACE_TOP,
            **{"from": _months_back(anchor, 12).isoformat(), "to": latest},
        ),
        # 8 Records: records/api.ts recordsQuery (no limit on the page's first load)
        _url("/api/records", **window),
        "/api/insights/records",
        # 9 Trophies
        "/api/achievements",
    ]


def prune(session: Session, data_version: int, local_date: date) -> int:
    """Drop rows of another data_version or local date, then the oldest beyond pc.PRUNE_TO_ROWS
    (the one constant, shared with the middleware's own prune)."""
    stale = cast(
        CursorResult[Any],
        session.execute(
            text("DELETE FROM response_cache WHERE data_version <> :dv OR local_date <> :ld"),
            {"dv": data_version, "ld": local_date},
        ),
    ).rowcount
    extra = cast(
        CursorResult[Any],
        session.execute(
            text(
                "DELETE FROM response_cache WHERE key IN ("
                "SELECT key FROM response_cache ORDER BY created_at DESC OFFSET :keep)"
            ),
            {"keep": pc.PRUNE_TO_ROWS},
        ),
    ).rowcount
    return int(stale or 0) + int(extra or 0)


@dataclass(frozen=True)
class WarmReport:
    warmed: int
    skipped: int
    failed: int
    seconds: float


_LAST_WARM = text(
    "INSERT INTO app_state (key, value) VALUES (:k, jsonb_build_object("
    "'data_version', CAST(:dv AS int), 'local_date', CAST(:ld AS text), 'finished_at', now(), "
    "'warmed', CAST(:w AS int), 'skipped', CAST(:s AS int), 'failed', CAST(:f AS int), "
    "'seconds', CAST(:secs AS float8))) "
    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
)


_HTTP_LOGGERS: Final = ("httpx", "httpx2")  # the test client logs every URL at INFO


@contextmanager
def _quiet_http_logs() -> Iterator[None]:
    """Counts are logged, never paths: mute the HTTP client's per-request INFO line."""
    loggers = [logging.getLogger(name) for name in _HTTP_LOGGERS]
    levels = [lg.level for lg in loggers]
    for lg in loggers:
        lg.setLevel(logging.WARNING)
    try:
        yield
    finally:
        for lg, level in zip(loggers, levels, strict=True):
            lg.setLevel(level)


def run_page_warm(
    session: Session,
    settings: Settings,
    app: FastAPI,
    *,
    budget_s: float = WARM_BUDGET_S,
    clock: Callable[[], float] = time.monotonic,
) -> WarmReport:
    started = clock()
    if not page_cache_on(session, settings):
        # Switched off after this job was queued: store nothing, record nothing (D36).
        return WarmReport(0, 0, 0, 0.0)
    data_version = get_data_version(session)
    local_date = today_local(settings.timezone)
    prune(session, data_version, local_date)
    targets = warm_targets(session, settings)
    # Decision 9: commit the prune so no warm request waits on a row this job deleted, and end the
    # transaction warm_targets read in, so no idle-in-transaction connection is held for the budget.
    session.commit()
    routes = pc.resolve_allowlist(app, pc.ALLOWLIST)
    client = TestClient(
        app,
        base_url=WARM_BASE_URL,
        raise_server_exceptions=False,
        cookies={COOKIE_NAME: issue_session(settings, "viewer")},
    )
    warmed = failed = skipped = 0
    with _quiet_http_logs():
        for index, target in enumerate(targets):
            if clock() - started >= budget_s:
                skipped = len(targets) - index
                break
            try:
                ok = client.get(target).status_code == 200
            except Exception:
                ok = False
            if ok:
                warmed += 1
            else:
                failed += 1
                route = pc.match_route(routes, urlsplit(target).path)
                logger.warning("page_warm: a target failed (%s)", route.template if route else "?")
    seconds = round(clock() - started, 1)
    session.execute(
        _LAST_WARM,
        {
            "k": LAST_WARM_KEY,
            "dv": data_version,
            "ld": local_date.isoformat(),
            "w": warmed,
            "s": skipped,
            "f": failed,
            "secs": seconds,
        },
    )
    logger.info(
        "page_warm: %d warmed, %d skipped, %d failed in %.1f s", warmed, skipped, failed, seconds
    )
    return WarmReport(warmed, skipped, failed, seconds)


@handler("page_warm")
def handle_page_warm(session: Session, payload: dict[str, Any]) -> None:
    from sunday_clays.api.app import create_app  # the worker builds the same app the API runs

    run_page_warm(session, get_settings(), create_app())
