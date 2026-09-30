import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
import pytest

from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.round_type import RoundType
from sunday_clays.explorer.engine import ExplorerFrames, run_query
from sunday_clays.explorer.spec import Agg, Dim, Filters, Metric, QuerySpec

ROUND_KEYS: dict[Dim, list[object]] = {
    Dim.SHOOTER: [1, 2, 3],
    Dim.EVENT: ["2024-12-01", "2025-03-02", "2025-07-06"],
    Dim.MONTH: ["2024-12", "2025-03", "2025-07"],
    Dim.YEAR: [2024, 2025],
    Dim.SEASON: ["winter", "spring", "summer"],
    Dim.MONTH_OF_YEAR: [3, 7, 12],
    Dim.ROUND_TYPE: ["sporting", "super_sporting"],
    Dim.GAUGE: ["12 Gauge", "Sub-Gauge", "unspecified"],
    Dim.STATUS: ["deceased", "guest", "member"],
    Dim.TEMP_BAND: ["<40", "40-55", "85+"],
    Dim.WIND_BAND: ["<10", "10-20", "20+"],
    Dim.PRECIP_BAND: ["dry", "wet"],
    Dim.CONDITION: ["clear", "rain", "windy"],
}
STATION_KEYS: dict[Dim, list[object]] = {
    Dim.SHOOTER: [1, 3],
    Dim.EVENT: ["2025-07-06"],
    Dim.MONTH: ["2025-07"],
    Dim.YEAR: [2025],
    Dim.SEASON: ["summer"],
    Dim.MONTH_OF_YEAR: [7],
    Dim.ROUND_TYPE: ["super_sporting"],
    Dim.GAUGE: ["12 Gauge", "Sub-Gauge"],
    Dim.STATUS: ["deceased", "member"],
    Dim.TEMP_BAND: ["85+"],
    Dim.WIND_BAND: ["20+"],
    Dim.PRECIP_BAND: ["dry"],
    Dim.CONDITION: ["windy"],
    Dim.STATION: ["4", "10"],
}
EVENT_KEYS: dict[Dim, list[object]] = {
    Dim.EVENT: ["2024-12-01", "2025-03-02", "2025-07-06", "2025-11-02"],
    Dim.MONTH: ["2024-12", "2025-03", "2025-07", "2025-11"],
    Dim.YEAR: [2024, 2025],
    Dim.SEASON: ["winter", "spring", "summer", "fall"],
    Dim.MONTH_OF_YEAR: [3, 7, 11, 12],
    Dim.ROUND_TYPE: ["sporting", "super_sporting"],
    Dim.TEMP_BAND: ["<40", "40-55", "85+", None],
    Dim.WIND_BAND: ["<10", "10-20", "20+", None],
    Dim.PRECIP_BAND: ["dry", "wet", None],
    Dim.CONDITION: ["clear", "rain", "windy", None],
}
ROUND_METRICS = [
    Metric.SCORE,
    Metric.ADJUSTED,
    Metric.RESIDUAL,
    Metric.RATING,
    Metric.ROUNDS,
    Metric.SHOOTERS,
    Metric.WINS,
]


def _expected_keys(metric: Metric, dim: Dim) -> list[object] | None:
    """Hand-listed group keys, or None when the combination must be rejected."""
    if metric is Metric.HIT_PCT:
        return STATION_KEYS[dim]
    if metric in (Metric.ATTENDANCE, Metric.DIFFICULTY):
        return EVENT_KEYS.get(dim)
    return ROUND_KEYS.get(dim)


def _key_column(dim: Dim) -> str:
    return {Dim.SHOOTER: "shooter_id", Dim.STATION: "station"}.get(dim, dim.value)


def _values(result_rows: Sequence[Mapping[str, object]], key: str) -> dict[object, object]:
    return {row[key]: row["value"] for row in result_rows}


