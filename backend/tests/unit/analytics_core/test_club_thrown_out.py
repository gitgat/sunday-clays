"""Club trends keep a thrown-out Sunday marked but out of every rolling line (T3c)."""

import math
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, timedelta

import pandas as pd

from sunday_clays.analytics import club_insights as ci
from sunday_clays.api.routes.club_insights import EventTrendOut

W = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(3)]


def _events(make_events: Callable[..., pd.DataFrame]) -> pd.DataFrame:
    return make_events(
        [
            {
                "event_date": W[0],
                "top_score": 40.0,
                "median": 30.0,
                "difficulty": 1.0,
                "stats_excluded": False,
            },
            {
                "event_date": W[1],
                "top_score": 50.0,
                "median": 40.0,
                "difficulty": math.nan,
                "stats_excluded": True,
            },
            {
                "event_date": W[2],
                "top_score": 44.0,
                "median": 34.0,
                "difficulty": 3.0,
                "stats_excluded": False,
            },
        ]
    )


def test_event_trends_keep_the_sunday_marked_but_out_of_every_rolling_line(
    make_events: Callable[..., pd.DataFrame],
) -> None:
    trend = ci.event_trends(_events(make_events), W[2])
    assert [
        (
            t.event_date,
            t.stats_excluded,
            t.top_score,
            t.top_score_rolling8,
            t.median_rolling8,
            t.difficulty_rolling8,
        )
        for t in trend
    ] == [
        (W[0], False, 40, 40.0, 30.0, 1.0),
        (W[1], True, 50, None, None, None),
        (W[2], False, 44, 42.0, 32.0, 2.0),
    ]
    assert EventTrendOut.model_validate(asdict(trend[1])).stats_excluded is True


def test_seasonality_counts_the_sunday_but_leaves_its_median_out(
    make_events: Callable[..., pd.DataFrame],
) -> None:
    jan = ci.seasonality(_events(make_events), W[2])[0]
    assert (jan.month, jan.n_events, jan.mean_median) == (1, 3, 32.0)
