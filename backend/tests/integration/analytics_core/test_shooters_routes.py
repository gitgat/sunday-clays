from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.app import create_app
from sunday_clays.api.routes import _filters

TODAY = date(2026, 9, 27)
# W[0] is today, W[7] seven weeks ago
W = [TODAY - timedelta(days=7 * k) for k in range(8)]


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: TODAY)


def test_shooter_paths_are_the_c8_templates() -> None:
    # C8 fixes `/api/shooters/{id}` (+ /rounds, /rating, /splits); Plan 08 indexes those
    # keys and sends `params: {path: {id}}`.
    paths = create_app().openapi()["paths"]
    for suffix in ("", "/rounds", "/rating", "/splits"):
        op = paths[f"/api/shooters/{{id}}{suffix}"]["get"]
        assert [p["name"] for p in op["parameters"] if p["in"] == "path"] == ["id"]


def test_list_search_and_active_filter(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    for d in W[:5]:
        seed.round(d, ann, 30)
    seed.round(W[0], bob, 25)
    seed.finish()
    seed.analyze()

    everyone = viewer_client.get("/api/shooters").json()
    active = viewer_client.get("/api/shooters", params={"active": "true"}).json()
    inactive = viewer_client.get("/api/shooters", params={"active": "false"}).json()
    search = viewer_client.get("/api/shooters", params={"q": "PRA"}).json()

    assert [s["display_name"] for s in everyone] == ["Oakley, Ann", "Pratt, Bob"]
    assert [s["shooter_id"] for s in active] == [ann]
    assert [s["shooter_id"] for s in inactive] == [bob]
    assert [s["shooter_id"] for s in search] == [bob]
    assert everyone[0]["n_rounds"] == 5
    assert everyone[0]["mu"] is not None


def test_directory_sorts_case_insensitively_then_by_id(
    seed: Any, viewer_client: TestClient
) -> None:
    pratt = seed.shooter("Pratt, Bob")
    cruz = seed.shooter("de la Cruz, Xavier")
    ann = seed.shooter("Oakley, Ann")
    ann_upper = seed.shooter("OAKLEY, ANN")  # casefold tie with ann: shooter_id decides
    for k, sid in enumerate((pratt, cruz, ann, ann_upper)):
        seed.round(W[k], sid, 30)
    seed.finish()

    body = viewer_client.get("/api/shooters").json()

    assert [s["shooter_id"] for s in body] == [cruz, ann, ann_upper, pratt]


def test_detail_stats_odometer_and_pbs(
    seed: Any, viewer_client: TestClient, session: Session
) -> None:
    ann = seed.shooter("Oakley, Ann", status="deceased")
    bob = seed.shooter("Pratt, Bob")
    seed.event(W[2], held=False)
    plan = [
        (W[7], 40, 30),
        (W[6], 38, 45),
        (W[3], 44, 30),
        (W[2], 20, 20),
        (W[1], 44, 20),
        (W[0], 35, 36),
    ]
    ann_round: dict[date, int] = {}
    for d, a, b in plan:
        ann_round[d] = seed.round(d, ann, a)
        seed.round(d, bob, b)
    seed.round(W[0], ann, 12)
    seed.finish()
    seed.analyze()
    session.execute(
        text(
            "INSERT INTO achievements_awarded (shooter_id, code, event_date)"
            " VALUES (:s, 'events:1', :d)"
        ),
        {"s": ann, "d": W[7]},
    )

    body = viewer_client.get(f"/api/shooters/{ann}").json()

    assert (body["status"], body["deceased"], body["left_censored"]) == (
        "deceased",
        True,
        False,
    )
    odo = body["odometer"]
    assert odo["rounds"] == 7
    assert odo["clays_thrown"] == 350
    assert odo["clays_broken"] == 40 + 38 + 44 + 20 + 44 + 35 + 12
    assert odo["hit_pct"] == pytest.approx(233 / 350)
    assert (odo["events"], odo["years_active"]) == (6, 1)
    # held events W7, W6, W3, W1, W0 (W2 not held, skipped): attended all five
    assert (odo["current_streak"], odo["longest_streak"]) == (5, 5)
    assert odo["favorite_month"] == 9  # Aug has 2 dates (W7, W6); Sep has 4
    assert odo["trophies"] == 1
    stats = body["stats"]
    assert (stats["n_rounds"], stats["best_score"], stats["wins"]) == (7, 44, 4)
    assert stats["podiums"] == 6
    assert body["pbs"][0] == {
        "scope": "overall",
        "key": "all",
        "score": 44,
        "event_date": W[3].isoformat(),
        "round_id": ann_round[W[3]],  # first reached at W[3], not the later 44 at W[1]
    }
    assert [(p["scope"], p["key"], p["score"]) for p in body["pbs"]] == [
        ("overall", "all", 44),
        ("year", "2026", 44),
    ]
    assert body["current_mu"] is not None


def test_unknown_shooter_is_404(viewer_client: TestClient) -> None:
    for path in ("", "/rounds", "/rating", "/splits?by=year"):
        r = viewer_client.get(f"/api/shooters/999999{path}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "shooter_not_found"


def test_round_type_filter_restricts_rounds(seed: Any, viewer_client: TestClient) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    seed.event(W[2], round_type="sporting")
    seed.event(W[1], round_type="super_sporting")
    seed.round(W[2], ann, 40)
    seed.round(W[1], ann, 30)
    seed.round(W[2], bob, 25)
    seed.finish()
    seed.analyze()
    params = {"round_type": "super_sporting"}

    detail = viewer_client.get(f"/api/shooters/{ann}", params=params).json()
    rounds = viewer_client.get(f"/api/shooters/{ann}/rounds", params=params).json()
    by_year = viewer_client.get(
        f"/api/shooters/{ann}/splits", params={**params, "by": "year"}
    ).json()

    assert detail["stats"]["n_rounds"] == 1
    assert detail["stats"]["best_score"] == 30
    assert detail["odometer"]["rounds"] == 2  # lifetime odometer ignores the filter
    assert [r["score"] for r in rounds] == [30]
    assert [(s["key"], s["n_rounds"]) for s in by_year] == [("2026", 1)]
    none = viewer_client.get(f"/api/shooters/{bob}", params=params).json()  # only sporting rounds
    assert (none["stats"]["n_rounds"], none["stats"]["avg_score"], none["pbs"]) == (
        0,
        None,
        [],
    )
    assert none["stats"]["best_score"] is None


def test_rounds_list_in_date_order(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(W[0], ann, 30)
    seed.round(W[1], ann, 41)
    seed.round(W[1], ann, 35)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(f"/api/shooters/{ann}/rounds").json()

    assert [(r["event_date"], r["ordinal"], r["score"]) for r in body] == [
        (W[1].isoformat(), 1, 41),
        (W[1].isoformat(), 2, 35),
        (W[0].isoformat(), 1, 30),
    ]
    assert [r["is_best_round"] for r in body] == [True, False, True]
    assert body[0]["round_type"] == "sporting"


def test_rating_series_band_and_peak(seed: Any, viewer_client: TestClient) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    for d, a in ((W[3], 30), (W[2], 45), (W[1], 20)):
        seed.round(d, ann, a)
        seed.round(d, bob, 30)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(f"/api/shooters/{ann}/rating").json()

    points = body["points"]
    assert [p["event_date"] for p in points] == [
        W[3].isoformat(),
        W[2].isoformat(),
        W[1].isoformat(),
    ]
    for p in points:
        assert p["lo"] == pytest.approx(p["mu"] - 1.96 * p["var"] ** 0.5)
        assert p["hi"] == pytest.approx(p["mu"] + 1.96 * p["var"] ** 0.5)
    assert body["peak_date"] == W[2].isoformat()
    assert body["peak_mu"] == max(p["mu"] for p in points)
    assert body["current_mu"] == points[-1]["mu"]


def test_splits_by_gauge_includes_unspecified(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(W[2], ann, 40, gauge_class="Sub-Gauge")
    seed.round(W[1], ann, 30)
    seed.round(W[0], ann, 34)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(f"/api/shooters/{ann}/splits", params={"by": "gauge"}).json()

    assert [(s["key"], s["n_rounds"], s["best"]) for s in body] == [
        ("Sub-Gauge", 1, 40),
        ("unspecified", 2, 34),
    ]
    assert body[1]["avg"] == 32.0


def test_splits_by_weather_band_use_no_data_sentinel(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(W[2], ann, 40)
    seed.round(W[1], ann, 30)
    seed.round(W[0], ann, 20)
    seed.weather(W[2], temp_f=38.0, gust_mph=25.0, precip_in=0.3)
    seed.weather(W[1], temp_f=72.0, gust_mph=4.0, precip_in=0.0)
    seed.finish()
    seed.analyze()

    def keys(by: str) -> list[tuple[str, int]]:
        body = viewer_client.get(f"/api/shooters/{ann}/splits", params={"by": by}).json()
        return [(s["key"], s["best"]) for s in body]

    assert keys("temp_band") == [("<40", 40), ("70-85", 30), ("no_data", 20)]
    assert keys("wind_band") == [("<10", 30), ("20+", 40), ("no_data", 20)]
    assert keys("precip_band") == [("dry", 30), ("wet", 40), ("no_data", 20)]


def test_splits_by_calendar_dims(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    for d, s in (
        (date(2025, 12, 7), 30),
        (date(2026, 1, 4), 32),
        (date(2026, 4, 5), 34),
        (date(2026, 7, 5), 36),
        (date(2026, 9, 6), 38),
    ):
        seed.round(d, ann, s)
    seed.finish()
    seed.analyze()

    def keys(by: str) -> list[str]:
        body = viewer_client.get(f"/api/shooters/{ann}/splits", params={"by": by}).json()
        return [s["key"] for s in body]

    assert keys("season") == ["winter", "spring", "summer", "fall"]
    assert keys("month") == ["2025-12", "2026-01", "2026-04", "2026-07", "2026-09"]
    assert keys("year") == ["2025", "2026"]
    assert keys("round_type") == ["sporting"]
    season = viewer_client.get(f"/api/shooters/{ann}/splits", params={"by": "season"}).json()
    assert (season[0]["n_rounds"], season[0]["avg"]) == (2, 31.0)
    assert viewer_client.get(f"/api/shooters/{ann}/splits?by=weekday").status_code == 422


def test_empty_live_tables_give_an_empty_directory(viewer_client: TestClient) -> None:
    assert viewer_client.get("/api/shooters").json() == []
    assert viewer_client.get("/api/shooters", params={"active": "true", "q": "x"}).json() == []


def test_unanalyzed_shooter_gets_nulls_not_500(seed: Any, viewer_client: TestClient) -> None:
    # Live tables rebuilt but s10/s30 not run yet: no metrics, no rating_history rows.
    ann = seed.shooter("Oakley, Ann", left_censored=True)
    seed.round(W[1], ann, 30, gauge_class="Sub-Gauge")
    seed.round(W[0], ann, 36)
    seed.finish()

    (summary,) = viewer_client.get("/api/shooters").json()
    detail = viewer_client.get(f"/api/shooters/{ann}").json()
    rating = viewer_client.get(f"/api/shooters/{ann}/rating").json()
    rounds = viewer_client.get(f"/api/shooters/{ann}/rounds").json()
    sporting = viewer_client.get(
        f"/api/shooters/{ann}/splits", params={"by": "gauge", "round_type": "super_sporting"}
    )

    assert (summary["mu"], summary["active"], summary["n_events"]) == (None, False, 2)
    assert (detail["current_mu"], detail["current_var"], detail["left_censored"]) == (
        None,
        None,
        True,
    )
    stats = detail["stats"]
    assert (stats["wins"], stats["podiums"], stats["avg_percentile"]) == (0, 0, None)
    assert (stats["avg_adjusted"], stats["median_score"], stats["n_events"]) == (None, 33.0, 2)
    assert (detail["odometer"]["current_streak"], detail["odometer"]["longest_streak"]) == (2, 2)
    assert detail["odometer"]["trophies"] == 0
    assert rating == {
        "shooter_id": ann,
        "points": [],
        "current_mu": None,
        "peak_mu": None,
        "peak_date": None,
    }
    assert [(r["gauge_class"], r["is_best_round"], r["event_rank"]) for r in rounds] == [
        ("Sub-Gauge", False, None),
        (None, False, None),
    ]
    assert {r["mu_before"] for r in rounds} == {None}
    assert (sporting.status_code, sporting.json()) == (200, [])


def test_splits_by_round_type_use_the_fixed_order(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.event(W[3], round_type="super_sporting")
    seed.event(W[2], round_type="sporting")
    for d, s in ((W[3], 40), (W[2], 30), (W[1], 20), (W[0], 22)):
        seed.round(d, ann, s)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(f"/api/shooters/{ann}/splits", params={"by": "round_type"}).json()

    assert [(s["key"], s["n_rounds"], s["best"], s["median"]) for s in body] == [
        # W[1], W[0] are seeded without a round type: they default to sporting
        ("sporting", 3, 30, 22.0),
        ("super_sporting", 1, 40, 40.0),
    ]
    assert all(isinstance(s["avg_adjusted"], float) for s in body)


def test_committed_fixture_shooter(fx_viewer_client: TestClient) -> None:
    found = fx_viewer_client.get("/api/shooters", params={"q": "ackerly, alton"}).json()
    assert [s["display_name"] for s in found] == ["Ackerly, Alton"]
    body = fx_viewer_client.get(f"/api/shooters/{found[0]['shooter_id']}").json()

    odo = body["odometer"]
    assert (odo["rounds"], odo["clays_broken"], odo["events"], odo["years_active"]) == (
        170,
        7313,
        167,
        7,
    )
    assert (odo["current_streak"], odo["longest_streak"]) == (1, 12)
    assert odo["favorite_month"] == 3  # March and November tie at 18; lowest month wins
    assert body["pbs"][0]["score"] == 49
    assert body["pbs"][0]["event_date"] == "2021-03-28"
    active = fx_viewer_client.get("/api/shooters", params={"active": "true"}).json()
    assert len(active) == 83
