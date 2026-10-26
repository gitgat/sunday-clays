from datetime import date

import pytest

from sunday_clays.domain.thrown_out import (
    MIN_DROP_ENTRIES,
    SUNDAY_THROWN_OUT,
    ThrownOut,
    detect_thrown_out,
    thrown_out_phrase,
)

D, E = date(2026, 10, 25), date(2026, 1, 11)
TARGETS = {(D, "4"): 7, (D, "10"): 8, (D, "11"): 7}  # layout order
MIXED = {(D, "4"): [7, 6, 5] * 3, (D, "10"): [8, 7] * 4}
T = ThrownOut


def test_every_entry_perfect_on_eight_entries_is_thrown_out() -> None:
    assert MIN_DROP_ENTRIES == 8
    assert detect_thrown_out({**MIXED, (D, "11"): [7] * 8}, TARGETS, {}, ()) == {
        D: (T("11", 7, True, "auto"),)
    }


def test_seven_entries_are_below_the_threshold() -> None:
    assert detect_thrown_out({**MIXED, (D, "11"): [7] * 7}, TARGETS, {}, ()) == {}


def test_one_entry_short_of_perfect_is_not_thrown_out() -> None:
    assert detect_thrown_out({**MIXED, (D, "11"): [7] * 19 + [6]}, TARGETS, {}, ()) == {}


def test_a_special_sunday_is_skipped_even_with_overrides() -> None:
    overrides = {(D, "4"): (3, True), (D, None): (4, True)}
    assert detect_thrown_out({**MIXED, (D, "11"): [7] * 20}, TARGETS, overrides, {D}) == {}


def test_override_on_forces_a_station_and_says_whether_it_was_credited() -> None:
    got = detect_thrown_out({**MIXED, (D, "11"): [7] * 20}, TARGETS, {(D, "4"): (5, True)}, ())
    assert got == {D: (T("4", 7, False, "override"), T("11", 7, True, "auto"))}


def test_override_on_a_station_with_no_entries_is_not_credited() -> None:
    got = detect_thrown_out({(D, "4"): [7] * 3}, TARGETS, {(D, "10"): (6, True)}, ())
    assert got == {D: (T("10", 8, False, "override"),)}


def test_override_off_clears_an_auto_station() -> None:
    assert detect_thrown_out({(D, "11"): [7] * 20}, TARGETS, {(D, "11"): (7, False)}, ()) == {}


def test_an_override_for_a_station_not_in_the_layout_adds_nothing() -> None:
    assert detect_thrown_out({}, TARGETS, {(D, "12"): (8, True)}, ()) == {}


def test_sunday_level_override_adds_an_unnamed_item_last_and_dates_sort() -> None:
    got = detect_thrown_out(
        {(D, "11"): [7] * 20}, TARGETS, {(D, None): (9, True), (E, None): (10, True)}, ()
    )
    assert list(got) == [E, D]
    assert got[D] == (T("11", 7, True, "auto"), T(None, None, False, "override"))
    assert got[E] == (T(None, None, False, "override"),)


@pytest.mark.parametrize(
    ("items", "phrase"),
    [
        ([T("11", 7, True, "auto")], "Station 11 was thrown out; everyone was credited 7/7"),
        ([T("11", 7, False, "override")], "Station 11 was thrown out"),
        (
            [T("4", 7, True, "auto"), T("11", 7, True, "auto")],
            "Stations 4 and 11 were thrown out; everyone was credited in full",
        ),
        (
            [T("3", 7, True, "auto"), T("4", 7, False, "override"), T("11", 7, True, "auto")],
            "Stations 3, 4 and 11 were thrown out",
        ),
        ([T(None, None, False, "override")], "A station was thrown out this Sunday"),
        (
            [T("7A", 6, True, "auto"), T(None, None, False, "override")],
            "Station 7A was thrown out; everyone was credited 6/6",
        ),
        ([], "A station was thrown out this Sunday"),
    ],
)
def test_thrown_out_phrase(items: list[ThrownOut], phrase: str) -> None:
    assert thrown_out_phrase(items) == phrase
    assert SUNDAY_THROWN_OUT == "A station was thrown out this Sunday"
