import math
from collections.abc import Callable
from datetime import date

import pandas as pd
import pytest

from sunday_clays.analytics.metrics import (
    best_round_mask,
    compute_event_metrics,
    compute_round_metrics,
)

D = date(2026, 9, 13)
D0 = date(2026, 9, 6)


def _by_id(metrics: pd.DataFrame) -> dict[int, dict[str, object]]:
    return {int(r["round_id"]): r for r in metrics.to_dict(orient="records")}


def test_ties_share_min_rank(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds([(D, 1, 45), (D, 2, 45), (D, 3, 40), (D, 4, 38)])

    m = _by_id(compute_round_metrics(rounds))

    assert [m[i]["event_rank"] for i in (1, 2, 3, 4)] == [1.0, 1.0, 3.0, 4.0]
    # average ranks 1.5, 1.5, 3, 4 over n_best = 4 -> (4 - r) / 3
    assert math.isclose(m[1]["percentile"], 2.5 / 3)
    assert math.isclose(m[2]["percentile"], 2.5 / 3)
    assert math.isclose(m[3]["percentile"], 1 / 3)
    assert m[4]["percentile"] == 0.0


def test_best_round_used_for_rank(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds(
        [
            {"event_date": D, "shooter_id": 1, "score": 30, "round_id": 10},
            {"event_date": D, "shooter_id": 1, "score": 44, "round_id": 11},
            {"event_date": D, "shooter_id": 2, "score": 42, "round_id": 12},
        ]
    )

    m = _by_id(compute_round_metrics(rounds))

    assert m[11]["is_best_round"] is True
    assert m[11]["event_rank"] == 1.0
    assert m[10]["is_best_round"] is False
    assert math.isnan(m[10]["event_rank"])
    assert math.isnan(m[10]["percentile"])
    assert m[12]["event_rank"] == 2.0
    # median of all three rounds (30, 42, 44) is 42; both of shooter 1's rounds count
    assert [m[i]["field_median"] for i in (10, 11, 12)] == [42.0, 42.0, 42.0]
    assert [m[i]["adjusted"] for i in (10, 11, 12)] == [-12.0, 2.0, 0.0]
    assert m[11]["percentile"] == 1.0
    assert m[12]["percentile"] == 0.0


def test_merged_aliases_same_day_single_best_round(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            {
                "event_date": D,
                "shooter_id": 7,
                "score": 40,
                "name_key": "tarleton wylie",
                "ordinal": 1,
                "round_id": 1,
            },
            {
                "event_date": D,
                "shooter_id": 7,
                "score": 40,
                "name_key": "tarleton amos",
                "ordinal": 1,
                "round_id": 2,
            },
            {"event_date": D, "shooter_id": 8, "score": 39, "round_id": 3},
        ]
    )

    m = _by_id(compute_round_metrics(rounds))

    assert [m[i]["is_best_round"] for i in (1, 2, 3)] == [False, True, True]
    assert m[2]["event_rank"] == 1.0
    assert m[3]["event_rank"] == 2.0
    # n_best counts distinct shooters (2), not rounds (3)
    assert m[3]["percentile"] == 0.0


def test_equal_scores_same_name_key_pick_lowest_ordinal(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            {
                "event_date": D,
                "shooter_id": 5,
                "score": 40,
                "ordinal": 2,
                "round_id": 1,
            },
            {
                "event_date": D,
                "shooter_id": 5,
                "score": 40,
                "ordinal": 1,
                "round_id": 2,
            },
        ]
    )

    m = _by_id(compute_round_metrics(rounds))

    assert [m[1]["is_best_round"], m[2]["is_best_round"]] == [False, True]


