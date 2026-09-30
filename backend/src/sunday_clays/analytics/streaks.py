"""Held events and attendance streaks (C7). The single streak implementation."""

from datetime import date

import pandas as pd

STREAK_COLUMNS: tuple[str, ...] = ("shooter_id", "current_streak", "longest_streak")


def held_event_dates(events: pd.DataFrame, as_of: date | None) -> list[date]:
    """Sorted dates of `results_complete` events, on or before `as_of` if given."""
    held = events.loc[events["results_complete"].astype(bool), "event_date"]
    return sorted(d for d in held if as_of is None or d <= as_of)


def streaks(rounds: pd.DataFrame, events: pd.DataFrame, as_of: date | None) -> pd.DataFrame:
    """Consecutive held events attended, per shooter with a round on/before `as_of`.

    Non-held dates are skipped: they neither extend nor break a streak. current_streak
    is the run ending at the latest held date <= as_of (0 if the shooter missed it).
    """
    held = held_event_dates(events, as_of)
    position = {d: i for i, d in enumerate(held)}
    upto = rounds if as_of is None else rounds.loc[rounds["event_date"] <= as_of]
    attended: dict[int, set[int]] = {int(s): set() for s in upto["shooter_id"].unique()}
    for shooter_id, event_date in zip(upto["shooter_id"], upto["event_date"], strict=True):
        if event_date in position:
            attended[int(shooter_id)].add(position[event_date])
    last = len(held) - 1
    rows: list[tuple[int, int, int]] = []
    for shooter_id in sorted(attended):
        longest = run = 0
        previous = -2
        for i in sorted(attended[shooter_id]):
            run = run + 1 if i == previous + 1 else 1
            longest = max(longest, run)
            previous = i
        current = run if previous == last else 0
        rows.append((shooter_id, current, longest))
    return pd.DataFrame(rows, columns=list(STREAK_COLUMNS)).astype("int64")
