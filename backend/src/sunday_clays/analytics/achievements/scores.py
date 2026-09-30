"""Scoring trophies (C12, Plan 10 T3): best-round tiers, comebacks and above-average runs.

"Earlier" always means earlier dates (AchContext.shooter_days prior_* / prev_* columns)."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext, empty_value_frame
from sunday_clays.analytics.achievements.registry import (
    Achievement,
    Award,
    Category,
    make_tiers,
    register,
)

COMEBACK_MIN_GAIN = 15
COMEBACK_MIN_PRIOR_ROUNDS = 5
ABOVE_AVERAGE_MIN_PRIOR_ROUNDS = 10
ABOVE_AVERAGE_RUN = 3


def round_score_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    if days.empty:
        return empty_value_frame()
    best = days.groupby("shooter_id")["day_best"].cummax()
    return pd.DataFrame(
        {
            "shooter_id": days["shooter_id"].to_numpy(),
            "event_date": days["event_ts"].to_numpy(),
            "value": best.to_numpy(dtype=float),
        }
    )


def _comeback(ctx: AchContext) -> Iterator[Award]:
    days = ctx.shooter_days
    hits = days[
        (days["prior_rounds"] >= COMEBACK_MIN_PRIOR_ROUNDS)
        & (days["day_best"] >= days["prev_day_best"] + COMEBACK_MIN_GAIN)
    ]
    for sid, day, rid, best, previous in zip(
        hits["shooter_id"],
        hits["event_date"],
        hits["best_round_id"],
        hits["day_best"],
        hits["prev_day_best"],
        strict=True,
    ):
        yield Award(
            int(sid), "comeback", day, int(rid), {"best": int(best), "previous_best": int(previous)}
        )


def _above_average_3(ctx: AchContext) -> Iterator[Award]:
    days = ctx.shooter_days
    if days.empty:
        return
    prior_rounds = days["prior_rounds"]
    career_average = days["prior_sum"] / prior_rounds.where(prior_rounds > 0)
    qualifies = (prior_rounds >= ABOVE_AVERAGE_MIN_PRIOR_ROUNDS) & (
        days["day_best"] > career_average
    )
    run_id = (~qualifies).astype(int).groupby(days["shooter_id"]).cumsum()
    run_length = qualifies.astype(int).groupby([days["shooter_id"], run_id]).cumsum()
    hits = days[run_length >= ABOVE_AVERAGE_RUN]
    for sid, day, rid in zip(
        hits["shooter_id"], hits["event_date"], hits["best_round_id"], strict=True
    ):
        yield Award(int(sid), "above_average_3", day, int(rid), {})


register(
    Achievement(
        code="round_score",
        name="Round Score",
        description="Your best single round.",
        category=Category.SCORING,
        art_key="round_score",
        tiers=make_tiers((30, 35, 40, 45, 48, 50), "in one round"),
        value=round_score_value,
    )
)
register(
    Achievement(
        code="comeback",
        name="Comeback",
        description=(
            "Beat your previous event's best round by 15 or more (after at least 5 rounds)."
        ),
        category=Category.SCORING,
        art_key="comeback",
        evaluate=_comeback,
        repeatable=True,
    )
)
register(
    Achievement(
        code="above_average_3",
        name="Above Average ×3",  # noqa: RUF001
        description=(
            "Three events in a row with a best round above your career average "
            "(after at least 10 rounds)."
        ),
        category=Category.SCORING,
        art_key="above_average_3",
        evaluate=_above_average_3,
    )
)
