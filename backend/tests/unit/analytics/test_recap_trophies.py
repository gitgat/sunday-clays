"""Recap trophy wording (owner, 2026-10-04): the number reached, never the metal."""

import re

import pytest

from sunday_clays.analytics.achievements.registry import all_achievements
from sunday_clays.analytics.recap_trophies import (
    ONE_OFF_EXPLANATIONS,
    recap_trophy_items,
)
from sunday_clays.analytics.summary import LEFT_OUT_TROPHY_CODES

METALS = re.compile(r"\b(bronze|silver|gold|platinum|diamond|tier|level)\b", re.IGNORECASE)


@pytest.mark.parametrize(
    ("codes", "items"),
    [
        (["events:4"], ["Events Attended - 50"]),
        (["clays_broken:3"], ["Clays Broken - 1,000"]),
        (["clays_broken:6"], ["Clays Broken - 10,000"]),
        (["events:1"], ["Events Attended - 1"]),
        (["round_score:5"], ["Round Score - 48"]),
    ],
)
def test_a_tier_reads_as_the_number_reached(codes: list[str], items: list[str]) -> None:
    assert recap_trophy_items(codes) == items


def test_only_the_highest_tier_of_a_family_crossed_on_the_day() -> None:
    assert recap_trophy_items(["events:3", "events:4"]) == ["Events Attended - 50"]
    assert recap_trophy_items(["events:4", "events:3"]) == ["Events Attended - 50"]


def test_families_stay_separate_and_keep_first_seen_order() -> None:
    assert recap_trophy_items(["events:3", "clays_broken:2", "events:4"]) == [
        "Events Attended - 50",
        "Clays Broken - 500",
    ]


def test_a_one_off_is_its_name_with_a_plain_explanation_when_needed() -> None:
    assert recap_trophy_items(["doubleheader"]) == [
        f"Doubleheader ({ONE_OFF_EXPLANATIONS['doubleheader']})"
    ]
    assert ONE_OFF_EXPLANATIONS["doubleheader"] == "two rounds in one day"


def test_a_one_off_without_an_explanation_is_just_the_name() -> None:
    assert recap_trophy_items(["three_bird_shoot"]) == ["3-Bird Shoot"]


def test_the_four_left_out_trophies_and_unknown_codes_are_dropped() -> None:
    assert recap_trophy_items(["first_win", "podium", "station_top_gun", "nope", "events:2"]) == [
        "Events Attended - 10"
    ]
    assert recap_trophy_items(["hardest_station_clean"]) == []
    assert LEFT_OUT_TROPHY_CODES.isdisjoint(ONE_OFF_EXPLANATIONS)


def test_nothing_ever_says_a_metal_tier_or_level() -> None:
    every = [a.code for a in all_achievements() if not a.tiers]
    every += [f"{a.code}:{t.level}" for a in all_achievements() for t in a.tiers]
    for code in every:
        for item in recap_trophy_items([code]):
            assert not METALS.search(item), item
    for text in ONE_OFF_EXPLANATIONS.values():
        assert not re.search(r"\b(you|your|he|she|his|her|class)\b", text, re.IGNORECASE)


def test_explanations_only_for_real_one_off_codes() -> None:
    one_offs = {a.code for a in all_achievements() if not a.tiers}
    assert set(ONE_OFF_EXPLANATIONS) <= one_offs


def test_a_fractional_threshold_keeps_its_decimals() -> None:
    from sunday_clays.analytics.achievements.registry import Metal, Tier
    from sunday_clays.analytics.recap_trophies import threshold_text

    assert threshold_text(Tier(1, 2.5, Metal.BRONZE, "x")) == "2.5"
    assert threshold_text(Tier(1, 10000.0, Metal.BRONZE, "x")) == "10,000"
