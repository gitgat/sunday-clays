"""Recap rules (Plan 19 §3.3.1, D15): podium ties, the 3-bird counts."""

from datetime import date

import pandas as pd
import pytest

from sunday_clays.api.routes.admin_recap import is_three_bird, podium_of, three_bird_counts


def day(*best: tuple[str, int, int | None]) -> pd.DataFrame:
    """(display_name, score, event_rank) best rounds, plus one non-best round."""
    rows = [
        {"display_name": n, "score": s, "event_rank": r, "is_best_round": True} for n, s, r in best
    ]
    rows.append(
        {"display_name": "Zed, Extra", "score": 10, "event_rank": None, "is_best_round": False}
    )
    return pd.DataFrame(rows)


def places(frame: pd.DataFrame) -> list[tuple[int, bool, int, list[str]]]:
    return [(p.place, p.tied, p.score, p.names) for p in podium_of(frame)]


def test_tied_first_then_third() -> None:
    frame = day(
        ("Stockton, Ethan", 49, 1),
        ("Finnegan, Stanton", 49, 1),
        ("Devlin, Sid", 47, 3),
        ("Kim, Pat", 40, 4),
    )
    assert places(frame) == [
        (1, True, 49, ["Stanton Finnegan", "Ethan Stockton"]),  # sorted by last name
        (3, False, 47, ["Sid Devlin"]),
    ]


def test_first_then_tied_second() -> None:
    frame = day(("Hadley, Ike", 48, 1), ("Kaplan, Noel", 46, 2), ("Devlin, Sid", 46, 2))
    assert places(frame) == [
        (1, False, 48, ["Ike Hadley"]),
        (2, True, 46, ["Sid Devlin", "Noel Kaplan"]),
    ]


def test_five_tied_for_third_are_all_listed_and_nobody_below() -> None:
    thirds = [(f"Shooter{i}, Test", 44, 3) for i in range(5)]
    frame = day(("A, One", 49, 1), ("B, Two", 47, 2), *thirds, ("C, Low", 40, 8))
    result = places(frame)
    assert [p[0] for p in result] == [1, 2, 3]
    assert len(result[2][3]) == 5
    assert result[2][1] is True
    assert "Low C" not in str(result)


def test_one_shooter() -> None:
    assert places(day(("Hadley, Ike", 44, 1))) == [(1, False, 44, ["Ike Hadley"])]


@pytest.mark.parametrize(
    ("label", "expected"),
    [("3-Bird Shoot", True), ("Three Bird Shoot", True), ("Turkey Shoot", False), (None, False)],
)
def test_is_three_bird(label: str | None, expected: bool) -> None:
    assert is_three_bird(label) is expected


def test_three_bird_counts_first_and_second_shoot() -> None:
    first, second = date(2026, 9, 20), date(2027, 3, 21)
    awarded = [first] * 12 + [second] * 3  # three_bird_shoot is awarded at a shooter's first one
    assert three_bird_counts(awarded, first) == (12, 12)
    assert three_bird_counts(awarded, second) == (3, 15)