@pytest.mark.parametrize("metric", list(Metric))
@pytest.mark.parametrize("dim", list(Dim))
def test_every_metric_dim_combination(metric: Metric, dim: Dim, frames: ExplorerFrames) -> None:
    spec = QuerySpec(metric=metric, group_by=[dim])
    expected = _expected_keys(metric, dim)
    if expected is None:
        with pytest.raises(DomainError) as excinfo:
            run_query(frames, spec)
        assert excinfo.value.code == "invalid_query"
        return
    result = run_query(frames, spec)
    assert [row[_key_column(dim)] for row in result.rows] == expected
    assert [c.key for c in result.columns][-2:] == ["value", "n"]
    json.loads(result.model_dump_json())  # every combination is JSON-serializable


def test_combination_count_matches_contract() -> None:
    valid = [(m, d) for m in Metric for d in Dim if _expected_keys(m, d) is not None]
    assert len(valid) == 7 * 13 + 14 + 10 + 10


def test_score_aggregations_overall(frames: ExplorerFrames) -> None:
    got = {
        agg: run_query(frames, QuerySpec(metric=Metric.SCORE, agg=agg)).rows[0]["value"]
        for agg in Agg
    }
    # scores: 40 30 36 44 38 32 41 39 45 -> sorted 30 32 36 38 39 40 41 44 45
    assert got[Agg.AVG] == pytest.approx(345 / 9)
    assert got[Agg.MEDIAN] == 39
    assert got[Agg.MAX] == 45
    assert got[Agg.MIN] == 30
    assert got[Agg.SUM] == 345
    assert got[Agg.COUNT] == 9
    assert got[Agg.P90] == pytest.approx(44.2)
    assert got[Agg.STDEV] == pytest.approx((202 / 8) ** 0.5)


def test_score_avg_by_year(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.SCORE, group_by=[Dim.YEAR]))
    assert _values(result.rows, "year") == {
        2024: pytest.approx(106 / 3),
        2025: pytest.approx(239 / 6),
    }
    assert [(r["year"], r["n"]) for r in result.rows] == [(2024, 3), (2025, 6)]
    assert result.n_rounds == 9
    assert result.columns[1].label == "Avg score"


def test_adjusted_and_residual_use_their_columns(frames: ExplorerFrames) -> None:
    adjusted = run_query(frames, QuerySpec(metric=Metric.ADJUSTED, group_by=[Dim.EVENT]))
    assert _values(adjusted.rows, "event") == {
        "2024-12-01": pytest.approx(-2 / 3),
        "2025-03-02": pytest.approx(-3 / 4),
        "2025-07-06": pytest.approx(0.0),
    }
    residual = run_query(frames, QuerySpec(metric=Metric.RESIDUAL, group_by=[Dim.SHOOTER]))
    assert _values(residual.rows, "shooter_id") == {
        1: pytest.approx(0.0),
        2: pytest.approx(-2.0),
        3: pytest.approx(7 / 3),
    }


def test_rating_counts_one_best_round_per_shooter_event(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.RATING, group_by=[Dim.SHOOTER]))
    # Able: 36.0 (E1), 37.0 (E2 best round only), 36.5 (E3); the E2 second round is not counted
    assert _values(result.rows, "shooter_id") == {
        1: pytest.approx(36.5),
        2: pytest.approx(29.25),
        3: pytest.approx(34.0),
    }
    assert result.rows[0]["shooter"] == "Able, Ann"


def test_counting_metrics_ignore_agg(frames: ExplorerFrames) -> None:
    rounds = run_query(frames, QuerySpec(metric=Metric.ROUNDS, agg=Agg.MAX, group_by=[Dim.SHOOTER]))
    assert _values(rounds.rows, "shooter_id") == {1: 4, 2: 2, 3: 3}
    assert rounds.columns[-2].type == "int"
    assert rounds.columns[-2].label == "Rounds"
    shooters = run_query(frames, QuerySpec(metric=Metric.SHOOTERS, group_by=[Dim.EVENT]))
    assert _values(shooters.rows, "event") == {"2024-12-01": 3, "2025-03-02": 3, "2025-07-06": 2}
    wins = run_query(frames, QuerySpec(metric=Metric.WINS, group_by=[Dim.SHOOTER]))
    assert _values(wins.rows, "shooter_id") == {1: 2, 2: 0, 3: 1}


