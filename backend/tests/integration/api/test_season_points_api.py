"""GET /api/leaderboards?metric=season_points on the committed fixtures (Decision D22)."""

from fastapi.testclient import TestClient


def test_ytd_points_2026_golden(fx_viewer_client: TestClient) -> None:
    response = fx_viewer_client.get(
        "/api/leaderboards",
        params={"period": "ytd", "metric": "season_points", "as_of": "2026-09-27"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["min_rounds_applied"] == 1
    assert [(r["rank"], r["value"]) for r in body["rows"][:6]] == [
        (1, 191.0),
        (2, 139.0),
        (3, 129.0),
        (4, 111.0),
        (4, 111.0),
        (4, 111.0),
    ]
    assert body["rows"][6]["rank"] == 7


def test_season_points_cover_only_the_last_8_sundays(fx_viewer_client: TestClient) -> None:
    def points(period: str) -> dict[int, float]:
        response = fx_viewer_client.get(
            "/api/leaderboards",
            params={"period": period, "metric": "season_points", "as_of": "2026-09-27"},
        )
        assert response.status_code == 200, response.text
        return {r["shooter_id"]: r["value"] for r in response.json()["rows"]}

    season, ytd = points("season"), points("ytd")
    assert season
    assert max(season.values()) < max(ytd.values())  # 8 Sundays cannot beat the whole year
    assert set(season) <= set(ytd)
