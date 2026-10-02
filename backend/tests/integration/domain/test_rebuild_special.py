"""Special Sundays in the live tables (Plan 17 Task 2)."""

from collections.abc import Callable
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.domain.identity import alias_rule_targets, lookup_shooter
from sunday_clays.domain.imports import commit_import, rollback_import, stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule, deactivate_rule
from sunday_clays.models import (
    DataIssue,
    Event,
    Round,
    Shooter,
    ShooterProfile,
    StationHit,
    StationLayout,
)

BEFORE, SPECIAL, AFTER = date(2026, 9, 13), date(2026, 9, 20), date(2026, 9, 27)
WEEKLY: list[tuple[object, ...]] = [
    ("Hadley, Ike", 41, BEFORE),
    ("Devlin, Sid", 35, BEFORE),
    ("Hadley, Ike", 43, AFTER),
    ("Devlin, Sid", 37, AFTER),
]
FIVES = (5,) * 10
STATION_CODES = {"station_score_mismatch", "station_name_unmatched", "station_round_ambiguous"}


def _commit(session: Session, data: bytes, name: str) -> int:
    preview = stage_import(session, data, name)
    commit_import(session, preview.import_id)
    return preview.import_id


def _scores_on(session: Session, day: date) -> dict[str, int]:
    rows = session.execute(
        select(Shooter.display_name, Round.score)
        .join(Shooter, Shooter.id == Round.shooter_id)
        .where(Round.event_date == day)
    ).all()
    return {str(name): int(score) for name, score in rows}


def _live_special(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
    weekly: list[tuple[object, ...]] = WEEKLY,
) -> int:
    _commit(session, scores_workbook(weekly), "scores.xlsx")
    special_id = _commit(session, special_workbook(), "special.xlsx")
    rebuild_live(session)
    return special_id


def test_a_special_sunday_goes_live_with_its_label_rounds_and_stations(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _live_special(session, scores_workbook, special_workbook)

    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.kind, event.label, event.target_total) == ("special", "Three Clay Shoot", 60)
    assert (event.round_type, event.round_type_source) == ("sporting", "none")
    assert (
        event.n_rounds,
        event.n_shooters,
        event.has_scores,
        event.has_stations,
        event.results_complete,
    ) == (5, 5, True, True, True)
    for day in (BEFORE, AFTER):
        regular = session.get(Event, day)
        assert regular is not None
        assert (regular.kind, regular.label, regular.target_total) == ("regular", None, 50)
    assert _scores_on(session, SPECIAL) == {
        "Hadley, Ike": 55,
        "Kaplan, Noel": 51,
        "Devlin, Sid": 48,
        "Abernathy, Preston": 44,
        "Kim, Pat": 39,
    }
    layout = session.execute(
        select(StationLayout.station_label, StationLayout.target_count)
        .where(StationLayout.event_date == SPECIAL)
        .order_by(StationLayout.station_no)
    ).all()
    assert [tuple(r) for r in layout] == [(str(n), 6) for n in range(1, 11)]
    hits = session.scalars(select(StationHit).where(StationHit.event_date == SPECIAL)).all()
    assert len(hits) == 50
    assert all(h.round_id is not None and h.shooter_id is not None for h in hits)
    assert (
        session.scalars(select(DataIssue.code).where(DataIssue.event_date == SPECIAL)).all() == []
    )


