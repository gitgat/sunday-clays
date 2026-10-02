"""Staging and previewing a special-event import (Plan 17 Task 1)."""

from collections.abc import Callable
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.domain.identity import lookup_shooter
from sunday_clays.domain.imports import (
    active_scores_import,
    active_special_sources,
    active_station_sources,
    commit_import,
    get_import_preview,
    rollback_import,
    stage_import,
)
from sunday_clays.domain.rules import RuleType, create_rule
from sunday_clays.domain.schemas import SpecialDiff
from sunday_clays.ingest.types import FileKind
from sunday_clays.models import (
    ImportScoreRow,
    ImportSpecialEvent,
    ImportStationHit,
    ImportStationLayout,
    ImportStationSheet,
)

SPECIAL = date(2026, 9, 20)
BEFORE = date(2026, 9, 13)
HITS = (5, 5, 5, 5, 5, 5, 5, 5, 5, 5)


def _stage(session: Session, data: bytes, name: str = "special.xlsx") -> tuple[int, SpecialDiff]:
    preview = stage_import(session, data, name)
    assert preview.kind is FileKind.SPECIAL
    assert isinstance(preview.diff, SpecialDiff)
    return preview.import_id, preview.diff


def test_staging_stores_the_sunday_rows_and_stations(
    session: Session, special_workbook: Callable[..., bytes]
) -> None:
    import_id, diff = _stage(session, special_workbook())

    assert (diff.event_date, diff.label, diff.target_total) == (SPECIAL, "3-Bird Shoot", 60)
    assert diff.stations == [str(n) for n in range(1, 11)]
    assert diff.n_shooters == 5
    assert diff.replaces_import is None
    assert diff.regular_rows_on_date == 0
    event = session.get(ImportSpecialEvent, import_id)
    assert event is not None
    assert (event.event_date, event.label, event.target_total) == (SPECIAL, "3-Bird Shoot", 60)
    rows = session.execute(
        select(
            ImportScoreRow.raw_name,
            ImportScoreRow.name_key,
            ImportScoreRow.score,
            ImportScoreRow.event_date,
            ImportScoreRow.status,
            ImportScoreRow.gauge_class,
        )
        .where(ImportScoreRow.import_id == import_id)
        .order_by(ImportScoreRow.row_number)
    ).all()
    assert [tuple(r) for r in rows] == [
        ("Hadley, Ike", "hadley ike", 55, SPECIAL, None, None),
        ("Kaplan, Noel", "kaplan noel", 51, SPECIAL, None, None),
        ("Devlin, Sid", "devlin sid", 48, SPECIAL, None, None),
        ("Abernathy, Preston", "abernathy preston", 44, SPECIAL, None, None),
        ("Kim, Pat", "kim pat", 39, SPECIAL, None, None),
    ]
    (sheet,) = session.scalars(
        select(ImportStationSheet).where(ImportStationSheet.import_id == import_id)
    )
    assert (sheet.sheet_name, sheet.event_date) == ("Special Event", SPECIAL)
    layout = session.execute(
        select(ImportStationLayout.station_label, ImportStationLayout.target_count)
        .where(ImportStationLayout.sheet_id == sheet.id)
        .order_by(ImportStationLayout.station_no)
    ).all()
    assert [tuple(r) for r in layout] == [(str(n), 6) for n in range(1, 11)]
    hits = session.scalar(
        select(func.sum(ImportStationHit.hits)).where(ImportStationHit.sheet_id == sheet.id)
    )
    assert hits == 55 + 51 + 48 + 44 + 39


def test_preview_lists_new_names_and_possible_duplicates(
    session: Session,
    special_workbook: Callable[..., bytes],
    seed_live_round: Callable[..., int],
) -> None:
    seed_live_round(session, "Hadley, Ike", BEFORE, 40)
    seed_live_round(session, "Bee, Bob", BEFORE, 38)
    entries = [("Hadley, Ike", HITS), ("Bee, Bobby", HITS), ("Kim, Pat", HITS)]

    _, diff = _stage(session, special_workbook(entries))

    assert diff.new_names == ["Bee, Bobby", "Kim, Pat"]
    assert diff.possible_duplicates == [("Bee, Bob", "Bee, Bobby")]


def test_an_alias_rule_makes_a_name_known_in_the_preview(
    session: Session,
    special_workbook: Callable[..., bytes],
    seed_live_round: Callable[..., int],
) -> None:
    seed_live_round(session, "Ace, Amy", BEFORE, 40)  # creates Amy and the alias
    amy_id = lookup_shooter(session, "ace amy")
    assert amy_id is not None
    create_rule(
        session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy_id}, None
    )

    _, diff = _stage(session, special_workbook([("Ace, Amelia", HITS), ("Kim, Pat", HITS)]))

    assert diff.new_names == ["Kim, Pat"]