def test_hit_pct_pools_targets_and_ignores_unlinked_entries(frames: ExplorerFrames) -> None:
    by_station = run_query(frames, QuerySpec(metric=Metric.HIT_PCT, group_by=[Dim.STATION]))
    assert _values(by_station.rows, "station") == {
        "4": pytest.approx(100 * 12 / 14),
        "10": pytest.approx(100 * 14 / 16),
    }
    overall = run_query(frames, QuerySpec(metric=Metric.HIT_PCT))
    assert overall.rows[0]["value"] == pytest.approx(100 * 26 / 30)
    assert overall.rows[0]["n"] == 4
    assert overall.n_rounds == 2


def test_attendance_by_year_uses_event_head_counts(frames: ExplorerFrames) -> None:
    avg = run_query(frames, QuerySpec(metric=Metric.ATTENDANCE, group_by=[Dim.YEAR]))
    assert _values(avg.rows, "year") == {2024: 3.0, 2025: 6.0}
    assert avg.n_rounds == 0
    total = run_query(frames, QuerySpec(metric=Metric.ATTENDANCE, agg=Agg.SUM, group_by=[Dim.YEAR]))
    assert _values(total.rows, "year") == {2024: 3.0, 2025: 18.0}
    assert total.columns[-2].label == "Total attendance"


def test_group_by_gauge_keeps_unspecified(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.GAUGE]))
    assert result.rows == [
        {"gauge": "12 Gauge", "value": 4, "n": 4},
        {"gauge": "Sub-Gauge", "value": 3, "n": 3},
        {"gauge": "unspecified", "value": 2, "n": 2},
    ]


def test_dim_season_december_is_winter(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.SEASON]))
    # the only winter rounds are the three shot on 2024-12-01
    assert result.rows[0] == {"season": "winter", "value": 3, "n": 3}


def test_dim_season_column_is_labelled_time_of_year(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.SEASON]))
    assert next((c.key, c.label) for c in result.columns) == ("season", "Time of year")


def test_two_dims_group_by_combination(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.YEAR, Dim.STATUS]))
    assert [(r["year"], r["status"], r["value"]) for r in result.rows] == [
        (2024, "deceased", 1),
        (2024, "guest", 1),
        (2024, "member", 1),
        (2025, "deceased", 2),
        (2025, "guest", 1),
        (2025, "member", 3),
    ]


def test_status_dim_uses_the_current_shooter_status(frames: ExplorerFrames) -> None:
    # round 3 has per-round status "member"; it still counts under Slocum's shooter_status
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.STATUS]))
    assert _values(result.rows, "status") == {"deceased": 3, "guest": 2, "member": 4}


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (Filters(statuses=["deceased"]), {3: 1}),
        (Filters(gauges=["Sub-Gauge", "unspecified"]), {2: 0, 3: 1}),
    ],
)
def test_wins_keep_the_full_field_rank_under_filters(
    filters: Filters, expected: dict[int, int], frames: ExplorerFrames
) -> None:
    # C7: event_rank is never recomputed inside a filtered subset. In the full field Slocum ranks
    # 2nd at E1 and E2 and 1st at E3; re-ranked among the filtered shooters he would win all three.
    by_shooter = run_query(
        frames, QuerySpec(metric=Metric.WINS, group_by=[Dim.SHOOTER], filters=filters)
    )
    assert _values(by_shooter.rows, "shooter_id") == expected
    by_event = run_query(
        frames, QuerySpec(metric=Metric.WINS, group_by=[Dim.EVENT], filters=filters)
    )
    assert _values(by_event.rows, "event") == {"2024-12-01": 0, "2025-03-02": 0, "2025-07-06": 1}


