"""GET /api/leaderboards against the committed fixture world (golden values: Decision D22)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import leaderboards
from sunday_clays.analytics.leaderboards import (
    NO_FILTERS,
    Leaderboard,
    LeaderboardFilters,
    LeaderboardFrames,
    LeaderboardMetric,
    LeaderboardPeriod,
)
from sunday_clays.api.app import create_app
from sunday_clays.api.routes import _filters
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.round_type import RoundType
from sunday_clays.domain.rules import RuleType, create_rule


def board(client: TestClient, **params: str) -> dict[str, Any]:
    response = client.get("/api/leaderboards", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_ytd_threshold_scales_early_year(fx_viewer_client: TestClient) -> None:
    body = board(fx_viewer_client, period="ytd", metric="avg_score", as_of="2024-01-28")
    assert body["min_rounds_applied"] == 1
    assert body["n_eligible"] == 34
    assert len(body["rows"]) == 34


def test_season_threshold_counts_the_last_8_sundays_only(fx_viewer_client: TestClient) -> None:
    body = board(fx_viewer_client, period="season", metric="avg_score", as_of="2026-09-27")
    dates = [d for d in body["event_dates"] if "2026-08-03" <= d <= "2026-09-27"]
    assert body["min_rounds_applied"] == min(5, max(1, -(-2 * len(dates) // 5)))
    ytd = board(fx_viewer_client, period="ytd", metric="avg_score", as_of="2026-09-27")
    assert ytd["min_rounds_applied"] == 5


def test_all_time_best_score_ties_share_rank_one(fx_viewer_client: TestClient) -> None:
    rows = board(fx_viewer_client, period="all_time", metric="best_score", as_of="2026-09-27")[
        "rows"
    ]
    assert [(r["rank"], r["value"]) for r in rows[:5]] == [(1, 50.0)] * 4 + [(5, 49.0)]


def test_fixture_golden_boards(fx_viewer_client: TestClient) -> None:
    wins = board(fx_viewer_client, period="all_time", metric="wins", as_of="2026-09-27")
    assert [r["value"] for r in wins["rows"][:3]] == [62.0, 45.0, 29.0]
    average = board(fx_viewer_client, period="all_time", metric="avg_score", as_of="2026-09-27")
    assert (average["min_rounds_applied"], average["n_eligible"]) == (15, 88)
    assert average["rows"][0]["value"] == 45.02
    rolling = board(fx_viewer_client, period="rolling_12", metric="avg_score", as_of="2026-09-27")
    assert (rolling["min_rounds_applied"], rolling["n_eligible"]) == (8, 49)


def test_round_type_filter_restricts_leaderboard_rounds(fx_viewer_client: TestClient) -> None:
    body = board(
        fx_viewer_client,
        period="all_time",
        metric="rounds",
        as_of="2026-09-27",
        round_type="super_sporting",
    )
    assert body["n_eligible"] == 32
    assert max(r["value"] for r in body["rows"]) == 2.0
    assert sum(r["value"] for r in body["rows"]) == 37.0


def test_gauge_filter_selects_gauge_rounds_and_unknown_gauge_is_empty(
    fx_viewer_client: TestClient,
) -> None:
    params = {"period": "all_time", "metric": "rounds", "as_of": "2026-09-27"}
    sub = board(fx_viewer_client, gauge="Sub-Gauge", **params)
    assert (sub["n_eligible"], sum(r["value"] for r in sub["rows"])) == (9, 9.0)
    unknown = board(fx_viewer_client, gauge="Nope Gauge", **params)
    assert (unknown["n_eligible"], unknown["rows"]) == (0, [])


def test_status_filter_uses_current_status_and_set_status_override(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    shooter_id = fx_session.execute(
        text("SELECT shooter_id FROM shooter_aliases WHERE name_key = 'amberson edith'")
    ).scalar_one()
    params = {"period": "all_time", "metric": "avg_score", "as_of": "2026-09-27"}

    def listed(status: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = board(fx_viewer_client, status=status, **params)["rows"]
        return rows

    assert shooter_id in {r["shooter_id"] for r in listed("guest")}
    assert shooter_id not in {r["shooter_id"] for r in listed("member")}
    create_rule(
        fx_session, RuleType.SET_STATUS, {"shooter_id": shooter_id, "status": "member"}, None
    )
    rebuild_live(fx_session)
    assert shooter_id not in {r["shooter_id"] for r in listed("guest")}
    row = next(r for r in listed("member") if r["shooter_id"] == shooter_id)
    assert (row["status"], row["n_rounds"]) == ("member", 35)


def test_deceased_shooters_stay_on_boards(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    lennox = fx_session.execute(
        text("SELECT shooter_id FROM shooter_aliases WHERE name_key = 'lennox stan'")
    ).scalar_one()
    average = board(fx_viewer_client, period="all_time", metric="avg_score", as_of="2026-09-27")
    row = next(r for r in average["rows"] if r["shooter_id"] == lennox)
    assert (row["status"], row["rank"], row["value"]) == ("deceased", 16, 40.81)
    events = board(fx_viewer_client, period="all_time", metric="events", as_of="2026-09-27")
    assert lennox in {r["shooter_id"] for r in events["rows"]}


def test_event_dates_list_every_scored_event(fx_viewer_client: TestClient) -> None:
    dates = board(fx_viewer_client, as_of="2026-09-27")["event_dates"]
    assert (len(dates), dates[0], dates[-1]) == (311, "2020-01-05", "2026-09-27")


def test_as_of_defaults_to_today_in_club_timezone(
    viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    zones: list[str] = []

    def today_in(tz: str) -> date:
        zones.append(tz)
        return date(2026, 9, 27)

    monkeypatch.setattr(_filters, "today_local", today_in)
    body = board(viewer_client)
    assert body["as_of"] == "2026-09-27"
    assert set(zones) == {"America/Los_Angeles"}
    assert (body["period"], body["metric"], body["min_rounds_applied"]) == (
        "season",
        "avg_score",
        1,
    )
    assert (body["rows"], body["event_dates"], body["n_eligible"]) == ([], [], 0)


@pytest.mark.parametrize(
    "params",
    [
        {"metric": "bogus"},
        {"metric": "rating"},
        {"metric": "most_improved"},
        {"period": "decade"},
        {"status": "vip"},
        {"round_type": "trap"},
        {"gauge": "g" * 41},
    ],
)
def test_invalid_query_values_are_rejected(
    viewer_client: TestClient, params: dict[str, str]
) -> None:
    assert viewer_client.get("/api/leaderboards", params=params).status_code == 422


def test_round_type_order_and_repeats_share_one_memo_entry(
    viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    computed: list[LeaderboardFilters] = []
    engine = leaderboards.leaderboard

    def counting(
        frames: LeaderboardFrames,
        period: LeaderboardPeriod,
        metric: LeaderboardMetric,
        as_of: date,
        filters: LeaderboardFilters = NO_FILTERS,
        *,
        since: date | None = None,
    ) -> Leaderboard:
        computed.append(filters)
        return engine(frames, period, metric, as_of, filters, since=since)

    monkeypatch.setattr(leaderboards, "leaderboard", counting)
    for round_types in (
        ["super_sporting", "sporting"],
        ["sporting", "super_sporting"],
        ["sporting", "super_sporting", "sporting", "super_sporting"],
    ):
        params = [("as_of", "2026-09-27"), *(("round_type", rt) for rt in round_types)]
        assert viewer_client.get("/api/leaderboards", params=params).status_code == 200
    assert computed == [
        LeaderboardFilters(round_types=(RoundType.SPORTING, RoundType.SUPER_SPORTING))
    ]


def test_row_status_publishes_the_shooter_status_enum() -> None:
    schemas = create_app().openapi()["components"]["schemas"]
    status = schemas["LeaderboardRowOut"]["properties"]["status"]
    assert status["anyOf"] == [
        {"enum": ["member", "guest", "deceased"], "type": "string"},
        {"type": "null"},
    ]
    assert "status" in schemas["LeaderboardRowOut"]["required"]


def test_classes_route_is_gone(fx_viewer_client: TestClient) -> None:
    assert fx_viewer_client.get("/api/classes").status_code == 404
    assert "/api/classes" not in create_app().openapi()["paths"]
    assert "klass" not in fx_viewer_client.get("/api/leaderboards").text


def test_since_replaces_the_period_start_and_is_echoed(fx_viewer_client: TestClient) -> None:
    ytd = board(fx_viewer_client, period="ytd", metric="wins", as_of="2026-09-27")
    custom = board(fx_viewer_client, metric="wins", since="2026-01-01", as_of="2026-09-27")
    assert custom["rows"] == ytd["rows"]
    quarter = board(fx_viewer_client, metric="wins", since="2026-06-28", as_of="2026-09-27")
    assert (ytd["since"], custom["since"], quarter["since"]) == (None, None, "2026-06-28")


def test_custom_average_threshold_follows_the_sundays_in_range(
    fx_viewer_client: TestClient,
) -> None:
    body = board(fx_viewer_client, metric="avg_score", since="2025-09-29", as_of="2026-09-27")
    dates = [d for d in body["event_dates"] if "2025-09-29" <= d <= "2026-09-27"]
    n = len(dates)
    assert body["min_rounds_applied"] == min(15, max(1, min(5, -(-2 * n // 5)), -(-3 * n // 20)))
    rolling = board(fx_viewer_client, period="rolling_12", metric="avg_score", as_of="2026-09-27")
    assert body["min_rounds_applied"] == rolling["min_rounds_applied"] == 8
    assert body["rows"] == rolling["rows"]


def test_since_after_as_of_is_400_and_equal_is_a_one_day_range(
    fx_viewer_client: TestClient,
) -> None:
    bad = fx_viewer_client.get(
        "/api/leaderboards", params={"since": "2026-09-28", "as_of": "2026-09-27"}
    )
    assert bad.status_code == 400
    assert bad.json() == {
        "error": {"code": "invalid_range", "message": "'since' must be on or before 'as_of'"}
    }
    one_day = board(fx_viewer_client, metric="rounds", since="2026-09-27", as_of="2026-09-27")
    assert one_day["rows"]
    assert (
        fx_viewer_client.get("/api/leaderboards", params={"since": "not-a-date"}).status_code == 422
    )


def test_custom_from_jan_1_is_the_ytd_board_with_the_same_minimum(
    fx_viewer_client: TestClient,
) -> None:
    ytd = board(fx_viewer_client, period="ytd", metric="avg_score", as_of="2026-09-27")
    custom = board(fx_viewer_client, metric="avg_score", since="2026-01-01", as_of="2026-09-27")
    assert custom["rows"] == ytd["rows"]
    assert custom["min_rounds_applied"] == ytd["min_rounds_applied"] == 5
    assert (custom["period"], custom["start"], custom["end"]) == ("ytd", "2026-01-01", "2026-09-27")


def test_a_board_reports_the_dates_it_counts(fx_viewer_client: TestClient) -> None:
    season = board(fx_viewer_client, period="season", as_of="2026-09-27")
    assert (season["start"], season["end"]) == ("2026-08-03", "2026-09-27")
    rolling = board(fx_viewer_client, period="rolling_12", as_of="2026-09-27")
    assert (rolling["start"], rolling["end"]) == ("2025-09-29", "2026-09-27")
    everything = board(fx_viewer_client, period="all_time", as_of="2026-09-27")
    assert (everything["start"], everything["end"]) == (None, "2026-09-27")
    custom = board(fx_viewer_client, since="2026-06-01", as_of="2026-09-20")
    assert (custom["start"], custom["end"]) == ("2026-06-01", "2026-09-20")


def test_as_of_defaults_to_the_latest_scored_sunday_not_the_clock(
    fx_viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: date(2030, 1, 1))
    body = board(fx_viewer_client, period="season")
    assert (body["as_of"], body["end"]) == ("2026-09-27", "2026-09-27")
    assert body["start"] == "2026-08-03"


def test_rating_gain_lists_only_gainers_over_the_window(fx_viewer_client: TestClient) -> None:
    body = board(fx_viewer_client, period="rolling_12", metric="rating_gain", as_of="2026-09-27")
    assert body["rows"]
    assert all(row["value"] > 0 for row in body["rows"])
    assert body["min_rounds_applied"] == 5
    values = [row["value"] for row in body["rows"]]
    assert values == sorted(values, reverse=True)