def test_profiles_count_the_special_sunday_as_an_event_but_not_a_round(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _live_special(session, scores_workbook, special_workbook)

    hadley = session.get(ShooterProfile, lookup_shooter(session, "hadley ike"))
    assert hadley is not None
    assert (hadley.n_events, hadley.n_rounds, hadley.first_event, hadley.last_event) == (
        3,
        2,
        BEFORE,
        AFTER,
    )
    kim = session.get(ShooterProfile, lookup_shooter(session, "kim pat"))
    assert kim is not None
    assert (kim.display_name, kim.status, kim.n_events, kim.n_rounds) == ("Kim, Pat", "guest", 1, 0)
    assert (kim.first_event, kim.last_event) == (SPECIAL, SPECIAL)


def test_weekly_rows_on_a_special_date_are_left_out_and_come_back_on_rollback(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    special_id = _live_special(
        session, scores_workbook, special_workbook, [*WEEKLY, ("Hadley, Ike", 40, SPECIAL)]
    )

    assert _scores_on(session, SPECIAL)["Hadley, Ike"] == 55
    assert len(_scores_on(session, SPECIAL)) == 5
    issue = session.execute(
        select(DataIssue.code, DataIssue.severity, DataIssue.details).where(
            DataIssue.event_date == SPECIAL
        )
    ).one()
    assert (issue.code, issue.severity) == ("special_event_date_conflict", "warning")
    assert issue.details == {"rows": 1, "special_import_id": special_id}

    rollback_import(session, special_id)
    rebuild_live(session)

    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.kind, event.label, event.target_total, event.n_rounds) == ("regular", None, 50, 1)
    assert _scores_on(session, SPECIAL) == {"Hadley, Ike": 40}


def test_a_newer_special_import_replaces_the_older_one_and_rollback_restores_it(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    first = _live_special(session, scores_workbook, special_workbook)
    corrected = special_workbook(
        [("Hadley, Ike", (6, 5, 6, 4, 6, 5, 6, 6, 5, 3))], label="Three Clay Shoot (corrected)"
    )
    second = _commit(session, corrected, "special-corrected.xlsx")
    rebuild_live(session)

    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.label, event.n_shooters) == ("Three Clay Shoot (corrected)", 1)
    assert _scores_on(session, SPECIAL) == {"Hadley, Ike": 52}

    rollback_import(session, second)
    rebuild_live(session)
    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.label, event.n_shooters) == ("Three Clay Shoot", 5)

    rollback_import(session, first)
    rebuild_live(session)
    assert session.get(Event, SPECIAL) is None
    assert _scores_on(session, SPECIAL) == {}
    assert (
        session.scalar(
            select(func.count()).select_from(StationHit).where(StationHit.event_date == SPECIAL)
        )
        == 0
    )


def test_alias_rules_book_special_rows_to_the_existing_shooter(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _commit(session, scores_workbook([*WEEKLY, ("Ace, Amy", 40, BEFORE)]), "scores.xlsx")
    rebuild_live(session)
    amy = lookup_shooter(session, "ace amy")
    assert amy is not None
    create_rule(session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy}, None)
    _commit(session, special_workbook([("Ace, Amelia", FIVES), ("Kim, Pat", FIVES)]), "s.xlsx")
    shooters_before = session.scalar(select(func.count()).select_from(Shooter))

    rebuild_live(session)

    booked = session.scalar(
        select(Round.shooter_id).where(Round.event_date == SPECIAL, Round.name_key == "ace amelia")
    )
    assert booked == amy
    assert session.scalar(select(func.count()).select_from(Shooter)) == shooters_before + 1  # Kim
    assert session.scalar(select(Shooter.id).where(Shooter.display_name == "Ace, Amelia")) is None
    profile = session.get(ShooterProfile, amy)
    assert profile is not None
    assert (profile.n_events, profile.n_rounds) == (2, 1)
    hit = session.scalar(
        select(StationHit.round_id)
        .where(StationHit.event_date == SPECIAL, StationHit.name_key == "ace amelia")
        .limit(1)
    )
    assert hit is not None  # the station row links to the booked round


def test_alias_rules_still_leave_weekly_rows_alone(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _commit(session, scores_workbook([*WEEKLY, ("Ace, Amy", 40, BEFORE)]), "scores.xlsx")
    rebuild_live(session)
    amy = lookup_shooter(session, "ace amy")
    assert amy is not None
    create_rule(session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy}, None)
    _commit(
        session,
        scores_workbook([*WEEKLY, ("Ace, Amy", 40, BEFORE), ("Ace, Amelia", 30, AFTER)]),
        "scores-2.xlsx",
    )
    rebuild_live(session)
    weekly_before = session.scalar(
        select(Round.shooter_id).where(Round.event_date == AFTER, Round.name_key == "ace amelia")
    )
    assert weekly_before is not None
    assert weekly_before != amy  # Decision 15: today's behaviour for weekly rows

    # the special sheet lists the same weekly name: only its special row is re-booked
    special_id = _commit(
        session, special_workbook([("Ace, Amelia", FIVES), ("Kim, Pat", FIVES)]), "s.xlsx"
    )
    rebuild_live(session)

    def weekly_shooter() -> int | None:
        return session.scalar(
            select(Round.shooter_id).where(
                Round.event_date == AFTER, Round.name_key == "ace amelia"
            )
        )

    assert weekly_shooter() == weekly_before
    assert (
        session.scalar(
            select(Round.shooter_id).where(
                Round.event_date == SPECIAL, Round.name_key == "ace amelia"
            )
        )
        == amy
    )
    rollback_import(session, special_id)
    rebuild_live(session)
    assert weekly_shooter() == weekly_before


