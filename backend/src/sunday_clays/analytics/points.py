"""Season championship points (C7): 10-8-6-5-4-3-2-1 by best-round rank, +1 per event."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

POINTS_BY_RANK: Mapping[int, int] = {1: 10, 2: 8, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
PARTICIPATION_POINTS = 1


def points_for_rank(rank: int) -> int:
    return POINTS_BY_RANK.get(rank, 0) + PARTICIPATION_POINTS


def event_points(rounds: pd.DataFrame) -> pd.DataFrame:
    best = rounds[rounds["is_best_round"].eq(True) & rounds["event_rank"].notna()]
    ranks = best["event_rank"].astype(int)
    return pd.DataFrame(
        {
            "event_date": best["event_date"].to_numpy(),
            "shooter_id": best["shooter_id"].to_numpy(),
            "event_rank": ranks.to_numpy(),
            "points": [points_for_rank(int(r)) for r in ranks],
        }
    )


def season_points(rounds: pd.DataFrame) -> pd.DataFrame:
    return (
        event_points(rounds)
        .groupby("shooter_id", as_index=False)
        .agg(value=("points", "sum"), n_rounds=("points", "size"))
    )
