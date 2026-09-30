"""Explorer additions insights link to (Plan 12 spec §3.6.3): difficulty, p25, min_score, ytd."""

import pytest
from pydantic import ValidationError

from sunday_clays.domain.errors import DomainError
from sunday_clays.explorer.engine import ExplorerFrames, run_query
from sunday_clays.explorer.spec import Agg, Dim, Filters, Metric, QuerySpec


def test_difficulty_is_one_value_per_sunday(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.DIFFICULTY, group_by=[Dim.EVENT]))
    assert [(r["event"], r["value"]) for r in result.rows] == [
        ("2024-12-01", 1.5),
        ("2025-03-02", -0.5),
        ("2025-07-06", 3.0),
        ("2025-11-02", None),  # attendance only: no difficulty
    ]
    assert result.columns[-2].label == "Avg how the day played"


@pytest.mark.parametrize(
    "filters",
    [Filters(shooter_ids=[1]), Filters(best_round_only=True), Filters(min_rounds=2)],
)
def test_difficulty_rejects_shooter_level_filters(frames: ExplorerFrames, filters: Filters) -> None:
    with pytest.raises(DomainError, match="Sunday total"):
        run_query(frames, QuerySpec(metric=Metric.DIFFICULTY, filters=filters))


def test_p25_is_the_low_end(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.SCORE, agg=Agg.P25))
    # scores sorted 30 32 36 38 39 40 41 44 45: position 8 * 0.25 = 2 -> 36
    assert result.rows[0]["value"] == 36.0
    assert result.columns[-2].label == "Low end of score"


def test_min_score_keeps_rounds_at_or_above_it(frames: ExplorerFrames) -> None:
    spec = QuerySpec(
        metric=Metric.ROUNDS, group_by=[Dim.YEAR], filters=Filters(min_score=40, shooter_ids=[1])
    )
    assert [(r["year"], r["value"]) for r in run_query(frames, spec).rows] == [(2024, 1), (2025, 1)]


@pytest.mark.parametrize(
    "metric", [Metric.ATTENDANCE, Metric.DIFFICULTY, Metric.RATING, Metric.HIT_PCT]
)
def test_min_score_needs_a_round_metric(frames: ExplorerFrames, metric: Metric) -> None:
    spec = QuerySpec(metric=metric, filters=Filters(min_score=40))
    with pytest.raises(DomainError, match="minimum score"):
        run_query(frames, spec)


def test_ytd_cuts_every_year_at_the_same_date(frames: ExplorerFrames) -> None:
    spec = QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.YEAR], filters=Filters(ytd="03-02"))
    # 2024: Dec 1 is after Mar 2 -> none; 2025: the Mar 2 rounds (4) only
    assert [(r["year"], r["value"]) for r in run_query(frames, spec).rows] == [(2025, 4)]


def test_ytd_needs_the_year_grouping(frames: ExplorerFrames) -> None:
    spec = QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.MONTH], filters=Filters(ytd="03-02"))
    with pytest.raises(DomainError, match="year grouping"):
        run_query(frames, spec)


@pytest.mark.parametrize("bad", ["3-2", "13-01", "02-30x", "00-10"])
def test_ytd_must_be_month_day(bad: str) -> None:
    with pytest.raises(ValueError, match="ytd"):
        Filters(ytd=bad)


@pytest.mark.parametrize("score", [-1, 51])
def test_min_score_is_bounded_to_a_round_score(score: int) -> None:
    with pytest.raises(ValidationError):
        Filters(min_score=score)
