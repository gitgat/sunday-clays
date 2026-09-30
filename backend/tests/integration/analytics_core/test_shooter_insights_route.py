from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.app import create_app
from sunday_clays.api.routes import _filters

TODAY = date(2026, 9, 27)

# The *Out field sets (D23: Plan 08 T2a's TypeScript types are generated from them).
INSIGHTS_FIELDS = {
    "shooter_id",
    "as_of",
    "n_rounds",
    "floor",
    "ceiling",
    "recent_n",
    "bad_day_rate",
    "form",
    "form_label",
    "wins",
    "podiums",
    "avg_percentile",
    "peak_mu",
    "peak_date",
    "learning_curve",
    "rust",
    "milestone",
}
LEARNING_POINT_FIELDS = {"k", "value", "club_median", "n_club"}
RUST_FIELDS = {"effect", "n", "club_effect"}
MILESTONE_FIELDS = {"next_events", "events_to_go", "weekly_rate", "projected_date"}


def test_insights_path_is_the_c8_template() -> None:
    op = create_app().openapi()["paths"]["/api/shooters/{id}/insights"]["get"]
    assert [p["name"] for p in op["parameters"] if p["in"] == "path"] == ["id"]


def test_insights_response_schema_pins_every_field() -> None:
    spec = create_app().openapi()
    op = spec["paths"]["/api/shooters/{id}/insights"]["get"]
    assert op["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ShooterInsightsOut"
    }
    schemas = spec["components"]["schemas"]
    for name, expected in {
        "ShooterInsightsOut": INSIGHTS_FIELDS,
        "LearningPointOut": LEARNING_POINT_FIELDS,
        "RustOut": RUST_FIELDS,
        "MilestoneOut": MILESTONE_FIELDS,
    }.items():
        # every field is always present in the body (nullable, never omitted)
        assert set(schemas[name]["properties"]) == expected, name
        assert set(schemas[name]["required"]) == expected, name
    props = schemas["ShooterInsightsOut"]["properties"]
    assert props["learning_curve"]["items"] == {"$ref": "#/components/schemas/LearningPointOut"}
    assert props["rust"] == {"$ref": "#/components/schemas/RustOut"}
    assert props["milestone"] == {"$ref": "#/components/schemas/MilestoneOut"}
    assert props["form_label"]["anyOf"] == [
        {"type": "string", "enum": ["hot", "cold", "steady"]},
        {"type": "null"},
    ]


def test_insights_as_of_defaults_to_today_and_slices(
    seed: Any, viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: TODAY)
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    for k in range(6):
        d = TODAY - timedelta(days=7 * k)
        seed.round(d, ann, 30 + k)
        seed.round(d, bob, 29)
    seed.finish()
    seed.analyze()

    today = viewer_client.get(f"/api/shooters/{ann}/insights").json()
    earlier = viewer_client.get(
        f"/api/shooters/{ann}/insights",
        params={"as_of": (TODAY - timedelta(days=14)).isoformat()},
    ).json()

    assert today["as_of"] == TODAY.isoformat()
    assert (today["n_rounds"], today["wins"], today["podiums"]) == (6, 6, 6)
    assert today["milestone"]["next_events"] == 10
    assert len(today["learning_curve"]) == 6
    assert today["form_label"] in {"hot", "cold", "steady"}
    assert today["peak_mu"] is not None
    assert (earlier["n_rounds"], len(earlier["learning_curve"])) == (4, 4)


def test_insights_before_first_round_is_empty_not_500(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(TODAY, ann, 30)
    seed.finish()
    seed.analyze()

    r = viewer_client.get(
        f"/api/shooters/{ann}/insights",
        params={"as_of": (TODAY - timedelta(days=1)).isoformat()},
    )

    assert r.status_code == 200
    body = r.json()
    assert set(body) == INSIGHTS_FIELDS
    assert (body["shooter_id"], body["as_of"]) == (ann, (TODAY - timedelta(days=1)).isoformat())
    assert (body["n_rounds"], body["recent_n"], body["wins"], body["podiums"]) == (0, 0, 0, 0)
    assert body["learning_curve"] == []
    assert [body[k] for k in ("floor", "ceiling", "bad_day_rate", "form", "form_label")] == [
        None
    ] * 5
    assert [body[k] for k in ("avg_percentile", "peak_mu", "peak_date")] == [None] * 3
    assert body["rust"] == {"effect": None, "n": 0, "club_effect": None}
    assert body["milestone"] == {
        "next_events": 1,
        "events_to_go": 1,
        "weekly_rate": 0.0,
        "projected_date": None,
    }


def test_insights_unknown_shooter_is_404(viewer_client: TestClient) -> None:
    r = viewer_client.get("/api/shooters/999999/insights")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "shooter_not_found"


def test_insights_on_committed_fixtures(fx_session: Session, fx_viewer_client: TestClient) -> None:
    shooter_id = fx_session.execute(
        text("SELECT shooter_id FROM shooter_profiles WHERE display_name = :n"),
        {"n": "Ackerly, Alton"},
    ).scalar_one()
    body = fx_viewer_client.get(
        f"/api/shooters/{shooter_id}/insights", params={"as_of": "2026-09-27"}
    ).json()

    # the full response shape, every nested object included
    assert set(body) == INSIGHTS_FIELDS
    assert set(body["rust"]) == RUST_FIELDS
    assert set(body["milestone"]) == MILESTONE_FIELDS
    assert {frozenset(p) for p in body["learning_curve"]} == {frozenset(LEARNING_POINT_FIELDS)}
    assert (body["shooter_id"], body["as_of"]) == (shooter_id, "2026-09-27")

    assert body["n_rounds"] == 170
    assert (body["milestone"]["next_events"], body["milestone"]["events_to_go"]) == (
        200,
        33,
    )
    assert body["recent_n"] == 20
    assert body["floor"] <= body["ceiling"]
    assert body["rust"]["club_effect"] is not None

    # Goldens computed independently from scores_2026-09-27.xlsx ("ALL SCORE DETAIL" and
    # "Attendance History", not through the app): his last 20 rounds run 2025-12-07 ..
    # 2026-09-27 (no multi-round day at the cut); per-date best rounds give 62 wins and 111
    # podiums on 167 dates (none of them 2024-11-10, the one non-held date), a mean
    # percentile of 0.868963592 (float4 in round_metrics); 11 of his dates fall in the 26
    # weeks to 2026-09-27, so 33 to go takes 78 weeks; 23 dates follow a >= 28-day gap and
    # hold 24 rounds; his first three events (2020-01-05/19/26) score
    # 39, 36, 39 against day medians 33.5, 34, 32.
    assert (body["floor"], body["ceiling"]) == (pytest.approx(36.9), pytest.approx(46.1))
    assert (body["wins"], body["podiums"]) == (62, 111)
    assert body["avg_percentile"] == pytest.approx(0.868963592, rel=1e-6)
    assert body["milestone"]["weekly_rate"] == pytest.approx(11 / 26)
    assert body["milestone"]["projected_date"] == "2028-03-26"
    assert body["rust"]["n"] == 24
    curve = body["learning_curve"]
    assert len(curve) == 167
    assert [p["value"] for p in curve[:3]] == [5.5, 2.0, 7.0]
    assert [p["k"] for p in curve] == list(range(1, 168))
    assert curve[0]["club_median"] is not None
    assert curve[0]["n_club"] > 0
    assert body["peak_mu"] is not None
    assert body["peak_date"] is not None
    assert body["peak_date"] <= "2026-09-27"
