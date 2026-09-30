from collections.abc import Mapping, Set
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.api.routes import admin_ops
from sunday_clays.models import Base

APP_STATE = Base.metadata.tables["app_state"]
DATA_ISSUES = Base.metadata.tables["data_issues"]
JOBS = Base.metadata.tables["jobs"]


def test_data_issues_list_the_fixture_issues(fx_admin_client: TestClient) -> None:
    issues = fx_admin_client.get("/api/admin/data-issues").json()
    found = {(issue["code"], issue["event_date"]) for issue in issues}
    assert ("station_score_mismatch", "2026-09-13") in found
    assert ("incomplete_results", "2024-11-10") in found
    assert [issue["code"] for issue in issues] == sorted(issue["code"] for issue in issues)


def test_data_issues_order_by_code_then_newest_date_nulls_last(
    admin_client: TestClient, session: Session
) -> None:
    rows = [
        ("b_code", None, "b undated"),
        ("b_code", date(2026, 1, 4), "b older"),
        ("a_code", date(2025, 6, 1), "a only"),
        ("b_code", date(2026, 2, 1), "b newer"),
    ]
    for code, event_date, message in rows:
        session.execute(
            insert(DATA_ISSUES).values(
                code=code, severity="warning", event_date=event_date, message=message
            )
        )
    issues = admin_client.get("/api/admin/data-issues").json()
    assert [issue["message"] for issue in issues] == ["a only", "b newer", "b older", "b undated"]
    assert issues[0]["details"] == {}
    assert issues[3]["event_date"] is None


def test_possible_duplicates_on_the_fixture(fx_admin_client: TestClient) -> None:
    pairs = fx_admin_client.get("/api/admin/possible-duplicates").json()
    keys = [(pair["a"]["name_key"], pair["b"]["name_key"]) for pair in pairs]
    assert len(pairs) == 25  # the Plan 02 T5 golden: 8 multi-token + 17 first-name-only hints
    assert ("preutt clay", "pruett clay") in keys
    assert ("stroud jasper", "skelton jasper") not in keys
    assert keys == sorted(keys)
    preutt = pairs[keys.index(("preutt clay", "pruett clay"))]
    assert (preutt["a"]["display_name"], preutt["b"]["display_name"]) == (
        "Preutt, Clay",
        "Pruett, Clay",
    )
    assert preutt["a"]["n_rounds"] == 1
    assert preutt["a"]["shooter_id"] != preutt["b"]["shooter_id"]


def test_audit_log_is_newest_first_and_paged(admin_client: TestClient) -> None:
    admin_client.post("/api/admin/recompute")
    admin_client.post("/api/admin/recompute", json={"recalibrate": True})
    newest = admin_client.get("/api/admin/audit", params={"limit": 1}).json()
    page = admin_client.get("/api/admin/audit", params={"limit": 2, "offset": 1}).json()
    assert [entry["action"] for entry in newest] == ["ops.recompute"]
    assert newest[0]["details"]["recalibrate"] is True
    assert [entry["action"] for entry in page] == ["ops.recompute", "auth.login"]
    assert page[0]["details"]["recalibrate"] is False


def test_audit_limit_is_bounded(admin_client: TestClient) -> None:
    assert admin_client.get("/api/admin/audit", params={"limit": 0}).status_code == 422
    assert admin_client.get("/api/admin/audit", params={"limit": 1001}).status_code == 422


def test_recompute_without_body_enqueues_plain_recompute(
    admin_client: TestClient, session: Session
) -> None:
    session.execute(insert(APP_STATE).values(key="skill_params", value={"obs_var": 14}))
    job_id = admin_client.post("/api/admin/recompute").json()["job_id"]
    kind, payload = session.execute(
        select(JOBS.c.kind, JOBS.c.payload).where(JOBS.c.id == job_id)
    ).one()
    assert kind == "recompute"
    assert not (payload or {}).get("recalibrate")
    assert session.scalar(select(APP_STATE.c.key).where(APP_STATE.c.key == "skill_params"))


def test_recompute_job_is_coalesced_under_the_recompute_key(
    admin_client: TestClient, session: Session
) -> None:
    job_id = admin_client.post("/api/admin/recompute", json={}).json()["job_id"]
    job = session.execute(
        select(JOBS.c.kind, JOBS.c.dedupe_key, JOBS.c.payload).where(JOBS.c.id == job_id)
    ).one()
    assert tuple(job) == ("recompute", "recompute", {})


def test_recalibrate_clears_skill_params_and_flags_the_job(
    admin_client: TestClient, session: Session
) -> None:
    session.execute(insert(APP_STATE).values(key="skill_params", value={"obs_var": 14}))
    response = admin_client.post("/api/admin/recompute", json={"recalibrate": True})
    payload = session.scalar(select(JOBS.c.payload).where(JOBS.c.id == response.json()["job_id"]))
    assert payload == {"recalibrate": True}
    assert session.scalar(select(APP_STATE.c.key).where(APP_STATE.c.key == "skill_params")) is None


def test_recalibrate_still_applies_when_a_plain_recompute_is_queued(
    admin_client: TestClient, session: Session
) -> None:
    session.execute(insert(APP_STATE).values(key="skill_params", value={"obs_var": 14}))
    plain = admin_client.post("/api/admin/recompute").json()["job_id"]
    coalesced = admin_client.post("/api/admin/recompute", json={"recalibrate": True}).json()
    assert coalesced["job_id"] == plain
    assert session.scalar(select(APP_STATE.c.key).where(APP_STATE.c.key == "skill_params")) is None


def test_possible_duplicates_second_call_does_not_recompute(
    fx_admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    real = admin_ops.duplicate_key_pairs

    def counting(
        key_dates: Mapping[str, Set[date]], key_shooter: Mapping[str, int]
    ) -> list[tuple[str, str]]:
        calls.append(1)
        return real(key_dates, key_shooter)

    monkeypatch.setattr(admin_ops, "duplicate_key_pairs", counting)
    first = fx_admin_client.get("/api/admin/possible-duplicates").json()
    second = fx_admin_client.get("/api/admin/possible-duplicates").json()
    assert first == second
    assert first
    assert calls == [1]
