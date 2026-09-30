"""Synthetic ExplorerFrames for the pure run_query tests (no DB): the `frames` fixture.

Three held events with rounds, one attendance-only event, station data on 2025-07-06 only.
Every expected value in the tests is derived by hand from the literals below.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from sunday_clays.explorer.engine import ExplorerFrames

NAN = np.nan
E1, E2, E3, E4 = date(2024, 12, 1), date(2025, 3, 2), date(2025, 7, 6), date(2025, 11, 2)

# event_date, round_type, head_count, temp_f, gust_mph, precip_in, condition,
# temp_band, wind_band, precip_band
EVENTS = [
    (E1, "sporting", 3, 38.0, 8.0, 0.0, "clear", "<40", "<10", "dry"),
    (E2, "sporting", 4, 50.0, 15.0, 0.05, "rain", "40-55", "10-20", "wet"),
    (E3, "super_sporting", 2, 90.0, 22.0, 0.0, "windy", "85+", "20+", "dry"),
    (E4, "sporting", 12, NAN, NAN, NAN, None, None, None, None),
]
# How each Sunday played (event_metrics.difficulty); the attendance-only E4 has none.
DIFFICULTY = {E1: 1.5, E2: -0.5, E3: 3.0, E4: NAN}
SHOOTERS = {
    1: ("Able, Ann", "member", "12 Gauge"),
    2: ("Baker, Bob", "guest", "unspecified"),
    3: ("Slocum, Cy", "deceased", "Sub-Gauge"),
}
# Per-round status where it differs from the shooter's current shooter_status: Slocum was still a
# member on E1. C7: the statuses filter and the status dim use shooter_status, never this column.
ROUND_STATUS = {3: "member"}
# round_id, event_date, shooter_id, ordinal, score, adjusted, residual, mu_after,
# event_rank, is_best_round
ROUNDS = [
    (1, E1, 1, 1, 40, 4.0, 2.0, 36.0, 1, True),
    (2, E1, 2, 1, 30, -6.0, -3.0, 29.0, 3, True),
    (3, E1, 3, 1, 36, 0.0, 1.0, 33.0, 2, True),
    (4, E2, 1, 1, 44, 4.5, 3.0, 37.0, 1, True),
    (5, E2, 1, 2, 38, -1.5, -3.0, 37.0, NAN, False),
    (6, E2, 2, 1, 32, -7.5, -1.0, 29.5, 3, True),
    (7, E2, 3, 1, 41, 1.5, 2.0, 34.0, 2, True),
    (8, E3, 1, 1, 39, -3.0, -2.0, 36.5, 2, True),
    (9, E3, 3, 1, 45, 3.0, 4.0, 35.0, 1, True),
]
# event_date, station_no, round_id, hits, target_count (the last entry is an unmatched name)
STATION_HITS = [
    (E3, 4, 8, 5, 7),
    (E3, 10, 8, 6, 8),
    (E3, 4, 9, 7, 7),
    (E3, 10, 9, 8, 8),
    (E3, 4, NAN, 3, 7),
]


def make_frames() -> ExplorerFrames:
    weather = {e[0]: e for e in EVENTS}
    rounds = pd.DataFrame(
        [
            {
                "round_id": rid,
                "event_date": d,
                "shooter_id": sid,
                "name_key": SHOOTERS[sid][0].lower(),
                "display_name": SHOOTERS[sid][0],
                "ordinal": ordinal,
                "score": score,
                "gauge_class": None if SHOOTERS[sid][2] == "unspecified" else SHOOTERS[sid][2],
                "gauge": SHOOTERS[sid][2],
                "status": ROUND_STATUS.get(rid, SHOOTERS[sid][1]),
                "shooter_status": SHOOTERS[sid][1],
                "round_type": weather[d][1],
                "field_median": NAN,
                "adjusted": adjusted,
                "event_rank": rank,
                "is_best_round": best,
                "percentile": NAN,
                "expected": NAN,
                "residual": residual,
                "mu_before": NAN,
                "mu_after": mu_after,
                "temp_f": weather[d][3],
                "apparent_f": NAN,
                "precip_in": weather[d][5],
                "wind_mph": NAN,
                "gust_mph": weather[d][4],
                "wind_dir_deg": NAN,
                "cloud_pct": NAN,
                "condition": weather[d][6],
                "temp_band": weather[d][7],
                "wind_band": weather[d][8],
                "precip_band": weather[d][9],
            }
            for (
                rid,
                d,
                sid,
                ordinal,
                score,
                adjusted,
                residual,
                mu_after,
                rank,
                best,
            ) in ROUNDS
        ]
    )
    events = pd.DataFrame(
        EVENTS,
        columns=[
            "event_date",
            "round_type",
            "head_count",
            "temp_f",
            "gust_mph",
            "precip_in",
            "condition",
            "temp_band",
            "wind_band",
            "precip_band",
        ],
    )
    events.insert(3, "difficulty", [DIFFICULTY[e[0]] for e in EVENTS])
    station_hits = pd.DataFrame(
        STATION_HITS, columns=["event_date", "station_no", "round_id", "hits", "target_count"]
    )
    station_hits.insert(2, "station_label", station_hits["station_no"].astype(str))
    return ExplorerFrames(rounds=rounds, station_hits=station_hits, events=events)


@pytest.fixture
def frames() -> ExplorerFrames:
    return make_frames()
