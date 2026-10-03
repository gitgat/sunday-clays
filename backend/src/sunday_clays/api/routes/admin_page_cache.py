"""GET /api/admin/page-cache (Plan 19 §3.7.6): what the page cache holds and when it last warmed."""

import logging
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError
from sqlalchemy import text

from sunday_clays.analytics.cache import read_data_version
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import LAST_WARM_KEY, page_cache_on
from sunday_clays.jobs.page_warm import warm_targets

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


class LastWarmOut(BaseModel):
    data_version: int
    local_date: date
    finished_at: datetime
    warmed: int
    skipped: int
    failed: int
    seconds: float


class CurrentKeyOut(BaseModel):
    data_version: int
    local_date: date


class PageCacheStatusOut(BaseModel):
    enabled: bool  # the switch and PAGE_CACHE_ENABLED both on
    forced_off: bool  # PAGE_CACHE_ENABLED is false
    rows: int
    bytes: int
    last_warm: LastWarmOut | None
    current: CurrentKeyOut
    targets: list[str]  # warm_targets(): what page_warm requests


def _last_warm(raw: object) -> LastWarmOut | None:
    """The stored last warm-up; a missing or malformed row reads as None (never a 500)."""
    if raw is None:
        return None
    try:
        return LastWarmOut.model_validate(raw)
    except ValidationError:
        logger.warning("page_cache.last_warm row is malformed; reporting no warm-up")
        return None


@router.get("/page-cache")
def get_page_cache_status(
    session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> PageCacheStatusOut:
    rows, size = session.execute(
        text("SELECT count(*), coalesce(sum(octet_length(body)), 0) FROM response_cache")
    ).one()
    raw = session.execute(
        text("SELECT value FROM app_state WHERE key = :k"), {"k": LAST_WARM_KEY}
    ).scalar()
    return PageCacheStatusOut(
        enabled=page_cache_on(session, settings),
        forced_off=not settings.page_cache_enabled,
        rows=int(rows),
        bytes=int(size),
        last_warm=_last_warm(raw),
        current=CurrentKeyOut(
            data_version=read_data_version(session),
            local_date=_filters.today_local(settings.timezone),
        ),
        targets=warm_targets(session, settings),
    )
