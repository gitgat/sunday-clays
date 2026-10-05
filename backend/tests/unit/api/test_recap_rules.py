"""Recap rules (Plan 19 §3.3.1, D15): the 3-bird counts."""

from datetime import date

import pytest

from sunday_clays.api.routes.admin_recap import is_three_bird, three_bird_counts


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
