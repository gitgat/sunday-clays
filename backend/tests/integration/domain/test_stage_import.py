import hashlib
import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date

import pytest
from sqlalchemy import Connection, Engine, delete, func, select, text
from sqlalchemy.orm import Session

from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.identity import resolve_shooter
from sunday_clays.domain.imports import (
    active_scores_import,
    active_station_sources,
    get_import_preview,
    stage_import,
)
from sunday_clays.domain.schemas import ImportPreview, ScoresDiff, StationsDiff
from sunday_clays.ingest.types import FileKind, ParseError, Severity
from sunday_clays.models import (
    Import,
    ImportAttendanceRow,
    ImportScoreRow,
    ImportStationSheet,
    Shooter,
)

D1, D2, D3 = date(2026, 9, 6), date(2026, 9, 13), date(2026, 9, 20)
FIXTURE_LAYOUT = (7, 7, 7, 7, 7, 7, 8)
NBSP = chr(0xA0)
FIVES = (5, 5, 5, 5, 5, 5, 5)  # station total 35
FOURS = (4, 4, 4, 4, 4, 4, 4)  # station total 28
CountQueries = Callable[[Session], AbstractContextManager[list[str]]]


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_stage_scores_fixture_into_empty_db(session: Session, scores_bytes: bytes) -> None:
    preview = stage_import(session, scores_bytes, "02 Scores and Attendance History.xlsx")
    assert preview.kind is FileKind.SCORES
    assert preview.duplicate_of is None
    diff = preview.diff
    assert isinstance(diff, ScoresDiff)
    assert (len(diff.events_added), diff.events_removed, diff.rows_added) == (311, [], 7480)
    assert (diff.rows_removed, diff.rows_changed, diff.attendance_changed) == (0, 0, 360)
    assert len(diff.new_names) == 332
    assert "Hadley, Ike" in diff.new_names
    assert len(diff.possible_duplicates) == 25
    assert preview.requires_removal_confirmation is False
    imp = session.get(Import, preview.import_id)
    assert imp is not None
    assert imp.status == "pending"
    assert imp.sha256 == hashlib.sha256(scores_bytes).hexdigest()
    assert _count(session, ImportScoreRow) == 7480
    assert _count(session, ImportAttendanceRow) == 360
    assert _count(session, Shooter) == 0  # staging never creates shooters


def test_parser_findings_pass_through_and_warning_rows_stay(
    session: Session, scores_workbook: Callable[..., bytes]
) -> None:
    saturday = date(2026, 9, 12)
    preview = stage_import(session, scores_workbook([("Hadley, Ike", 34, saturday)]), "s.xlsx")
    (non_sunday,) = [f for f in preview.findings if f.code == "non_sunday_date"]
    assert (non_sunday.severity, non_sunday.sheet, non_sunday.row, non_sunday.event_date) == (
        Severity.WARNING,
        None,
        None,
        saturday,
    )
    assert non_sunday.message.endswith("(in score rows)")
    assert _count(session, ImportScoreRow) == 1


def test_non_sunday_findings_say_where_the_date_occurs(
    session: Session, scores_workbook: Callable[..., bytes]
) -> None:
    saturday, monday = date(2026, 9, 12), date(2026, 9, 14)
    data = scores_workbook([("Hadley, Ike", 34, saturday)], [(saturday, 1), (monday, 3)])
    preview = stage_import(session, data, "s.xlsx")
    placed = {
        f.event_date: (f.sheet, f.row, f.message)
        for f in preview.findings
        if f.code == "non_sunday_date"
    }
    assert placed == {
        saturday: (
            None,
            None,
            "2026-09-12 is a Saturday, not a Sunday (in score rows and Attendance History)",
        ),
        monday: (None, None, "2026-09-14 is a Monday, not a Sunday (in Attendance History)"),
    }


def test_attendance_only_scores_file_stages_no_rows(
    session: Session, scores_workbook: Callable[..., bytes]
) -> None:
    preview = stage_import(session, scores_workbook([], [(D1, 12)]), "attendance.xlsx")
    assert isinstance(preview.diff, ScoresDiff)
    assert (
        preview.diff.rows_added,
        preview.diff.events_added,
        preview.diff.attendance_changed,
    ) == (0, [], 1)
    assert (_count(session, ImportScoreRow), _count(session, ImportAttendanceRow)) == (0, 1)


