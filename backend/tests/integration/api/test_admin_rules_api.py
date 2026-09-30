from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.models import Base

AUDIT = Base.metadata.tables["audit_log"]
JOBS = Base.metadata.tables["jobs"]
PROFILES = Base.metadata.tables["shooter_profiles"]
RULES = Base.metadata.tables["rules"]
ROUND_TYPE_RULE = {
    "rule_type": "round_type_override",
    "payload": {"event_date": "2026-09-13", "round_type": "sporting"},
    "note": "stations were all even that week",
}


def _last_action(session: Session) -> str | None:
    return session.scalar(select(AUDIT.c.action).order_by(AUDIT.c.id.desc()).limit(1))


def _job(session: Session, job_id: int) -> tuple[str, str | None, str]:
    row = session.execute(
        select(JOBS.c.kind, JOBS.c.dedupe_key, JOBS.c.status).where(JOBS.c.id == job_id)
    ).one()
    return row.kind, row.dedupe_key, row.status


def _count(session: Session, table_name: str) -> int:
    return int(session.scalar(select(func.count()).select_from(Base.metadata.tables[table_name])))


def _shooter(session: Session, display_name: str) -> int:
    return int(
        session.execute(
            select(PROFILES.c.shooter_id).where(PROFILES.c.display_name == display_name)
        ).scalar_one()
    )


