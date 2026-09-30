from typing import Any

import pytest
from pydantic import ValidationError

from sunday_clays.explorer.spec import Agg, Dim, Filters, Metric, QuerySpec


def test_minimal_spec_gets_the_documented_defaults() -> None:
    spec = QuerySpec.model_validate({"metric": "score"})
    assert spec.agg is Agg.AVG
    assert spec.group_by == []
    assert spec.sort == "key_asc"
    assert spec.limit == 500
    assert spec.filters == Filters()
    assert spec.filters.date_from is None
    assert spec.filters.temp_f is None
    assert spec.filters.min_rounds == 0
    assert spec.filters.best_round_only is False


def test_group_by_allows_at_most_two_dims() -> None:
    assert QuerySpec(metric=Metric.SCORE, group_by=[Dim.YEAR, Dim.GAUGE]).group_by == [
        Dim.YEAR,
        Dim.GAUGE,
    ]
    with pytest.raises(ValidationError, match="at most 2"):
        QuerySpec.model_validate({"metric": "score", "group_by": ["year", "gauge", "status"]})


def test_limit_is_capped_at_5000() -> None:
    assert QuerySpec(metric=Metric.SCORE, limit=5000).limit == 5000
    with pytest.raises(ValidationError):
        QuerySpec(metric=Metric.SCORE, limit=5001)


@pytest.mark.parametrize(
    "payload",
    [
        {"metric": "handicap"},
        {"metric": "score", "agg": "mode"},
        {"metric": "score", "group_by": ["weekday"]},
        {"metric": "score", "sort": "random"},
        {"metric": "score", "filters": {"round_types": ["trap"]}},
        {"metric": "score", "filters": {"temp_f": [40, 50, 60]}},
    ],
)
def test_unknown_values_are_rejected(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        QuerySpec.model_validate(payload)


def test_weather_ranges_are_numeric_pairs() -> None:
    assert Filters.model_validate({"temp_f": [40, 70]}).temp_f == (40.0, 70.0)
