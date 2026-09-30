import pytest

from sunday_clays.station_label import label_number, label_rank, label_sort_key, parse_label


@pytest.mark.parametrize(
    ("value", "label"),
    [
        (7, "7"),
        (7.0, "7"),
        ("7", "7"),
        (" 7 ", "7"),
        ("7.0", "7"),
        ("07", "7"),
        ("7A", "7A"),
        (" 7a ", "7A"),
        ("12B", "12B"),
    ],
)
def test_valid_labels_are_normalized(value: object, label: str) -> None:
    assert parse_label(value) == label


@pytest.mark.parametrize(
    "value",
    [True, None, 0, "0", "0A", -1, 7.5, "7.5", "100", "7AB", "A7", "", "Total", "7 A", [7], b"7"],
)
def test_anything_else_is_not_a_label(value: object) -> None:
    assert parse_label(value) is None


def test_stations_sort_by_number_then_suffix() -> None:
    labels = ["8", "7A", "10", "4", "7", "7B", "5"]
    assert sorted(labels, key=label_sort_key) == ["4", "5", "7", "7A", "7B", "8", "10"]
    assert sorted(labels, key=label_rank) == sorted(labels, key=label_sort_key)
    assert [label_number(x) for x in ("7", "7A", "12")] == [7, 7, 12]
    assert label_rank("7") == 700
    assert label_rank("7A") == 701


@pytest.mark.parametrize("bad", ["", "x", "7AB"])
def test_helpers_refuse_a_non_label(bad: str) -> None:
    for fn in (label_number, label_sort_key, label_rank):
        with pytest.raises(ValueError, match="not a station label"):
            fn(bad)