def test_a_shooter_has_one_round_on_a_special_sunday_the_first_one_kept(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _commit(session, scores_workbook([*WEEKLY, ("Ace, Amy", 40, BEFORE)]), "scores.xlsx")
    rebuild_live(session)
    amy = lookup_shooter(session, "ace amy")
    assert amy is not None
    create_rule(session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy}, None)
    _commit(session, special_workbook([("Ace, Amy", (6,) * 10), ("Ace, Amelia", FIVES)]), "s.xlsx")

    rebuild_live(session)

    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.n_rounds, event.n_shooters) == (1, 1)
    assert _scores_on(session, SPECIAL) == {"Ace, Amy": 60}  # the first row, not the repeat
    issues = session.execute(
        select(DataIssue.severity, DataIssue.details).where(
            DataIssue.code == "special_duplicate_shooter"
        )
    ).all()
    assert [(i.severity, i.details) for i in issues] == [
        (
            "warning",
            {"event_date": SPECIAL.isoformat(), "shooter_id": amy, "name_keys": ["ace amelia"]},
        )
    ]


def test_the_special_sheet_wins_over_a_stations_workbook_tab_of_the_same_date(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
) -> None:
    _commit(session, scores_workbook(WEEKLY), "scores.xlsx")
    tab = [("Hadley, Ike", (1,) * 7)]
    _commit(session, stations_workbook([("9 20 26", SPECIAL, (3,) * 7, tab)]), "st.xlsx")
    special_id = _commit(session, special_workbook(), "special.xlsx")

    rebuild_live(session)

    layout = session.execute(
        select(
            StationLayout.station_label, StationLayout.target_count, StationLayout.source_import_id
        ).where(StationLayout.event_date == SPECIAL)
    ).all()
    assert len(layout) == 10
    assert {(r.target_count, r.source_import_id) for r in layout} == {(6, special_id)}


def test_alias_rule_targets_ignore_inactive_rules_and_the_newest_rule_wins(
    session: Session, scores_workbook: Callable[..., bytes]
) -> None:
    _commit(
        session, scores_workbook([("Ace, Amy", 40, BEFORE), ("Bee, Bob", 41, BEFORE)]), "s.xlsx"
    )
    rebuild_live(session)
    amy, bob = lookup_shooter(session, "ace amy"), lookup_shooter(session, "bee bob")
    assert amy is not None
    assert bob is not None
    gone = create_rule(
        session, RuleType.ALIAS_NAME, {"name_key": "ghost one", "shooter_id": amy}, None
    )
    deactivate_rule(session, gone)
    create_rule(session, RuleType.ALIAS_NAME, {"name_key": "twice two", "shooter_id": amy}, None)
    create_rule(session, RuleType.ALIAS_NAME, {"name_key": "twice two", "shooter_id": bob}, None)

    assert alias_rule_targets(session) == {"twice two": bob}


def test_the_left_out_weekly_rows_message_agrees_with_the_count(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _live_special(
        session, scores_workbook, special_workbook, [*WEEKLY, ("Hadley, Ike", 40, SPECIAL)]
    )
    one = session.scalar(
        select(DataIssue.message).where(DataIssue.code == "special_event_date_conflict")
    )
    assert one is not None
    assert one.startswith("1 row in the scores workbook on 2026-09-20 is left out")

    _commit(
        session,
        scores_workbook([*WEEKLY, ("Hadley, Ike", 40, SPECIAL), ("Devlin, Sid", 30, SPECIAL)]),
        "scores-2.xlsx",
    )
    rebuild_live(session)
    two = session.scalar(
        select(DataIssue.message).where(DataIssue.code == "special_event_date_conflict")
    )
    assert two is not None
    assert two.startswith("2 rows in the scores workbook on 2026-09-20 are left out")


def test_a_round_type_override_still_applies_to_a_special_sunday(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    create_rule(
        session,
        RuleType.ROUND_TYPE_OVERRIDE,
        {"event_date": SPECIAL.isoformat(), "round_type": "super_sporting"},
        None,
    )
    _live_special(session, scores_workbook, special_workbook)

    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.kind, event.round_type, event.round_type_source) == (
        "special",
        "super_sporting",
        "override",
    )


def test_a_rebuild_with_a_special_sunday_is_idempotent(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
    live_rows: Callable[[Session], dict[str, list[dict[str, Any]]]],
) -> None:
    _live_special(session, scores_workbook, special_workbook)
    first = live_rows(session)
    rebuild_live(session)
    assert live_rows(session) == first


def test_the_scores_preview_never_checks_a_special_sheet_against_weekly_rows(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _live_special(session, scores_workbook, special_workbook)

    preview = stage_import(
        session, scores_workbook([*WEEKLY, ("Hadley, Ike", 40, SPECIAL)]), "scores-2.xlsx"
    )

    assert [f.code for f in preview.findings if f.event_date == SPECIAL] == ["special_event_date"]
    assert not [f for f in preview.findings if f.code in STATION_CODES]
