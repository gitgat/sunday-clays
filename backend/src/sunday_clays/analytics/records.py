"""Club records (Plan 09 T3): pure over the C7 frames, round-type filtered, sliced by as_of."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.frames import (
    apply_round_type_filter,
    load_appearances,
    load_calendar,
    load_events,
    load_rating_history,
    load_rounds,
)
from sunday_clays.analytics.streaks import streaks
from sunday_clays.domain.round_type import RoundType

RECORD_LIMIT = 10
PERFECT_SCORE = 50
# A rating peak only counts once the shooter has shot this many rounds (the Rating board's rule).
RATING_MIN_ROUNDS = 5


@dataclass(frozen=True)
class RoundRecord:
    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    value: float


@dataclass(frozen=True)
class JumpRecord:
    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    prev_event_date: date
    from_score: int
    to_score: int
    value: float


@dataclass(frozen=True)
class ShooterRecord:
    rank: int
    shooter_id: int
    display_name: str
    value: float


@dataclass(frozen=True)
class RatingRecord:
    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    value: float


@dataclass(frozen=True)
class Records:
    as_of: date
    highest_scores: tuple[RoundRecord, ...]
    perfect_rounds: tuple[RoundRecord, ...]
    biggest_adjusted: tuple[RoundRecord, ...]
    biggest_jumps: tuple[JumpRecord, ...]
    most_events: tuple[ShooterRecord, ...]
    longest_streaks: tuple[ShooterRecord, ...]
    highest_ratings: tuple[RatingRecord, ...]
    since: date | None = None
    # Per list: every row that qualifies (before the limit), and how many rows beyond the limit
    # share the last listed value ("3 more tied at 49"). Keys are the seven list names.
    totals: dict[str, int] = field(default_factory=dict)
    tied_more: dict[str, int] = field(default_factory=dict)


def _with_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["event_date"] = pd.to_datetime(out["event_date"]).dt.date
    return out


@dataclass(frozen=True)
class Ranked:
    """One list: its rows (at most ``limit``), the rows that qualify, the tie cut by the limit."""

    rows: list[dict[Any, Any]]
    total: int
    tied_more: int


def _ranked(
    df: pd.DataFrame, order: list[str], limit: int | None, *, newest_first: bool = False
) -> Ranked:
    """Sort by ``order`` (first key descending, the rest ascending), min-rank on value.

    ``newest_first`` sorts the ``event_date`` key descending too (the perfect-50s list).
    """
    ascending = [False] + [True] * (len(order) - 1)
    if newest_first:
        ascending[order.index("event_date")] = False
    out = df.assign(value=df["value"].astype(float).round(2))
    out = out.sort_values(order, ascending=ascending, kind="mergesort")
    out = out.assign(rank=out["value"].rank(method="min", ascending=False).astype(int))
    total = len(out)
    if limit is None or total <= limit:
        return Ranked(out.to_dict("records"), total, 0)
    kept, rest = out.head(limit), out.iloc[limit:]
    tied = int(rest["value"].eq(kept["value"].iloc[-1]).sum()) if limit > 0 else 0
    return Ranked(kept.to_dict("records"), total, tied)


def _round_records(
    rounds: pd.DataFrame,
    values: pd.Series,
    names: pd.DataFrame,
    limit: int | None,
    *,
    newest_first: bool = False,
) -> tuple[tuple[RoundRecord, ...], int, int]:
    df = rounds[["shooter_id", "event_date", "ordinal"]].assign(value=values.to_numpy())
    df = df.merge(names, on="shooter_id", how="left")
    ranked = _ranked(
        df, ["value", "event_date", "sort_key", "ordinal"], limit, newest_first=newest_first
    )
    rows = tuple(
        RoundRecord(
            rank=int(r["rank"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            event_date=r["event_date"],
            value=float(r["value"]),
        )
        for r in ranked.rows
    )
    return rows, ranked.total, ranked.tied_more


def _shooter_records(
    values: pd.DataFrame, names: pd.DataFrame, limit: int | None
) -> tuple[tuple[ShooterRecord, ...], int, int]:
    df = values.merge(names, on="shooter_id", how="left")
    ranked = _ranked(df, ["value", "sort_key", "shooter_id"], limit)
    rows = tuple(
        ShooterRecord(
            rank=int(r["rank"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            value=float(r["value"]),
        )
        for r in ranked.rows
    )
    return rows, ranked.total, ranked.tied_more


def _jumps(
    rounds: pd.DataFrame, events: pd.DataFrame, names: pd.DataFrame, limit: int | None
) -> tuple[tuple[JumpRecord, ...], int, int]:
    order = sorted(set(events.loc[events["has_scores"].eq(True), "event_date"]))
    position = {day: i for i, day in enumerate(order)}
    best = rounds.groupby(["shooter_id", "event_date"], as_index=False).agg(score=("score", "max"))
    best = best[best["event_date"].isin(order)]
    best = best.assign(pos=best["event_date"].map(position)).sort_values(
        ["shooter_id", "pos"], kind="mergesort"
    )
    by_shooter = best.groupby("shooter_id")
    best = best.assign(
        prev_pos=by_shooter["pos"].shift(),
        prev_score=by_shooter["score"].shift(),
        prev_date=by_shooter["event_date"].shift(),
    )
    jumps = best[(best["pos"] - best["prev_pos"]).eq(1)]
    jumps = jumps.assign(value=jumps["score"] - jumps["prev_score"])
    jumps = jumps[jumps["value"] > 0].merge(names, on="shooter_id", how="left")
    ranked = _ranked(jumps, ["value", "event_date", "sort_key", "shooter_id"], limit)
    rows = tuple(
        JumpRecord(
            rank=int(r["rank"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            event_date=r["event_date"],
            prev_event_date=r["prev_date"],
            from_score=int(r["prev_score"]),
            to_score=int(r["score"]),
            value=float(r["value"]),
        )
        for r in ranked.rows
    )
    return rows, ranked.total, ranked.tied_more


def _highest_ratings(
    history: pd.DataFrame, rounds: pd.DataFrame, names: pd.DataFrame, limit: int | None
) -> tuple[tuple[RatingRecord, ...], int, int]:
    """Each shooter's peak rating, from the Sunday of their 5th round on (any round type)."""
    per_day = rounds.groupby(["shooter_id", "event_date"], as_index=False).size()
    per_day["seen"] = per_day.groupby("shooter_id")["size"].cumsum()
    seasoned = history.merge(
        per_day[["shooter_id", "event_date", "seen"]], on=["shooter_id", "event_date"]
    )
    seasoned = seasoned[seasoned["seen"] >= RATING_MIN_ROUNDS]
    peaks = (
        seasoned.sort_values(["shooter_id", "mu", "event_date"], ascending=[True, False, True])
        .groupby("shooter_id")
        .head(1)
    )
    df = peaks[["shooter_id", "event_date"]].assign(value=peaks["mu"].to_numpy())
    df = df.merge(names, on="shooter_id", how="left")
    ranked = _ranked(df, ["value", "event_date", "sort_key", "shooter_id"], limit)
    rows = tuple(
        RatingRecord(
            rank=int(r["rank"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            event_date=r["event_date"],
            value=float(r["value"]),
        )
        for r in ranked.rows
    )
    return rows, ranked.total, ranked.tied_more


def compute_records(
    rounds: pd.DataFrame,
    events: pd.DataFrame,
    history: pd.DataFrame,
    *,
    as_of: date,
    round_types: Sequence[RoundType] = (),
    limit: int | None = RECORD_LIMIT,
    since: date | None = None,
    appearances: pd.DataFrame | None = None,
    calendar: pd.DataFrame | None = None,
) -> Records:
    """Records over ``[since, as_of]`` (everything up to ``as_of`` when ``since`` is None).

    ``limit`` caps every list (``None`` = every row). The perfect 50s list is newest first.
    "Most Sundays" and "Longest runs" read ``appearances`` and ``calendar`` (special Sundays
    included, Plan 17); without them the rounds and events stand in.
    """
    all_rounds = _with_dates(rounds)
    upto = all_rounds[all_rounds["event_date"] <= as_of]
    # Every round up to as_of, any round type: an alias first used later never reorders ties.
    names = upto.groupby("shooter_id", as_index=False).agg(
        display_name=("display_name", "first"), sort_key=("name_key", "min")
    )
    dated_events = _with_dates(events)

    def in_range(df: pd.DataFrame) -> pd.DataFrame:
        return df if since is None else df[df["event_date"] >= since]

    past_rounds = in_range(apply_round_type_filter(upto, round_types))
    past_events = in_range(
        apply_round_type_filter(dated_events[dated_events["event_date"] <= as_of], round_types)
    )
    dated_history = _with_dates(history)
    past_history = in_range(dated_history[dated_history["event_date"] <= as_of])
    perfect = past_rounds[past_rounds["score"] == PERFECT_SCORE]
    adjusted = past_rounds[past_rounds["adjusted"].notna()]
    seen = _with_dates(rounds if appearances is None else appearances)
    seen_upto = seen[seen["event_date"] <= as_of]
    # The D6 tie key comes from scored rounds (``names``), as on the Sundays board; only a shooter
    # with no scored round takes it from the special sheet's spelling.
    sunday_names = (
        seen_upto.groupby("shooter_id", as_index=False)
        .agg(display_name=("display_name", "first"), seen_key=("name_key", "min"))
        .merge(names[["shooter_id", "sort_key"]], on="shooter_id", how="left")
    )
    sunday_names["sort_key"] = sunday_names["sort_key"].fillna(sunday_names["seen_key"])
    sunday_names = sunday_names.drop(columns="seen_key")
    every_sunday = _with_dates(events if calendar is None else calendar)
    past_seen = in_range(apply_round_type_filter(seen_upto, round_types))
    past_calendar = in_range(
        apply_round_type_filter(every_sunday[every_sunday["event_date"] <= as_of], round_types)
    )
    attended = past_seen.groupby("shooter_id", as_index=False).agg(value=("event_date", "nunique"))
    streak = streaks(past_seen, past_calendar, as_of)
    longest = streak.loc[streak["longest_streak"] > 0, ["shooter_id", "longest_streak"]].rename(
        columns={"longest_streak": "value"}
    )
    scores = _round_records(past_rounds, past_rounds["score"], names, limit)
    perfects = _round_records(perfect, perfect["score"], names, limit, newest_first=True)
    beat_field = _round_records(adjusted, adjusted["adjusted"], names, limit)
    jumps = _jumps(past_rounds, past_events, names, limit)
    attendance = _shooter_records(attended, sunday_names, limit)
    runs = _shooter_records(longest, sunday_names, limit)
    ratings = _highest_ratings(past_history, upto, names, limit)
    listed = {
        "highest_scores": scores,
        "perfect_rounds": perfects,
        "biggest_adjusted": beat_field,
        "biggest_jumps": jumps,
        "most_events": attendance,
        "longest_streaks": runs,
        "highest_ratings": ratings,
    }
    return Records(
        as_of=as_of,
        highest_scores=scores[0],
        perfect_rounds=perfects[0],
        biggest_adjusted=beat_field[0],
        biggest_jumps=jumps[0],
        most_events=attendance[0],
        longest_streaks=runs[0],
        highest_ratings=ratings[0],
        since=since,
        totals={name: total for name, (_, total, _) in listed.items()},
        tied_more={name: tied for name, (_, _, tied) in listed.items()},
    )


@cached_by_data_version
def records_for(
    session: Session,
    as_of: date,
    round_types: tuple[RoundType, ...],
    since: date | None = None,
    limit: int | None = RECORD_LIMIT,
) -> Records:
    """`compute_records` over the live frames; pass a resolved date and a sorted, unique tuple."""
    return compute_records(
        load_rounds(session),
        load_events(session),
        load_rating_history(session),
        as_of=as_of,
        round_types=round_types,
        since=since,
        limit=limit,
        appearances=load_appearances(session),
        calendar=load_calendar(session),
    )
