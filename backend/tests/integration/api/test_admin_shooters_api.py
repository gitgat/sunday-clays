import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.models import Base

AUDIT = Base.metadata.tables["audit_log"]
JOBS = Base.metadata.tables["jobs"]
PROFILES = Base.metadata.tables["shooter_profiles"]
RULES = Base.metadata.tables["rules"]


def _shooter(session: Session, display_name: str) -> int:
    return int(
        session.execute(
            select(PROFILES.c.shooter_id).where(PROFILES.c.display_name == display_name)
        ).scalar_one()
    )


def _count(session: Session, table_name: str) -> int:
    return int(session.scalar(select(func.count()).select_from(Base.metadata.tables[table_name])))


def _newest_rule(session: Session) -> tuple[str, dict[str, object]]:
    row = session.execute(
        select(RULES.c.rule_type, RULES.c.payload).order_by(RULES.c.id.desc()).limit(1)
    ).one()
    return row.rule_type, row.payload


def _last_action(session: Session) -> str | None:
    return session.scalar(select(AUDIT.c.action).order_by(AUDIT.c.id.desc()).limit(1))


def _job(session: Session, job_id: int) -> tuple[str, str | None, str]:
    row = session.execute(
        select(JOBS.c.kind, JOBS.c.dedupe_key, JOBS.c.status).where(JOBS.c.id == job_id)
    ).one()
    return row.kind, row.dedupe_key, row.status


