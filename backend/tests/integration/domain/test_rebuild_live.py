import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.domain.imports import stage_import
from sunday_clays.domain.rebuild import LIVE_TABLES, RebuildReport, rebuild_live
from sunday_clays.models import (
    AppState,
    DataIssue,
    Event,
    Import,
    Round,
    Rule,
    Shooter,
    ShooterProfile,
    StationHit,
    StationLayout,
)

CountQueries = Callable[[Session], AbstractContextManager[list[str]]]
LiveRowsFn = Callable[[Session], dict[str, list[dict[str, Any]]]]

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)
LAYOUT = (7, 7, 7, 7, 7, 7, 8)
FIVES = (5, 5, 5, 5, 5, 5, 5)
NBSP = chr(0xA0)
GOLDEN = Path(__file__).resolve().parents[2] / "golden"
# every events column besides event_date (C4); the snapshot holds them all
EVENT_COLUMNS = (
    "round_type",
    "round_type_source",
    "head_count",
    "n_rounds",
    "n_shooters",
    "has_scores",
    "has_stations",
    "results_complete",
)


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _events(session: Session) -> dict[date, Event]:
    return {e.event_date: e for e in session.scalars(select(Event))}


def _issues(session: Session) -> list[tuple[str, date | None]]:
    return sorted(
        (code, d) for code, d in session.execute(select(DataIssue.code, DataIssue.event_date))
    )


def _last_rebuild_at(session: Session) -> object:
    return session.scalar(select(AppState.value).where(AppState.key == "last_rebuild_at"))


def test_live_tables_are_the_decision_13_list_in_delete_order() -> None:
    assert LIVE_TABLES == (
        "station_hits",
        "round_metrics",
        "rounds",
        "shooter_profiles",
        "station_layouts",
        "data_issues",
        "events",
    )


def test_only_live_tables_reference_live_tables_and_they_are_deleted_first(
    session: Session,
) -> None:
    # rebuild_live DELETEs in LIVE_TABLES order: every foreign key into a live table must come
    # from a live table listed before it, or the DELETE of the referenced rows fails
    references = session.execute(
        text(
            "SELECT conrelid::regclass::text, confrelid::regclass::text FROM pg_constraint "
            "WHERE contype = 'f' AND confrelid::regclass::text = ANY(:live)"
        ),
        {"live": list(LIVE_TABLES)},
    ).all()
    position = {name: n for n, name in enumerate(LIVE_TABLES)}
    assert {("rounds", "events"), ("station_hits", "rounds"), ("round_metrics", "rounds")} <= {
        (child, parent) for child, parent in references
    }
    assert [
        (child, parent)
        for child, parent in references
        if child not in position or position[child] >= position[parent]
    ] == []


def test_fixtures_rebuild_golden(
    session: Session,
    scores_bytes: bytes,
    stations_bytes: bytes,
    mark_committed: Callable[[Session, int], None],
) -> None:
    mark_committed(session, stage_import(session, scores_bytes, "scores.xlsx").import_id)
    mark_committed(session, stage_import(session, stations_bytes, "stations.xlsx").import_id)
    report = rebuild_live(session)
    assert report == RebuildReport(
        n_events=360, n_rounds=7480, n_shooters=332, n_station_events=2, n_issues=2
    )
    events = _events(session)
    assert sum(e.has_scores for e in events.values()) == 311
    assert sum(e.results_complete for e in events.values()) == 310
    assert sum(e.head_count is not None for e in events.values()) == 360
    assert {
        d: (e.round_type, e.round_type_source) for d, e in events.items() if e.has_stations
    } == {
        D1: ("super_sporting", "stations"),
        D2: ("super_sporting", "stations"),
    }
    scored = [e.round_type for e in events.values() if e.has_scores]
    assert (scored.count("super_sporting"), scored.count("sporting"), len(scored)) == (2, 309, 311)
    assert {e.round_type for e in events.values()} == {"sporting", "super_sporting"}
    assert _count(session, Shooter) == 332
    assert session.scalar(select(func.count()).where(ShooterProfile.left_censored)) == 48
    assert _issues(session) == [
        ("incomplete_results", date(2024, 11, 10)),
        ("station_score_mismatch", D2),
    ]
    hadley = session.scalars(
        select(DataIssue).where(DataIssue.code == "station_score_mismatch")
    ).one()
    assert (
        hadley.details["raw_name"],
        hadley.details["station_total"],
        hadley.details["score"],
    ) == (
        "Hadley, Ike",
        36,
        34,
    )
    assert session.scalar(select(func.count()).where(StationHit.round_id.is_(None))) == 0
    assert _count(session, StationLayout) == 14


