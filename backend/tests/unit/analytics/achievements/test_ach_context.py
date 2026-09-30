"""AchContext slicing and per-shooter day series (Plan 10 T1)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from sunday_clays.analytics.achievements.context import (
    AchContext,
    empty_value_frame,
    load_station_entries,
)
from sunday_clays.analytics.streaks import streaks


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def test_until_drops_later_rows_from_every_frame(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 40)
        .round(1, sun(1), 41)
        .round(1, sun(2), 42)
        .station(1, sun(2), 4, 7, entry_row=10)
        .rating(1, sun(2), 31.0)
        .event(sun(3), has_scores=False, results_complete=False, head_count=12)
        .build()
    )
    cut = ctx.until(sun(1))
    assert sorted(set(cut.rounds["event_date"])) == [sun(0), sun(1)]
    assert sorted(set(cut.events["event_date"])) == [sun(0), sun(1)]
    assert cut.station_hits.empty
    assert cut.rating_history.empty
    assert cut.as_of == sun(1)


def test_until_none_returns_same_context(ctx_builder):
    ctx = ctx_builder().round(1, sun(0), 40).build()
    assert ctx.until(None) is ctx


def test_shooter_days_prior_columns_use_earlier_dates_only(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 40)
        .round(1, sun(0), 44)
        .round(1, sun(1), 30)
        .round(1, sun(2), 47)
        .build()
    )
    days = ctx.shooter_days
    assert list(days["event_date"]) == [sun(0), sun(1), sun(2)]
    assert list(days["n_rounds"]) == [2, 1, 1]
    assert list(days["day_best"]) == [44, 30, 47]
    assert list(days["day_sum"]) == [84, 30, 47]
    assert list(days["n_events"]) == [1, 2, 3]
    assert list(days["cum_rounds"]) == [2, 3, 4]
    assert list(days["prior_rounds"]) == [0, 2, 3]
    assert list(days["prior_sum"]) == [0, 84, 114]
    assert pd.isna(days["prior_best"].iloc[0])
    assert list(days["prior_best"].iloc[1:]) == [44.0, 44.0]
    assert pd.isna(days["prev_day_best"].iloc[0])
    assert list(days["prev_day_best"].iloc[1:]) == [44.0, 30.0]
    assert pd.isna(days["prev_ts"].iloc[0])
    assert days["prev_ts"].iloc[2] == pd.Timestamp(sun(1))


def test_best_round_id_prefers_higher_score_then_lower_ordinal(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 38)  # round 1
        .round(1, sun(0), 45)  # round 2: best
        .round(2, sun(0), 40)  # round 3: ordinal 1, best on the tie
        .round(2, sun(0), 40)  # round 4: ordinal 2
        .build()
    )
    days = ctx.shooter_days.set_index("shooter_id")
    assert days.loc[1, "best_round_id"] == 2
    assert days.loc[2, "best_round_id"] == 3


def test_for_shooter_keeps_every_event(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 40)
        .round(2, sun(1), 41)
        .station(2, sun(1), 4, 7, entry_row=10)
        .station(None, sun(1), 4, 3, entry_row=11)
        .rating(2, sun(1), 30.0)
        .build()
    )
    own = ctx.for_shooter(1)
    assert set(own.rounds["shooter_id"]) == {1}
    assert sorted(own.events["event_date"]) == [sun(0), sun(1)]
    assert own.station_hits.empty
    assert own.rating_history.empty
    assert list(ctx.for_shooter(2).station_hits["entry_row"]) == [10]


def test_from_frames_accepts_datetime64_event_dates(ctx_builder):
    base = ctx_builder().round(1, sun(0), 40).build()
    ctx = AchContext.from_frames(
        rounds=base.rounds.drop(columns=["event_ts"]).assign(
            event_date=pd.to_datetime(base.rounds["event_date"])
        ),
        events=base.events.drop(columns=["event_ts"]),
        station_hits=base.station_hits.drop(columns=["event_ts"]),
        rating_history=base.rating_history.drop(columns=["event_ts"]),
    )
    assert list(ctx.shooter_days["event_date"]) == [sun(0)]


def test_held_dates_skip_incomplete_events(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 40)
        .round(1, sun(1), 40)
        .event(sun(1), results_complete=False)
        .build()
    )
    assert ctx.held_dates() == [sun(0)]


def test_shooter_days_of_empty_context_has_typed_columns(ctx_builder):
    days = ctx_builder().build().shooter_days
    assert days.empty
    assert str(days["event_ts"].dtype).startswith("datetime64")


# --- Beyond the brief: dtype stability and the Plan 06 delegations --------------------------------

DAY_DTYPES = {
    "shooter_id": "int64",
    "event_ts": "datetime64[ns]",
    "event_date": "object",
    "n_rounds": "int64",
    "day_best": "int64",
    "day_sum": "int64",
    "best_round_id": "int64",
    "n_events": "int64",
    "cum_rounds": "int64",
    "cum_sum": "int64",
    "prior_rounds": "int64",
    "prior_sum": "int64",
    "prior_best": "float64",
    "prev_ts": "datetime64[ns]",
    "prev_day_best": "float64",
}


def dtypes(frame: pd.DataFrame) -> dict[str, str]:
    return {str(name): str(dtype) for name, dtype in frame.dtypes.items()}


def test_event_ts_and_day_series_dtypes_match_empty_frames(ctx_builder):
    """pandas 3 infers datetime64[s] from date objects; event_ts is pinned to ns so a sliced (or
    empty) value frame compares equal to a full one in no_leak."""
    ctx = ctx_builder().round(1, sun(0), 40).round(1, sun(1), 41).rating(1, sun(0), 30.0).build()
    empty = ctx_builder().build()
    for frame in (ctx.rounds, ctx.events, ctx.station_hits, ctx.rating_history, empty.rounds):
        assert str(frame["event_ts"].dtype) == "datetime64[ns]"
    assert dtypes(ctx.shooter_days) == DAY_DTYPES
    assert dtypes(empty.shooter_days) == DAY_DTYPES
    assert list(ctx.shooter_days) == list(DAY_DTYPES)


def test_empty_value_frame_is_the_typed_long_frame():
    frame = empty_value_frame()
    assert frame.empty
    assert dtypes(frame) == {
        "shooter_id": "int64",
        "event_date": "datetime64[ns]",
        "value": "float64",
    }


STATION_DTYPES = {
    "event_date": "object",
    "station_no": "int64",
    "station_label": "str",
    "target_count": "int64",
    "sheet_id": "int64",
    "entry_row": "int64",
    "shooter_id": "Int64",
    "round_id": "Int64",
    "hits": "int64",
    "event_ts": "datetime64[ns]",
}


class _RowsSession:
    """Feeds rows to load_station_entries without a database."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def execute(self, _statement: object) -> _RowsSession:
        return self

    def mappings(self) -> list[dict[str, Any]]:
        return self._rows