@pytest.mark.parametrize("sort", ["key_asc", "key_desc"])
@pytest.mark.parametrize(
    ("dim", "reading", "value", "keys"),
    [
        (Dim.TEMP_BAND, "temp_f", 52.0, [("40-55", 2024), ("40-55", 2025), ("85+", 2025)]),
        (Dim.WIND_BAND, "gust_mph", 18.0, [("10-20", 2024), ("10-20", 2025), ("20+", 2025)]),
        (Dim.PRECIP_BAND, "precip_in", 0.01, [("dry", 2024), ("dry", 2025), ("wet", 2025)]),
    ],
)
def test_weather_band_then_year_orders_years_within_each_band(
    sort: Literal["key_asc", "key_desc"],
    dim: Dim,
    reading: str,
    value: float,
    keys: list[tuple[str, int]],
    frames: ExplorerFrames,
) -> None:
    # D21: key_* orders by each dim in turn. E1 (2024) moves into the band of keys[0], which a
    # 2025 event is also in, with a higher reading than that event: the band's lowest reading
    # then differs per year, and must not order the years.
    rounds = frames.rounds.copy()
    e1 = rounds["event_date"] == date(2024, 12, 1)
    rounds.loc[e1, reading] = value
    rounds.loc[e1, dim.value] = keys[0][0]
    result = run_query(
        replace(frames, rounds=rounds),
        QuerySpec(metric=Metric.ROUNDS, group_by=[dim, Dim.YEAR], sort=sort),
    )
    expected = keys if sort == "key_asc" else keys[::-1]
    assert [(r[dim.value], r["year"]) for r in result.rows] == expected


@pytest.mark.parametrize(
    ("filters", "expected_rounds"),
    [
        (Filters(date_from=date(2025, 1, 1)), 6),
        (Filters(date_to=date(2025, 3, 2)), 7),
        (Filters(shooter_ids=[3]), 3),
        (Filters(round_types=[RoundType.SUPER_SPORTING]), 2),
        (Filters(statuses=["guest"]), 2),
        (Filters(statuses=["deceased"]), 3),  # incl. round 3, whose per-round status is member
        (Filters(gauges=["unspecified"]), 2),
        (Filters(temp_f=(45.0, 95.0)), 6),
        (Filters(gust_mph=(0.0, 10.0)), 3),
        (Filters(precip_in=(0.02, 1.0)), 4),
        (Filters(min_rounds=3), 7),
        (Filters(best_round_only=True), 8),
    ],
)
def test_round_filters(filters: Filters, expected_rounds: int, frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, filters=filters))
    assert result.rows[0]["value"] == expected_rounds
    assert result.n_rounds == expected_rounds


def test_event_filters_apply_to_attendance(frames: ExplorerFrames) -> None:
    by_temp = run_query(
        frames, QuerySpec(metric=Metric.ATTENDANCE, agg=Agg.SUM, filters=Filters(temp_f=(0, 60)))
    )
    assert by_temp.rows[0]["value"] == 7.0  # E1 + E2; the weatherless E4 never matches a range
    by_type = run_query(
        frames,
        QuerySpec(
            metric=Metric.ATTENDANCE,
            agg=Agg.SUM,
            filters=Filters(round_types=[RoundType.SPORTING], date_from=date(2025, 1, 1)),
        ),
    )
    assert by_type.rows[0]["value"] == 16.0  # E2 + E4


