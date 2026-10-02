"""Leaderboards (C7): period x metric x filters, time-sliced by ``as_of``.

Pure over the C7 frames. The only DB-facing functions are ``load_leaderboard_frames``,
``leaderboard_for`` and ``leaderboard_event_dates``, each memoized by ``data_version``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Literal

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.frames import (
    apply_round_type_filter,
    load_appearances,
    load_events,
    load_rating_history,
    load_rounds,
)
from sunday_clays.analytics.points import season_points
from sunday_clays.domain.round_type import RoundType

ShooterStatus = Literal["member", "guest", "deceased"]

ROLLING_DAYS = 364
ACTIVE_WINDOW = timedelta(days=ROLLING_DAYS)
ACTIVE_MIN_ROUNDS = 5
IMPROVED_MIN_BEFORE = 10
IMPROVED_MIN_INSIDE = 5
# Eight Sundays is a short window, so "rating gain" over the season needs only 3 rounds inside.
IMPROVED_SEASON_MIN_INSIDE = 3
SEASON_DAYS = 56
IMPROVED_ALL_TIME_MIN = 15
ROW_COLUMNS = ["rank", "shooter_id", "display_name", "status", "value", "n_rounds"]


class LeaderboardPeriod(StrEnum):
    SEASON = "season"  # rolling last 8 Sundays (56 days); never resets
    YTD = "ytd"  # 1 January of the as-of year through as-of
    ROLLING_12 = "rolling_12"
    ALL_TIME = "all_time"


class LeaderboardMetric(StrEnum):
    AVG_SCORE = "avg_score"
    AVG_ADJUSTED = "avg_adjusted"
    BEST_SCORE = "best_score"
    WINS = "wins"
    PODIUMS = "podiums"
    EVENTS = "events"
    ROUNDS = "rounds"
    RATING_GAIN = "rating_gain"  # rating now minus rating at the window's start; gainers only
    SEASON_POINTS = "season_points"


@dataclass(frozen=True)
class LeaderboardFrames:
    rounds: pd.DataFrame  # C7 load_rounds columns, event_date as datetime.date
    events: pd.DataFrame  # C7 load_events columns, event_date as datetime.date
    history: pd.DataFrame  # C7 load_rating_history columns, event_date as datetime.date
    # shooter_id, display_name, status, sort_key. sort_key spans all rounds, so boards
    # never order by it: they re-derive the D6 tie key from rounds on or before as_of.
    shooters: pd.DataFrame
    # One row per shooter per Sunday shot, special Sundays included (Plan 17): the Sundays board
    # reads it, and so does the D6 tie key of a shooter with no scored round (_tie_keys).
    # Without special Sundays it is the rounds themselves.
    appearances: pd.DataFrame


def _with_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["event_date"] = pd.to_datetime(out["event_date"]).dt.date
    return out


def _normalized_rounds(rounds: pd.DataFrame) -> pd.DataFrame:
    """Dates as ``datetime.date``; nullable loader dtypes (Int64/boolean/<NA>) as float/bool."""
    out = _with_dates(rounds)
    out["event_rank"] = pd.to_numeric(out["event_rank"], errors="coerce").astype(float)
    out["adjusted"] = pd.to_numeric(out["adjusted"], errors="coerce").astype(float)
    out["is_best_round"] = out["is_best_round"].eq(True).fillna(False).astype(bool)
    return out


def make_leaderboard_frames(
    rounds: pd.DataFrame,
    events: pd.DataFrame,
    history: pd.DataFrame,
    appearances: pd.DataFrame | None = None,
) -> LeaderboardFrames:
    dated = _normalized_rounds(rounds)
    seen = dated if appearances is None else _with_dates(appearances)
    names = seen.groupby("shooter_id", as_index=False).agg(
        display_name=("display_name", "first"),
        status=("shooter_status", "first"),
    )
    shooters = names.merge(_tie_keys(dated, seen), on="shooter_id", how="left")
    return LeaderboardFrames(
        rounds=dated,
        events=_with_dates(events),
        history=_with_dates(history),
        shooters=shooters,
        appearances=seen,
    )


def scored_event_dates(events: pd.DataFrame) -> list[date]:
    return sorted(set(events.loc[events["has_scores"].eq(True), "event_date"]))


def period_bounds(
    period: LeaderboardPeriod, as_of: date, since: date | None = None
) -> tuple[date | None, date]:
    """The window's inclusive bounds. A custom ``since`` replaces the period's start.

    Callers must pass ``since <= as_of`` (the API routes reject anything else with a 400).
    """
    if since is not None:
        return since, as_of
    if period is LeaderboardPeriod.SEASON:
        return as_of - timedelta(days=SEASON_DAYS - 1), as_of
    if period is LeaderboardPeriod.YTD:
        return date(as_of.year, 1, 1), as_of
    if period is LeaderboardPeriod.ROLLING_12:
        return as_of - timedelta(days=ROLLING_DAYS - 1), as_of
    return None, as_of


def scaled_min_rounds(events: pd.DataFrame, period: LeaderboardPeriod, as_of: date) -> int:
    """Season/YTD average-board minimum: min(5, max(1, ceil(0.4 * E))), E = scored Sundays in it."""
    start, end = period_bounds(period, as_of)
    in_window = events[
        events["has_scores"].eq(True)
        & (events["event_date"] >= start)
        & (events["event_date"] <= end)
    ]
    n_events = int(in_window["event_date"].nunique())
    return min(5, max(1, math.ceil(0.4 * n_events)))


def custom_min_rounds(events: pd.DataFrame, since: date, as_of: date) -> int:
    """Average-board minimum for a custom range: min(15, max(1, min(5, ceil(.4n)), ceil(.15n))).

    ``n`` is the number of scored Sundays in ``[since, as_of]``; integer ceilings avoid float
    rounding at the boundaries.
    """
    in_range = events[
        events["has_scores"].eq(True)
        & (events["event_date"] >= since)
        & (events["event_date"] <= as_of)
    ]
    n = int(in_range["event_date"].nunique())
    return min(15, max(1, min(5, -(-2 * n // 5)), -(-3 * n // 20)))


_AVERAGE_MIN_ROUNDS = {LeaderboardPeriod.ROLLING_12: 8, LeaderboardPeriod.ALL_TIME: 15}


def rating_gain_inside_min(period: LeaderboardPeriod) -> int:
    """Rounds a shooter needs inside a (non-custom) window for the rating-gain board.

    The season is only 8 Sundays, so it asks for 3; YTD and rolling 12 months keep 5.
    """
    return IMPROVED_SEASON_MIN_INSIDE if period is LeaderboardPeriod.SEASON else IMPROVED_MIN_INSIDE


def canonical_window(
    period: LeaderboardPeriod, as_of: date, since: date | None
) -> tuple[LeaderboardPeriod, date | None]:
    """A ``since`` that is exactly the start of YTD, the season or rolling 12 is that period.

    So a custom range from 1 January gives the same board, with the same minimum rounds, as YTD.
    Any other ``since`` stays a custom start (the period is then ignored).
    """
    if since is None:
        return period, None
    for named in (LeaderboardPeriod.YTD, LeaderboardPeriod.SEASON, LeaderboardPeriod.ROLLING_12):
        if period_bounds(named, as_of)[0] == since:
            return named, None
    return period, since


def min_rounds_for(
    metric: LeaderboardMetric,
    period: LeaderboardPeriod,
    events: pd.DataFrame,
    as_of: date,
    since: date | None = None,
) -> int:
    if since is not None:
        if metric in (LeaderboardMetric.AVG_SCORE, LeaderboardMetric.AVG_ADJUSTED):
            return custom_min_rounds(events, since, as_of)
        if metric is LeaderboardMetric.RATING_GAIN:
            return IMPROVED_MIN_INSIDE
        return 1
    if metric in (LeaderboardMetric.AVG_SCORE, LeaderboardMetric.AVG_ADJUSTED):
        if period in (LeaderboardPeriod.SEASON, LeaderboardPeriod.YTD):
            return scaled_min_rounds(events, period, as_of)
        return _AVERAGE_MIN_ROUNDS[period]
    if metric is LeaderboardMetric.RATING_GAIN:
        if period is LeaderboardPeriod.ALL_TIME:
            return IMPROVED_ALL_TIME_MIN
        return rating_gain_inside_min(period)
    return 1


@dataclass(frozen=True)
class LeaderboardFilters:
    round_types: tuple[RoundType, ...] = ()
    gauge: str | None = None
    status: ShooterStatus | None = None


NO_FILTERS = LeaderboardFilters()


@dataclass(frozen=True)
class LeaderboardRow:
    rank: int
    shooter_id: int
    display_name: str
    status: str | None
    value: float
    n_rounds: int


@dataclass(frozen=True)
class Leaderboard:
    period: LeaderboardPeriod
    metric: LeaderboardMetric
    as_of: date
    min_rounds_applied: int
    rows: pd.DataFrame  # ROW_COLUMNS, best first
    since: date | None = None

    @property
    def start(self) -> date | None:
        """First day the board counts (``None`` = from the beginning); the last day is ``as_of``."""
        return period_bounds(self.period, self.as_of, self.since)[0]

    @property
    def n_eligible(self) -> int:
        return len(self.rows)

    def records(self, top: int | None = None) -> list[LeaderboardRow]:
        frame = self.rows if top is None else self.rows.head(top)
        return [
            LeaderboardRow(
                rank=int(rec["rank"]),
                shooter_id=int(rec["shooter_id"]),
                display_name=str(rec["display_name"]),
                status=None if pd.isna(rec["status"]) else str(rec["status"]),
                value=float(rec["value"]),
                n_rounds=int(rec["n_rounds"]),
            )
            for rec in frame.to_dict("records")
        ]


def _window(df: pd.DataFrame, start: date | None, end: date) -> pd.DataFrame:
    mask = df["event_date"] <= end
    if start is not None:
        mask &= df["event_date"] >= start
    return df[mask]


def _round_filters(rounds: pd.DataFrame, filters: LeaderboardFilters) -> pd.DataFrame:
    out = apply_round_type_filter(rounds, filters.round_types)
    if filters.gauge is not None:
        out = out[out["gauge"] == filters.gauge]
    return out


def _agg(rounds: pd.DataFrame, column: str, how: str) -> pd.DataFrame:
    return rounds.groupby("shooter_id", as_index=False).agg(
        value=(column, how), n_rounds=(column, "size")
    )


def _avg_score(rounds: pd.DataFrame) -> pd.DataFrame:
    return _agg(rounds, "score", "mean")


def _avg_adjusted(rounds: pd.DataFrame) -> pd.DataFrame:
    return _agg(rounds[rounds["adjusted"].notna()], "adjusted", "mean")


def _best_score(rounds: pd.DataFrame) -> pd.DataFrame:
    return _agg(rounds, "score", "max")


def _events(rounds: pd.DataFrame) -> pd.DataFrame:
    # The count column reads "Sundays" on this board: the Sunday count, not the round count.
    body = _agg(rounds, "event_date", "nunique")
    return body.assign(n_rounds=body["value"].astype(int))


def _rounds(rounds: pd.DataFrame) -> pd.DataFrame:
    return _agg(rounds, "score", "size")


def _finishes(rounds: pd.DataFrame, max_rank: int) -> pd.DataFrame:
    hit = rounds["is_best_round"].eq(True) & rounds["event_rank"].le(max_rank)
    return _agg(rounds.assign(finish=hit.astype(int)), "finish", "sum")


def _wins(rounds: pd.DataFrame) -> pd.DataFrame:
    return _finishes(rounds, 1)


def _podiums(rounds: pd.DataFrame) -> pd.DataFrame:
    return _finishes(rounds, 3)


ROUND_METRICS: dict[LeaderboardMetric, Callable[[pd.DataFrame], pd.DataFrame]] = {
    LeaderboardMetric.AVG_SCORE: _avg_score,
    LeaderboardMetric.AVG_ADJUSTED: _avg_adjusted,
    LeaderboardMetric.BEST_SCORE: _best_score,
    LeaderboardMetric.WINS: _wins,
    LeaderboardMetric.PODIUMS: _podiums,
    LeaderboardMetric.EVENTS: _events,
    LeaderboardMetric.ROUNDS: _rounds,
    LeaderboardMetric.SEASON_POINTS: season_points,
}


def _tie_keys(
    rounds: pd.DataFrame, appearances: pd.DataFrame, as_of: date | None = None
) -> pd.DataFrame:
    """shooter_id, sort_key: the D6 tie key (smallest ``name_key``) from scored rounds; only a
    shooter with no scored round (special Sundays only, Plan 17) takes it from appearances.

    A special sheet's spelling (say an alias-ruled first name that sorts first) therefore never
    reorders tied rows on a score board or on the Sundays board.
    """
    if as_of is not None:
        rounds = rounds[rounds["event_date"] <= as_of]
        appearances = appearances[appearances["event_date"] <= as_of]
    scored = rounds.groupby("shooter_id", as_index=False).agg(sort_key=("name_key", "min"))
    seen = appearances.groupby("shooter_id", as_index=False).agg(sort_key=("name_key", "min"))
    only_seen = seen[~seen["shooter_id"].isin(scored["shooter_id"])]
    return pd.concat([scored, only_seen], ignore_index=True)


def _shooters_as_of(frames: LeaderboardFrames, as_of: date) -> pd.DataFrame:
    """``frames.shooters`` with the D6 tie key taken from rounds (appearances for a shooter with
    none) on or before ``as_of`` only.

    C7 no-leak: a later round (say under an alias merged in afterwards, whose ``name_key``
    sorts first) must never reorder tied rows on a past board or move a top-N cut.
    """
    keys = _tie_keys(frames.rounds, frames.appearances, as_of)
    return frames.shooters.drop(columns="sort_key").merge(keys, on="shooter_id", how="left")


def _finalize(
    body: pd.DataFrame, shooters: pd.DataFrame, min_rounds: int, status: str | None
) -> pd.DataFrame:
    rows = body[body["n_rounds"] >= min_rounds].merge(shooters, on="shooter_id", how="left")
    if status is not None:
        rows = rows[rows["status"] == status]
    rows = rows.assign(value=rows["value"].astype(float).round(2))
    rows = rows.sort_values(
        ["value", "sort_key", "shooter_id"], ascending=[False, True, True], kind="mergesort"
    )
    rows = rows.assign(rank=rows["value"].rank(method="min", ascending=False).astype(int))
    return rows[ROW_COLUMNS].reset_index(drop=True)


def active_shooter_ids(rounds: pd.DataFrame, as_of: date) -> set[int]:
    """Shooters with >=1 round in (as_of - 364d, as_of] and >=5 rounds <= as_of."""
    upto = rounds.loc[rounds["event_date"] <= as_of]
    counts = upto["shooter_id"].value_counts()
    eligible = {int(s) for s in counts[counts >= ACTIVE_MIN_ROUNDS].index.tolist()}
    recent = {int(s) for s in upto.loc[upto["event_date"] > as_of - ACTIVE_WINDOW, "shooter_id"]}
    return eligible & recent


def _rating_gain(
    frames: LeaderboardFrames,
    period: LeaderboardPeriod,
    as_of: date,
    since: date | None = None,
) -> pd.DataFrame:
    rounds = frames.rounds[frames.rounds["event_date"] <= as_of]
    history = frames.history[frames.history["event_date"] <= as_of].sort_values(
        ["shooter_id", "event_date"], kind="mergesort"
    )
    end_mu = history.groupby("shooter_id")["mu"].last()
    start, _ = period_bounds(period, as_of, since)
    inside_min = IMPROVED_MIN_INSIDE if since is not None else rating_gain_inside_min(period)
    if start is None:
        ordered = rounds.sort_values(["shooter_id", "event_date", "ordinal"], kind="mergesort")
        nth = ordered.assign(k=ordered.groupby("shooter_id").cumcount() + 1)
        tenth = nth.loc[nth["k"] == IMPROVED_MIN_BEFORE, ["shooter_id", "event_date"]]
        start_mu = tenth.merge(history, on=["shooter_id", "event_date"]).set_index("shooter_id")[
            "mu"
        ]
        n_rounds = rounds.groupby("shooter_id").size()
        eligible = set(n_rounds[n_rounds >= IMPROVED_ALL_TIME_MIN].index)
    else:
        n_before = rounds[rounds["event_date"] < start].groupby("shooter_id").size()
        n_rounds = rounds[rounds["event_date"] >= start].groupby("shooter_id").size()
        start_mu = history[history["event_date"] < start].groupby("shooter_id")["mu"].last()
        eligible = set(n_before[n_before >= IMPROVED_MIN_BEFORE].index) & set(
            n_rounds[n_rounds >= inside_min].index
        )
    delta = (end_mu - start_mu).dropna()
    delta = delta[delta.index.isin(sorted(eligible))]
    return pd.DataFrame(
        {
            "shooter_id": delta.index.astype(int),
            "value": delta.to_numpy(dtype=float),
            "n_rounds": [int(n_rounds[sid]) for sid in delta.index],
        }
    )


def leaderboard(
    frames: LeaderboardFrames,
    period: LeaderboardPeriod,
    metric: LeaderboardMetric,
    as_of: date,
    filters: LeaderboardFilters = NO_FILTERS,
    *,
    since: date | None = None,
) -> Leaderboard:
    """Callers must pass ``since <= as_of``; ``since`` replaces the period's start."""
    period, since = canonical_window(period, as_of, since)
    min_rounds = min_rounds_for(metric, period, frames.events, as_of, since)
    if metric is LeaderboardMetric.RATING_GAIN:
        gains = _rating_gain(frames, period, as_of, since)
        body = gains[gains["value"] > 0]  # only gainers: a positive-only board
    elif metric is LeaderboardMetric.EVENTS and filters.gauge is None:
        # Sundays shot, special Sundays included (Plan 17); a gauge filter counts scored Sundays
        start, end = period_bounds(period, as_of, since)
        seen = _window(frames.appearances, start, end)
        body = _events(apply_round_type_filter(seen, filters.round_types))
    else:
        start, end = period_bounds(period, as_of, since)
        body = ROUND_METRICS[metric](_round_filters(_window(frames.rounds, start, end), filters))
    rows = _finalize(body, _shooters_as_of(frames, as_of), min_rounds, filters.status)
    return Leaderboard(period, metric, as_of, min_rounds, rows, since)


@cached_by_data_version
def load_leaderboard_frames(session: Session) -> LeaderboardFrames:
    return make_leaderboard_frames(
        load_rounds(session),
        load_events(session),
        load_rating_history(session),
        load_appearances(session),
    )


@cached_by_data_version
def leaderboard_for(
    session: Session,
    period: LeaderboardPeriod,
    metric: LeaderboardMetric,
    as_of: date,
    filters: LeaderboardFilters,
    since: date | None = None,
) -> Leaderboard:
    return leaderboard(
        load_leaderboard_frames(session), period, metric, as_of, filters, since=since
    )


@cached_by_data_version
def leaderboard_event_dates(session: Session) -> tuple[date, ...]:
    """Every has_scores event date, ascending (a small memo: hits never copy the frames)."""
    return tuple(scored_event_dates(load_leaderboard_frames(session).events))