def test_preview_says_which_live_import_it_replaces(
    session: Session, special_workbook: Callable[..., bytes]
) -> None:
    first, _ = _stage(session, special_workbook())
    commit_import(session, first)
    corrected = special_workbook(label="3-Bird Shoot (corrected)")

    second, diff = _stage(session, corrected, "special-corrected.xlsx")

    assert diff.replaces_import == first
    commit_import(session, second)
    assert active_special_sources(session)[SPECIAL].import_id == second
    rollback_import(session, second)
    assert active_special_sources(session)[SPECIAL].import_id == first
    assert active_special_sources(session)[SPECIAL].label == "3-Bird Shoot"
    rollback_import(session, first)
    assert active_special_sources(session) == {}


def test_regular_rows_on_the_special_date_are_flagged_in_both_previews(
    session: Session,
    special_workbook: Callable[..., bytes],
    scores_workbook: Callable[..., bytes],
) -> None:
    weekly = stage_import(
        session,
        scores_workbook([("Hadley, Ike", 40, SPECIAL), ("Devlin, Sid", 35, BEFORE)]),
        "scores.xlsx",
    )
    commit_import(session, weekly.import_id)

    special_id, diff = _stage(session, special_workbook())
    assert diff.regular_rows_on_date == 1
    flagged = [
        f
        for f in get_import_preview(session, special_id).findings
        if f.code == "regular_scores_on_special_date"
    ]
    assert [(f.severity.value, f.event_date, f.message) for f in flagged] == [
        (
            "warning",
            SPECIAL,
            "The live scores workbook has 1 row on this date; it is left out while this "
            "special shoot is live",
        ),
    ]
    commit_import(session, special_id)

    again = stage_import(
        session,
        scores_workbook([("Hadley, Ike", 41, SPECIAL), ("Devlin, Sid", 35, BEFORE)]),
        "scores-again.xlsx",
    )
    flagged = [f for f in again.findings if f.code == "special_event_date"]
    assert [(f.severity.value, f.event_date, f.sheet, f.message) for f in flagged] == [
        (
            "warning",
            SPECIAL,
            "ALL SCORE DETAIL",
            "2026-09-20 is the special shoot '3-Bird Shoot': its 1 row here is left out "
            "while that import is live",
        ),
    ]
    assert all(f.event_date != BEFORE for f in flagged)


def test_several_regular_rows_on_the_special_date_use_the_plural(
    session: Session,
    special_workbook: Callable[..., bytes],
    scores_workbook: Callable[..., bytes],
) -> None:
    weekly = stage_import(
        session,
        scores_workbook([("Hadley, Ike", 40, SPECIAL), ("Devlin, Sid", 35, SPECIAL)]),
        "scores.xlsx",
    )
    commit_import(session, weekly.import_id)

    special_id, diff = _stage(session, special_workbook())
    assert diff.regular_rows_on_date == 2
    (flagged,) = [
        f
        for f in get_import_preview(session, special_id).findings
        if f.code == "regular_scores_on_special_date"
    ]
    assert flagged.message == (
        "The live scores workbook has 2 rows on this date; they are left out while this "
        "special shoot is live"
    )
    commit_import(session, special_id)
    again = stage_import(
        session,
        scores_workbook([("Hadley, Ike", 41, SPECIAL), ("Devlin, Sid", 36, SPECIAL)]),
        "scores-again.xlsx",
    )
    (note,) = [f for f in again.findings if f.code == "special_event_date"]
    assert note.message == (
        "2026-09-20 is the special shoot '3-Bird Shoot': its 2 rows here are left out "
        "while that import is live"
    )


def test_a_repeated_name_is_left_out_of_the_staged_rows_and_the_count(
    session: Session, special_workbook: Callable[..., bytes]
) -> None:
    entries = [("Hadley, Ike", HITS), ("Kim, Pat", HITS), ("Hadley, Ike", (1,) * 10)]
    preview = stage_import(session, special_workbook(entries), "dupe.xlsx")
    assert isinstance(preview.diff, SpecialDiff)

    assert preview.diff.n_shooters == 2
    staged = session.scalars(
        select(ImportScoreRow.score)
        .where(ImportScoreRow.import_id == preview.import_id)
        .order_by(ImportScoreRow.row_number)
    ).all()
    assert list(staged) == [50, 50]
    assert [(f.code, f.severity.value) for f in preview.findings] == [
        ("name_repeated_in_sheet", "error")
    ]


