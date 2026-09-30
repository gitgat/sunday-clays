import pytest

from sunday_clays.domain.round_type import RoundType, classify_round_type
from sunday_clays.ingest.types import StationLayoutEntry


def _layout(*targets: int) -> list[StationLayoutEntry]:
    return [StationLayoutEntry(station_no=4 + i, target_count=t) for i, t in enumerate(targets)]


@pytest.mark.parametrize(
    ("targets", "expected"),
    [
        ((7, 7, 7, 7, 7, 7, 8), RoundType.SUPER_SPORTING),  # the fixture layout
        ((8, 8, 8, 8, 8, 10), RoundType.SPORTING),
        ((6, 6, 6, 6, 6, 6, 6, 7), RoundType.SUPER_SPORTING),  # one odd station is enough
        ((), RoundType.SPORTING),  # no station data defaults to sporting
    ],
)
def test_classify_round_type(targets: tuple[int, ...], expected: RoundType) -> None:
    assert classify_round_type(_layout(*targets)) is expected


def test_round_type_has_exactly_two_members() -> None:
    assert [rt.value for rt in RoundType] == ["sporting", "super_sporting"]
