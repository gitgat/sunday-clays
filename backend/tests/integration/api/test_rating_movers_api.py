"""GET /api/leaderboards/movers (Plan 12 Phase 4 T1): the `lb-movers` chart, rating climbers."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from sunday_clays.analytics.leaderboards import LeaderboardRow
from sunday_clays.api.routes.leaderboards import rating_climbers


def _row(rank: int, sid: int, name: str, value: float) -> LeaderboardRow:
    return LeaderboardRow(
        rank=rank, shooter_id=sid, display_name=name, status="member", value=value, n_rounds=9
    )


def test_rating_climbers_keep_the_gain_and_never_a_rank() -> None:
    rows = [_row(1, 4, "D", 5.26), _row(2, 5, "E", 2.0)]
    climbers = rating_climbers(rows)
    assert [(c.shooter_id, c.display_name, c.gain, c.n_rounds) for c in climbers] == [
        (4, "D", 5.26, 9),
        (5, "E", 2.0, 9),
    ]
    assert set(type(climbers[0]).model_fields) == {"shooter_id", "display_name", "gain", "n_rounds"}


def _get(client: TestClient, path: str, **params: str) -> dict[str, Any]:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_movers_are_the_rating_gain_board(fx_viewer_client: TestClient) -> None:
    window = {"period": "rolling_12", "as_of": "2026-09-27"}
    body = _get(fx_viewer_client, "/api/leaderboards/movers", **window)
    board = _get(fx_viewer_client, "/api/leaderboards", metric="rating_gain", **window)
    assert body["rows"]  # the fixture world has climbers
    assert (body["as_of"], body["start"], body["end"]) == (
        "2026-09-27",
        board["start"],
        "2026-09-27",
    )
    assert [(r["shooter_id"], r["display_name"], r["n_rounds"]) for r in body["rows"]] == [
        (r["shooter_id"], r["display_name"], r["n_rounds"]) for r in board["rows"]
    ]
    assert [r["gain"] for r in body["rows"]] == [round(r["value"], 2) for r in board["rows"]]
    assert all(r["gain"] > 0 for r in body["rows"])
    gains = [r["gain"] for r in body["rows"]]
    assert gains == sorted(gains, reverse=True)
    assert all("rank" not in r and "places" not in r for r in body["rows"])


def test_movers_follow_a_custom_start_date(fx_viewer_client: TestClient) -> None:
    params = {"as_of": "2026-09-27", "since": "2026-03-01"}
    body = _get(fx_viewer_client, "/api/leaderboards/movers", **params)
    board = _get(fx_viewer_client, "/api/leaderboards", metric="rating_gain", **params)
    assert (body["start"], body["end"]) == ("2026-03-01", "2026-09-27")
    assert [r["shooter_id"] for r in body["rows"]] == [r["shooter_id"] for r in board["rows"]]


def test_movers_reject_a_start_after_the_end(fx_viewer_client: TestClient) -> None:
    response = fx_viewer_client.get(
        "/api/leaderboards/movers", params={"as_of": "2026-01-01", "since": "2026-02-01"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"


def test_movers_honour_the_status_filter(fx_viewer_client: TestClient) -> None:
    params = {"period": "rolling_12", "as_of": "2026-09-27", "status": "guest"}
    body = _get(fx_viewer_client, "/api/leaderboards/movers", **params)
    board = _get(fx_viewer_client, "/api/leaderboards", metric="rating_gain", **params)
    everyone = _get(
        fx_viewer_client, "/api/leaderboards/movers", period="rolling_12", as_of="2026-09-27"
    )
    assert [r["shooter_id"] for r in body["rows"]] == [r["shooter_id"] for r in board["rows"]]
    assert len(body["rows"]) < len(everyone["rows"])
