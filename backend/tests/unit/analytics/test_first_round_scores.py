from datetime import date

import pandas as pd

from sunday_clays.analytics.cohorts import first_round_scores


def _rounds(*rows: tuple[int, date, int]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["shooter_id", "event_date", "score"])


def test_best_round_of_each_first_date_within_the_window() -> None:
    rounds = _rounds(
        (1, date(2025, 1, 5), 30),
        (1, date(2025, 1, 5), 36),
        (1, date(2025, 1, 12), 49),
        (2, date(2025, 1, 12), 20),
        (3, date(2025, 2, 2), 41),
    )
    assert first_round_scores(rounds, None, None) == [20, 36, 41]
    assert first_round_scores(rounds, date(2025, 1, 6), None) == [20, 41]
    assert first_round_scores(rounds, None, date(2025, 1, 12)) == [20, 36]


def test_no_rounds() -> None:
    assert first_round_scores(_rounds(), None, None) == []
