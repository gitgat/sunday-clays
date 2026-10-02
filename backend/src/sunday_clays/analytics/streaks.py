"""Held events and attendance streaks (C7). The single streak implementation."""

import itertools
from datetime import date

import pandas as pd

from sunday_clays.analytics.frames import EVENT_KIND_SPECIAL

STREAK_COLUMNS: tuple[str, ...] = ("shooter_id", "current_streak", "longest_streak")


def held_event_dates(events: pd.DataFrame, as_of: date | None) -> list[date]:
    """Sorted dates of `results_complete` events, on or before `as_of` if given."""
    held = events.loc[events["results_complete"].astype(bool), "event_date"]
    return sorted(d for d in held if as_of is None or d <= as_of)


def _special_dates(events: pd.DataFrame) -> set[date]:
    """Dates of special Sundays (Plan 17); none when the frame has no `kind` column."""
    if "kind" not in events.columns:
        return set()
    return set(events.loc[events["kind"].eq(EVENT_KIND_SPECIAL), "event_date"])


def streaks(rounds: pd.DataFrame, events: pd.DataFrame, as_of: date | None) -> pd.DataFrame:
    """Consecutive held events attended, per shooter with a round on/before `as_of`.

    Non-held dates are skipped: they neither extend nor break a streak. A special Sunday (an
    events `kind` of 'special', Plan 17) extends the run of everyone who came and is skipped for
    everyone else: two attended dates are consecutive when no *regular* held date lies between
    them. current_streak is the run whose last date has no regular held date after it (0 if the
    shooter missed the latest regular held date). `rounds` may be an appearance frame: only
    shooter_id and event_date are read.
    """
    held = held_event_dates(events, as_of)
    special = _special_dates(events)
    position = {d: i for i, d in enumerate(held)}
    # regular_before[k]: regular held dates among held[:k]
    regular_before = list(itertools.accumulate((d not in special for d in held), initial=0))
    upto = rounds if as_of is None else rounds.loc[rounds["event_date"] <= as_of]
    attended: dict[int, set[int]] = {int(s): set() for s in upto["shooter_id"].unique()}
    for shooter_id, event_date in zip(upto["shooter_id"], upto["event_date"], strict=True):
        if event_date in position:
            attended[int(shooter_id)].add(position[event_date])
    total_regular = regular_before[-1]
    rows: list[tuple[int, int, int]] = []
    for shooter_id in sorted(attended):
        longest = run = 0
        previous: int | None = None
        for i in sorted(attended[shooter_id]):
            gapless = previous is not None and regular_before[i] == regular_before[previous + 1]
            run = run + 1 if gapless else 1
            longest = max(longest, run)
            previous = i
        current = (
            run if previous is not None and regular_before[previous + 1] == total_regular else 0
        )
        rows.append((shooter_id, current, longest))
    return pd.DataFrame(rows, columns=list(STREAK_COLUMNS)).astype("int64")
