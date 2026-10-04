"""R1 for the Features page copy: no he/she/his/her/him/hers/himself/herself and no "class"."""

from typing import get_args

import pytest

from sunday_clays.analytics.insights.lints import lint_text
from sunday_clays.domain.features import FEATURES, Feature, FeatureKey

BANNED_CODES = ("pronoun", "class")


@pytest.mark.parametrize("feature", FEATURES, ids=lambda f: f.key)
def test_feature_label_and_description_use_no_banned_word(feature: Feature) -> None:
    for text in (feature.label, feature.description):
        problems = [p for p in lint_text(text, named=False) if p.startswith(BANNED_CODES)]
        assert problems == [], text


def test_the_lint_used_here_does_catch_the_banned_words() -> None:
    # Kills a mutation that filters on the wrong lint codes: both words must still be caught.
    assert any(p.startswith("pronoun") for p in lint_text("Her preview", named=False))
    assert any(p.startswith("class") for p in lint_text("A class of shooter", named=False))


def test_the_registry_holds_six_features_then_the_page_cache_kill_switch() -> None:
    assert [(f.key, f.kind, f.default_on) for f in FEATURES] == [
        ("link_previews", "feature", False),
        ("tour_glossary", "feature", False),
        ("weekly_recap", "feature", False),
        ("pwa", "feature", False),
        ("club_milestones", "feature", False),
        ("summary_card", "feature", False),
        ("page_cache", "infrastructure", True),
    ]


def test_the_registry_covers_every_feature_key_exactly_once() -> None:
    keys = [f.key for f in FEATURES]
    assert len(keys) == len(set(keys))
    assert set(keys) == set(get_args(FeatureKey))
