"""Leaderboard time machine (C8 ``/api/leaderboards/history``).

One frame per has_scores event in [date_from, date_to]; each frame is the top-N rows of
``leaderboard(period, metric, as_of=event_date, same filters)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.leaderboards import (
    NO_FILTERS,
    LeaderboardFilters,
    LeaderboardFrames,
    LeaderboardMetric,
    LeaderboardPeriod,
    LeaderboardRow,
    leaderboard,
    load_leaderboard_frames,
    scored_event_dates,
)


@dataclass(frozen=True)
class HistoryFrame:
    event_date: date
    rows: tuple[LeaderboardRow, ...]


def history_dates(events: pd.DataFrame, date_from: date, date_to: date) -> list[date]:
    return [d for d in scored_event_dates(events) if date_from <= d <= date_to]


def leaderboard_history(
    frames: LeaderboardFrames,
    period: LeaderboardPeriod,
    metric: LeaderboardMetric,
    *,
    top: int,
    date_from: date,
    date_to: date,
    filters: LeaderboardFilters = NO_FILTERS,
    since: date | None = None,
) -> tuple[HistoryFrame, ...]:
    """Frames per scored Sunday; a ``since`` makes every board cover ``[since, frame Sunday]``."""
    return tuple(
        HistoryFrame(
            event_date=day,
            rows=tuple(leaderboard(frames, period, metric, day, filters, since=since).records(top)),
        )
        for day in history_dates(frames.events, date_from, date_to)
    )


@cached_by_data_version
def leaderboard_history_for(
    session: Session,
    period: LeaderboardPeriod,
    metric: LeaderboardMetric,
    top: int,
    date_from: date,
    date_to: date,
    filters: LeaderboardFilters,
    since: date | None = None,
) -> tuple[HistoryFrame, ...]:
    return leaderboard_history(
        load_leaderboard_frames(session),
        period,
        metric,
        top=top,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
        since=since,
    )