@pytest.mark.parametrize("empty", [False, True])
def test_builder_station_frame_mirrors_load_station_entries(ctx_builder, empty):
    """Unit tests of empty station selections run on the dtypes production gives (int64 ids)."""
    builder = ctx_builder()
    rows: list[dict[str, Any]] = []
    if not empty:
        builder.station(1, sun(0), 4, 7, entry_row=10).station(None, sun(0), 5, 3, entry_row=11)
        rows = [
            {
                "event_date": sun(0),
                "station_no": station_no,
                "station_label": str(station_no),
                "target_count": 7,
                "sheet_id": 1,
                "entry_row": entry_row,
                "shooter_id": shooter_id,
                "round_id": None,
                "hits": hits,
            }
            for shooter_id, station_no, hits, entry_row in ((1, 4, 7, 10), (None, 5, 3, 11))
        ]
    built = builder.build().station_hits
    assert dtypes(built) == STATION_DTYPES
    production = load_station_entries(cast(Session, _RowsSession(rows)))
    pd.testing.assert_frame_equal(built.drop(columns=["event_ts"]), production)


def test_shooter_days_is_computed_once_per_context(ctx_builder):
    ctx = ctx_builder().round(1, sun(0), 40).build()
    assert ctx.shooter_days is ctx.shooter_days
    assert ctx.until(sun(0)).shooter_days is not ctx.shooter_days


def streak_ctx(ctx_builder):
    builder = ctx_builder()
    for i in range(6):
        builder.round(1, sun(i), 40 + i).rating(1, sun(i), 30.0 + i)
        if i != 3:
            builder.round(2, sun(i), 35).rating(2, sun(i), 25.0)
    return builder.round(3, sun(5), 20).rating(3, sun(5), 10.0).build()


def test_streaks_at_is_plan06_streaks_memoized_per_day(ctx_builder):
    ctx = streak_ctx(ctx_builder)
    got = ctx.streaks_at(sun(5))
    pd.testing.assert_frame_equal(got, streaks(ctx.rounds, ctx.events, sun(5)))
    assert list(got["current_streak"]) == [6, 2, 1]
    assert ctx.streaks_at(sun(5)) is got
    assert ctx.streaks_at(sun(4)) is not got
