"""The ``page_view_rollup`` job (Plan 16): once a day, fold raw page views older than about 90
days into day and week totals and delete them (domain/page_views.py), then delete page-view
rate-limit rows older than their 10-minute window (auth/ratelimit.py)."""

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import prune_page_view_attempts
from sunday_clays.config import get_settings
from sunday_clays.domain.page_views import rollup_page_views
from sunday_clays.jobs.handlers import handler

logger = logging.getLogger(__name__)


@handler("page_view_rollup")
def handle_page_view_rollup(session: Session, payload: dict[str, Any]) -> None:
    tz = get_settings().timezone
    report = rollup_page_views(session, datetime.now(ZoneInfo(tz)).date(), tz)
    # A beacon only prunes when one arrives: clear what the last burst before a quiet spell left.
    prune_page_view_attempts(session)
    logger.info("rolled up %d page views before %s", report.rolled, report.cutoff)