def test_a_duplicate_upload_returns_the_stored_special_preview(
    session: Session, special_workbook: Callable[..., bytes]
) -> None:
    data = special_workbook()
    first, diff = _stage(session, data)

    again = stage_import(session, data, "same.xlsx")

    assert again.duplicate_of == first
    assert again.diff == diff
    assert get_import_preview(session, first).diff == diff


def test_a_special_import_is_never_a_scores_or_stations_source(
    session: Session, special_workbook: Callable[..., bytes]
) -> None:
    import_id, _ = _stage(session, special_workbook())
    commit_import(session, import_id)

    assert active_scores_import(session) is None
    assert active_station_sources(session) == {}
    source = active_special_sources(session)[SPECIAL]
    assert (source.import_id, source.label, source.target_total) == (
        import_id,
        "3-Bird Shoot",
        60,
    )


def test_two_sheet_names_for_one_shooter_are_counted_once_and_warned(
    session: Session,
    special_workbook: Callable[..., bytes],
    seed_live_round: Callable[..., int],
) -> None:
    seed_live_round(session, "Ace, Amy", BEFORE, 40)
    amy_id = lookup_shooter(session, "ace amy")
    assert amy_id is not None
    create_rule(
        session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy_id}, None
    )

    import_id, diff = _stage(
        session,
        special_workbook([("Ace, Amy", HITS), ("Ace, Amelia", HITS), ("Kim, Pat", HITS)]),
    )

    assert diff.n_shooters == 2
    flagged = [
        f
        for f in get_import_preview(session, import_id).findings
        if f.code == "special_duplicate_shooter"
    ]
    assert [(f.severity.value, f.event_date) for f in flagged] == [("warning", SPECIAL)]
    assert "Ace, Amy" in flagged[0].message
    assert "Ace, Amelia" in flagged[0].message


def test_a_stations_tab_on_a_live_special_date_is_warned_and_not_added(
    session: Session,
    special_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
) -> None:
    special_id, _ = _stage(session, special_workbook())
    commit_import(session, special_id)

    tab = stations_workbook(
        [("9 20 26", SPECIAL, [6] * 7, [("Hadley, Ike", (5, 5, 5, 5, 5, 5, 5))])]
    )
    preview = stage_import(session, tab, "stations.xlsx")

    assert preview.kind is FileKind.STATIONS
    assert preview.diff.events_added == []  # type: ignore[union-attr]
    flagged = [f for f in preview.findings if f.code == "stations_tab_on_special_date"]
    assert [(f.severity.value, f.event_date, f.sheet) for f in flagged] == [
        ("warning", SPECIAL, "9 20 26")
    ]
    assert "ignored" in flagged[0].message
    assert not [f for f in preview.findings if f.code.startswith("station_")]


def test_duplicate_shooter_warning_also_shows_with_weekly_rows_on_the_date(
    session: Session,
    special_workbook: Callable[..., bytes],
    scores_workbook: Callable[..., bytes],
    seed_live_round: Callable[..., int],
) -> None:
    seed_live_round(session, "Ace, Amy", BEFORE, 40)
    amy_id = lookup_shooter(session, "ace amy")
    assert amy_id is not None
    create_rule(
        session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy_id}, None
    )
    weekly = stage_import(session, scores_workbook([("Devlin, Sid", 35, SPECIAL)]), "w.xlsx")
    commit_import(session, weekly.import_id)

    import_id, diff = _stage(session, special_workbook([("Ace, Amy", HITS), ("Ace, Amelia", HITS)]))

    assert diff.regular_rows_on_date == 1
    codes = [f.code for f in get_import_preview(session, import_id).findings]
    assert "special_duplicate_shooter" in codes
    assert "regular_scores_on_special_date" in codes
    message = next(
        f.message
        for f in get_import_preview(session, import_id).findings
        if f.code == "special_duplicate_shooter"
    )
    assert message.startswith('"Ace, Amelia" and "Ace, Amy"')


def test_a_hidden_first_row_does_not_make_the_second_a_duplicate(
    session: Session,
    special_workbook: Callable[..., bytes],
    seed_live_round: Callable[..., int],
) -> None:
    seed_live_round(session, "Ace, Amy", BEFORE, 40)
    amy_id = lookup_shooter(session, "ace amy")
    assert amy_id is not None
    create_rule(
        session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy_id}, None
    )
    create_rule(
        session,
        RuleType.HIDE_ROUND,
        {"event_date": SPECIAL, "name_key": "ace amy", "ordinal": 1, "raw_score": 50},
        None,
    )

    import_id, diff = _stage(
        session, special_workbook([("Ace, Amy", HITS), ("Ace, Amelia", (4,) * 10)])
    )

    assert diff.n_shooters == 1
    findings = get_import_preview(session, import_id).findings
    assert "special_duplicate_shooter" not in [f.code for f in findings]
