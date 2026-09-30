"""Shared query parameters and date helpers for read routes (skipped by discovery)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.domain.errors import DomainError

#: The latest Sunday with scores; /api/meta and every "latest scored Sunday" default share it.
LAST_SCORE_DATE_SQL = "SELECT max(event_date) FROM events WHERE has_scores"

round_type_param = Query(default=[], alias="round_type")


def today_local(tz: str) -> date:
    """Today's date in the club's timezone (C2 `settings.timezone`)."""
    return datetime.now(ZoneInfo(tz)).date()


def resolve_as_of(as_of: date | None, tz: str) -> date:
    """C7: `as_of=None` means today in the club timezone (before any cached call)."""
    return as_of if as_of is not None else today_local(tz)


def latest_scored_day(session: Session, tz: str) -> date:
    """The latest Sunday with scores: the "today" of every server default (falls back to today)."""
    latest = session.execute(text(LAST_SCORE_DATE_SQL)).scalar()
    return latest if latest is not None else today_local(tz)


def check_window(since: date | None, as_of: date | None) -> None:
    """A window whose start is after its end is a client error, never an empty answer."""
    if since is not None and as_of is not None and since > as_of:
        raise DomainError("invalid_range", "'since' must be on or before 'as_of'")


def in_window(frame: pd.DataFrame, since: date | None, as_of: date | None) -> pd.DataFrame:
    """Rows whose `event_date` is in [since, as_of]; a missing end is open."""
    keep = pd.Series(True, index=frame.index)
    if since is not None:
        keep &= frame["event_date"] >= since
    if as_of is not None:
        keep &= frame["event_date"] <= as_of
    return frame.loc[keep]