def test_fixtures_rebuild_matches_golden_events_snapshot(
    session: Session,
    scores_bytes: bytes,
    stations_bytes: bytes,
    mark_committed: Callable[[Session, int], None],
) -> None:
    snap = json.loads((GOLDEN / "rebuild_events.json").read_text())
    canonical = json.dumps(snap, separators=(",", ":"), sort_keys=True).encode()
    assert hashlib.sha256(canonical).hexdigest() == (
        "c4e5f1ce06847aceee5feabbe0cf4ea269ef24b5489066450f5a1182f30fbe1b"
    )
    mark_committed(session, stage_import(session, scores_bytes, "scores.xlsx").import_id)
    mark_committed(session, stage_import(session, stations_bytes, "stations.xlsx").import_id)
    rebuild_live(session)
    got = [
        {"event_date": e.event_date.isoformat()} | {c: getattr(e, c) for c in EVENT_COLUMNS}
        for e in session.scalars(select(Event).order_by(Event.event_date))
    ]
    assert got == snap


def test_stage_stations_preview_flags_hadley_mismatch(
    session: Session,
    scores_bytes: bytes,
    stations_bytes: bytes,
    mark_committed: Callable[[Session, int], None],
) -> None:
    mark_committed(session, stage_import(session, scores_bytes, "scores.xlsx").import_id)
    rebuild_live(session)
    preview = stage_import(session, stations_bytes, "stations.xlsx")
    station = [
        (f.code, f.event_date, f.name) for f in preview.findings if f.code.startswith("station_")
    ]
    assert station == [("station_score_mismatch", D2, "Hadley, Ike")]