def test_sorting_and_limit(frames: ExplorerFrames) -> None:
    desc = run_query(
        frames,
        QuerySpec(metric=Metric.SCORE, group_by=[Dim.SHOOTER], sort="value_desc", limit=2),
    )
    assert [r["shooter_id"] for r in desc.rows] == [3, 1]
    assert desc.truncated is True
    asc = run_query(
        frames, QuerySpec(metric=Metric.SCORE, group_by=[Dim.SHOOTER], sort="value_asc")
    )
    assert [r["shooter_id"] for r in asc.rows] == [2, 1, 3]
    assert asc.truncated is False
    key_desc = run_query(
        frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.YEAR], sort="key_desc")
    )
    assert [r["year"] for r in key_desc.rows] == [2025, 2024]


def test_missing_values_serialize_as_null_and_sort_last(frames: ExplorerFrames) -> None:
    rounds = frames.rounds.copy()
    rounds.loc[rounds["event_date"] == date(2024, 12, 1), "adjusted"] = np.nan
    result = run_query(
        replace(frames, rounds=rounds),
        QuerySpec(metric=Metric.ADJUSTED, group_by=[Dim.EVENT], sort="value_desc"),
    )
    assert result.rows[-1] == {"event": "2024-12-01", "value": None, "n": 0}
    assert json.loads(result.model_dump_json())["rows"][-1]["value"] is None
    single = run_query(
        frames, QuerySpec(metric=Metric.SCORE, agg=Agg.STDEV, group_by=[Dim.SHOOTER])
    )
    assert all(row["value"] is not None for row in single.rows)
    one_round = run_query(
        frames,
        QuerySpec(
            metric=Metric.SCORE,
            agg=Agg.STDEV,
            group_by=[Dim.SHOOTER],
            filters=Filters(date_to=date(2024, 12, 1)),
        ),
    )
    assert [row["value"] for row in one_round.rows] == [None, None, None]


@pytest.mark.parametrize("agg", list(Agg))
def test_a_group_without_readings_is_null_for_every_agg(agg: Agg, frames: ExplorerFrames) -> None:
    rounds = frames.rounds.copy()
    rounds.loc[rounds["event_date"] == date(2024, 12, 1), "adjusted"] = np.nan
    result = run_query(
        replace(frames, rounds=rounds),
        QuerySpec(metric=Metric.ADJUSTED, agg=agg, group_by=[Dim.EVENT]),
    )
    empty = 0 if agg is Agg.COUNT else None
    assert result.rows[0] == {"event": "2024-12-01", "value": empty, "n": 0}
    assert all(row["value"] is not None for row in result.rows[1:])


def test_sum_and_p90_skip_missing_readings(frames: ExplorerFrames) -> None:
    rounds = frames.rounds.copy()
    rounds.loc[rounds["event_date"] == date(2024, 12, 1), "adjusted"] = np.nan
    rounds.loc[rounds["round_id"] == 5, "adjusted"] = np.nan
    changed = replace(frames, rounds=rounds)
    # E2 adjusted 4.5, -7.5, 1.5 (round 5 missing); E3 -3.0, 3.0
    total = run_query(changed, QuerySpec(metric=Metric.ADJUSTED, agg=Agg.SUM, group_by=[Dim.EVENT]))
    assert [(r["event"], r["value"], r["n"]) for r in total.rows] == [
        ("2024-12-01", None, 0),
        ("2025-03-02", pytest.approx(-1.5), 3),
        ("2025-07-06", pytest.approx(0.0), 2),
    ]
    p90 = run_query(changed, QuerySpec(metric=Metric.ADJUSTED, agg=Agg.P90, group_by=[Dim.EVENT]))
    assert [(r["event"], r["value"], r["n"]) for r in p90.rows] == [
        ("2024-12-01", None, 0),
        ("2025-03-02", pytest.approx(3.9), 3),  # sorted -7.5 1.5 4.5: 1.5 + 0.8 * 3.0
        ("2025-07-06", pytest.approx(2.4), 2),  # -3.0 + 0.9 * 6.0
    ]


