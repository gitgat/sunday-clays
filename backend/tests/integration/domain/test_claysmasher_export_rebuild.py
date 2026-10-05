"""ClaySmasher scores export across real imports, rebuilds and merges."""

import csv
import io
import zipfile
from collections.abc import Callable
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.domain.imports import commit_import, stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule
from sunday_clays.ingest.names import identity_key, name_key
from sunday_clays.models import ShooterAlias

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)


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


def _sporting(client: TestClient, shooter_id: int) -> list[tuple[str, str]]:
    """(Date, Total Hits) of each row of the shooter's sporting CSV."""
    response = client.get(f"/api/shooters/{shooter_id}/claysmasher-export")
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        text = archive.read("claysmasher-sporting.csv").decode("utf-8")
    rows = [r for r in csv.reader(io.StringIO(text, newline="")) if not r[0].startswith("#")]
    head, *body = rows
    return [(row[head.index("Date")], row[head.index("Total Hits")]) for row in body]


def test_a_reimport_replaces_the_exported_scores(
    session: Session, viewer_client: TestClient, scores_workbook: Callable[..., bytes]
) -> None:
    _commit(session, scores_workbook([("Doe, Jane", 41, D1)]), "v1.xlsx")
    jane = _shooter(session, "Doe, Jane", D1)
    assert _sporting(viewer_client, jane) == [("09/06/2026", "41")]

    _commit(session, scores_workbook([("Doe, Jane", 42, D1), ("Doe, Jane", 38, D2)]), "v2.xlsx")

    assert _sporting(viewer_client, jane) == [("09/06/2026", "42"), ("09/13/2026", "38")]


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

    response = viewer_client.get(f"/api/shooters/{richard}/claysmasher-export")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "shooter_merged",
            "message": f"Shooter {richard} was merged into {rick}",
        },
        "merged_into": rick,
    }
    assert _sporting(viewer_client, rick) == [("09/06/2026", "30"), ("09/13/2026", "33")]
