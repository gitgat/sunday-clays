"""GET /api/club/first-rounds (Plan 12 Phase 3 T2): the `first-rounds` chart on /club."""

from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from sunday_clays.api.app import create_app

D1 = date(2025, 8, 31)
D2 = date(2026, 9, 6)
D3 = date(2026, 9, 13)


def test_first_rounds_openapi() -> None:
    spec = create_app().openapi()
    op = spec["paths"]["/api/club/first-rounds"]["get"]
    assert [p["name"] for p in op["parameters"]] == ["from", "to"]
    props = spec["components"]["schemas"]["FirstRoundsOut"]["properties"]
    assert list(props) == ["n", "median", "counts"]


def test_first_rounds_best_score_of_each_first_sunday(seed: Any, viewer_client: TestClient) -> None:
    ann, bob, cat = (seed.shooter(n) for n in ("Oakley, Ann", "Pratt, Bob", "Quinn, Cat"))
    seed.round(D1, ann, 30)
    seed.round(D1, ann, 34)  # best round of Ann's first Sunday
    seed.round(D2, ann, 45)  # not a first round
    seed.round(D2, bob, 22)
    seed.round(D3, cat, 40)
    seed.finish()

    body = viewer_client.get("/api/club/first-rounds").json()

    assert (body["n"], body["median"]) == (3, 34.0)
    assert len(body["counts"]) == 51
    assert [i for i, c in enumerate(body["counts"]) if c] == [22, 34, 40]

    window = viewer_client.get(
        "/api/club/first-rounds", params={"from": "2026-01-01", "to": "2026-09-06"}
    ).json()
    assert (window["n"], [i for i, c in enumerate(window["counts"]) if c]) == (1, [22])


def test_first_rounds_empty(seed: Any, viewer_client: TestClient) -> None:
    seed.finish()
    body = viewer_client.get("/api/club/first-rounds").json()
    assert (body["n"], body["median"], sum(body["counts"]), len(body["counts"])) == (0, None, 0, 51)


def test_first_rounds_matches_new_faces_rule(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/club/first-rounds").json()
    shooters = fx_viewer_client.get("/api/club/summary").json()["n_shooters"]
    assert body["n"] == shooters  # every shooter with a round has exactly one first round
