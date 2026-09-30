"""Per-round and per-event field metrics (C7): best round, rank, percentile."""

import pandas as pd

ROUND_METRIC_COLUMNS: tuple[str, ...] = (
    "round_id",
    "field_median",
    "adjusted",
    "event_rank",
    "is_best_round",
    "percentile",
)
EVENT_METRIC_COLUMNS: tuple[str, ...] = (
    "event_date",
    "n",
    "median",
    "mean",
    "stdev",
    "top_score",
    "difficulty",
)
BEST_ROUND_ORDER: tuple[str, ...] = (
    "event_date",
    "shooter_id",
    "score",
    "name_key",
    "ordinal",
)


def _require_unique_index(rounds: pd.DataFrame) -> None:
    """Results are aligned back to the input rows by label (`reindex(rounds.index)`)."""
    if not rounds.index.is_unique:
        raise ValueError(
            "rounds must have a unique index (e.g. pd.concat(..., ignore_index=True)): "
            "metrics are aligned back to the input rows by label"
        )


def best_round_mask(rounds: pd.DataFrame) -> pd.Series:
    """One True per (event_date, shooter_id): score desc, then name_key, ordinal.

    The index of `rounds` must be unique (any order, need not be a RangeIndex), else
    ValueError: the mask is aligned back to the input rows by label. The sort key is total
    on `load_rounds` data because rounds are unique on (event_date, name_key, ordinal)
    (uq_rounds_event_date_name_key_ordinal), so the pick never depends on row order.
    """
    _require_unique_index(rounds)
    ordered = rounds.sort_values(
        list(BEST_ROUND_ORDER),
        ascending=[True, True, False, True, True],
        kind="mergesort",
    )
    first = ~ordered.duplicated(["event_date", "shooter_id"], keep="first")
    return first.reindex(rounds.index)


def compute_round_metrics(rounds: pd.DataFrame) -> pd.DataFrame:
    """Field metrics for every round.

    Input columns: round_id, event_date, shooter_id, name_key, ordinal, score, held. The
    index must be unique (see best_round_mask), else ValueError.
    Output columns: ROUND_METRIC_COLUMNS, one row per input round (same order, RangeIndex).
    - field_median/adjusted: median of all rounds that day / score - median; NaN when
      the event is not held.
    - is_best_round: first round per (event_date, shooter_id) by score desc, name_key,
      ordinal.
    - event_rank: min-rank of best rounds by score (ties share); NaN for other rounds.
    - percentile: (n_best - average rank) / (n_best - 1), 1.0 when n_best == 1; NaN for
      non-best rounds and at non-held events.
    """
    if rounds.empty:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in ROUND_METRIC_COLUMNS})
    held = rounds["held"].astype(bool)
    median = rounds.groupby("event_date")["score"].transform("median").astype("float64")
    best = best_round_mask(rounds)
    best_scores = rounds.loc[best, ["event_date", "score"]]
    by_event = best_scores.groupby("event_date")["score"]
    rank_min = by_event.rank(method="min", ascending=False)
    rank_avg = by_event.rank(method="average", ascending=False)
    n_best = by_event.transform("size").astype("float64")
    denominator = (n_best - 1).where(n_best > 1)
    percentile = ((n_best - rank_avg) / denominator).where(n_best > 1, 1.0)
    percentile = percentile.where(held.loc[best])
    return pd.DataFrame(
        {
            "round_id": rounds["round_id"],
            "field_median": median.where(held),
            "adjusted": (rounds["score"] - median).where(held),
            "event_rank": rank_min.reindex(rounds.index),
            "is_best_round": best,
            "percentile": percentile.reindex(rounds.index),
        }
    ).reset_index(drop=True)


def compute_event_metrics(rounds: pd.DataFrame) -> pd.DataFrame:
    """Per scored event: n rounds, median, mean, sample stdev (NaN for n=1), top score.

    `difficulty` is NaN here; the s30 skill step fills it.
    """
    if rounds.empty:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in EVENT_METRIC_COLUMNS})
    scores = rounds.groupby("event_date")["score"]
    out = pd.DataFrame(
        {
            "n": scores.size(),
            "median": scores.median().astype("float64"),
            "mean": scores.mean(),
            "stdev": scores.std(ddof=1),
            "top_score": scores.max(),
        }
    ).reset_index()
    out["difficulty"] = float("nan")
    return out[list(EVENT_METRIC_COLUMNS)]
