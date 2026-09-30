from datetime import date

from sunday_clays.api.routes.admin_ops import duplicate_key_pairs

JAN_05, JAN_12, JAN_19 = date(2025, 1, 5), date(2025, 1, 12), date(2025, 1, 19)


def test_similar_keys_of_two_shooters_form_one_ordered_pair() -> None:
    key_dates = {"pruett clay": {JAN_12}, "preutt clay": {JAN_05}}
    shooters = {"pruett clay": 2, "preutt clay": 1}
    assert duplicate_key_pairs(key_dates, shooters) == [("preutt clay", "pruett clay")]


def test_keys_already_resolved_to_one_shooter_are_not_paired() -> None:
    key_dates = {"preutt clay": {JAN_05}, "pruett clay": {JAN_12}}
    assert duplicate_key_pairs(key_dates, {"preutt clay": 7, "pruett clay": 7}) == []


def test_a_shooter_pair_is_reported_once_via_its_smallest_key_pair() -> None:
    key_dates = {"preutt clay": {JAN_05}, "pruett clay": {JAN_12}, "pruitt clay": {JAN_19}}
    shooters = {"preutt clay": 1, "pruett clay": 2, "pruitt clay": 2}
    assert duplicate_key_pairs(key_dates, shooters) == [("preutt clay", "pruett clay")]


def test_dissimilar_keys_are_not_paired() -> None:
    key_dates = {"hadley ike": {JAN_05}, "devlin sid": {JAN_12}}
    assert duplicate_key_pairs(key_dates, {"hadley ike": 1, "devlin sid": 2}) == []
