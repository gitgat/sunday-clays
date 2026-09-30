from collections.abc import Callable
from datetime import date

import pandas as pd
import pytest

from sunday_clays.analytics.cohorts import cohort_returns, cohort_tables, newcomer_cohorts


def _shooters(censored: set[int], ids: range) -> pd.DataFrame:
    return pd.DataFrame({"shooter_id": list(ids), "left_censored": [i in censored for i in ids]})


def _assert_one_pass_matches(
    rounds: pd.DataFrame, shooters: pd.DataFrame, table: pd.DataFrame, returns: pd.DataFrame
) -> None:
    """`cohort_tables` (one pass, the route's) equals the two separate tables exactly."""
    one_pass_table, one_pass_returns = cohort_tables(rounds, shooters)
    pd.testing.assert_frame_equal(one_pass_table, table)
    pd.testing.assert_frame_equal(one_pass_returns, returns)


def test_cohorts_track_retention_and_skip_left_censored(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            (date(2024, 3, 3), 1, 30),
            (date(2025, 3, 2), 1, 30),
            (date(2026, 3, 1), 1, 30),
            (date(2024, 5, 5), 2, 30),
            (date(2025, 6, 1), 3, 30),
            (date(2025, 6, 8), 3, 30),
            (date(2024, 1, 7), 9, 30),
            (date(2026, 1, 4), 9, 30),
        ]
    )
    shooters = _shooters({9}, range(1, 10))

    table = newcomer_cohorts(rounds, shooters)

    assert [tuple(r) for r in table.itertuples(index=False)] == [
        (2024, 0, 2, 2, 1.0),
        (2024, 1, 2, 1, 0.5),
        (2024, 2, 2, 1, 0.5),
        (2025, 0, 1, 1, 1.0),
        (2025, 1, 1, 0, 0.0),
    ]
    returns = cohort_returns(rounds, shooters)
    assert [tuple(r) for r in returns.itertuples(index=False)] == [
        (2024, 2, 1),
        (2025, 1, 1),
    ]
    _assert_one_pass_matches(rounds, shooters, table, returns)


def test_cohorts_empty_when_everyone_is_left_censored(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds([(date(2020, 1, 5), 1, 30)])
    table = newcomer_cohorts(rounds, _shooters({1}, range(1, 2)))
    assert table.empty
    assert list(table.columns) == [
        "cohort_year",
        "offset",
        "n_cohort",
        "n_active",
        "share",
    ]
    returns = cohort_returns(rounds, _shooters({1}, range(1, 2)))
    assert returns.empty
    _assert_one_pass_matches(rounds, _shooters({1}, range(1, 2)), table, returns)


def test_offsets_run_to_the_last_year_with_any_round(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    # Only the left-censored shooter 9 shot in 2026; 2026 is still a data year.
    rounds = make_rounds([(date(2024, 3, 3), 1, 30), (date(2026, 1, 4), 9, 30)])

    table = newcomer_cohorts(rounds, _shooters({9}, range(1, 10)))

    assert [tuple(r) for r in table.itertuples(index=False)] == [
        (2024, 0, 1, 1, 1.0),
        (2024, 1, 1, 0, 0.0),
        (2024, 2, 1, 0, 0.0),
    ]


@pytest.mark.parametrize("empty", [True, False], ids=["empty", "non_empty"])
def test_cohort_tables_keep_column_dtypes(
    make_rounds: Callable[..., pd.DataFrame], empty: bool
) -> None:
    if empty:
        rounds = pd.DataFrame(
            {"event_date": pd.Series(dtype=object), "shooter_id": pd.Series(dtype="int64")}
        )
    else:
        rounds = make_rounds([(date(2024, 3, 3), 1, 30), (date(2025, 3, 2), 1, 30)])
    shooters = _shooters(set(), range(1, 1 if empty else 2))

    table = newcomer_cohorts(rounds, shooters)
    returns = cohort_returns(rounds, shooters)

    assert (table.empty, returns.empty) == (empty, empty)
    assert list(table.dtypes.astype(str).items()) == [
        ("cohort_year", "int64"),
        ("offset", "int64"),
        ("n_cohort", "int64"),
        ("n_active", "int64"),
        ("share", "float64"),
    ]
    assert list(returns.dtypes.astype(str).items()) == [
        ("cohort_year", "int64"),
        ("n_cohort", "int64"),
        ("n_returned", "int64"),
    ]
    _assert_one_pass_matches(rounds, shooters, table, returns)
