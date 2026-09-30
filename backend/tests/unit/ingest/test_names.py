import io
from datetime import date, datetime

import openpyxl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sunday_clays.ingest.names import (
    base_key,
    clean_display_name,
    identity_key,
    name_key,
    similar_name_keys,
)

FEB_23 = date(2025, 2, 23)
MAR_02 = date(2025, 3, 2)
MAR_09 = date(2025, 3, 9)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Kowalczyk, Barrett\xa0", "Kowalczyk, Barrett"),
        ("  Lachance,   Tucker ", "Lachance, Tucker"),
        ("Amos**", "Amos**"),
        ("Gri\N{LATIN SMALL LIGATURE FF}in, Pat", "Griffin, Pat"),
    ],
)
def test_clean_display_name(raw: str, expected: str) -> None:
    assert clean_display_name(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Linwood Luther", "linwood luther"),
        ("Linwood, Luther", "linwood luther"),
        ("O\N{RIGHT SINGLE QUOTATION MARK}Halloran, Stanley", "o'halloran stanley"),
        ("O'Halloran, Stanley\xa0", "o'halloran stanley"),
        ("O\xb4Halloran, Stanley", "o'halloran stanley"),
        ("Tarleton\N{EN DASH}Ackerly, Ann", "tarleton-ackerly ann"),
        ("  KOWALCZYK,\tBarrett ", "kowalczyk barrett"),
        ("Lachance, Tucker ", "lachance tucker"),
        ("Amos**", "amos"),
        ("Barrett (Raymond's Dad)", "barrett raymond's dad"),
        ("Stra\xdfe, Hans", "strasse hans"),
        ("**", ""),
    ],
)
def test_name_key(raw: str, expected: str) -> None:
    assert name_key(raw) == expected


def test_curly_and_straight_apostrophes_share_a_key() -> None:
    assert name_key("O\N{RIGHT SINGLE QUOTATION MARK}Halloran, Stanley") == name_key(
        "O'Halloran, Stanley"
    )


def test_name_key_is_idempotent_when_nfkc_creates_an_apostrophe() -> None:
    # U+0149 decomposes to U+02BC + "n" under NFKC, after the first translate.
    assert name_key("\N{LATIN SMALL LETTER N PRECEDED BY APOSTROPHE}") == "'n"
    assert name_key(name_key("\N{LATIN SMALL LETTER N PRECEDED BY APOSTROPHE}")) == "'n"


@settings(database=None, max_examples=500)
@given(st.text())
def test_name_key_is_idempotent(raw: str) -> None:
    key = name_key(raw)
    assert name_key(key) == key


@settings(database=None)
@given(st.text(), st.dates())
def test_base_key_inverts_identity_key(raw: str, event_date: date) -> None:
    key = name_key(raw)
    assert base_key(identity_key(key, event_date)) == key


def test_identity_key_scopes_first_name_only_keys_to_the_event() -> None:
    assert identity_key("tarleton wendell", FEB_23) == "tarleton wendell"
    assert identity_key("desmond", FEB_23) == "desmond@2025-02-23"
    assert base_key("desmond@2025-02-23") == "desmond"
    assert base_key("tarleton wendell") == "tarleton wendell"


def test_fixture_names_collapse_to_332_keys(scores_bytes: bytes) -> None:
    workbook = openpyxl.load_workbook(io.BytesIO(scores_bytes), data_only=True)
    sheet = workbook["ALL SCORE DETAIL"]
    rows = [
        (str(name), event.date())
        for name, _score, event in sheet.iter_rows(min_row=2, max_col=3, values_only=True)
        if isinstance(event, datetime)
    ]
    raw_names = {name for name, _ in rows}
    identities = {identity_key(name_key(name), day) for name, day in rows}
    one_token = {identity for identity in identities if "@" in identity}

    assert len(rows) == 7480
    assert len(raw_names) == 336
    assert len({name_key(name) for name in raw_names}) == 332
    assert len(identities) == 332
    assert len(one_token) == 17
    assert {identity.partition("@")[2] for identity in one_token} == {"2025-02-23"}


@pytest.mark.parametrize(
    ("key", "candidate"),
    [
        ("hammond bennett", "hamond bennett"),  # full ratio 0.97
        ("o brien patrick", "obrien patrick"),  # full ratio 0.97; surnames 0.29
        ("o brien patrick", "obrian patrick"),  # full ratio 0.90 only; surnames 0.29
        ("tarleton wendell", "tarletonwendell@2025-03-02"),  # full ratio vs a one-token key
        ("lindenmeb katie", "lindenmeyer catie"),  # surname 0.80 + given 0.80; prefixes differ
        ("lindenmeb darrel", "lindenmeyer darrell"),  # surname 0.80 + given 0.92 + "dar" prefix
        ("lennox stan", "lennox stanley"),  # surname 1.0 + shared "sta" prefix
    ],
)
def test_similar_full_names_are_flagged(key: str, candidate: str) -> None:
    candidates = {key: {FEB_23}, candidate: {MAR_02}}

    assert similar_name_keys(key, {FEB_23}, candidates) == [candidate]


@pytest.mark.parametrize(
    ("key", "candidate"),
    [
        ("pinnock dudley", "pinnock jed"),  # surname 1.0, given 0.22, prefixes differ
        ("stroud jasper", "skelton jasper"),  # full 0.74, surname 0.46
        ("hale ed", "halt ed"),  # surname 0.75 < 0.80; full 0.86
        ("burkhalter elias", "elias@2025-03-02"),  # found only from the one-token side
    ],
)
def test_dissimilar_names_are_not_flagged(key: str, candidate: str) -> None:
    assert similar_name_keys(key, {FEB_23}, {candidate: {MAR_02}}) == []


def test_candidates_that_shot_the_same_day_are_excluded() -> None:
    candidates = {
        "ledford rolland": {MAR_02, MAR_09},
        "pierpont tate": {MAR_02},
        "fullerton tate": {FEB_23},
    }

    assert similar_name_keys("ledford roland", {FEB_23, MAR_09}, candidates) == []
    assert similar_name_keys("tate@2025-02-23", {FEB_23}, candidates) == ["pierpont tate"]


def test_one_token_key_flags_returning_guest_and_matching_given_names() -> None:
    candidates = {
        "desmond@2025-02-23": {FEB_23},
        "desmond@2025-03-09": {MAR_09},
        "hargrove desmond": {MAR_02},
        "jimenez carlos": {MAR_02},
        "jim bob": {MAR_02},
        "landon@2025-03-02": {MAR_02},
    }

    assert similar_name_keys("desmond@2025-02-23", {FEB_23}, candidates) == [
        "desmond@2025-03-09",
        "hargrove desmond",
    ]


def test_key_itself_is_never_returned() -> None:
    assert similar_name_keys("desmond@2025-02-23", set(), {"desmond@2025-02-23": {FEB_23}}) == []
