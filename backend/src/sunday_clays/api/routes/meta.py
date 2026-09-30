"""GET /api/meta: data_version, date range and live-table counts."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from sunday_clays.analytics import cache
from sunday_clays.api.routes._filters import LAST_SCORE_DATE_SQL
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep

router = APIRouter()

_COUNTS_SQL = """
SELECT
  (SELECT min(event_date) FROM events) AS first_event_date,
  (SELECT max(event_date) FROM events) AS last_event_date,
  (SELECT min(event_date) FROM events WHERE has_scores) AS first_score_date,
  (__LAST_SCORE__) AS last_score_date,
  (SELECT count(*) FROM events) AS n_events,
  (SELECT count(*) FROM events WHERE has_scores) AS n_scored_events,
  (SELECT count(*) FROM events WHERE results_complete) AS n_held_events,
  (SELECT count(*) FROM events WHERE has_stations) AS n_station_events,
  (SELECT count(*) FROM rounds) AS n_rounds,
  (SELECT count(*) FROM shooter_profiles) AS n_shooters,
  (SELECT value #>> '{}' FROM app_state WHERE key = 'last_rebuild_at')
    AS last_rebuild_at
""".replace("__LAST_SCORE__", LAST_SCORE_DATE_SQL)


class MetaOut(BaseModel):
    app_version: str
    data_version: int
    first_event_date: date | None
    last_event_date: date | None
    first_score_date: date | None
    last_score_date: date | None
    n_events: int
    n_scored_events: int
    n_held_events: int
    n_station_events: int
    n_rounds: int
    n_shooters: int
    last_rebuild_at: datetime | None


@router.get("/api/meta")
def get_meta(session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]) -> MetaOut:
    row = session.execute(text(_COUNTS_SQL)).mappings().one()
    return MetaOut(
        app_version=settings.app_version, data_version=cache.read_data_version(session), **row
    )
