import math
from collections.abc import Callable
from datetime import date

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics import frames
from sunday_clays.domain.round_type import RoundType


@pytest.mark.parametrize(
    ("temp_f", "band"),
    [
        (None, None),
        (math.nan, None),
        (-5.0, "<40"),
        (39.99, "<40"),
        (40.0, "40-55"),
        (54.9, "40-55"),
        (55.0, "55-70"),
        (69.9, "55-70"),
        (70.0, "70-85"),
        (84.9, "70-85"),
        (85.0, "85+"),
        (101.0, "85+"),
    ],
)
def test_temp_band_half_open_edges(temp_f: float | None, band: str | None) -> None:
    assert frames.temp_band(temp_f) == band


@pytest.mark.parametrize(
    ("gust", "band"),
    [
        (None, None),
        (math.nan, None),
        (0.0, "<10"),
        (9.99, "<10"),
        (10.0, "10-20"),
        (19.99, "10-20"),
        (20.0, "20+"),
        (45.0, "20+"),
    ],
)
def test_wind_band_uses_gust_edges(gust: float | None, band: str | None) -> None:
    assert frames.wind_band(gust) == band


@pytest.mark.parametrize(
    ("precip", "band"),
    [
        (None, None),
        (math.nan, None),
        (0.0, "dry"),
        (0.019, "dry"),
        (0.02, "wet"),
        # a stored float4 0.02 read through a binary cursor or a ::float8 cast (Plan 05
        # Decision 11): rounded to 3 dp first, so it stays on the wet side like `rain`
        (0.019999999552965164, "wet"),
        (1.3, "wet"),
    ],
)
def test_precip_band_threshold_is_two_hundredths(precip: float | None, band: str | None) -> None:
    assert frames.precip_band(precip) == band


def test_band_orders_list_every_label_once() -> None:
    labels = {frames.temp_band(t) for t in (0, 45, 60, 75, 90)}
    assert labels == set(frames.TEMP_BANDS)
    assert {frames.wind_band(g) for g in (0, 15, 30)} == set(frames.WIND_BANDS)
    assert {frames.precip_band(p) for p in (0, 1)} == set(frames.PRECIP_BANDS)


@pytest.mark.parametrize(
    ("month", "season"),
    [
        (12, "winter"),
        (1, "winter"),
        (2, "winter"),
        (3, "spring"),
        (5, "spring"),
        (6, "summer"),
        (8, "summer"),
        (9, "fall"),
        (11, "fall"),
    ],
)
def test_season_label_december_is_winter(month: int, season: str) -> None:
    assert frames.season_label(date(2025, month, 7)) == season


def _typed(make_rounds: Callable[..., pd.DataFrame]) -> pd.DataFrame:
    return make_rounds(
        [
            {
                "event_date": date(2026, 9, 6),
                "shooter_id": 1,
                "score": 30,
                "round_type": "sporting",
            },
            {
                "event_date": date(2026, 9, 13),
                "shooter_id": 1,
                "score": 31,
                "round_type": "super_sporting",
            },
            {"event_date": date(2026, 9, 20), "shooter_id": 1, "score": 32},
        ]
    )


def test_round_type_filter_empty_list_keeps_everything(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    kept = frames.apply_round_type_filter(_typed(make_rounds), [])
    assert kept["score"].tolist() == [30, 31, 32]


def test_round_type_filter_keeps_only_listed_types(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    kept = frames.apply_round_type_filter(_typed(make_rounds), [RoundType.SUPER_SPORTING])
    assert kept["score"].tolist() == [31]
    both = frames.apply_round_type_filter(
        _typed(make_rounds), [RoundType.SUPER_SPORTING, RoundType.SPORTING]
    )
    assert both["score"].tolist() == [30, 31, 32]  # a round with no round_type is sporting


def test_builder_matches_load_rounds_columns(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    built = make_rounds([(date(2026, 9, 6), 1, 30), (date(2026, 9, 6), 1, 35)])
    assert set(frames.ROUND_COLUMNS) <= set(built.columns)
    assert built["ordinal"].tolist() == [1, 2]
    assert built.loc[built["ordinal"] == 1, "score"].item() == 35
    assert built["gauge"].tolist() == ["unspecified", "unspecified"]


def test_db_records_maps_missing_values_to_none_and_numpy_to_python() -> None:
    df = pd.DataFrame(
        {
            "a": pd.array([1, None], dtype="Int64"),
            "b": [1.5, math.nan],
            "c": ["x", None],
            "d": [True, False],
        }
    )
    records = frames.db_records(df)
    assert records == [
        {"a": 1, "b": 1.5, "c": "x", "d": True},
        {"a": None, "b": None, "c": None, "d": False},
    ]
    assert type(records[0]["a"]) is int
    assert type(records[1]["d"]) is bool
    boxed = pd.DataFrame({"n": pd.Series([np.int64(3), np.float64("nan")], dtype=object)})
    assert frames.db_records(boxed) == [{"n": 3}, {"n": None}]


def test_appearances_from_rounds_is_one_regular_row_per_shooter_and_day(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d1, d2 = date(2026, 9, 6), date(2026, 9, 13)
    rounds = make_rounds([(d2, 1, 30), (d1, 1, 40), (d1, 1, 35), (d1, 2, 20)])

    out = frames.appearances_from_rounds(rounds)

    assert list(out.columns) == list(frames.APPEARANCE_COLUMNS)
    assert [(r.event_date, r.shooter_id, r.kind) for r in out.itertuples()] == [
        (d1, 1, "regular"),
        (d1, 2, "regular"),
        (d2, 1, "regular"),
    ]
    assert out["shooter_id"].dtype == "int64"
    assert out["held"].tolist() == [True, True, True]
    empty = frames.appearances_from_rounds(rounds.iloc[0:0])
    assert list(empty.columns) == list(frames.APPEARANCE_COLUMNS)
    assert empty.empty


def test_calendar_from_events_marks_every_sunday_regular_with_fifty_targets(
    make_events: Callable[..., pd.DataFrame],
) -> None:
    out = frames.calendar_from_events(make_events([date(2026, 9, 6), date(2026, 9, 13)]))

    assert out["kind"].tolist() == ["regular", "regular"]
    assert out["label"].tolist() == [None, None]
    assert out["target_total"].tolist() == [50, 50]
