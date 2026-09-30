from datetime import date

from sunday_clays.domain.diff import (
    RowChanges,
    StagedScore,
    assign_ordinals,
    attendance_by_date,
    attendance_changes,
    possible_duplicate_pairs,
    representative_names,
    score_row_changes,
    station_changes,
)

D1, D2, D3 = date(2026, 9, 6), date(2026, 9, 13), date(2026, 9, 20)


def _row(
    row_id: int,
    key: str,
    d: date,
    score: int,
    *,
    row_number: int | None = None,
    raw: str = "",
    status: str | None = "member",
) -> StagedScore:
    return StagedScore(row_id, row_number or row_id, raw or key, key, d, score, status, None)


def test_ordinals_rank_same_day_rounds_by_score_then_row_number() -> None:
    rows = [
        _row(1, "a b", D1, 30),
        _row(2, "a b", D1, 40),
        _row(3, "a b", D1, 40),
        _row(4, "c d", D1, 25),
    ]
    assert assign_ordinals(rows) == {2: 1, 3: 2, 1: 3, 4: 1}


def test_score_row_changes_counts_added_removed_changed() -> None:
    old = [_row(1, "a b", D1, 30), _row(2, "c d", D1, 31), _row(3, "e f", D2, 20)]
    new = [
        _row(11, "a b", D1, 30),  # unchanged
        _row(12, "c d", D1, 33),  # score changed
        _row(13, "g h", D3, 40),  # added (new event)
    ]
    assert score_row_changes(new, old) == RowChanges(
        events_added=[D3], events_removed=[D2], rows_added=1, rows_removed=1, rows_changed=1
    )


def test_status_or_gauge_change_counts_as_changed_row() -> None:
    old = [_row(1, "a b", D1, 30, status="guest")]
    new = [_row(2, "a b", D1, 30, status="member")]
    assert score_row_changes(new, old).rows_changed == 1


def test_representative_name_is_the_most_recent_spelling() -> None:
    rows = [
        _row(1, "linwood luther", D1, 30, raw="Linwood Luther"),
        _row(2, "linwood luther", D2, 30, raw="Linwood, Luther", row_number=9),
        _row(3, "linwood luther", D2, 30, raw="Linwood,  Luther", row_number=12),
    ]
    assert representative_names(rows) == {"linwood luther": "Linwood, Luther"}


def test_attendance_later_row_wins_and_changes_are_counted() -> None:
    new = attendance_by_date([(2, D1, 20), (3, D2, 18), (9, D2, 19)])
    assert new == {D1: 20, D2: 19}
    assert attendance_changes(new, {D1: 20, D2: 18, D3: 5}) == 2  # D2 changed, D3 removed


def test_station_changes_split_added_replaced_unchanged() -> None:
    layout = ((4, 7), (5, 8))
    same = (layout, (("hadley ike", 4, 5),))
    changed = (layout, (("hadley ike", 4, 6),))
    added, replaced, unchanged = station_changes(
        {D1: same, D2: changed, D3: same}, {D1: same, D2: same}
    )
    assert (added, replaced, unchanged) == ([D3], [D2], [D1])


def test_possible_duplicate_pairs_are_unordered_and_skip_same_day_candidates() -> None:
    key_dates = {
        "preutt luther": {D1},
        "pruett luther": {D2},
        "tate@2026-09-06": {D1},
        "fullerton tate": {D1},  # shot the same day as the first-name-only "Tate": not flagged
        "pierpont tate": {D3},
    }
    display = {
        "preutt luther": "Preutt, Luther",
        "pruett luther": "Pruett, Luther",
        "tate@2026-09-06": "Tate",
        "fullerton tate": "Fullerton, Tate",
        "pierpont tate": "Pierpont, Tate",
    }
    pairs = possible_duplicate_pairs(["preutt luther", "tate@2026-09-06"], key_dates, display)
    assert pairs == [("Pierpont, Tate", "Tate"), ("Preutt, Luther", "Pruett, Luther")]