def test_duplicate_upload_returns_existing_preview(
    session: Session, scores_workbook: Callable[..., bytes]
) -> None:
    data = scores_workbook([("Hadley, Ike", 34, D1)])
    first = stage_import(session, data, "a.xlsx")
    second = stage_import(session, data, "b.xlsx")
    assert (second.import_id, second.duplicate_of, second.filename) == (
        first.import_id,
        first.import_id,
        "a.xlsx",
    )
    assert _count(session, Import) == 1


def test_discarded_file_can_be_staged_again(
    session: Session, scores_workbook: Callable[..., bytes]
) -> None:
    data = scores_workbook([("Hadley, Ike", 34, D1)])
    first = stage_import(session, data, "a.xlsx")
    imp = session.get(Import, first.import_id)
    assert imp is not None
    imp.status = "discarded"
    session.flush()
    again = stage_import(session, data, "a.xlsx")
    assert again.duplicate_of is None
    assert again.import_id != first.import_id


def test_stale_scores_file_requires_removal_confirmation(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    rows = [
        ("Hadley, Ike", 34, D1),
        ("Crenshaw, Noel", 37, D2),
        ("Hadley, Ike", 30, D3),
        ("Crenshaw, Noel", 31, D3),
    ]
    mark_committed(session, stage_import(session, scores_workbook(rows), "v1.xlsx").import_id)
    stale = stage_import(session, scores_workbook(rows[:2]), "v0.xlsx")
    assert isinstance(stale.diff, ScoresDiff)
    assert (stale.diff.events_removed, stale.diff.rows_removed) == ([D3], 2)
    assert stale.requires_removal_confirmation is True
    assert get_import_preview(session, stale.import_id) == stale


def test_changed_score_is_not_a_removal(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    mark_committed(
        session,
        stage_import(session, scores_workbook([("Hadley, Ike", 34, D2)]), "v1.xlsx").import_id,
    )
    fixed = stage_import(session, scores_workbook([("Hadley, Ike", 36, D2)]), "v2.xlsx")
    assert isinstance(fixed.diff, ScoresDiff)
    assert (fixed.diff.rows_changed, fixed.diff.rows_removed, fixed.diff.events_removed) == (
        1,
        0,
        [],
    )
    assert fixed.requires_removal_confirmation is False


def test_new_names_and_possible_duplicates_against_known_shooters(
    session: Session, scores_workbook: Callable[..., bytes]
) -> None:
    resolve_shooter(session, "Pruett, Luther", D1)
    preview = stage_import(
        session, scores_workbook([("Preutt, Luther", 38, D2), ("Hadley, Ike", 34, D2)]), "s.xlsx"
    )
    assert isinstance(preview.diff, ScoresDiff)
    assert preview.diff.new_names == ["Hadley, Ike", "Preutt, Luther"]
    assert preview.diff.possible_duplicates == [("Preutt, Luther", "Pruett, Luther")]


def test_possible_duplicates_use_live_round_dates_of_known_shooters(
    session: Session, scores_workbook: Callable[..., bytes], seed_live_round: Callable[..., int]
) -> None:
    seed_live_round(session, "Pruett, Luther", D2, 38)  # shot the same day as the new spelling
    seed_live_round(session, "Crenshaw, Noel", D1, 37)
    preview = stage_import(
        session,
        scores_workbook([("Preutt, Luther", 38, D2), ("Crenshaw, Neol", 36, D2)]),
        "s.xlsx",
    )
    assert isinstance(preview.diff, ScoresDiff)
    assert preview.diff.possible_duplicates == [("Crenshaw, Neol", "Crenshaw, Noel")]


def test_stations_preview_flags_score_mismatch_against_live_rounds(
    session: Session, stations_workbook: Callable[..., bytes], seed_live_round: Callable[..., int]
) -> None:
    seed_live_round(session, "Hadley, Ike", D2, 34)
    data = stations_workbook(
        [("9 13 26", D2, FIXTURE_LAYOUT, [("Hadley, Ike", (5, 6, 5, 5, 5, 5, 5))])]
    )
    preview = stage_import(session, data, "stations.xlsx")
    assert preview.kind is FileKind.STATIONS
    assert preview.requires_removal_confirmation is False
    station = [f for f in preview.findings if f.code.startswith("station_")]
    assert [(f.code, f.sheet, f.row, f.event_date, f.name, f.severity) for f in station] == [
        ("station_score_mismatch", "9 13 26", 10, D2, "Hadley, Ike", Severity.WARNING)
    ]


def test_stations_preview_flags_unmatched_name_without_creating_shooter(
    session: Session, stations_workbook: Callable[..., bytes]
) -> None:
    data = stations_workbook(
        [("9 13 26", D2, FIXTURE_LAYOUT, [("Nobody," + NBSP + "New", (5, 5, 5, 5, 5, 5, 5))])]
    )
    preview = stage_import(session, data, "stations.xlsx")
    station = [(f.code, f.sheet, f.name) for f in preview.findings if f.code.startswith("station_")]
    assert station == [("station_name_unmatched", "9 13 26", "Nobody, New")]  # NBSP cleaned
    assert _count(session, Shooter) == 0


def test_stations_diff_against_active_sources(
    session: Session,
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    hadley = ("Hadley, Ike", (5, 5, 5, 5, 5, 5, 5))
    v1 = stations_workbook(
        [("9 6 26", D1, FIXTURE_LAYOUT, [hadley]), ("9 13 26", D2, FIXTURE_LAYOUT, [hadley])]
    )
    mark_committed(session, stage_import(session, v1, "v1.xlsx").import_id)
    v2 = stations_workbook(
        [
            ("9 6 26", D1, FIXTURE_LAYOUT, [hadley]),
            ("9 13 26", D2, FIXTURE_LAYOUT, [("Hadley, Ike", (6, 5, 5, 5, 5, 5, 5))]),
            ("9 20 26", D3, FIXTURE_LAYOUT, [hadley]),
            ("10 4 26", date(2026, 10, 4), FIXTURE_LAYOUT, []),  # empty template tab
        ]
    )
    preview = stage_import(session, v2, "v2.xlsx")
    assert preview.diff == StationsDiff(
        events_added=[D3], events_replaced=[D2], events_unchanged=[D1], sheets_skipped=["10 4 26"]
    )


def test_scores_preview_links_against_live_station_hits(
    session: Session,
    scores_workbook: Callable[..., bytes],
    seed_live_station_entry: Callable[..., None],
) -> None:
    resolve_shooter(session, "Hadley, Ike", D1)
    seed_live_station_entry(session, "Hadley, Ike", D2, (5, 6, 5, 5, 5, 5, 5), entry_row=15)
    seed_live_station_entry(session, "Newman, Guy", D2, (4, 4, 4, 4, 4, 4, 4), entry_row=16)
    seed_live_station_entry(session, "Ghost, Guy", D2, (3, 3, 3, 3, 3, 3, 3), entry_row=17)
    data = scores_workbook(
        [("Hadley, Ike", 34, D2), ("Newman, Guy", 28, D2), ("Hadley, Ike", 30, D1)]
    )
    preview = stage_import(session, data, "scores.xlsx")
    station = [
        (f.code, f.sheet, f.name, f.row) for f in preview.findings if f.code.startswith("station_")
    ]
    # row 15 is the entry row on the live station tab ("seed" in the helper), not a scores-file row
    assert station == [
        ("station_score_mismatch", "seed", "Hadley, Ike", 15),
        ("station_name_unmatched", "seed", "Ghost, Guy", 17),
    ]


def test_scores_preview_station_findings_come_in_date_then_row_order(
    session: Session,
    scores_workbook: Callable[..., bytes],
    seed_live_station_entry: Callable[..., None],
) -> None:
    ghosts = [(D2, 14), (D2, 13), (D2, 12), (D2, 11), (D1, 22), (D1, 21), (D1, 20)]
    for n, (event_date, entry_row) in enumerate(ghosts):
        seed_live_station_entry(session, f"Ghost, No{n}", event_date, FOURS, entry_row=entry_row)
    seed_live_station_entry(session, "Hadley, Ike", D2, FIVES, entry_row=10)
    # Hash grouping returns groups in no particular order, so only the query's ORDER BY sorts them.
    session.execute(text("SET LOCAL enable_sort = off"))
    preview = stage_import(session, scores_workbook([("Hadley, Ike", 34, D2)]), "scores.xlsx")
    assert [(f.event_date, f.row, f.code) for f in preview.findings] == [
        (D1, 20, "station_name_unmatched"),
        (D1, 21, "station_name_unmatched"),
        (D1, 22, "station_name_unmatched"),
        (D2, 10, "station_score_mismatch"),
        (D2, 11, "station_name_unmatched"),
        (D2, 12, "station_name_unmatched"),
        (D2, 13, "station_name_unmatched"),
        (D2, 14, "station_name_unmatched"),
    ]


def test_stations_preview_findings_come_in_date_then_row_order(
    session: Session, stations_workbook: Callable[..., bytes], seed_live_round: Callable[..., int]
) -> None:
    seed_live_round(session, "Hadley, Ike", D1, 34)
    data = stations_workbook(
        [
            ("9 13 26", D2, FIXTURE_LAYOUT, [("Ghost, Guy", FOURS)]),
            ("9 6 26", D1, FIXTURE_LAYOUT, [("Hadley, Ike", FIVES), ("Nobody, New", FOURS)]),
        ]
    )
    preview = stage_import(session, data, "stations.xlsx")
    assert [(f.sheet, f.row, f.code) for f in preview.findings] == [
        ("9 6 26", 10, "station_score_mismatch"),
        ("9 6 26", 11, "station_name_unmatched"),
        ("9 13 26", 10, "station_name_unmatched"),
    ]


def test_scores_preview_gives_every_new_name_a_temporary_id(
    session: Session,
    scores_workbook: Callable[..., bytes],
    seed_live_station_entry: Callable[..., None],
) -> None:
    # Newbie's only score row is on D1, but he is on the D2 station sheet. The rebuild creates his
    # shooter from the D1 row and reports station_score_missing (never shown in a preview), so the
    # preview must not call him unmatched.
    seed_live_station_entry(session, "Newbie, Ned", D2, FOURS, entry_row=12)
    preview = stage_import(session, scores_workbook([("Newbie, Ned", 30, D1)]), "scores.xlsx")
    assert [f.code for f in preview.findings if f.code.startswith("station_")] == []


def test_stations_preview_lookups_take_a_fixed_number_of_queries(
    session: Session, stations_workbook: Callable[..., bytes], count_queries: CountQueries
) -> None:
    def one_tab(names: list[str]) -> bytes:
        return stations_workbook([("9 13 26", D2, FIXTURE_LAYOUT, [(n, FIVES) for n in names])])

    with count_queries(session) as one_entry:
        stage_import(session, one_tab(["Hadley, Ike"]), "one.xlsx")
    names = ["Hadley, Ike", "Crenshaw, Noel", "Devlin, Sid", "Linwood, Luther", "Pruett, Luther"]
    with count_queries(session) as five_entries:
        stage_import(session, one_tab(names), "five.xlsx")
    assert len(five_entries) == len(one_entry)


def test_scores_preview_lookups_take_a_fixed_number_of_queries(
    session: Session,
    scores_workbook: Callable[..., bytes],
    seed_live_station_entry: Callable[..., None],
    count_queries: CountQueries,
) -> None:
    resolve_shooter(session, "Hadley, Ike", D1)
    seed_live_station_entry(session, "Hadley, Ike", D2, FIVES, entry_row=10)
    with count_queries(session) as one_entry:
        stage_import(session, scores_workbook([("Hadley, Ike", 34, D2)]), "a.xlsx")
    for entry_row, name in enumerate(
        ["Crenshaw, Noel", "Devlin, Sid", "Linwood, Luther"], start=11
    ):
        seed_live_station_entry(session, name, D2, FOURS, entry_row=entry_row)
    with count_queries(session) as four_entries:
        stage_import(session, scores_workbook([("Hadley, Ike", 35, D2)]), "b.xlsx")
    assert len(four_entries) == len(one_entry)


def test_get_import_preview_unknown_id_is_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        get_import_preview(session, 999_999)
    assert excinfo.value.code == "import_not_found"


def test_get_import_preview_without_a_stored_diff_fails_loudly(session: Session) -> None:
    imp = Import(kind="scores", filename="x.xlsx", sha256="0" * 64, file_bytes=b"x")
    session.add(imp)
    session.flush()
    with pytest.raises(KeyError):
        get_import_preview(session, imp.id)


def test_seeded_station_entries_share_a_sheet_per_date_and_keep_a_valid_preview(
    session: Session, seed_live_station_entry: Callable[..., None]
) -> None:
    seed_live_station_entry(session, "Hadley, Ike", D2, FIVES, entry_row=15)
    seed_live_station_entry(session, "Newman, Guy", D2, FOURS, entry_row=16)
    seed_live_station_entry(session, "Hadley, Ike", D1, FIVES, entry_row=15)
    seeds = session.scalars(select(Import.id).order_by(Import.id)).all()
    assert [get_import_preview(session, seed).diff for seed in seeds] == [
        StationsDiff(events_added=[d], events_replaced=[], events_unchanged=[], sheets_skipped=[])
        for d in (D2, D1)
    ]
    assert _count(session, ImportStationSheet) == 2


def test_unusable_file_raises_parse_error_and_stages_nothing(session: Session) -> None:
    with pytest.raises(ParseError):
        stage_import(session, b"not a workbook", "notes.xlsx")
    assert _count(session, Import) == 0


def _wait_until_blocked_on_advisory_lock(probe: Connection, worker: threading.Thread) -> None:
    deadline = time.monotonic() + 10
    while worker.is_alive() and time.monotonic() < deadline:
        waiting = probe.scalar(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted")
        )
        if waiting:
            return
        time.sleep(0.02)


def test_concurrent_uploads_of_one_file_serialize_on_its_sha256(
    engine: Engine, scores_workbook: Callable[..., bytes]
) -> None:
    """Two transactions: the second upload waits for the first to commit, then sees it."""
    data = scores_workbook([("Lock, Tester", 33, D1)])
    first_conn, second_conn, probe = engine.connect(), engine.connect(), engine.connect()
    first, second = Session(bind=first_conn), Session(bind=second_conn)
    outcome: dict[str, object] = {}

    def upload_second() -> None:
        try:
            outcome["preview"] = stage_import(second, data, "b.xlsx")
        except Exception as exc:  # surfaced by the assertion below
            outcome["error"] = exc

    worker = threading.Thread(target=upload_second)
    staged: ImportPreview | None = None
    try:
        staged = stage_import(first, data, "a.xlsx")
        worker.start()
        _wait_until_blocked_on_advisory_lock(probe, worker)
        first.commit()
        worker.join(timeout=30)
        assert not worker.is_alive()
        preview = outcome.get("preview")
        assert isinstance(preview, ImportPreview), outcome
        assert (preview.import_id, preview.duplicate_of) == (staged.import_id, staged.import_id)
    finally:
        first.close()  # rolls back if the commit was never reached, releasing the lock
        first_conn.close()
        worker.join(timeout=30)
        second.close()
        second_conn.close()
        if staged is not None:
            with engine.begin() as cleanup:
                cleanup.execute(delete(Import).where(Import.id == staged.import_id))
        probe.close()


def test_active_sources_follow_newest_commit(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    assert active_scores_import(session) is None
    assert active_station_sources(session) == {}
    older = stage_import(session, scores_workbook([("Hadley, Ike", 34, D1)]), "older.xlsx")
    newer = stage_import(session, scores_workbook([("Hadley, Ike", 35, D1)]), "newer.xlsx")
    stage_import(session, scores_workbook([("Hadley, Ike", 36, D1)]), "pending.xlsx")
    mark_committed(session, newer.import_id)
    mark_committed(session, older.import_id)  # committed last, so it is the live one
    assert active_scores_import(session) == older.import_id
    hadley = ("Hadley, Ike", (5, 5, 5, 5, 5, 5, 5))
    s1 = stage_import(
        session,
        stations_workbook(
            [("9 6 26", D1, FIXTURE_LAYOUT, [hadley]), ("9 13 26", D2, FIXTURE_LAYOUT, [hadley])]
        ),
        "s1.xlsx",
    )
    s2 = stage_import(
        session,
        stations_workbook(
            [("9 13 26", D2, FIXTURE_LAYOUT, [("Hadley, Ike", (6, 5, 5, 5, 5, 5, 5))])]
        ),
        "s2.xlsx",
    )
    mark_committed(session, s1.import_id)
    mark_committed(session, s2.import_id)
    sheet_of = {s.id: s.import_id for s in session.scalars(select(ImportStationSheet))}
    assert {d: sheet_of[sid] for d, sid in active_station_sources(session).items()} == {
        D1: s1.import_id,
        D2: s2.import_id,
    }