def test_create_rule_lists_it_enqueues_rebuild_and_audits(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    created = fx_admin_client.post("/api/admin/rules", json=ROUND_TYPE_RULE)
    assert created.status_code == 200
    rule_id, job_id = created.json()["rule_id"], created.json()["job_id"]
    newest = fx_admin_client.get("/api/admin/rules").json()[0]
    assert (newest["id"], newest["rule_type"], newest["active"]) == (
        rule_id,
        "round_type_override",
        True,
    )
    assert newest["payload"]["round_type"] == "sporting"
    assert newest["note"] == "stations were all even that week"
    assert _job(fx_session, job_id) == ("rebuild", "rebuild", "queued")
    assert _last_action(fx_session) == "rules.create"


def test_station_reset_takes_a_station_label_such_as_7a(
    fx_admin_client: TestClient,
) -> None:
    created = fx_admin_client.post(
        "/api/admin/rules",
        json={
            "rule_type": "station_reset",
            "payload": {"station": "7A", "effective_date": "2026-09-13", "note": "new trap"},
        },
    )
    assert created.status_code == 200
    newest = fx_admin_client.get("/api/admin/rules").json()[0]
    assert newest["payload"] == {
        "station": "7A",
        "effective_date": "2026-09-13",
        "note": "new trap",
    }


def test_round_type_override_rejects_unknown_round_type(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    before = fx_session.scalar(select(func.count()).select_from(RULES))
    response = fx_admin_client.post(
        "/api/admin/rules",
        json={
            "rule_type": "round_type_override",
            "payload": {"event_date": "2026-09-13", "round_type": "unknown"},
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_rule"
    assert fx_session.scalar(select(func.count()).select_from(RULES)) == before


def test_invalid_payload_is_400_and_creates_nothing(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    before = fx_session.scalar(select(func.count()).select_from(RULES))
    response = fx_admin_client.post(
        "/api/admin/rules", json={"rule_type": "merge_shooter", "payload": {}}
    )
    assert response.status_code == 400
    assert set(response.json()["error"]) == {"code", "message"}
    assert response.json()["error"]["code"] == "invalid_rule"  # Plan 03 Decision 15
    assert fx_session.scalar(select(func.count()).select_from(RULES)) == before


def test_unknown_rule_type_is_422(fx_admin_client: TestClient) -> None:
    response = fx_admin_client.post(
        "/api/admin/rules", json={"rule_type": "delete_everything", "payload": {}}
    )
    assert response.status_code == 422


def test_deactivate_rule_enqueues_rebuild_and_audits(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    jobs_before = _count(fx_session, "jobs")
    created = fx_admin_client.post("/api/admin/rules", json=ROUND_TYPE_RULE).json()
    rule_id = created["rule_id"]
    assert _job(fx_session, created["job_id"]) == ("rebuild", "rebuild", "queued")
    response = fx_admin_client.post(f"/api/admin/rules/{rule_id}/deactivate")
    assert response.status_code == 200
    assert response.json() == {"rule_id": rule_id, "job_id": created["job_id"]}  # coalesced
    assert _job(fx_session, response.json()["job_id"]) == ("rebuild", "rebuild", "queued")
    assert _count(fx_session, "jobs") == jobs_before + 1
    listed = {rule["id"]: rule for rule in fx_admin_client.get("/api/admin/rules").json()}
    assert listed[rule_id]["active"] is False
    assert _last_action(fx_session) == "rules.deactivate"


def test_deactivate_unknown_rule_is_404(fx_admin_client: TestClient) -> None:
    response = fx_admin_client.post("/api/admin/rules/987654/deactivate")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "rule_not_found"


def test_deactivate_inactive_rule_is_409_and_audits_nothing(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    rule_id = fx_admin_client.post("/api/admin/rules", json=ROUND_TYPE_RULE).json()["rule_id"]
    fx_admin_client.post(f"/api/admin/rules/{rule_id}/deactivate")
    audit_before = fx_session.scalar(select(func.count()).select_from(AUDIT))
    response = fx_admin_client.post(f"/api/admin/rules/{rule_id}/deactivate")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "rule_not_active"
    assert fx_session.scalar(select(func.count()).select_from(AUDIT)) == audit_before


def test_deactivation_that_would_close_a_merge_cycle_is_400_and_writes_nothing(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    a, b, c = (
        _shooter(fx_session, name) for name in ("Stroud, Jasper", "Skelton, Jasper", "Hadley, Ike")
    )

    def merge(source: int, target: int) -> int:
        payload = {"source_shooter_id": source, "target_shooter_id": target}
        response = fx_admin_client.post(
            "/api/admin/rules", json={"rule_type": "merge_shooter", "payload": payload}
        )
        assert response.status_code == 200
        return int(response.json()["rule_id"])

    merge(b, a)
    b_to_c = merge(b, c)  # newest rule per source wins, so b -> a is shadowed
    merge(a, b)  # a -> b -> c: no cycle while b -> c is active
    before = {name: _count(fx_session, name) for name in ("rules", "jobs", "audit_log")}
    response = fx_admin_client.post(f"/api/admin/rules/{b_to_c}/deactivate")  # b -> a returns
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "merge_cycle"
    assert {name: _count(fx_session, name) for name in before} == before
    listed = {rule["id"]: rule for rule in fx_admin_client.get("/api/admin/rules").json()}
    assert (listed[b_to_c]["active"], listed[b_to_c]["deactivated_at"]) == (True, None)
    assert _last_action(fx_session) == "rules.create"


def test_hide_round_without_raw_score_stores_the_live_score(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    rounds = Base.metadata.tables["rounds"]
    event_date, name_key, ordinal, score = fx_session.execute(
        select(rounds.c.event_date, rounds.c.name_key, rounds.c.ordinal, rounds.c.score)
        .where(rounds.c.name_key == "hadley ike")
        .order_by(rounds.c.event_date.desc(), rounds.c.ordinal)
        .limit(1)
    ).one()
    payload = {"event_date": event_date.isoformat(), "name_key": name_key, "ordinal": ordinal}
    response = fx_admin_client.post(
        "/api/admin/rules", json={"rule_type": "hide_round", "payload": payload}
    )
    assert response.status_code == 200
    stored = fx_session.scalar(
        select(RULES.c.payload).where(RULES.c.id == response.json()["rule_id"])
    )
    assert stored == {**payload, "raw_score": score}


def test_rule_for_a_missing_round_is_404(fx_admin_client: TestClient, fx_session: Session) -> None:
    before = fx_session.scalar(select(func.count()).select_from(RULES))
    payload = {"event_date": "2026-09-13", "name_key": "hadley ike", "ordinal": 9}
    response = fx_admin_client.post(
        "/api/admin/rules", json={"rule_type": "hide_round", "payload": payload}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "round_not_found"
    assert fx_session.scalar(select(func.count()).select_from(RULES)) == before