def test_unmatched_station_name_becomes_issue(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    mark_committed(
        session,
        stage_import(session, scores_workbook([("Hadley, Ike", 35, D2)]), "s.xlsx").import_id,
    )
    sheet = [("Hadley, Ike", FIVES), ("Nobody," + NBSP + "New", (4, 4, 4, 4, 4, 4, 4))]
    mark_committed(
        session,
        stage_import(
            session, stations_workbook([("9 13 26", D2, LAYOUT, sheet)]), "st.xlsx"
        ).import_id,
    )
    rebuild_live(session)
    issue = session.scalars(
        select(DataIssue).where(DataIssue.code == "station_name_unmatched")
    ).one()
    assert issue.event_date == D2
    assert issue.shooter_id is None
    assert (issue.details["name_key"], issue.details["raw_name"], issue.details["event_date"]) == (
        "nobody new",
        "Nobody," + NBSP + "New",
        "2026-09-13",
    )
    unmatched = session.scalars(select(StationHit).where(StationHit.name_key == "nobody new")).all()
    assert len(unmatched) == 7
    assert all(h.shooter_id is None and h.round_id is None for h in unmatched)
    # no shooter row is created for the unmatched station name
    assert session.scalars(select(Shooter.display_name)).all() == ["Hadley, Ike"]


def test_a_lettered_station_is_kept_as_its_own_station_and_linked(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    mark_committed(
        session,
        stage_import(session, scores_workbook([("Hadley, Ike", 30, D2)]), "s.xlsx").import_id,
    )
    stations = (4, 5, 6, 7, "7A", 8)
    tabs = [("9 13 26", D2, (7, 7, 7, 8, 6, 7), [("Hadley, Ike", (5, 5, 5, 6, 4, 5))])]
    sheets = stations_workbook(tabs, stations)
    staged = stage_import(session, sheets, "st.xlsx")
    mark_committed(session, staged.import_id)
    report = rebuild_live(session)
    assert report.n_station_events == 1
    layout = session.execute(
        select(StationLayout.station_label, StationLayout.station_no, StationLayout.target_count)
        .where(StationLayout.event_date == D2)
        .order_by(StationLayout.station_no, StationLayout.station_label)
    ).all()
    assert layout == [("4", 4, 7), ("5", 5, 7), ("6", 6, 7), ("7", 7, 8), ("7A", 7, 6), ("8", 8, 7)]
    hits = session.execute(
        select(
            StationHit.station_label, StationHit.station_no, StationHit.hits, StationHit.round_id
        ).order_by(StationHit.station_no, StationHit.station_label)
    ).all()
    round_id = session.scalars(select(Round.id)).one()
    assert [(label, no, value) for label, no, value, _ in hits] == [
        ("4", 4, 5),
        ("5", 5, 5),
        ("6", 6, 5),
        ("7", 7, 6),
        ("7A", 7, 4),
        ("8", 8, 5),
    ]
    assert {rid for *_, rid in hits} == {round_id}  # the station total equals the score: linked
    assert _issues(session) == []
    # the same sheet staged again is unchanged, and a changed 7A hit is a replaced Sunday
    empty_tab = (
        "10 4 26",
        date(2026, 10, 4),
        (7, 7, 7, 8, 6, 7),
        [],
    )  # only makes the bytes differ
    again = stage_import(session, stations_workbook([*tabs, empty_tab], stations), "st2.xlsx")
    assert again.diff.events_unchanged == [D2]
    changed = stage_import(
        session,
        stations_workbook(
            [("9 13 26", D2, (7, 7, 7, 8, 6, 7), [("Hadley, Ike", (5, 5, 5, 6, 5, 5))])], stations
        ),
        "st3.xlsx",
    )
    assert changed.diff.events_replaced == [D2]


def test_empty_template_tab_adds_no_event(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    mark_committed(
        session,
        stage_import(session, scores_workbook([("Hadley, Ike", 35, D2)]), "s.xlsx").import_id,
    )
    tabs = [
        ("9 13 26", D2, LAYOUT, [("Hadley, Ike", FIVES)]),
        ("10 4 26", date(2026, 10, 4), LAYOUT, []),
    ]
    mark_committed(session, stage_import(session, stations_workbook(tabs), "st.xlsx").import_id)
    rebuild_live(session)
    assert list(_events(session)) == [D2]


def test_rounds_ordinals_shooters_and_counts(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    rows = [
        ("Hadley, Ike", 30, D1),
        ("Hadley, Ike", 40, D1),
        ("Linwood Luther", 38, D1),
        ("Linwood, Luther", 41, D2),
    ]
    mark_committed(
        session,
        stage_import(session, scores_workbook(rows, [(D1, 2), (D2, 5)]), "s.xlsx").import_id,
    )
    report = rebuild_live(session)
    assert (report.n_events, report.n_rounds, report.n_shooters) == (2, 4, 2)
    hadley = session.execute(
        select(Round.ordinal, Round.score, Round.source_row)
        .where(Round.name_key == "hadley ike")
        .order_by(Round.ordinal)
    ).all()
    assert hadley == [(1, 40, 3), (2, 30, 2)]
    events = _events(session)
    assert (events[D1].n_rounds, events[D1].n_shooters, events[D1].results_complete) == (3, 2, True)
    assert (events[D2].n_shooters, events[D2].head_count, events[D2].results_complete) == (
        1,
        5,
        False,
    )
    assert _issues(session) == [("incomplete_results", D2)]


def test_merge_rule_puts_both_names_on_one_profile(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    rows = [("Preutt, Luther", 30, D1), ("Pruett, Luther", 33, D2)]
    mark_committed(session, stage_import(session, scores_workbook(rows), "s.xlsx").import_id)
    rebuild_live(session)
    ids = dict(session.execute(select(Shooter.display_name, Shooter.id)).all())
    session.add(
        Rule(
            rule_type="merge_shooter",
            payload={
                "source_shooter_id": ids["Preutt, Luther"],
                "target_shooter_id": ids["Pruett, Luther"],
            },
        )
    )
    session.flush()
    rebuild_live(session)
    assert set(session.scalars(select(Round.shooter_id))) == {ids["Pruett, Luther"]}
    profile = session.scalars(select(ShooterProfile)).one()
    assert (profile.display_name, profile.n_rounds, profile.n_events) == ("Pruett, Luther", 2, 2)


def test_profile_status_first_event_and_left_censoring(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    start = date(2020, 1, 5)
    rows = [
        ("Early, Bird", 30, start, "Guest"),
        ("Early, Bird", 31, start + timedelta(days=7), "Member"),
        ("Late, Comer", 30, start + timedelta(days=56), "Member"),
        ("Late, Comer", 32, start + timedelta(days=63), "Guest"),
        ("Just, Inside", 30, start + timedelta(days=49), "Member"),
        ("Gone, Now", 30, start, "Deceased"),
        ("Gone, Now", 30, start + timedelta(days=7), "Member"),
        ("No, Status", 30, start + timedelta(days=70), None),
    ]
    mark_committed(session, stage_import(session, scores_workbook(rows), "s.xlsx").import_id)
    rebuild_live(session)
    profiles = {p.display_name: p for p in session.scalars(select(ShooterProfile))}
    assert {n: p.status for n, p in profiles.items()} == {
        "Early, Bird": "member",
        "Late, Comer": "guest",
        "Just, Inside": "member",
        "Gone, Now": "deceased",
        "No, Status": "guest",
    }
    assert {n: p.left_censored for n, p in profiles.items()} == {
        "Early, Bird": True,
        "Late, Comer": False,
        "Just, Inside": True,
        "Gone, Now": True,
        "No, Status": False,
    }
    assert (profiles["Late, Comer"].first_event, profiles["Late, Comer"].last_event) == (
        start + timedelta(days=56),
        start + timedelta(days=63),
    )
    # rounds keep the raw per-row status
    assert set(session.scalars(select(Round.status))) == {"guest", "member", "deceased", None}


def test_profile_status_skips_blank_latest_status_and_ties_go_to_the_lowest_ordinal(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    rows = [
        # the latest round has no status: the earlier recorded 'member' stands (not 'guest')
        ("Blank, Latest", 30, D1, "Member"),
        ("Blank, Latest", 31, D2, None),
        # two rounds on the latest date: ordinal 1 (the higher raw score) decides, though its row
        # comes later in the file
        ("Same, Day", 30, D2, "Member"),
        ("Same, Day", 40, D2, "Guest"),
    ]
    mark_committed(session, stage_import(session, scores_workbook(rows), "s.xlsx").import_id)
    rebuild_live(session)
    profiles = session.execute(select(ShooterProfile.display_name, ShooterProfile.status)).all()
    assert dict(profiles) == {
        "Blank, Latest": "member",
        "Same, Day": "guest",
    }
    assert session.execute(
        select(Round.ordinal, Round.score, Round.status)
        .where(Round.name_key == "same day")
        .order_by(Round.ordinal)
    ).all() == [(1, 40, "guest"), (2, 30, "member")]


def test_even_layout_is_sporting_and_newest_station_import_wins(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    mark_committed(
        session,
        stage_import(
            session, scores_workbook([("Hadley, Ike", 35, D1), ("Hadley, Ike", 30, D2)]), "s.xlsx"
        ).import_id,
    )
    old = stage_import(
        session,
        stations_workbook(
            [
                ("9 6 26", D1, LAYOUT, [("Hadley, Ike", FIVES)]),
                ("9 13 26", D2, LAYOUT, [("Hadley, Ike", (4, 4, 4, 4, 4, 5, 5))]),
            ]
        ),
        "a.xlsx",
    )
    new = stage_import(
        session,
        stations_workbook(
            [("9 13 26", D2, (8, 8, 8, 8, 8, 10), [("Hadley, Ike", (5, 5, 5, 5, 5, 5))])],
            stations=(4, 5, 6, 7, 8, 9),
        ),
        "b.xlsx",
    )
    mark_committed(session, old.import_id)
    mark_committed(session, new.import_id)
    rebuild_live(session)
    events = _events(session)
    assert (events[D1].round_type, events[D2].round_type) == ("super_sporting", "sporting")
    sources = dict(
        session.execute(
            select(StationLayout.event_date, StationLayout.source_import_id).distinct()
        ).all()
    )
    assert sources == {D1: old.import_id, D2: new.import_id}
    assert session.scalar(select(func.count()).where(StationHit.round_id.is_(None))) == 0


def test_station_lookups_take_a_fixed_number_of_queries(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
    count_queries: CountQueries,
) -> None:
    # One identity_resolver per rebuild: more station entries must not mean more queries.
    def one_tab(names: list[str]) -> bytes:
        return stations_workbook([("9 13 26", D2, LAYOUT, [(n, FIVES) for n in names])])

    names = ["Hadley, Ike", "Crenshaw, Noel", "Devlin, Sid", "Linwood, Luther", "Pruett, Luther"]
    scores = scores_workbook([(n, sum(FIVES), D2) for n in names])  # every entry links exactly
    mark_committed(session, stage_import(session, scores, "s.xlsx").import_id)
    mark_committed(session, stage_import(session, one_tab(names[:1]), "a.xlsx").import_id)
    rebuild_live(session)  # creates the shooters, so both counted rebuilds only look them up
    with count_queries(session) as one_entry:
        rebuild_live(session)
    mark_committed(session, stage_import(session, one_tab(names), "b.xlsx").import_id)
    with count_queries(session) as five_entries:
        rebuild_live(session)
    assert _count(session, StationHit) == len(names) * len(LAYOUT)
    assert session.scalar(select(func.count()).where(StationHit.round_id.is_(None))) == 0
    assert _issues(session) == []
    assert len(five_entries) == len(one_entry)


def test_live_inserts_send_one_statement_per_table(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
    count_queries: CountQueries,
) -> None:
    # NULL and non-NULL interleave in every nullable live column (rounds.status/gauge_class,
    # events.head_count, station_hits.shooter_id/round_id, data_issues.shooter_id); an ORM bulk
    # insert that drops None keys would send one statement per run of equal key sets.
    d0 = D1 - timedelta(days=7)
    rows = [
        ("Hadley, Ike", 35, d0, None, None),
        ("Hadley, Ike", 34, D1, "Member", "12 Gauge"),
        ("Devlin, Sid", 30, D1, None, "20 Gauge"),
        ("Crenshaw, Noel", 31, D1, "Guest", None),
        ("Hadley, Ike", 34, D2, None, None),
        ("Devlin, Sid", 35, D2, "Member", None),
    ]
    scores = scores_workbook(rows, [(D1, 3)])
    mark_committed(session, stage_import(session, scores, "s.xlsx").import_id)
    sheet = [("Hadley, Ike", FIVES), ("Nobody, New", (4, 4, 4, 4, 4, 4, 4)), ("Devlin, Sid", FIVES)]
    tab = stations_workbook([("9 13 26", D2, LAYOUT, sheet)])
    mark_committed(session, stage_import(session, tab, "st.xlsx").import_id)
    with count_queries(session) as statements:
        rebuild_live(session)
    inserts = Counter(m.group(1) for s in statements if (m := re.match(r"INSERT INTO (\w+)", s)))
    assert {t: n for t, n in inserts.items() if t in LIVE_TABLES} == dict.fromkeys(
        ("events", "rounds", "station_layouts", "station_hits", "shooter_profiles", "data_issues"),
        1,
    )
    # the NULLs are written as NULLs
    assert session.execute(
        select(Round.status, Round.gauge_class).order_by(Round.event_date, Round.source_row)
    ).all() == [
        (None, None),
        ("member", "12 Gauge"),
        (None, "20 Gauge"),
        ("guest", None),
        (None, None),
        ("member", None),
    ]
    assert [e.head_count for e in session.scalars(select(Event).order_by(Event.event_date))] == [
        None,
        3,
        None,
    ]
    assert session.execute(
        select(DataIssue.code, DataIssue.shooter_id.is_(None)).order_by(DataIssue.id)
    ).all() == [("station_name_unmatched", True), ("station_score_mismatch", False)]
    assert session.scalar(select(func.count()).where(StationHit.round_id.is_(None))) == 7


def test_rebuild_never_reads_live_objects_the_session_held_before_it(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    def scores(score: int, status: str, filename: str) -> None:
        workbook = scores_workbook([("Hadley, Ike", score, D2, status)])
        mark_committed(session, stage_import(session, workbook, filename).import_id)

    scores(35, "Member", "a.xlsx")
    tab = stations_workbook([("9 13 26", D2, LAYOUT, [("Hadley, Ike", FIVES)])])
    mark_committed(session, stage_import(session, tab, "st.xlsx").import_id)
    rebuild_live(session)
    held = session.scalars(select(Round)).one()  # scored 35, still referenced
    # keyed by shooter_id, a natural key the rebuild writes again
    held_profile = session.scalars(select(ShooterProfile)).one()
    assert (held.score, held_profile.status, _issues(session)) == (35, "member", [])
    scores(34, "Guest", "b.xlsx")  # the same round, now scored 34 by a guest
    rebuild_live(session)
    # the station link compares with the rebuilt round, not the held object's old score
    assert [
        (i.code, i.details["station_total"], i.details["score"])
        for i in session.scalars(select(DataIssue))
    ] == [("station_score_mismatch", 35, 34)]
    # and the caller's own queries see the rebuilt rows, never a held pre-rebuild object
    assert session.scalars(select(Round)).one().score == 34
    assert session.get(Round, held.id) is None  # its row is gone
    profile = session.get(ShooterProfile, held_profile.shooter_id)
    assert profile is not None
    assert profile.status == "guest"
    # the held objects are detached pre-rebuild snapshots
    assert (held.score, held_profile.status) == (35, "member")


def test_rebuild_is_repeatable_and_bumps_data_version(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
    live_rows: LiveRowsFn,
) -> None:
    rows = [
        ("Hadley, Ike", 30, D1),
        ("Crenshaw, Noel", 31, D1, "Guest"),
        ("Hadley, Ike", 34, D2),
        ("Devlin, Sid", 30, D2, None, "20 Gauge"),
    ]
    scores = scores_workbook(rows, [(D1, 10)])  # 2 of 10 on D1: incomplete_results
    mark_committed(session, stage_import(session, scores, "s.xlsx").import_id)
    sheet = [("Hadley, Ike", FIVES), ("Nobody, New", (4, 4, 4, 4, 4, 4, 4))]  # mismatch, unmatched
    tab = stations_workbook([("9 13 26", D2, LAYOUT, sheet)])
    mark_committed(session, stage_import(session, tab, "st.xlsx").import_id)
    before = get_data_version(session)
    assert _last_rebuild_at(session) is None
    first = rebuild_live(session)
    snapshot = live_rows(session)
    first_ids = set(session.scalars(select(Round.id)))
    second = rebuild_live(session)
    assert first == second == RebuildReport(2, 4, 3, 1, 3)
    # full rows of every live table, round links included; ids renumbered, as none is reused
    assert live_rows(session) == snapshot
    assert min(session.scalars(select(Round.id))) > max(first_ids)
    assert [t for t, table_rows in snapshot.items() if not table_rows] == ["round_metrics"]
    assert _count(session, Shooter) == 3
    assert get_data_version(session) == before + 2
    written = _last_rebuild_at(session)
    assert isinstance(written, str)
    assert datetime.fromisoformat(written).tzinfo is not None


def test_rebuild_without_committed_imports_empties_live_tables(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    preview = stage_import(session, scores_workbook([("Hadley, Ike", 35, D1)]), "s.xlsx")
    mark_committed(session, preview.import_id)
    rebuild_live(session)
    imp = session.get(Import, preview.import_id)
    assert imp is not None
    imp.status = "rolled_back"
    session.flush()
    assert rebuild_live(session) == RebuildReport(0, 0, 0, 0, 0)
    assert (_count(session, Event), _count(session, Round), _count(session, ShooterProfile)) == (
        0,
        0,
        0,
    )
    assert _count(session, Shooter) == 1  # identity is durable
