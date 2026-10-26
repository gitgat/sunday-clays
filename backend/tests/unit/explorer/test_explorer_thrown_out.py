"""Explorer statistics leave out thrown-out Sundays and stations; counts keep them."""

from dataclasses import replace
from datetime import date

import pytest

from sunday_clays.api.app import create_app
from sunday_clays.explorer.engine import ExplorerFrames, run_query
from sunday_clays.explorer.spec import Agg, Dim, Filters, Metric, QuerySpec

E2 = date(2025, 3, 2)


def _thrown_out(frames: ExplorerFrames) -> ExplorerFrames:
    """E2 is a Sunday with a station thrown out; station 10 is a thrown-out station."""
    return replace(
        frames,
        rounds=frames.rounds.assign(stats_excluded=frames.rounds["event_date"].eq(E2)),
        events=frames.events.assign(stats_excluded=frames.events["event_date"].eq(E2)),
        station_hits=frames.station_hits.assign(
            dropped=frames.station_hits["station_label"].eq("10")
        ),
    )


def _values(rows: list[dict[str, str | int | float | None]], key: str) -> dict[object, object]:
    return {r[key]: r["value"] for r in rows}


def test_score_metrics_leave_out_a_thrown_out_sunday(frames: ExplorerFrames) -> None:
    f = _thrown_out(frames)
    overall = run_query(f, QuerySpec(metric=Metric.SCORE))
    assert overall.rows[0]["value"] == pytest.approx(38.0)  # (40+30+36+39+45)/5
    assert (overall.rows[0]["n"], overall.n_rounds) == (5, 5)
    for metric in (Metric.SCORE, Metric.ADJUSTED, Metric.RESIDUAL, Metric.RATING):
        result = run_query(f, QuerySpec(metric=metric, group_by=[Dim.EVENT]))
        assert [r["event"] for r in result.rows] == ["2024-12-01", "2025-07-06"], metric
    difficulty = run_query(f, QuerySpec(metric=Metric.DIFFICULTY, group_by=[Dim.EVENT]))
    assert [r["event"] for r in difficulty.rows] == ["2024-12-01", "2025-07-06", "2025-11-02"]


def test_count_metrics_keep_a_thrown_out_sunday(frames: ExplorerFrames) -> None:  # guard
    f = _thrown_out(frames)
    assert run_query(f, QuerySpec(metric=Metric.ROUNDS)).rows[0]["value"] == 9
    shooters = run_query(f, QuerySpec(metric=Metric.SHOOTERS, group_by=[Dim.EVENT]))
    assert _values(shooters.rows, "event") == {"2024-12-01": 3, "2025-03-02": 3, "2025-07-06": 2}
    wins = run_query(f, QuerySpec(metric=Metric.WINS, group_by=[Dim.SHOOTER]))
    assert _values(wins.rows, "shooter_id") == {1: 2, 2: 0, 3: 1}
    att = run_query(f, QuerySpec(metric=Metric.ATTENDANCE, agg=Agg.SUM, group_by=[Dim.EVENT]))
    assert _values(att.rows, "event")["2025-03-02"] == 4.0


def test_min_score_counts_official_scores_but_not_score_stats(frames: ExplorerFrames) -> None:
    f = _thrown_out(frames)
    rounds = run_query(f, QuerySpec(metric=Metric.ROUNDS, filters=Filters(min_score=40)))
    assert rounds.rows[0]["value"] == 4
    score = run_query(
        f, QuerySpec(metric=Metric.SCORE, agg=Agg.COUNT, filters=Filters(min_score=40))
    )
    assert score.rows[0]["value"] == 2


def test_min_rounds_on_a_score_metric_counts_only_scored_rounds(frames: ExplorerFrames) -> None:
    result = run_query(
        _thrown_out(frames),
        QuerySpec(metric=Metric.SCORE, group_by=[Dim.SHOOTER], filters=Filters(min_rounds=2)),
    )
    assert _values(result.rows, "shooter_id") == {
        1: pytest.approx(39.5),
        3: pytest.approx(40.5),
    }


def test_hit_pct_leaves_out_a_thrown_out_station(frames: ExplorerFrames) -> None:
    f = _thrown_out(frames)
    by_station = run_query(f, QuerySpec(metric=Metric.HIT_PCT, group_by=[Dim.STATION]))
    assert _values(by_station.rows, "station") == {"4": pytest.approx(100 * 12 / 14)}
    overall = run_query(f, QuerySpec(metric=Metric.HIT_PCT))
    assert overall.rows[0]["value"] == pytest.approx(100 * 12 / 14)
    assert (overall.rows[0]["n"], overall.n_rounds) == (2, 2)


def test_count_rows_by_sunday_list_the_thrown_out_dates(frames: ExplorerFrames) -> None:
    f = _thrown_out(frames)
    by_event = run_query(f, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.EVENT]))
    assert by_event.thrown_out_dates == ["2025-03-02"]
    assert run_query(f, QuerySpec(metric=Metric.SCORE, group_by=[Dim.EVENT])).thrown_out_dates == []
    assert run_query(f, QuerySpec(metric=Metric.ROUNDS)).thrown_out_dates == []
    hit = run_query(f, QuerySpec(metric=Metric.HIT_PCT, group_by=[Dim.EVENT]))
    assert hit.thrown_out_dates == []
    schema = create_app().openapi()["components"]["schemas"]["QueryResult"]
    assert "thrown_out_dates" in schema["required"]


def test_a_score_total_counts_clays_broken_on_a_thrown_out_sunday(frames: ExplorerFrames) -> None:
    f = _thrown_out(frames)
    total = run_query(f, QuerySpec(metric=Metric.SCORE, agg=Agg.SUM))
    every_round = float(frames.rounds["score"].sum())
    assert (total.rows[0]["value"], total.n_rounds) == (every_round, 9)
    by_event = run_query(f, QuerySpec(metric=Metric.SCORE, agg=Agg.SUM, group_by=[Dim.EVENT]))
    assert "2025-03-02" in _values(by_event.rows, "event")
    assert by_event.thrown_out_dates == ["2025-03-02"]
