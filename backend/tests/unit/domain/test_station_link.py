from datetime import date

from sunday_clays.domain.station_link import (
    LinkRound,
    StationEntry,
    StationLink,
    link_station_entries,
)
from sunday_clays.ingest.types import Finding

D = date(2026, 8, 30)


def _entry(
    row: int, total: int, shooter_id: int | None = 7, name: str = "Nickerson, Neal"
) -> StationEntry:
    return StationEntry(D, row, name, "nickerson neal", shooter_id, total)


def _round(round_id: int, ordinal: int, score: int, shooter_id: int = 7) -> LinkRound:
    return LinkRound(round_id, D, shooter_id, ordinal, score)


def _codes(findings: list[Finding]) -> list[tuple[str, int | None]]:
    return [(f.code, f.row) for f in findings]


def test_two_station_entries_link_to_distinct_rounds() -> None:
    # Nickerson, Neal 2026-08-30: two rounds of 40 and two station rows totalling 40.
    links, findings = link_station_entries(
        [_entry(10, 40), _entry(11, 40)], [_round(501, 1, 40), _round(502, 2, 40)]
    )
    assert sorted(links, key=lambda link: link.entry_row) == [
        StationLink(D, 10, 7, 501),
        StationLink(D, 11, 7, 502),
    ]
    assert findings == []


def test_exact_score_match_wins_over_ordinal_order() -> None:
    links, findings = link_station_entries(
        [_entry(10, 38), _entry(11, 44)], [_round(501, 1, 44), _round(502, 2, 38)]
    )
    assert {link.entry_row: link.round_id for link in links} == {10: 502, 11: 501}
    assert findings == []


def test_single_round_mismatch_is_not_ambiguous() -> None:
    links, findings = link_station_entries([_entry(15, 36, name="Hadley, Ike")], [_round(9, 1, 34)])
    assert links == [StationLink(D, 15, 7, 9)]
    assert _codes(findings) == [("station_score_mismatch", 15)]
    assert findings[0].event_date == D
    assert findings[0].name == "Hadley, Ike"
    assert findings[0].severity.value == "warning"


def test_second_pass_pairing_on_multi_round_day_is_ambiguous_and_mismatched() -> None:
    links, findings = link_station_entries(
        [_entry(10, 40), _entry(11, 40)], [_round(501, 1, 40), _round(502, 2, 38)]
    )
    assert {link.entry_row: link.round_id for link in links} == {10: 501, 11: 502}
    assert sorted(_codes(findings)) == [
        ("station_round_ambiguous", 11),
        ("station_score_mismatch", 11),
    ]


def test_entry_without_a_round_left_gets_station_score_missing() -> None:
    links, findings = link_station_entries([_entry(10, 40), _entry(11, 30)], [_round(501, 1, 40)])
    assert {link.entry_row: link.round_id for link in links} == {10: 501, 11: None}
    assert _codes(findings) == [("station_score_missing", 11)]


def test_unmatched_name_is_reported_and_never_linked() -> None:
    links, findings = link_station_entries(
        [_entry(12, 33, shooter_id=None, name="Nobody, New")], [_round(501, 1, 33)]
    )
    assert links == [StationLink(D, 12, None, None)]
    assert _codes(findings) == [("station_name_unmatched", 12)]


def test_rounds_of_other_shooters_and_days_are_never_used() -> None:
    other_day = LinkRound(600, date(2026, 9, 6), 7, 1, 40)
    other_shooter = _round(601, 1, 40, shooter_id=8)
    links, findings = link_station_entries([_entry(10, 40)], [other_day, other_shooter])
    assert links == [StationLink(D, 10, 7, None)]
    assert _codes(findings) == [("station_score_missing", 10)]


def test_second_pass_pairs_leftovers_by_station_total_descending() -> None:
    links, findings = link_station_entries(
        [_entry(10, 31), _entry(11, 44)], [_round(501, 1, 45), _round(502, 2, 30)]
    )
    assert {link.entry_row: link.round_id for link in links} == {11: 501, 10: 502}
    assert sorted(_codes(findings)) == [
        ("station_round_ambiguous", 10),
        ("station_round_ambiguous", 11),
        ("station_score_mismatch", 10),
        ("station_score_mismatch", 11),
    ]


def test_messages_quote_the_cleaned_name_and_findings_keep_the_raw_one() -> None:
    hadley = "Hadley," + chr(0xA0) + "Ike"
    nobody = "Nobody," + chr(0xA0) + "New"
    _, findings = link_station_entries(
        [
            _entry(10, 40, name=hadley),
            _entry(11, 30, name=hadley),
            _entry(12, 20, name=hadley),
            _entry(13, 33, shooter_id=None, name=nobody),
        ],
        [_round(501, 1, 38), _round(502, 2, 36)],
    )
    assert sorted((f.code, f.row, f.message) for f in findings) == [
        ("station_name_unmatched", 13, 'Station sheet name "Nobody, New" matches no shooter'),
        (
            "station_round_ambiguous",
            10,
            '"Hadley, Ike" shot 2 rounds; station total 40 was paired with the round scored 38',
        ),
        (
            "station_round_ambiguous",
            11,
            '"Hadley, Ike" shot 2 rounds; station total 30 was paired with the round scored 36',
        ),
        ("station_score_mismatch", 10, 'Station total 40 != score 38 for "Hadley, Ike"'),
        ("station_score_mismatch", 11, 'Station total 30 != score 36 for "Hadley, Ike"'),
        ("station_score_missing", 12, 'No score row left for "Hadley, Ike" (station total 20)'),
    ]
    assert {f.name for f in findings} == {hadley, nobody}  # raw spelling, NBSP kept
