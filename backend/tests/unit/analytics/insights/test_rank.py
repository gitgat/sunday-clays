"""Ranking inputs (spec §3.4)."""

import pytest

from sunday_clays.analytics.insights.rank import base_score, rarity, recency


def test_recency_is_1_5_on_the_reference_sunday_and_decays_per_held_sunday(sun):
    held = [sun(i) for i in range(5)]
    assert recency(sun(4), sun(4), held) == 1.5
    assert recency(sun(2), sun(4), held) == pytest.approx(1.5 * 0.8**2)
    assert recency(None, sun(4), held) == 1.0


@pytest.mark.parametrize(
    ("share", "value"), [(3 / 84, 2.9), (23 / 84, 1.4), (0.5, 1.0), (0.9, 1.0), (0.0, 3.0)]
)
def test_rarity_matches_the_spec_examples(share, value):
    assert rarity(share) == pytest.approx(value, abs=0.05)


def test_strength_is_capped_at_two_in_the_score():
    assert base_score(5, 3.7, 1.0) == 10.0
    assert base_score(3, 1.2, 2.0) == pytest.approx(7.2)
