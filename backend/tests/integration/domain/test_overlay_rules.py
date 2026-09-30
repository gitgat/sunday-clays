from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.engine.interfaces import DBAPICursor
from sqlalchemy.orm import Session

from sunday_clays.domain.errors import ConflictError, DomainError, NotFoundError
from sunday_clays.domain.identity import resolve_shooter
from sunday_clays.domain.imports import stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule, deactivate_rule
from sunday_clays.models import (
    DataIssue,
    Event,
    Round,
    Rule,
    Shooter,
    ShooterProfile,
    StationHit,
)

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)
LAYOUT = (7, 7, 7, 7, 7, 7, 8)
Stage = Callable[..., None]
LiveRowsFn = Callable[[Session], dict[str, list[dict[str, Any]]]]
D2_ROUND = {"event_date": "2026-09-13", "name_key": "hadley ike"}


@pytest.fixture
def load_scores(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> Stage:
    """Stage + commit a scores workbook built from rows, then rebuild."""

    def _load(rows: list[tuple[object, ...]], name: str = "s.xlsx") -> None:
        mark_committed(session, stage_import(session, scores_workbook(rows), name).import_id)
        rebuild_live(session)

    return _load


def _shooter(session: Session, display_name: str) -> int:
    return session.scalars(select(Shooter.id).where(Shooter.display_name == display_name)).one()


def _scores(session: Session, name_key: str) -> list[tuple[date, int, int]]:
    return [
        (d, o, s)
        for d, o, s in session.execute(
            select(Round.event_date, Round.ordinal, Round.score)
            .where(Round.name_key == name_key)
            .order_by(Round.event_date, Round.ordinal)
        )
    ]


def _issues(session: Session, code: str) -> list[DataIssue]:
    return list(session.scalars(select(DataIssue).where(DataIssue.code == code)))


@pytest.mark.parametrize(
    ("rule_type", "payload", "message"),
    [
        (
            RuleType.SCORE_OVERRIDE,
            {"event_date": "2026-09-13", "name_key": "hadley ike", "ordinal": 1, "score": 51},
            "score",
        ),
        (RuleType.SET_STATUS, {"shooter_id": 1, "status": "retired"}, "status"),
        (RuleType.RENAME_SHOOTER, {"shooter_id": 1, "display_name": "   "}, "display_name"),
        (RuleType.ALIAS_NAME, {"name_key": "hadley dik", "shooter_id": 1, "extra": True}, "extra"),
        ("not_a_rule", {}, "not_a_rule"),
    ],
)
def test_create_rule_rejects_invalid_payloads(
    session: Session, rule_type: str, payload: dict[str, object], message: str
) -> None:
    with pytest.raises(DomainError) as excinfo:
        create_rule(session, rule_type, payload, None)  # type: ignore[arg-type]
    assert excinfo.value.code == "invalid_rule"
    assert message in excinfo.value.message
    assert session.scalar(select(func.count()).select_from(Rule)) == 0


def test_create_rule_rejects_unknown_shooter(session: Session) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        create_rule(session, RuleType.SET_STATUS, {"shooter_id": 424242, "status": "member"}, None)
    assert excinfo.value.code == "shooter_not_found"


def test_merge_shooter_rule_and_deactivation(session: Session, load_scores: Stage) -> None:
    load_scores([("Preutt, Luther", 30, D1), ("Pruett, Luther", 33, D2)])
    source, target = _shooter(session, "Preutt, Luther"), _shooter(session, "Pruett, Luther")
    with pytest.raises(DomainError, match="itself"):
        create_rule(
            session,
            RuleType.MERGE_SHOOTER,
            {"source_shooter_id": target, "target_shooter_id": target},
            None,
        )
    rule_id = create_rule(
        session,
        RuleType.MERGE_SHOOTER,
        {"source_shooter_id": source, "target_shooter_id": target},
        "typo",
    )
    rebuild_live(session)
    assert set(session.scalars(select(Round.shooter_id))) == {target}
    assert session.scalars(select(ShooterProfile.n_rounds)).all() == [2]
    deactivate_rule(session, rule_id)
    rebuild_live(session)
    assert set(session.scalars(select(Round.shooter_id))) == {source, target}


def test_merge_cycle_is_rejected_and_not_stored(session: Session, load_scores: Stage) -> None:
    load_scores([("Roland, Sam", 30, D1), ("Rolland, Sam", 33, D2)])
    a, b = _shooter(session, "Roland, Sam"), _shooter(session, "Rolland, Sam")
    create_rule(
        session, RuleType.MERGE_SHOOTER, {"source_shooter_id": a, "target_shooter_id": b}, None
    )
    with pytest.raises(DomainError) as excinfo:
        create_rule(
            session, RuleType.MERGE_SHOOTER, {"source_shooter_id": b, "target_shooter_id": a}, None
        )
    assert excinfo.value.code == "merge_cycle"
    assert session.scalar(select(func.count()).select_from(Rule)) == 1


def test_deactivation_that_would_form_a_merge_cycle_is_rejected(
    session: Session, load_scores: Stage
) -> None:
    load_scores([("Aa, Bb", 30, D1), ("Cc, Dd", 31, D2), ("Ee, Ff", 32, date(2026, 9, 20))])
    a, b, c = (_shooter(session, name) for name in ("Aa, Bb", "Cc, Dd", "Ee, Ff"))

    def merge(source: int, target: int) -> int:
        payload = {"source_shooter_id": source, "target_shooter_id": target}
        return create_rule(session, RuleType.MERGE_SHOOTER, payload, None)

    merge(b, a)
    b_to_c = merge(b, c)  # newest rule per source wins, so b -> a is shadowed
    merge(a, b)  # a -> b -> c: no cycle while b -> c is active
    with pytest.raises(DomainError) as excinfo:
        deactivate_rule(session, b_to_c)  # b -> a would come back: a -> b -> a
    assert excinfo.value.code == "merge_cycle"
    rule = session.get(Rule, b_to_c)
    assert rule is not None
    assert (rule.active, rule.deactivated_at) == (True, None)
    rebuild_live(session)  # merge_map still resolves, so rebuilds keep working
    assert set(session.scalars(select(Round.shooter_id))) == {c}


def test_merged_same_day_rounds_is_an_info_issue(session: Session, load_scores: Stage) -> None:
    load_scores([("Roland, Sam", 30, D1), ("Rolland, Sam", 33, D1)])
    a, b = _shooter(session, "Roland, Sam"), _shooter(session, "Rolland, Sam")
    create_rule(
        session, RuleType.MERGE_SHOOTER, {"source_shooter_id": a, "target_shooter_id": b}, None
    )
    rebuild_live(session)
    [issue] = _issues(session, "merged_same_day_rounds")
    assert (issue.severity, issue.event_date, issue.shooter_id) == ("info", D1, b)
    assert issue.details == {"name_keys": ["roland sam", "rolland sam"]}


def test_rename_shooter_changes_profile_only(session: Session, load_scores: Stage) -> None:
    load_scores([("Linwood Luther", 30, D1)])
    shooter = _shooter(session, "Linwood Luther")
    rule_id = create_rule(
        session,
        RuleType.RENAME_SHOOTER,
        {"shooter_id": shooter, "display_name": " Linwood, Luther "},
        None,
    )
    rebuild_live(session)
    assert session.scalars(select(ShooterProfile.display_name)).one() == "Linwood, Luther"
    assert session.get(Shooter, shooter).display_name == "Linwood Luther"  # type: ignore[union-attr]
    deactivate_rule(session, rule_id)
    rebuild_live(session)
    assert session.scalars(select(ShooterProfile.display_name)).one() == "Linwood Luther"


def test_set_status_overrides_profile_but_not_rounds(session: Session, load_scores: Stage) -> None:
    load_scores([("Hadley, Ike", 30, D1, "Member")])
    create_rule(
        session,
        RuleType.SET_STATUS,
        {"shooter_id": _shooter(session, "Hadley, Ike"), "status": "deceased"},
        None,
    )
    rebuild_live(session)
    assert session.scalars(select(ShooterProfile.status)).one() == "deceased"
    assert session.scalars(select(Round.status)).one() == "member"


def test_score_override_changes_score_and_fills_raw_score(
    session: Session, load_scores: Stage
) -> None:
    load_scores([("Hadley, Ike", 40, D2), ("Hadley, Ike", 34, D2)])
    rule_id = create_rule(
        session,
        RuleType.SCORE_OVERRIDE,
        {"event_date": "2026-09-13", "name_key": "hadley ike", "ordinal": 2, "score": 36},
        "sheet says 36",
    )
    assert session.get(Rule, rule_id).payload["raw_score"] == 34  # type: ignore[union-attr]
    rebuild_live(session)
    assert _scores(session, "hadley ike") == [(D2, 1, 40), (D2, 2, 36)]  # ordinal kept


def test_score_override_needs_a_live_round(session: Session, load_scores: Stage) -> None:
    load_scores([("Hadley, Ike", 34, D2)])
    with pytest.raises(NotFoundError) as excinfo:
        create_rule(
            session,
            RuleType.SCORE_OVERRIDE,
            {"event_date": "2026-09-13", "name_key": "hadley ike", "ordinal": 2, "score": 36},
            None,
        )
    assert excinfo.value.code == "round_not_found"


def test_score_override_does_not_retarget(session: Session, load_scores: Stage) -> None:
    load_scores([("Hadley, Ike", 40, D2), ("Hadley, Ike", 30, D2)], "v1.xlsx")
    rule_id = create_rule(
        session,
        RuleType.SCORE_OVERRIDE,
        {"event_date": "2026-09-13", "name_key": "hadley ike", "ordinal": 2, "score": 32},
        None,
    )
    # A later upload re-keys the 30 as 35: ordinal 2 now has raw score 35, not the rule's 30.
    load_scores([("Hadley, Ike", 40, D2), ("Hadley, Ike", 35, D2)], "v2.xlsx")
    assert _scores(session, "hadley ike") == [(D2, 1, 40), (D2, 2, 35)]
    [issue] = _issues(session, "rule_target_missing")
    assert issue.details["rule_id"] == rule_id
    assert issue.severity == "warning"


def test_hide_round_drops_it_and_deactivation_restores(
    session: Session, load_scores: Stage
) -> None:
    load_scores([("Hadley, Ike", 40, D2), ("Hadley, Ike", 12, D2), ("Crenshaw, Noel", 37, D2)])
    rule_id = create_rule(
        session,
        RuleType.HIDE_ROUND,
        {"event_date": "2026-09-13", "name_key": "hadley ike", "ordinal": 2},
        "test round",
    )
    rebuild_live(session)
    assert _scores(session, "hadley ike") == [(D2, 1, 40)]
    assert session.get(Event, D2).n_rounds == 2  # type: ignore[union-attr]
    deactivate_rule(session, rule_id)
    rebuild_live(session)
    assert _scores(session, "hadley ike") == [(D2, 1, 40), (D2, 2, 12)]


def test_stale_rule_emits_rule_target_missing(session: Session, load_scores: Stage) -> None:
    load_scores([("Hadley, Ike", 34, D2), ("Crenshaw, Noel", 37, D2)], "v1.xlsx")
    rule_id = create_rule(
        session,
        RuleType.HIDE_ROUND,
        {"event_date": "2026-09-13", "name_key": "crenshaw noel", "ordinal": 1},
        None,
    )
    load_scores([("Hadley, Ike", 34, D2)], "v2.xlsx")  # Crenshaw's row is gone
    [issue] = _issues(session, "rule_target_missing")
    assert (issue.event_date, issue.details["rule_id"]) == (D2, rule_id)
    assert _scores(session, "hadley ike") == [(D2, 1, 34)]


def test_round_type_override_wins_and_missing_date_is_reported(
    session: Session, load_scores: Stage
) -> None:
    load_scores([("Hadley, Ike", 34, D2)])
    create_rule(
        session,
        RuleType.ROUND_TYPE_OVERRIDE,
        {"event_date": "2026-09-13", "round_type": "sporting"},
        None,
    )
    orphan = create_rule(
        session,
        RuleType.ROUND_TYPE_OVERRIDE,
        {"event_date": "2026-09-20", "round_type": "sporting"},
        None,
    )
    rebuild_live(session)
    event = session.get(Event, D2)
    assert event is not None
    assert (event.round_type, event.round_type_source) == ("sporting", "override")
    [issue] = _issues(session, "rule_target_missing")
    assert (issue.event_date, issue.details["rule_id"]) == (date(2026, 9, 20), orphan)
    # Decision 14: details are {rule_id, ...payload}
    assert issue.details == {
        "rule_id": orphan,
        "event_date": "2026-09-20",
        "round_type": "sporting",
    }


def test_station_reset_is_stored_but_changes_no_live_rows(
    session: Session, load_scores: Stage, live_rows: LiveRowsFn
) -> None:
    load_scores([("Hadley, Ike", 34, D2)])
    before = live_rows(session)
    rule_id = create_rule(
        session,
        RuleType.STATION_RESET,
        {"station_no": 7, "effective_date": "2026-09-13", "note": "new presentation"},
        None,
    )
    rebuild_live(session)
    rule = session.get(Rule, rule_id)
    assert rule is not None
    assert rule.payload == {
        "station_no": 7,
        "effective_date": "2026-09-13",
        "note": "new presentation",
    }
    assert live_rows(session) == before


def test_alias_rule_links_unmatched_station_name(
    session: Session,
    load_scores: Stage,
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    load_scores([("Hadley, Ike", 34, D2)])
    sheet = [("Hadley, Dik", (5, 5, 5, 5, 5, 5, 4))]
    mark_committed(
        session,
        stage_import(
            session, stations_workbook([("9 13 26", D2, LAYOUT, sheet)]), "st.xlsx"
        ).import_id,
    )
    rebuild_live(session)
    assert [i.details["name_key"] for i in _issues(session, "station_name_unmatched")] == [
        "hadley dik"
    ]
    hadley = _shooter(session, "Hadley, Ike")
    create_rule(
        session,
        RuleType.ALIAS_NAME,
        {"name_key": "hadley dik", "shooter_id": hadley},
        "station typo",
    )
    rebuild_live(session)
    assert _issues(session, "station_name_unmatched") == []
    round_id = session.scalars(select(Round.id)).one()
    assert set(session.execute(select(StationHit.shooter_id, StationHit.round_id)).all()) == {
        (hadley, round_id)
    }


def test_deactivate_rule_errors(session: Session, load_scores: Stage) -> None:
    load_scores([("Hadley, Ike", 34, D2)])
    rule_id = create_rule(
        session,
        RuleType.SET_STATUS,
        {"shooter_id": _shooter(session, "Hadley, Ike"), "status": "guest"},
        None,
    )
    deactivate_rule(session, rule_id)
    rule = session.get(Rule, rule_id)
    assert rule is not None
    assert rule.active is False
    assert rule.deactivated_at is not None
    with pytest.raises(ConflictError) as conflict:
        deactivate_rule(session, rule_id)
    assert conflict.value.code == "rule_not_active"
    with pytest.raises(NotFoundError) as missing:
        deactivate_rule(session, 999_999)
    assert missing.value.code == "rule_not_found"


# --- beyond the brief: Task 2 ruling on alias_name keys, Decision 15 contract -----------------


@pytest.mark.parametrize(
    "name_key",
    [
        "Hadley, Dik",  # the raw spelling, not its name_key
        "hadley  dik",  # name_key collapses whitespace
        " hadley dik",  # nor does it keep outer whitespace
        "hadley",  # a one-token key is always dated
        "hadley@13-09-2026",  # the suffix is an ISO date
        "hadley@20260913",  # date.fromisoformat reads this, but identity_key never writes it
        "hadley@2026-02-30",  # no such day
        "hadley dik@2026-09-13",  # a key with two or more tokens is never dated
        "@2026-09-13",  # no name at all
        "",
    ],
)
def test_alias_name_rejects_a_key_that_is_not_an_identity_key(
    session: Session, name_key: str
) -> None:
    hadley = resolve_shooter(session, "Hadley, Ike", D2)
    with pytest.raises(DomainError) as excinfo:
        create_rule(
            session, RuleType.ALIAS_NAME, {"name_key": name_key, "shooter_id": hadley}, None
        )
    assert excinfo.value.code == "invalid_rule"
    assert "name_key" in excinfo.value.message
    assert session.scalar(select(func.count()).select_from(Rule)) == 0


def test_alias_name_with_a_dated_one_token_key_links_a_first_name_entry(
    session: Session,
    load_scores: Stage,
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    load_scores([("Hadley, Ike", 34, D2)])
    tab = stations_workbook([("9 13 26", D2, LAYOUT, [("Dik", (5, 5, 5, 5, 5, 5, 4))])])
    mark_committed(session, stage_import(session, tab, "st.xlsx").import_id)
    rebuild_live(session)
    [unmatched] = _issues(session, "station_name_unmatched")
    assert unmatched.details["name_key"] == "dik@2026-09-13"
    hadley = _shooter(session, "Hadley, Ike")
    rule_id = create_rule(
        session, RuleType.ALIAS_NAME, {"name_key": "dik@2026-09-13", "shooter_id": hadley}, None
    )
    assert session.get(Rule, rule_id).payload == {  # type: ignore[union-attr]
        "name_key": "dik@2026-09-13",
        "shooter_id": hadley,
    }
    rebuild_live(session)
    assert _issues(session, "station_name_unmatched") == []
    round_id = session.scalars(select(Round.id)).one()
    assert set(session.execute(select(StationHit.shooter_id, StationHit.round_id)).all()) == {
        (hadley, round_id)
    }


def test_explicit_raw_score_is_stored_as_given_and_never_retargets(
    session: Session, load_scores: Stage
) -> None:
    load_scores([("Hadley, Ike", 34, D2)])
    rule_id = create_rule(
        session,
        RuleType.HIDE_ROUND,
        {"event_date": "2026-09-13", "name_key": "hadley ike", "ordinal": 1, "raw_score": 35},
        None,
    )
    assert session.get(Rule, rule_id).payload["raw_score"] == 35  # type: ignore[union-attr]
    rebuild_live(session)
    assert _scores(session, "hadley ike") == [(D2, 1, 34)]  # 34 is not the rule's 35: not hidden
    [issue] = _issues(session, "rule_target_missing")
    assert issue.details == {
        "rule_id": rule_id,
        "event_date": "2026-09-13",
        "name_key": "hadley ike",
        "ordinal": 1,
        "raw_score": 35,
    }


def test_newest_active_rule_wins_for_one_target(session: Session, load_scores: Stage) -> None:
    load_scores([("Hadley, Ike", 34, D2)])
    hadley = _shooter(session, "Hadley, Ike")
    target = {"event_date": "2026-09-13", "name_key": "hadley ike", "ordinal": 1}
    for rule_type, payload in [
        (RuleType.RENAME_SHOOTER, {"shooter_id": hadley, "display_name": "Ike Hadley"}),
        (RuleType.RENAME_SHOOTER, {"shooter_id": hadley, "display_name": "Clint Hadley"}),
        (RuleType.SET_STATUS, {"shooter_id": hadley, "status": "guest"}),
        (RuleType.SET_STATUS, {"shooter_id": hadley, "status": "deceased"}),
        (RuleType.ROUND_TYPE_OVERRIDE, {"event_date": "2026-09-13", "round_type": "sporting"}),
        (
            RuleType.ROUND_TYPE_OVERRIDE,
            {"event_date": "2026-09-13", "round_type": "super_sporting"},
        ),
        (RuleType.SCORE_OVERRIDE, {**target, "score": 36}),
        (RuleType.SCORE_OVERRIDE, {**target, "score": 38}),
    ]:
        create_rule(session, rule_type, payload, None)
    rebuild_live(session)
    profile = session.scalars(select(ShooterProfile)).one()
    assert (profile.display_name, profile.status) == ("Clint Hadley", "deceased")
    event = session.get(Event, D2)
    assert event is not None
    assert (event.round_type, event.round_type_source) == ("super_sporting", "override")
    assert _scores(session, "hadley ike") == [(D2, 1, 38)]
    assert session.scalars(select(DataIssue.code)).all() == []


# --- rename and set_status follow merges ------------------------------------------------------


def _profiles(session: Session) -> list[tuple[int, str, str]]:
    return [
        (shooter_id, display_name, status)
        for shooter_id, display_name, status in session.execute(
            select(ShooterProfile.shooter_id, ShooterProfile.display_name, ShooterProfile.status)
        )
    ]


def test_rename_and_status_of_a_merged_away_shooter_apply_to_the_merge_target(
    session: Session, load_scores: Stage
) -> None:
    load_scores([("Preutt, Luther", 30, D1, "Member"), ("Pruett, Luther", 33, D2, "Member")])
    source, target = _shooter(session, "Preutt, Luther"), _shooter(session, "Pruett, Luther")
    create_rule(
        session,
        RuleType.RENAME_SHOOTER,
        {"shooter_id": source, "display_name": "Jonas Pruett"},
        None,
    )
    create_rule(session, RuleType.SET_STATUS, {"shooter_id": source, "status": "deceased"}, None)
    create_rule(
        session,
        RuleType.MERGE_SHOOTER,
        {"source_shooter_id": source, "target_shooter_id": target},
        None,
    )
    rebuild_live(session)
    assert _profiles(session) == [(target, "Jonas Pruett", "deceased")]


@pytest.mark.parametrize("newer_on", ["target", "source"])
def test_newest_rename_and_status_win_across_a_merged_pair(
    session: Session, load_scores: Stage, newer_on: str
) -> None:
    load_scores([("Preutt, Luther", 30, D1, "Member"), ("Pruett, Luther", 33, D2, "Member")])
    source, target = _shooter(session, "Preutt, Luther"), _shooter(session, "Pruett, Luther")
    older, newer = (source, target) if newer_on == "target" else (target, source)
    for shooter_id, display_name, status in [
        (older, "Old Name", "guest"),
        (newer, "New Name", "deceased"),
    ]:
        create_rule(
            session,
            RuleType.RENAME_SHOOTER,
            {"shooter_id": shooter_id, "display_name": display_name},
            None,
        )
        create_rule(
            session, RuleType.SET_STATUS, {"shooter_id": shooter_id, "status": status}, None
        )
    create_rule(
        session,
        RuleType.MERGE_SHOOTER,
        {"source_shooter_id": source, "target_shooter_id": target},
        None,
    )
    rebuild_live(session)
    assert _profiles(session) == [(target, "New Name", "deceased")]


# --- score_override and hide_round keys are identity keys -------------------------------------


@pytest.mark.parametrize(
    ("rule_type", "extra"),
    [
        pytest.param(RuleType.SCORE_OVERRIDE, {"score": 36}, id="score_override"),
        pytest.param(RuleType.HIDE_ROUND, {}, id="hide_round"),
    ],
)
@pytest.mark.parametrize(
    "name_key",
    [
        "Hadley, Ike",  # the raw spelling, not its name_key
        " hadley ike",  # name_key keeps no outer whitespace
        "hadley",  # a one-token key is always dated
        "hadley ike@2026-09-13",  # a key with two or more tokens is never dated
    ],
)
def test_round_rules_reject_a_key_that_is_not_an_identity_key(
    session: Session, rule_type: RuleType, extra: dict[str, int], name_key: str
) -> None:
    # raw_score is given, so nothing but the key check stands between the payload and storage
    payload = {"event_date": "2026-09-13", "name_key": name_key, "ordinal": 1, "raw_score": 34}
    with pytest.raises(DomainError) as excinfo:
        create_rule(session, rule_type, {**payload, **extra}, None)
    assert excinfo.value.code == "invalid_rule"
    assert "name_key" in excinfo.value.message
    assert session.scalar(select(func.count()).select_from(Rule)) == 0


# --- raw_score is filled from the target's rows only ------------------------------------------


@contextmanager
def _rows_read(session: Session, table: str) -> Iterator[list[int]]:
    """Row count of every SELECT from ``table`` the session's connection runs inside the block."""
    counts: list[int] = []

    def record(_conn: object, cursor: DBAPICursor, statement: str, *_rest: object) -> None:
        if statement.startswith("SELECT") and f"FROM {table} " in statement:
            counts.append(cursor.rowcount)

    connection = session.connection()
    event.listen(connection, "after_cursor_execute", record)
    try:
        yield counts
    finally:
        event.remove(connection, "after_cursor_execute", record)


def test_raw_score_fill_reads_only_the_targets_rows_with_the_rebuilds_ordinals(
    session: Session, load_scores: Stage
) -> None:
    load_scores(
        [
            ("Hadley, Ike", 40, D2),
            ("Crenshaw, Noel", 37, D2),
            ("Hadley, Ike", 34, D2),
            ("Hadley, Ike", 30, D1),
            ("Hadley, Ike", 45, D2),
            ("Devlin, Sid", 38, D1),
        ]
    )
    # the rebuild keyed the whole six-row import: ordinals by raw score desc, then row number
    live = {ordinal: score for d, ordinal, score in _scores(session, "hadley ike") if d == D2}
    assert live == {1: 45, 2: 40, 3: 34}
    with _rows_read(session, "import_score_rows") as counts:
        rule_ids = [
            create_rule(session, RuleType.HIDE_ROUND, {**D2_ROUND, "ordinal": ordinal}, None)
            for ordinal in live
        ]
    filled = session.execute(
        select(Rule.payload["ordinal"].as_integer(), Rule.payload["raw_score"].as_integer()).where(
            Rule.id.in_(rule_ids)
        )
    ).all()
    assert dict(filled) == live
    assert counts == [3, 3, 3]  # one filtered SELECT per rule: Hadley's three rows on D2 only


def test_raw_score_fill_without_a_committed_scores_import_is_round_not_found(
    session: Session,
) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        create_rule(
            session,
            RuleType.HIDE_ROUND,
            {"event_date": "2026-09-13", "name_key": "hadley ike", "ordinal": 1},
            None,
        )
    assert excinfo.value.code == "round_not_found"


# --- deactivating any rule restores the no-rule live tables -----------------------------------

BuildPayload = Callable[[Callable[[str], int]], dict[str, object]]


@pytest.mark.parametrize(
    ("rule_type", "payload", "changes"),
    [
        pytest.param(
            RuleType.MERGE_SHOOTER,
            lambda shooter: {
                "source_shooter_id": shooter("Preutt, Luther"),
                "target_shooter_id": shooter("Pruett, Luther"),
            },
            {"rounds", "shooter_profiles"},
            id="merge_shooter",
        ),
        pytest.param(
            RuleType.RENAME_SHOOTER,
            lambda shooter: {"shooter_id": shooter("Hadley, Ike"), "display_name": "Clint Hadley"},
            {"shooter_profiles"},
            id="rename_shooter",
        ),
        pytest.param(
            RuleType.SCORE_OVERRIDE,
            lambda _: {**D2_ROUND, "ordinal": 2, "score": 36},
            {"rounds"},
            id="score_override",
        ),
        pytest.param(  # round numbers after the hidden row shift, so Pruett's station link moves
            RuleType.HIDE_ROUND,
            lambda _: {**D2_ROUND, "ordinal": 1},
            {"rounds", "events", "shooter_profiles", "station_hits"},
            id="hide_round",
        ),
        pytest.param(
            RuleType.ROUND_TYPE_OVERRIDE,
            lambda _: {"event_date": "2026-09-06", "round_type": "sporting"},
            {"events"},
            id="round_type_override",
        ),
        pytest.param(
            RuleType.SET_STATUS,
            lambda shooter: {"shooter_id": shooter("Crenshaw, Noel"), "status": "member"},
            {"shooter_profiles"},
            id="set_status",
        ),
        pytest.param(
            RuleType.STATION_RESET,
            lambda _: {"station_no": 7, "effective_date": "2026-09-13", "note": "new thrower"},
            set(),  # Plan 10 reads station_reset for eras; no live table depends on it
            id="station_reset",
        ),
        pytest.param(
            RuleType.ALIAS_NAME,
            lambda shooter: {
                "name_key": "crenshaw noell",
                "shooter_id": shooter("Crenshaw, Noel"),
            },
            {"station_hits", "data_issues"},
            id="alias_name",
        ),
    ],
)
def test_deactivating_a_rule_restores_the_no_rule_live_tables(
    session: Session,
    load_scores: Stage,
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
    live_rows: LiveRowsFn,
    rule_type: RuleType,
    payload: BuildPayload,
    changes: set[str],
) -> None:
    load_scores(
        [
            ("Hadley, Ike", 30, D1, "Member"),
            ("Preutt, Luther", 31, D1),
            ("Hadley, Ike", 40, D2, "Member"),
            ("Hadley, Ike", 34, D2, "Member"),
            ("Crenshaw, Noel", 37, D2, "Guest"),
            ("Pruett, Luther", 33, D2),
        ]
    )
    sheet = [("Pruett, Luther", (5, 5, 5, 5, 5, 4, 4)), ("Crenshaw, Noell", (5, 5, 5, 5, 5, 5, 7))]
    tab = stations_workbook([("9 13 26", D2, LAYOUT, sheet)])
    mark_committed(session, stage_import(session, tab, "st.xlsx").import_id)
    rebuild_live(session)
    baseline = live_rows(session)
    rule_id = create_rule(session, rule_type, payload(lambda name: _shooter(session, name)), None)
    rebuild_live(session)
    with_rule = live_rows(session)
    assert {table for table, rows in with_rule.items() if rows != baseline[table]} == changes
    deactivate_rule(session, rule_id)
    rebuild_live(session)
    assert live_rows(session) == baseline
