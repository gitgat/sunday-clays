"""Competition trophies (C12, Plan 10 T3): the only ranking-based trophies. Ranks are full-field
min ranks over best rounds (round_metrics.event_rank, C7), so ties share a rank; achievements
ignore every filter."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext
from sunday_clays.analytics.achievements.registry import Achievement, Award, Category, register

MIN_FIELD = 5


def _best_rounds_in_full_fields(ctx: AchContext) -> pd.DataFrame:
    rounds = ctx.rounds
    field_size = rounds.groupby("event_ts")["shooter_id"].transform("nunique")
    best = rounds["is_best_round"].eq(True)
    return rounds[best & (field_size >= MIN_FIELD)].sort_values(
        ["shooter_id", "event_ts"], kind="stable"
    )


def _first_win(ctx: AchContext) -> Iterator[Award]:
    best = _best_rounds_in_full_fields(ctx)
    wins = best[best["event_rank"] == 1]
    for sid, ts, rid in zip(wins["shooter_id"], wins["event_ts"], wins["round_id"], strict=True):
        yield Award(int(sid), "first_win", ts.date(), int(rid), {})


def _podium(ctx: AchContext) -> Iterator[Award]:
    best = _best_rounds_in_full_fields(ctx)
    podium = best[best["event_rank"] <= 3]
    for sid, ts, rid, rank in zip(
        podium["shooter_id"],
        podium["event_ts"],
        podium["round_id"],
        podium["event_rank"],
        strict=True,
    ):
        yield Award(int(sid), "podium", ts.date(), int(rid), {"rank": int(rank)})


register(
    Achievement(
        code="first_win",
        name="First Win",
        description="Top score of the day (ties count) with at least 5 shooters.",
        category=Category.COMPETITION,
        art_key="first_win",
        evaluate=_first_win,
    )
)
register(
    Achievement(
        code="podium",
        name="Podium",
        description="Finished in the top 3 (ties count) with at least 5 shooters.",
        category=Category.COMPETITION,
        art_key="podium",
        evaluate=_podium,
    )
)
