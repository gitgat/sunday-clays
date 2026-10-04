"""The `events` launch switch is registered (Plan 20 §5.1)."""

from typing import get_args

from sunday_clays.domain.features import FEATURES, FeatureKey


def test_the_events_switch_is_registered_with_its_label() -> None:
    assert "events" in get_args(FeatureKey)
    events = next(f for f in FEATURES if f.key == "events")
    assert events.label == "Club events"
    assert events.description == (
        "Club event sign-ups: the Club events page, the Coming up card on Home and the sign-up"
        " line on About."
    )
