import pytest

import checks

TARGETS = [7, 7, 8]


def reasons(tots, event_total, official=22, matched=True):
    return checks.check_reading(tots, event_total, TARGETS, official, matched=matched)


def test_consistent_reading_has_no_reasons():
    assert reasons([7, 7, 8], 22) == []


def test_station_count():
    assert checks.STATION_COUNT in reasons([7, 7], 14, official=14)


def test_missing_tot():
    assert checks.TOT_MISSING in reasons([7, None, 8], 15)


@pytest.mark.parametrize("tots", [[8, 7, 7], [7, -1, 8]])
def test_tot_out_of_range(tots):
    assert checks.TOT_OUT_OF_RANGE in reasons(tots, sum(tots), official=sum(tots))


def test_sum_vs_event_total():
    assert reasons([7, 7, 8], 21) == [checks.SUM_VS_EVENT_TOTAL]


def test_event_total_missing():
    assert reasons([7, 7, 8], None) == [checks.EVENT_TOTAL_MISSING]


def test_no_official_match():
    assert reasons([7, 7, 8], 22, official=None, matched=False) == [checks.NO_OFFICIAL_MATCH]


def test_sheet_vs_official_when_self_consistent():
    assert reasons([7, 7, 8], 22, official=18) == [checks.SHEET_VS_OFFICIAL]


def test_matched_without_official_value_skips_comparison():
    assert reasons([7, 7, 8], 22, official=None, matched=True) == []


def test_normalise_name_orders_tokens_and_drops_punctuation():
    assert checks.normalise_name("Testerson, Ann") == checks.normalise_name("ann TESTERSON")
    assert checks.normalise_name("O'Sample, Flo") == "flo o sample"


def test_best_match_handwriting_variants():
    officials = ["Testerson, Ann", "Fakeman, Bo"]
    assert checks.best_match("Ann Testerson", officials) == 0
    assert checks.best_match("Bo Fakemen", officials) == 1
    assert checks.best_match("Zebra Quux", officials) is None
    assert checks.best_match("", officials) is None


def test_match_names_is_one_to_one_closest_first():
    officials = ["Testerson, Ann", "Testerson, Anne"]
    # Both sheets look like Ann; the exact one keeps Ann and the other falls to the next row.
    assert checks.match_names(["Ann Testerson", "Ann Testersen"], officials) == [0, 1]
    assert checks.match_names(["Ann Testersen", "Ann Testerson"], officials) == [1, 0]


def test_match_names_a_row_is_used_at_most_once():
    assert checks.match_names(["Ann Testerson", "Ann Testerson"], ["Testerson, Ann"]) == [0, None]


def test_match_names_blank_and_unknown_stay_unmatched():
    assert checks.match_names(["", "Nobody Known"], ["Testerson, Ann"]) == [None, None]


def test_match_names_prefers_the_row_a_sheet_agrees_with_when_a_shooter_has_two_rounds():
    officials = ["Testerson, Ann", "Testerson, Ann"]
    names = ["Ann Testerson", "Ann Testerson"]
    assert checks.match_names(names, officials) == [0, 1]
    assert checks.match_names(names, officials, sums=[25, 22], hits=[22, 25]) == [1, 0]
    assert checks.match_names(names, officials, sums=[22, 25], hits=[22, 25]) == [0, 1]
