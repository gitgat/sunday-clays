from datetime import date

import pytest
from pydantic import ValidationError

from sunday_clays.domain.rules import PAYLOAD_MODELS, RuleType, StationDropPayload


def test_station_drop_is_a_rule_type_with_its_payload_model() -> None:
    assert RuleType("station_drop") is RuleType.STATION_DROP
    assert PAYLOAD_MODELS[RuleType.STATION_DROP] is StationDropPayload


def test_station_drop_payload_normalizes_the_label() -> None:
    p = StationDropPayload.model_validate(
        {"event_date": "2026-10-25", "station_label": " 7a ", "dropped": True}
    )
    assert (p.event_date, p.station_label, p.dropped) == (date(2026, 10, 25), "7A", True)


def test_station_drop_payload_rejects_a_non_label() -> None:
    with pytest.raises(ValidationError, match="is not a station number or label like 7A"):
        StationDropPayload.model_validate(
            {"event_date": "2026-10-25", "station_label": "Total", "dropped": True}
        )


def test_a_sunday_level_payload_can_only_mark_thrown_out() -> None:
    with pytest.raises(
        ValidationError, match="A Sunday-level rule can only mark a Sunday as thrown out"
    ):
        StationDropPayload.model_validate({"event_date": "2026-10-25", "dropped": False})
    p = StationDropPayload.model_validate({"event_date": "2026-10-25", "dropped": True})
    assert p.model_dump(mode="json") == {
        "event_date": "2026-10-25",
        "station_label": None,
        "dropped": True,
    }