def test_merge_dry_run_reports_shared_dates_and_changes_nothing(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    stroud, skelton = (
        _shooter(fx_session, "Stroud, Jasper"),
        _shooter(fx_session, "Skelton, Jasper"),
    )
    before = {name: _count(fx_session, name) for name in ("rules", "jobs", "audit_log")}
    response = fx_admin_client.post(
        "/api/admin/shooters/merge",
        json={"source_shooter_id": skelton, "target_shooter_id": stroud, "dry_run": True},
    )
    assert response.status_code == 200
    assert response.json() == {"shared_dates": 18, "job_id": None}
    assert {name: _count(fx_session, name) for name in before} == before  # no rule, job or audit


def test_merge_creates_rule_enqueues_rebuild_and_audits(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    stroud, skelton = (
        _shooter(fx_session, "Stroud, Jasper"),
        _shooter(fx_session, "Skelton, Jasper"),
    )
    response = fx_admin_client.post(
        "/api/admin/shooters/merge",
        json={"source_shooter_id": skelton, "target_shooter_id": stroud},
    )
    body = response.json()
    assert body["shared_dates"] == 18
    assert _job(fx_session, body["job_id"]) == ("rebuild", "rebuild", "queued")
    assert _newest_rule(fx_session) == (
        "merge_shooter",
        {"source_shooter_id": skelton, "target_shooter_id": stroud},
    )
    assert _last_action(fx_session) == "shooters.merge"


@pytest.mark.parametrize("dry_run", [{}, {"dry_run": False}, {"dry_run": True}])
def test_merge_with_itself_is_400_even_as_a_dry_run(
    fx_admin_client: TestClient, fx_session: Session, dry_run: dict[str, bool]
) -> None:
    # Decision D18: the self-merge check comes first, so a dry run is refused too.
    hadley = _shooter(fx_session, "Hadley, Ike")
    before = {name: _count(fx_session, name) for name in ("rules", "jobs", "audit_log")}
    response = fx_admin_client.post(
        "/api/admin/shooters/merge",
        json={"source_shooter_id": hadley, "target_shooter_id": hadley, **dry_run},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "merge_same_shooter"
    assert {name: _count(fx_session, name) for name in before} == before


def test_merge_with_unknown_shooter_is_404(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    hadley = _shooter(fx_session, "Hadley, Ike")
    response = fx_admin_client.post(
        "/api/admin/shooters/merge",
        json={"source_shooter_id": 987_654, "target_shooter_id": hadley, "dry_run": True},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"


def test_merge_that_closes_a_cycle_is_400_and_writes_nothing(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    stroud, skelton = (
        _shooter(fx_session, "Stroud, Jasper"),
        _shooter(fx_session, "Skelton, Jasper"),
    )
    fx_admin_client.post(
        "/api/admin/shooters/merge",
        json={"source_shooter_id": skelton, "target_shooter_id": stroud},
    )
    before = {name: _count(fx_session, name) for name in ("rules", "jobs", "audit_log")}
    response = fx_admin_client.post(
        "/api/admin/shooters/merge",
        json={"source_shooter_id": stroud, "target_shooter_id": skelton},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "merge_cycle"
    assert {name: _count(fx_session, name) for name in before} == before


@pytest.mark.parametrize(
    ("path", "body", "action", "rule_type", "payload"),
    [
        (
            "rename",
            {"display_name": "  Ike Hadley  "},
            "shooters.rename",
            "rename_shooter",
            {"display_name": "Ike Hadley"},
        ),
        (
            "status",
            {"status": "deceased"},
            "shooters.status",
            "set_status",
            {"status": "deceased"},
        ),
        (
            "aliases",
            {"name_key": "hadley clint"},
            "shooters.alias",
            "alias_name",
            {"name_key": "hadley clint"},
        ),
        (
            "aliases",
            {"name_key": " ike@2026-09-13 "},
            "shooters.alias",
            "alias_name",
            {"name_key": "ike@2026-09-13"},
        ),
    ],
)
def test_shooter_fix_creates_rule_enqueues_rebuild_and_audits(
    fx_admin_client: TestClient,
    fx_session: Session,
    path: str,
    body: dict[str, str],
    action: str,
    rule_type: str,
    payload: dict[str, str],
) -> None:
    hadley = _shooter(fx_session, "Hadley, Ike")
    response = fx_admin_client.post(f"/api/admin/shooters/{hadley}/{path}", json=body)
    assert response.status_code == 200
    assert set(response.json()) == {"rule_id", "job_id"}
    assert _newest_rule(fx_session) == (rule_type, {"shooter_id": hadley, **payload})
    assert _job(fx_session, response.json()["job_id"]) == ("rebuild", "rebuild", "queued")
    assert _last_action(fx_session) == action


def test_consecutive_shooter_fixes_share_one_queued_rebuild(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    hadley = _shooter(fx_session, "Hadley, Ike")
    jobs_before = _count(fx_session, "jobs")
    first = fx_admin_client.post(
        f"/api/admin/shooters/{hadley}/rename", json={"display_name": "Ike Hadley"}
    ).json()["job_id"]
    assert _job(fx_session, first) == ("rebuild", "rebuild", "queued")
    second = fx_admin_client.post(
        f"/api/admin/shooters/{hadley}/status", json={"status": "guest"}
    ).json()["job_id"]
    assert second == first
    assert _count(fx_session, "jobs") == jobs_before + 1


@pytest.mark.parametrize("name_key", ["Hadley, Ike", "ike", "hadley  ike", "ike@2026-9-13"])
def test_alias_that_is_not_an_identity_key_is_400_and_writes_nothing(
    fx_admin_client: TestClient, fx_session: Session, name_key: str
) -> None:
    hadley = _shooter(fx_session, "Hadley, Ike")
    before = {name: _count(fx_session, name) for name in ("rules", "jobs", "audit_log")}
    response = fx_admin_client.post(
        f"/api/admin/shooters/{hadley}/aliases", json={"name_key": name_key}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_rule"
    assert {name: _count(fx_session, name) for name in before} == before


@pytest.mark.parametrize(
    ("path", "body"),
    [("rename", {"display_name": "   "}), ("status", {"status": "ghost"}), ("aliases", {})],
)
def test_invalid_shooter_fix_body_is_422(
    fx_admin_client: TestClient, fx_session: Session, path: str, body: dict[str, str]
) -> None:
    hadley = _shooter(fx_session, "Hadley, Ike")
    assert (
        fx_admin_client.post(f"/api/admin/shooters/{hadley}/{path}", json=body).status_code == 422
    )


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("rename", {"display_name": "Nobody"}),
        ("status", {"status": "guest"}),
        ("aliases", {"name_key": "nobody"}),
    ],
)
def test_shooter_fix_for_unknown_shooter_is_404(
    fx_admin_client: TestClient, path: str, body: dict[str, str]
) -> None:
    response = fx_admin_client.post(f"/api/admin/shooters/987654/{path}", json=body)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"
