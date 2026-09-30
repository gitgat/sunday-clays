"""load_explorer_frames over stubbed Plan 06 loaders; tests/integration covers the real database."""

import math
from datetime import date

import pandas as pd
import pytest

from sunday_clays.analytics import frames as fr
from sunday_clays.explorer import engine
from sunday_clays.explorer.spec import Dim, Metric, QuerySpec

D1 = date(2025, 1, 5)
D2 = date(2025, 7, 6)
NAN = math.nan


@pytest.fixture
def stubbed_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stubs every loader the Explorer reads."""
    rounds = pd.DataFrame(
        {
            "round_id": [1, 2, 3],
            "event_date": [D1, D1, D2],
            "shooter_id": [10, 11, 10],
            "score": [40, 30, 42],
            "temp_f": [38.0, 38.0, NAN],
            "gust_mph": [22.0, 22.0, NAN],
            "precip_in": [0.0, 0.0, NAN],
        }
    )
    events = pd.DataFrame(
        {
            "event_date": [D1, D2],
            "round_type": ["sporting", "super_sporting"],
            "head_count": [2.0, 1.0],
            "difficulty": [1.25, NAN],
            "n_rounds": [2, 1],
            "temp_f": [38.0, NAN],
            "gust_mph": [22.0, NAN],
            "precip_in": [0.0, NAN],
            "condition": ["windy", None],
        }
    )
    hits = pd.DataFrame(
        {
            "event_date": [D2],
            "station_no": [4],
            "station_label": ["4"],
            "target_count": [7],
            "round_id": [3],
            "hits": [5],
        }
    )
    monkeypatch.setattr(fr, "load_rounds", lambda session: rounds)
    monkeypatch.setattr(fr, "load_events", lambda session: events)
    monkeypatch.setattr(fr, "load_station_hits", lambda session: hits)


def test_loader_adds_weather_bands_and_keeps_missing_weather_missing(
    stubbed_loaders: None,
) -> None:
    frames = engine.load_explorer_frames.__wrapped__(None)

    first = frames.rounds.iloc[0]
    assert (first["temp_band"], first["wind_band"], first["precip_band"]) == ("<40", "20+", "dry")
    assert frames.rounds.iloc[2][["temp_band", "wind_band", "precip_band"]].isna().all()
    assert list(frames.events.columns) == [
        "event_date",
        "round_type",
        "head_count",
        "difficulty",
        *engine.WEATHER_COLUMNS,
        "temp_band",
        "wind_band",
        "precip_band",
    ]
    assert frames.station_hits["target_count"].tolist() == [7]


def test_loaded_frames_answer_queries(stubbed_loaders: None) -> None:
    frames = engine.load_explorer_frames.__wrapped__(None)

    result = engine.run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.TEMP_BAND]))

    assert [(r["temp_band"], r["value"]) for r in result.rows] == [("<40", 2), (None, 1)]
