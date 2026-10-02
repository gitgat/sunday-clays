"""ClaySmasher export across real imports, rebuilds, rules and merges (spec 2026-10-01 §4.1)."""

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from sunday_clays.domain.imports import commit_import, rollback_import, stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule
from sunday_clays.ingest.names import identity_key, name_key
from sunday_clays.models import Round, ShooterAlias

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)
LAYOUT = (8, 8, 6, 8, 6, 8, 6)  # stations 4..10 (the workbook default), 50 targets, all even
JANE_HITS = (6, 7, 5, 6, 5, 7, 5)  # 41


def _commit(session: Session, data: bytes, filename: str) -> int:
    import_id = stage_import(session, data, filename).import_id
    commit_import(session, import_id)
    rebuild_live(session)
    return import_id


def _shooter(session: Session, raw_name: str, day: date) -> int:
    shooter_id = session.scalar(
        select(ShooterAlias.shooter_id).where(
            ShooterAlias.name_key == identity_key(name_key(raw_name), day)
        )
    )
    assert shooter_id is not None
    return shooter_id


def _export(client: TestClient, shooter_id: int) -> dict[str, Any]:
    response = client.get(f"/api/shooters/{shooter_id}/export")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _stamp(round_out: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(round_out["updated_at"])


def _import_time(session: Session, import_id: int, column: str) -> datetime:
    value = session.execute(
        text(f"SELECT {column} FROM imports WHERE id = :id"),  # noqa: S608 - fixed column names
        {"id": import_id},
    ).scalar_one()
    assert isinstance(value, datetime)
    return value


def test_round_keys_survive_a_reimport_while_round_ids_do_not(
    session: Session, viewer_client: TestClient, scores_workbook: Callable[..., bytes]
) -> None:
    rows = [("Doe, Jane", 41, D1), ("Doe, Jane", 38, D2), ("Roe, Rick", 30, D1)]
    _commit(session, scores_workbook(rows), "v1.xlsx")
    jane = _shooter(session, "Doe, Jane", D1)
    before = _export(viewer_client, jane)
    ids_before = set(session.scalars(select(Round.id).where(Round.shooter_id == jane)))

    _commit(session, scores_workbook([*rows, ("Roe, Rick", 33, D2)]), "v2.xlsx")
    after = _export(viewer_client, jane)
    ids_after = set(session.scalars(select(Round.id).where(Round.shooter_id == jane)))

    assert ids_before.isdisjoint(ids_after)  # rebuild renumbered every round
    key = identity_key(name_key("Doe, Jane"), D1)
    assert [r["round_key"] for r in after["rounds"]] == [
        f"2026-09-06:{key}:1",
        f"2026-09-13:{key}:1",
    ]
    assert [r["round_key"] for r in after["rounds"]] == [r["round_key"] for r in before["rounds"]]


def test_merged_away_shooter_is_404_with_the_survivor(
    session: Session, viewer_client: TestClient, scores_workbook: Callable[..., bytes]
) -> None:
    _commit(
        session,
        scores_workbook([("Roe, Rick", 30, D1), ("Roe, Richard", 33, D2)]),
        "v1.xlsx",
    )
    rick = _shooter(session, "Roe, Rick", D1)
    richard = _shooter(session, "Roe, Richard", D2)
    create_rule(
        session,
        RuleType.MERGE_SHOOTER,
        {"source_shooter_id": richard, "target_shooter_id": rick},
        None,
    )
    rebuild_live(session)

    response = viewer_client.get(f"/api/shooters/{richard}/export")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "shooter_merged",
            "message": f"Shooter {richard} was merged into {rick}",
        },
        "merged_into": rick,
    }
    survivor = _export(viewer_client, rick)
    assert [(r["round_key"], r["score"]) for r in survivor["rounds"]] == [
        (f"2026-09-06:{identity_key(name_key('Roe, Rick'), D1)}:1", 30),
        (f"2026-09-13:{identity_key(name_key('Roe, Richard'), D2)}:1", 33),
    ]


def test_updated_at_moves_forward_on_reimport_and_on_rollback(
    session: Session, viewer_client: TestClient, scores_workbook: Callable[..., bytes]
) -> None:
    v1 = _commit(session, scores_workbook([("Doe, Jane", 41, D1)]), "v1.xlsx")
    jane = _shooter(session, "Doe, Jane", D1)
    first = _export(viewer_client, jane)["rounds"][0]
    assert _stamp(first) == _import_time(session, v1, "committed_at")

    v2 = _commit(session, scores_workbook([("Doe, Jane", 42, D1)]), "v2.xlsx")
    second = _export(viewer_client, jane)["rounds"][0]
    assert (second["score"], second["round_key"]) == (42, first["round_key"])
    assert _stamp(second) == _import_time(session, v2, "committed_at")

    rollback_import(session, v2)  # v1 is live again; its commit time is older than v2's
    rebuild_live(session)
    third = _export(viewer_client, jane)["rounds"][0]
    assert third["score"] == 41
    assert _stamp(third) == _import_time(session, v2, "rolled_back_at")
    assert _stamp(third) > _stamp(second)


def test_station_sheet_rounds_export_in_station_order_and_bump_updated_at(
    session: Session,
    viewer_client: TestClient,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
) -> None:
    _commit(session, scores_workbook([("Doe, Jane", 41, D2)]), "scores.xlsx")
    stations = _commit(
        session,
        stations_workbook([("9 13 26", D2, LAYOUT, [("Doe, Jane", JANE_HITS)])]),
        "stations.xlsx",
    )
    jane = _shooter(session, "Doe, Jane", D2)

    (only,) = _export(viewer_client, jane)["rounds"]

    assert [
        (s["order"], s["station_label"], s["target_count"], s["hits"]) for s in only["stations"]
    ] == [
        (1, "4", 8, 6),
        (2, "5", 8, 7),
        (3, "6", 6, 5),
        (4, "7", 8, 6),
        (5, "8", 6, 5),
        (6, "9", 8, 7),
        (7, "10", 6, 5),
    ]
    assert (only["target_count"], only["round_type"]) == (50, "sporting")
    assert _stamp(only) == _import_time(session, stations, "committed_at")


def test_a_score_override_rule_moves_updated_at_to_the_rule(
    session: Session, viewer_client: TestClient, scores_workbook: Callable[..., bytes]
) -> None:
    _commit(session, scores_workbook([("Doe, Jane", 41, D1)]), "v1.xlsx")
    jane = _shooter(session, "Doe, Jane", D1)
    rule_id = create_rule(
        session,
        RuleType.SCORE_OVERRIDE,
        {
            "event_date": D1.isoformat(),
            "name_key": identity_key(name_key("Doe, Jane"), D1),
            "ordinal": 1,
            "score": 45,
        },
        None,
    )
    # now() is this test transaction's start, before the import's clock_timestamp(); in
    # production each rule is created in its own request transaction, after the import.
    created = session.execute(
        text("UPDATE rules SET created_at = clock_timestamp() WHERE id = :id RETURNING created_at"),
        {"id": rule_id},
    ).scalar_one()
    rebuild_live(session)

    (only,) = _export(viewer_client, jane)["rounds"]

    assert only["score"] == 45
    assert _stamp(only) == created
