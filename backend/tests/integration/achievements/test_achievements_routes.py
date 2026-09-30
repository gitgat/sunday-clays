"""Achievement read endpoints over the fx world with toy trophies (Plan 10 T1)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text

from sunday_clays.analytics.achievements import registry
from sunday_clays.analytics.achievements.context import AchContext
from sunday_clays.analytics.achievements.registry import Achievement, Award, Category
from sunday_clays.analytics.steps.s50_achievements import STEP
from sunday_clays.api.app import create_app


@pytest.fixture
def awarded(fx_session, toy_trophies) -> None:
    STEP.run(fx_session)


def rows(session: Any, sql: str, **params: Any) -> list[Any]:
    return list(session.execute(text(sql), params).all())


def test_list_achievements_counts_holders_and_rarity(fx_viewer_client, awarded):
    body = fx_viewer_client.get("/api/achievements").json()
    assert body["n_shooters"] == 332
    by_code = {t["code"]: t for t in body["trophies"]}
    assert list(by_code) == ["toy_events:1", "toy_events:2", "toy_perfect"]
    tier = by_code["toy_events:2"]
    assert (
        tier["family"],
        tier["metal"],
        tier["level"],
        tier["label"],
        tier["holders"],
        tier["rarity_pct"],
    ) == (
        "toy_events",
        "silver",
        2,
        "10 events",
        107,
        32.2,
    )
    assert by_code["toy_perfect"]["metal"] is None
    assert by_code["toy_perfect"]["holders"] == 4
    assert body["recent_total"] > 20
    assert len(body["recent"]) == min(body["recent_total"], 200)
    assert body["recent"][0]["event_date"] == max(t["last_awarded"] for t in body["trophies"])


def test_achievement_detail_lists_holders_with_first_dates(fx_viewer_client, fx_session, awarded):
    body = fx_viewer_client.get("/api/achievements/toy_perfect").json()
    expected = {
        int(sid): first.isoformat()
        for sid, first in rows(
            fx_session,
            "SELECT shooter_id, min(event_date) FROM rounds WHERE score = 50 GROUP BY shooter_id",
        )
    }
    assert {h["shooter_id"]: h["first_date"] for h in body["holders"]} == expected
    assert all(h["count"] == 1 and h["dates"] == [h["first_date"]] for h in body["holders"])
    assert body["trophy"]["code"] == "toy_perfect"


def test_tier_code_with_colon_resolves(fx_viewer_client, awarded):
    response = fx_viewer_client.get("/api/achievements/toy_events:2")
    assert response.status_code == 200
    assert len(response.json()["holders"]) == 107


def test_unknown_achievement_is_404(fx_viewer_client, awarded):
    response = fx_viewer_client.get("/api/achievements/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "achievement_not_found"


def test_shooter_achievements_report_earned_progress_and_locked(
    fx_viewer_client, fx_session, awarded
):
    [(shooter_id, first)] = rows(
        fx_session,
        "SELECT shooter_id, min(event_date) FROM rounds "
        "WHERE shooter_id NOT IN (SELECT shooter_id FROM rounds WHERE score = 50) "
        "GROUP BY shooter_id HAVING count(DISTINCT event_date) = 3 ORDER BY shooter_id LIMIT 1",
    )
    body = fx_viewer_client.get(f"/api/shooters/{shooter_id}/achievements").json()
    assert [(e["code"], e["first_date"], e["count"]) for e in body["earned"]] == [
        ("toy_events:1", first.isoformat(), 1)
    ]
    [p] = body["progress"]
    assert (
        p["value"],
        p["earned_level"],
        p["next_level"],
        p["next_threshold"],
        p["next_label"],
    ) == (
        3.0,
        1,
        2,
        10.0,
        "10 events",
    )
    assert p["fraction"] == pytest.approx(0.3)
    assert [locked["code"] for locked in body["locked"]] == ["toy_perfect"]


def test_most_frequent_shooter_has_maxed_progress(fx_viewer_client, fx_session, awarded):
    [(shooter_id, n_events)] = rows(
        fx_session,
        "SELECT shooter_id, count(DISTINCT event_date) AS n FROM rounds GROUP BY shooter_id "
        "ORDER BY n DESC, shooter_id LIMIT 1",
    )
    [p] = fx_viewer_client.get(f"/api/shooters/{shooter_id}/achievements").json()["progress"]
    assert (p["value"], p["earned_level"], p["next_level"], p["fraction"]) == (
        float(n_events),
        2,
        None,
        1.0,
    )


def test_unknown_shooter_is_404(fx_viewer_client, awarded):
    response = fx_viewer_client.get("/api/shooters/999999/achievements")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"


def test_event_achievements_list_that_days_awards(fx_viewer_client, fx_session, awarded):
    [(day,)] = rows(fx_session, "SELECT max(event_date) FROM achievements_awarded")
    [(expected,)] = rows(
        fx_session, "SELECT count(*) FROM achievements_awarded WHERE event_date = :d", d=day
    )
    body = fx_viewer_client.get(f"/api/events/{day.isoformat()}/achievements").json()
    assert body["event_date"] == day.isoformat()
    assert len(body["awards"]) == expected > 0
    assert all(a["event_date"] == day.isoformat() for a in body["awards"])


def test_event_achievements_unknown_date_is_404(fx_viewer_client, awarded):
    response = fx_viewer_client.get("/api/events/2026-09-14/achievements")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"


# --- Beyond the brief -----------------------------------------------------------------------------

C8_PATHS = {
    "/api/achievements": ([], "AchievementsOut"),
    "/api/achievements/{code}": (["code"], "AchievementDetailOut"),
    "/api/shooters/{id}/achievements": (["id"], "ShooterAchievementsOut"),
    "/api/events/{date}/achievements": (["date"], "EventAchievementsOut"),
}


def test_achievement_paths_are_the_c8_templates():
    """D17: C8 path templates and parameter names are kept literally; responses are *Out models."""
    spec = create_app().openapi()
    for path, (params, model) in C8_PATHS.items():
        op = spec["paths"][path]["get"]
        assert [p["name"] for p in op.get("parameters", []) if p["in"] == "path"] == params
        assert op["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": f"#/components/schemas/{model}"
        }
    assert "ProgressOut" in spec["components"]["schemas"]


def _forty_eight_plus(ctx: AchContext) -> Iterator[Award]:
    high = ctx.rounds[ctx.rounds["score"] >= 48]
    for sid, ts, rid in zip(high["shooter_id"], high["event_ts"], high["round_id"], strict=True):
        yield Award(int(sid), "toy_48", ts.date(), int(rid), {})


def test_repeatable_trophy_holders_count_every_day(fx_viewer_client, fx_session, toy_trophies):
    registry.register(
        Achievement(
            code="toy_48",
            name="Toy 48",
            description="Shot 48+.",
            category=Category.SCORING,
            art_key="toy_48",
            evaluate=_forty_eight_plus,
            repeatable=True,
        )
    )
    STEP.run(fx_session)
    body = fx_viewer_client.get("/api/achievements/toy_48").json()
    expected = rows(
        fx_session,
        "SELECT r.shooter_id, array_agg(DISTINCT r.event_date ORDER BY r.event_date) AS dates "
        "FROM rounds r JOIN shooter_profiles p ON p.shooter_id = r.shooter_id WHERE r.score >= 48 "
        "GROUP BY r.shooter_id, p.display_name ORDER BY min(r.event_date), p.display_name, "
        "r.shooter_id",
    )
    got = [(h["shooter_id"], h["count"], h["dates"], h["first_date"]) for h in body["holders"]]
    assert got == [
        (sid, len(dates), [d.isoformat() for d in dates], dates[0].isoformat())
        for sid, dates in expected
    ]
    assert max(h["count"] for h in body["holders"]) > 1
    assert body["trophy"]["repeatable"] is True
    assert body["trophy"]["holders"] == len(expected)


def test_awards_for_unregistered_codes_are_ignored(fx_viewer_client, fx_session, awarded):
    """A row left by a trophy removed from the code never breaks or leaks into a response."""
    [(day,)] = rows(fx_session, "SELECT max(event_date) FROM achievements_awarded")
    [(shooter_id,)] = rows(
        fx_session,
        "SELECT min(shooter_id) FROM rounds WHERE event_date = :d",
        d=day,
    )
    fx_session.execute(
        text(
            "INSERT INTO achievements_awarded (shooter_id, code, event_date, round_id, details) "
            "VALUES (:s, 'retired_code', :d, NULL, CAST('{}' AS jsonb))"
        ),
        {"s": shooter_id, "d": day},
    )
    listing = fx_viewer_client.get("/api/achievements").json()
    assert "retired_code" not in {a["code"] for a in listing["recent"]}
    assert "retired_code" not in {t["code"] for t in listing["trophies"]}
    event = fx_viewer_client.get(f"/api/events/{day.isoformat()}/achievements").json()
    assert "retired_code" not in {a["code"] for a in event["awards"]}
    assert len(event["awards"]) > 0
    shooter = fx_viewer_client.get(f"/api/shooters/{shooter_id}/achievements").json()
    assert "retired_code" not in {e["code"] for e in shooter["earned"]}
    assert "toy_events:1" in {e["code"] for e in shooter["earned"]}
    assert fx_viewer_client.get("/api/achievements/retired_code").status_code == 404


def test_empty_catalog_lists_no_trophies(fx_viewer_client, fx_session, isolated_registry):
    STEP.run(fx_session)
    body = fx_viewer_client.get("/api/achievements").json()
    assert body == {"n_shooters": 332, "trophies": [], "recent": [], "recent_total": 0}
    [(shooter_id,)] = rows(fx_session, "SELECT min(shooter_id) FROM rounds")
    shooter = fx_viewer_client.get(f"/api/shooters/{shooter_id}/achievements").json()
    assert (shooter["earned"], shooter["progress"], shooter["locked"]) == ([], [], [])


def test_award_rows_carry_names_metals_and_details(fx_viewer_client, fx_session, awarded):
    [(shooter_id, day, display_name)] = rows(
        fx_session,
        "SELECT a.shooter_id, a.event_date, p.display_name FROM achievements_awarded a "
        "JOIN shooter_profiles p ON p.shooter_id = a.shooter_id "
        "WHERE a.code = 'toy_events:2' ORDER BY a.event_date, a.shooter_id LIMIT 1",
    )
    body = fx_viewer_client.get(f"/api/events/{day.isoformat()}/achievements").json()
    [award] = [
        a for a in body["awards"] if a["shooter_id"] == shooter_id and a["code"] == "toy_events:2"
    ]
    assert award == {
        "shooter_id": shooter_id,
        "display_name": display_name,
        "code": "toy_events:2",
        "family": "toy_events",
        "name": "Toy Events",
        "label": "10 events",
        "metal": "silver",
        "art_key": "toy_events",
        "event_date": day.isoformat(),
        "round_id": None,
        "details": {"threshold": 10.0, "value": 10.0},
    }


def test_event_awards_break_display_name_ties_by_shooter(
    fx_viewer_client, fx_session, toy_trophies
):
    """display_name is not unique: same-named shooters with the same trophy come back by id."""
    [(day,)] = rows(fx_session, "SELECT max(event_date) FROM events")
    shooter_ids = [
        sid
        for (sid,) in rows(
            fx_session, "SELECT shooter_id FROM shooter_profiles ORDER BY shooter_id LIMIT 5"
        )
    ]
    fx_session.execute(text("DELETE FROM achievements_awarded"))
    # Rows written in the reverse of the expected order, so a name/code-only sort would return
    # them in heap order (the join follows shooter_profiles' heap order) and not by id.
    for shooter_id in reversed(shooter_ids):
        fx_session.execute(
            text("UPDATE shooter_profiles SET display_name = 'Pat Doe' WHERE shooter_id = :s"),
            {"s": shooter_id},
        )
        fx_session.execute(
            text(
                "INSERT INTO achievements_awarded (shooter_id, code, event_date, details) "
                "VALUES (:s, 'toy_perfect', :d, CAST('{}' AS jsonb))"
            ),
            {"s": shooter_id, "d": day},
        )
    body = fx_viewer_client.get(f"/api/events/{day.isoformat()}/achievements").json()
    assert [(a["display_name"], a["shooter_id"]) for a in body["awards"]] == [
        ("Pat Doe", shooter_id) for shooter_id in shooter_ids
    ]
