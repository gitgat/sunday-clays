"""Round type of an event day, derived from its station layout (Global Constraints, C5)."""

from collections.abc import Sequence
from enum import StrEnum

from sunday_clays.ingest.types import StationLayoutEntry


class RoundType(StrEnum):
    SPORTING = "sporting"
    SUPER_SPORTING = "super_sporting"


def classify_round_type(layout: Sequence[StationLayoutEntry]) -> RoundType:
    """Any odd target count => super sporting; everything else, even no stations => sporting."""
    if any(entry.target_count % 2 == 1 for entry in layout):
        return RoundType.SUPER_SPORTING
    return RoundType.SPORTING