def test_sum_and_p90_by_two_dims(frames: ExplorerFrames) -> None:
    # each group's reducer must line up with its own keys
    spec = QuerySpec(metric=Metric.SCORE, agg=Agg.P90, group_by=[Dim.STATUS, Dim.YEAR])
    p90 = run_query(frames, spec)
    assert [(r["status"], r["year"], r["value"]) for r in p90.rows] == [
        ("deceased", 2024, 36.0),
        ("deceased", 2025, pytest.approx(44.6)),  # sorted 41 45: 41 + 0.9 * 4
        ("guest", 2024, 30.0),
        ("guest", 2025, 32.0),
        ("member", 2024, 40.0),
        ("member", 2025, pytest.approx(43.0)),  # sorted 38 39 44: 39 + 0.8 * 5
    ]
    total = run_query(frames, spec.model_copy(update={"agg": Agg.SUM}))
    assert [(r["status"], r["year"], r["value"]) for r in total.rows] == [
        ("deceased", 2024, 36.0),
        ("deceased", 2025, 86.0),
        ("guest", 2024, 30.0),
        ("guest", 2025, 32.0),
        ("member", 2024, 40.0),
        ("member", 2025, 121.0),
    ]


@pytest.mark.parametrize("agg", list(Agg))
def test_empty_result_after_filters(agg: Agg, frames: ExplorerFrames) -> None:
    result = run_query(
        frames,
        QuerySpec(
            metric=Metric.SCORE, agg=agg, group_by=[Dim.YEAR], filters=Filters(shooter_ids=[99])
        ),
    )
    assert result.rows == []
    assert result.n_rounds == 0
    assert result.truncated is False


@pytest.mark.parametrize(
    ("spec", "fragment"),
    [
        (QuerySpec(metric=Metric.SCORE, group_by=[Dim.YEAR, Dim.YEAR]), "only once"),
        (QuerySpec(metric=Metric.SCORE, limit=0), "limit"),
        (QuerySpec(metric=Metric.SCORE, group_by=[Dim.STATION]), "Hit %"),
        (QuerySpec(metric=Metric.ATTENDANCE, group_by=[Dim.GAUGE]), "gauge"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(shooter_ids=[1])), "filters"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(statuses=["member"])), "filters"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(gauges=["SxS"])), "filters"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(min_rounds=5)), "filters"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(best_round_only=True)), "filters"),
    ],
)
def test_invalid_queries_are_rejected(
    spec: QuerySpec, fragment: str, frames: ExplorerFrames
) -> None:
    with pytest.raises(DomainError) as excinfo:
        run_query(frames, spec)
    assert excinfo.value.code == "invalid_query"
    assert fragment in str(excinfo.value)


def test_hit_pct_without_station_data_is_rejected(frames: ExplorerFrames) -> None:
    unlinked = frames.station_hits.assign(round_id=np.nan)
    with pytest.raises(DomainError, match="station data"):
        run_query(replace(frames, station_hits=unlinked), QuerySpec(metric=Metric.HIT_PCT))


def test_a_lettered_station_is_its_own_group_between_its_number_and_the_next(
    frames: ExplorerFrames,
) -> None:
    hits = frames.station_hits
    lettered = hits[hits["station_no"] == 4].assign(station_label="4A", hits=1)
    more = hits[hits["station_no"] == 10].assign(station_no=10, station_label="10")
    combined = replace(
        frames, station_hits=pd.concat([more, lettered, hits[hits["station_no"] == 4]])
    )
    by_station = run_query(combined, QuerySpec(metric=Metric.HIT_PCT, group_by=[Dim.STATION]))
    assert [row["station"] for row in by_station.rows] == ["4", "4A", "10"]
    assert by_station.columns[0].type == "string"
    descending = run_query(
        combined, QuerySpec(metric=Metric.HIT_PCT, group_by=[Dim.STATION], sort="key_desc")
    )
    assert [row["station"] for row in descending.rows] == ["10", "4A", "4"]
