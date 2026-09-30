"""GET /api/leaderboards/history (C8) on the committed fixtures and an empty database."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.routes import _filters

ROW_KEYS = ("shooter_id", "display_name", "status", "value", "rank")


def history(client: TestClient, params: dict[str, str]) -> dict[str, Any]:
    response = client.get("/api/leaderboards/history", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.mark.parametrize("period", ["season", "ytd"])
def test_history_frames_match_the_leaderboard_endpoint(
    fx_viewer_client: TestClient, period: str
) -> None:
    query = {"top": "5", "from": "2026-09-01", "to": "2026-09-30"}
    body = history(fx_viewer_client, {**query, "period": period})
    assert (body["period"], body["metric"]) == (period, "season_points")
    assert [f["event_date"] for f in body["frames"]] == ["2026-09-06", "2026-09-13", "2026-09-27"]
    for frame in body["frames"]:
        board = fx_viewer_client.get(
            "/api/leaderboards",
            params={"period": period, "metric": "season_points", "as_of": frame["event_date"]},
        ).json()
        assert frame["rows"] == [{key: row[key] for key in ROW_KEYS} for row in board["rows"][:5]]
    if period == "ytd":
        assert body["frames"][-1]["rows"][0]["value"] == 191.0


def test_history_ytd_points_reset_jan1_on_the_fixture(fx_viewer_client: TestClient) -> None:
    body = history(fx_viewer_client, {"from": "2025-12-28", "to": "2026-01-04", "period": "ytd"})
    assert [(f["event_date"], f["rows"][0]["value"]) for f in body["frames"]] == [
        ("2025-12-28", 254.0),
        ("2026-01-04", 11.0),
    ]


def test_history_passes_filters_to_every_frame(fx_viewer_client: TestClient) -> None:
    params = {
        "period": "all_time",
        "metric": "rounds",
        "top": "50",
        "from": "2026-09-01",
        "to": "2026-09-30",
        "round_type": "super_sporting",
    }
    frames = history(fx_viewer_client, params)["frames"]
    assert [f["event_date"] for f in frames] == ["2026-09-06", "2026-09-13", "2026-09-27"]
    last = frames[-1]["rows"]
    assert (len(last), sum(r["value"] for r in last)) == (32, 37.0)


def test_history_defaults_to_this_year_up_to_the_latest_scored_sunday(
    fx_viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: date(2026, 1, 4))
    frames = history(fx_viewer_client, {"period": "ytd"})["frames"]
    assert frames[0]["event_date"] == "2026-01-04"
    assert frames[-1]["event_date"] == "2026-09-27"
    assert all(f["event_date"] >= "2026-01-01" for f in frames)
    assert len(frames[0]["rows"]) == 10


def test_history_defaults_on_an_empty_database(viewer_client: TestClient) -> None:
    assert history(viewer_client, {}) == {
        "period": "season",
        "metric": "season_points",
        "frames": [],
    }


def test_history_rejects_an_inverted_range(viewer_client: TestClient) -> None:
    response = viewer_client.get(
        "/api/leaderboards/history", params={"from": "2026-02-01", "to": "2026-01-01"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"


def test_history_top_500_holds_every_ranked_shooter(fx_viewer_client: TestClient) -> None:
    base = {"period": "all_time", "metric": "rounds", "from": "2026-09-01", "to": "2026-09-30"}
    frames = history(fx_viewer_client, {**base, "top": "500"})["frames"]
    assert [f["event_date"] for f in frames] == ["2026-09-06", "2026-09-13", "2026-09-27"]
    for frame in frames:
        board = fx_viewer_client.get(
            "/api/leaderboards",
            params={"period": "all_time", "metric": "rounds", "as_of": frame["event_date"]},
        ).json()
        assert len(frame["rows"]) == len(board["rows"]) > 50


@pytest.mark.parametrize("top", ["0", "501"])
def test_history_top_is_bounded(viewer_client: TestClient, top: str) -> None:
    assert viewer_client.get("/api/leaderboards/history", params={"top": top}).status_code == 422


def test_history_round_type_order_and_repeats_share_one_result(
    fx_viewer_client: TestClient,
) -> None:
    base = {
        "period": "all_time",
        "metric": "rounds",
        "top": "3",
        "from": "2026-09-01",
        "to": "2026-09-30",
    }
    one = fx_viewer_client.get(
        "/api/leaderboards/history",
        params=[*base.items(), ("round_type", "sporting"), ("round_type", "super_sporting")],
    )
    two = fx_viewer_client.get(
        "/api/leaderboards/history",
        params=[
            *base.items(),
            ("round_type", "super_sporting"),
            ("round_type", "sporting"),
            ("round_type", "sporting"),
        ],
    )
    assert one.status_code == two.status_code == 200
    assert one.json() == two.json()
    only = fx_viewer_client.get(
        "/api/leaderboards/history", params=[*base.items(), ("round_type", "sporting")]
    )
    assert only.status_code == 200
    assert only.json() != one.json()


def test_history_status_filter_reaches_every_frame(fx_viewer_client: TestClient) -> None:
    params = {"top": "50", "from": "2026-09-01", "to": "2026-09-30", "status": "guest"}
    frames = history(fx_viewer_client, params)["frames"]
    rows = [row for frame in frames for row in frame["rows"]]
    assert rows
    assert {row["status"] for row in rows} == {"guest"}


def test_history_gauge_filter_reaches_every_frame(fx_viewer_client: TestClient) -> None:
    base = {"period": "all_time", "metric": "rounds", "top": "50", "from": "2026-09-01"}
    everything = history(fx_viewer_client, {**base, "to": "2026-09-30"})["frames"][-1]["rows"]
    gauge = history(fx_viewer_client, {**base, "to": "2026-09-30", "gauge": "12"})["frames"][-1][
        "rows"
    ]
    assert sum(r["value"] for r in gauge) < sum(r["value"] for r in everything)


def test_history_rejects_an_unknown_status(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/leaderboards/history", params={"status": "bogus"})
    assert response.status_code == 422


def test_since_frames_equal_the_ytd_frames(fx_viewer_client: TestClient) -> None:
    common = {"metric": "season_points", "to": "2026-09-27"}
    custom = history(fx_viewer_client, {**common, "since": "2026-01-01"})
    ytd = history(fx_viewer_client, {**common, "from": "2026-01-01", "period": "ytd"})
    assert custom["frames"] == ytd["frames"]
    assert custom["frames"]


def test_since_alone_starts_the_first_frame_on_or_after_it(fx_viewer_client: TestClient) -> None:
    body = history(fx_viewer_client, {"since": "2026-03-01", "to": "2026-09-27"})
    assert body["frames"][0]["event_date"] >= "2026-03-01"
    last = body["frames"][-1]
    board = fx_viewer_client.get(
        "/api/leaderboards",
        params={"metric": "season_points", "since": "2026-03-01", "as_of": last["event_date"]},
    ).json()
    assert [r["value"] for r in last["rows"]] == [r["value"] for r in board["rows"][:10]]


def test_since_after_from_is_400(viewer_client: TestClient) -> None:
    response = viewer_client.get(
        "/api/leaderboards/history", params={"since": "2026-03-01", "from": "2026-02-01"}
    )
    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "invalid_range", "message": "'since' must be on or before 'from'"}
    }