def test_non_held_event_has_ranks_but_no_field_metrics(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds([(D0, 1, 40), (D0, 2, 30)], held=False)

    m = _by_id(compute_round_metrics(rounds))

    assert [m[1]["event_rank"], m[2]["event_rank"]] == [1.0, 2.0]
    assert all(
        math.isnan(m[i][c]) for i in (1, 2) for c in ("field_median", "adjusted", "percentile")
    )


def test_single_shooter_percentile_is_one(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    m = _by_id(compute_round_metrics(make_rounds([(D, 1, 20)])))
    assert m[1]["percentile"] == 1.0
    assert m[1]["event_rank"] == 1.0


def test_ranks_are_per_event(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds([(D0, 1, 20), (D0, 2, 25), (D, 1, 30), (D, 2, 10)])

    metrics = compute_round_metrics(rounds)
    joined = rounds[["round_id", "event_date", "shooter_id"]].merge(metrics, on="round_id")
    ranks = {(r.event_date, r.shooter_id): r.event_rank for r in joined.itertuples()}

    assert ranks == {(D0, 1): 2.0, (D0, 2): 1.0, (D, 1): 1.0, (D, 2): 2.0}


def test_empty_frames_have_the_output_columns(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    empty = make_rounds([(D, 1, 20)]).iloc[0:0]
    assert list(compute_round_metrics(empty).columns) == [
        "round_id",
        "field_median",
        "adjusted",
        "event_rank",
        "is_best_round",
        "percentile",
    ]
    event_metrics = compute_event_metrics(empty)
    assert event_metrics.empty
    assert list(event_metrics.columns) == [
        "event_date",
        "n",
        "median",
        "mean",
        "stdev",
        "top_score",
        "difficulty",
    ]


def test_event_metrics_per_event(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds([(D0, 1, 20), (D0, 2, 30), (D0, 1, 40), (D, 3, 25)])

    ev = compute_event_metrics(rounds).set_index("event_date")

    assert ev.loc[D0, "n"] == 3
    assert ev.loc[D0, "median"] == 30.0
    assert ev.loc[D0, "mean"] == 30.0
    assert ev.loc[D0, "stdev"] == 10.0
    assert ev.loc[D0, "top_score"] == 40
    assert ev.loc[D, "n"] == 1
    assert math.isnan(ev.loc[D, "stdev"])
    assert ev["difficulty"].isna().all()


def test_shuffled_index_mixed_held_rows_stay_aligned(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            {"event_date": D0, "shooter_id": 1, "score": 40, "held": False},
            {"event_date": D0, "shooter_id": 2, "score": 30, "held": False},
            {"event_date": D, "shooter_id": 1, "score": 45},
            {"event_date": D, "shooter_id": 1, "score": 30},
            {"event_date": D, "shooter_id": 2, "score": 45},
            {"event_date": D, "shooter_id": 3, "score": 40},
        ]
    )
    # a filtered, reordered frame: non-contiguous labels, not in label order
    shuffled = rounds.set_axis([50, 3, 41, 7, 12, 0]).iloc[[3, 0, 5, 1, 4, 2]]

    metrics = compute_round_metrics(shuffled)

    assert metrics["round_id"].tolist() == shuffled["round_id"].tolist()
    assert metrics.index.tolist() == list(range(6))
    m = _by_id(metrics)
    assert best_round_mask(shuffled).tolist() == [False, True, True, True, True, True]
    # held date D: best rounds 45, 45, 40 (shooter 1's 30 is not best); median of all 4 = 42.5
    assert [m[i]["event_rank"] for i in (3, 5, 6)] == [1.0, 1.0, 3.0]
    assert [m[i]["percentile"] for i in (3, 5, 6)] == [0.75, 0.75, 0.0]
    assert math.isnan(m[4]["event_rank"])
    assert math.isnan(m[4]["percentile"])
    assert [m[i]["field_median"] for i in (3, 4, 5, 6)] == [42.5] * 4
    assert [m[i]["adjusted"] for i in (3, 4, 5, 6)] == [2.5, -12.5, 2.5, -2.5]
    # non-held date D0: ranks only
    assert [m[1]["event_rank"], m[2]["event_rank"]] == [1.0, 2.0]
    assert all(
        math.isnan(m[i][c]) for i in (1, 2) for c in ("field_median", "adjusted", "percentile")
    )


@pytest.mark.parametrize("compute", [best_round_mask, compute_round_metrics])
def test_duplicate_index_labels_raise_clearly(
    make_rounds: Callable[..., pd.DataFrame],
    compute: Callable[[pd.DataFrame], object],
) -> None:
    # e.g. pd.concat of two load_rounds frames without ignore_index=True
    rounds = make_rounds([(D, 1, 45), (D, 2, 40)])
    later = make_rounds([{"event_date": D0, "shooter_id": 1, "score": 30, "round_id": 3}])
    doubled = pd.concat([rounds, later])  # labels 0, 1, 0

    with pytest.raises(ValueError, match="rounds must have a unique index"):
        compute(doubled)
