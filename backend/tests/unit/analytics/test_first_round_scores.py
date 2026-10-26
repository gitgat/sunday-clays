from datetime import date

import pandas as pd

from sunday_clays.analytics.cohorts import first_round_scores


def _rounds(*rows: tuple[int, date, int] | tuple[int, date, int, bool]) -> pd.DataFrame:
    padded = [(*row, False) if len(row) == 3 else row for row in rows]
    return pd.DataFrame(padded, columns=["shooter_id", "event_date", "score", "stats_excluded"])


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


def test_a_shooter_whose_first_sunday_was_thrown_out_is_left_out() -> None:
    rounds = _rounds(
        (1, date(2025, 1, 5), 50, True), (1, date(2025, 1, 12), 33), (2, date(2025, 1, 12), 28)
    )
    assert first_round_scores(rounds, None, None) == [28]
