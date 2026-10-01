"""What an admin reads for a bumped post key (Plan 14 Task 3)."""

import pytest

from sunday_clays.api.routes.admin_sheet import post_label


@pytest.mark.parametrize(
    ("key", "label"),
    [
        ("0123456789abcdef0123", "New personal best for Ike Hadley: 46."),
        ("trophy:round_score:4:2026-09-27", "Trophy round_score:4, 2026-09-27"),
        ("otd:2026-09-27:2", "On this day, 2026-09-27"),
        ("fedcba9876543210fedc", "No longer on a Sheet"),
        ("trophy:broken", "No longer on a Sheet"),
    ],
)
def test_post_labels(key: str, label: str) -> None:
    headlines = {"0123456789abcdef0123": "New personal best for Ike Hadley: 46."}
    assert post_label(key, headlines) == label
