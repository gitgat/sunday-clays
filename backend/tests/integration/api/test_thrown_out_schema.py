"""The thrown-out fields are always sent, so the OpenAPI schema requires them."""

import pytest

from sunday_clays.api.app import create_app

FIELDS = [
    ("EventSummaryOut", "stats_excluded"),
    ("EventSummaryOut", "thrown_out"),
    ("EventDetailOut", "stats_excluded"),
    ("EventDetailOut", "thrown_out"),
    ("EventResultOut", "stats_excluded"),
    ("WinnerOut", "stats_excluded"),
    ("AttendanceOut", "stats_excluded"),
    ("StationLayoutOut", "dropped"),
    ("RecapOut", "thrown_out"),
    ("ThrownOutOut", "station_label"),
    ("ThrownOutOut", "target_count"),
    ("ThrownOutOut", "credited"),
]


@pytest.mark.parametrize(("model", "field"), FIELDS)
def test_thrown_out_fields_are_required_in_the_openapi_schema(model: str, field: str) -> None:
    assert field in create_app().openapi()["components"]["schemas"][model]["required"]
