"""DF-4: since / as_of on the club summary and distribution and on the shooter routes.

A window never leaks: nothing dated outside [since, as_of] reaches a windowed number, while the
odometer, the year-by-year table and the personal bests stay lifetime.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.routes import _filters

TODAY = date(2026, 9, 27)
# W[0] is the latest Sunday, W[7] seven weeks earlier.
W = [TODAY - timedelta(days=7 * k) for k in range(8)]
OLD = date(2024, 6, 2)


@pytest.fixture(autouse=True)
def _wall_clock_is_far_away(monkeypatch: pytest.MonkeyPatch) -> None:
    # The wall clock is months after the last scored Sunday: defaults must count from the data.
    monkeypatch.setattr(_filters, "today_local", lambda tz: date(2027, 3, 1))


def _seed_club(seed: Any) -> tuple[int, int]:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob", status="guest")
    seed.round(OLD, ann, 10)
    seed.round(W[7], ann, 20)
    seed.round(W[7], bob, 24)
    seed.round(W[1], ann, 40)
    seed.round(W[0], ann, 50)
    seed.round(W[0], bob, 30)
    seed.finish()
    seed.analyze()
    return ann, bob


def test_club_summary_window_counts_only_the_window(seed: Any, viewer_client: TestClient) -> None:
    _seed_club(seed)

    body = viewer_client.get(
        "/api/club/summary", params={"since": W[1].isoformat(), "as_of": W[0].isoformat()}
    ).json()

    assert (body["n_events"], body["n_scored_events"], body["n_rounds"]) == (2, 2, 3)
    assert body["n_shooters"] == 2
    assert (body["top_score"], body["clays_broken"], body["n_perfect"]) == (50, 120, 1)
    assert (body["first_event"], body["last_event"]) == (W[1].isoformat(), W[0].isoformat())
    assert body["shooters_by_status"] == {"member": 1, "guest": 1}
    # The year-by-year table is not windowed: every year still shows.
    assert [
        (y["year"], y["member_rounds"] + y["guest_rounds"]) for y in body["status_by_year"]
    ] == [
        (2024, 1),
        (2026, 5),
    ]


def test_club_summary_as_of_hides_later_sundays(seed: Any, viewer_client: TestClient) -> None:
    _seed_club(seed)

    body = viewer_client.get("/api/club/summary", params={"as_of": W[7].isoformat()}).json()

    assert (body["n_rounds"], body["top_score"], body["last_event"]) == (
        3,
        24,
        W[7].isoformat(),
    )


def test_club_summary_without_a_window_is_all_time(seed: Any, viewer_client: TestClient) -> None:
    _seed_club(seed)

    assert viewer_client.get("/api/club/summary").json()["n_rounds"] == 6


def test_club_summary_empty_window(seed: Any, viewer_client: TestClient) -> None:
    _seed_club(seed)

    body = viewer_client.get(
        "/api/club/summary", params={"since": "2025-01-01", "as_of": "2025-12-31"}
    ).json()

    assert (body["n_rounds"], body["n_shooters"], body["avg_score"]) == (0, 0, None)
    assert body["first_event"] is None


@pytest.mark.parametrize(
    "path",
    ["/api/club/summary", "/api/club/distribution", "/api/shooters/1", "/api/shooters/1/splits"],
)
def test_a_reversed_window_is_a_bad_request(
    seed: Any, viewer_client: TestClient, path: str
) -> None:
    _seed_club(seed)

    response = viewer_client.get(
        path, params={"since": "2026-09-27", "as_of": "2026-01-01", "by": "year"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"


def test_club_distribution_window_drops_other_years(seed: Any, viewer_client: TestClient) -> None:
    _seed_club(seed)

    everything = viewer_client.get("/api/club/distribution").json()
    windowed = viewer_client.get(
        "/api/club/distribution", params={"since": W[1].isoformat(), "as_of": W[0].isoformat()}
    ).json()

    assert [(g["key"], g["n"]) for g in everything] == [("2024", 1), ("2026", 5)]
    assert [(g["key"], g["n"]) for g in windowed] == [("2026", 3)]
    assert sorted(i for i, c in enumerate(windowed[0]["counts"]) if c) == [30, 40, 50]


def test_shooter_detail_window_stats_and_lifetime_stay_apart(
    seed: Any, viewer_client: TestClient
) -> None:
    ann, _ = _seed_club(seed)

    plain = viewer_client.get(f"/api/shooters/{ann}").json()
    body = viewer_client.get(
        f"/api/shooters/{ann}", params={"since": W[1].isoformat(), "as_of": W[0].isoformat()}
    ).json()

    assert plain["window_stats"] is None
    assert body["stats"] == plain["stats"]
    assert body["odometer"] == plain["odometer"]
    assert body["pbs"] == plain["pbs"]
    assert body["stats"]["n_rounds"] == 4
    win = body["window_stats"]
    assert (win["n_rounds"], win["n_events"], win["best_score"]) == (2, 2, 50)
    assert win["avg_score"] == 45.0


def test_shooter_detail_window_before_their_first_round_is_empty(
    seed: Any, viewer_client: TestClient
) -> None:
    ann, _ = _seed_club(seed)

    win = viewer_client.get(
        f"/api/shooters/{ann}", params={"since": "2025-01-01", "as_of": "2025-12-31"}
    ).json()["window_stats"]

    assert (win["n_rounds"], win["avg_score"], win["best_score"]) == (0, None, None)


def test_shooter_splits_window(seed: Any, viewer_client: TestClient) -> None:
    ann, _ = _seed_club(seed)

    everything = viewer_client.get(f"/api/shooters/{ann}/splits", params={"by": "year"}).json()
    windowed = viewer_client.get(
        f"/api/shooters/{ann}/splits",
        params={"by": "year", "since": W[1].isoformat(), "as_of": W[0].isoformat()},
    ).json()

    assert [(s["key"], s["n_rounds"]) for s in everything] == [("2024", 1), ("2026", 3)]
    assert [(s["key"], s["n_rounds"], s["best"]) for s in windowed] == [("2026", 2, 50)]


def test_regulars_and_active_count_from_the_latest_scored_sunday(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    for d in W[:5]:
        seed.round(d, ann, 30)
    seed.finish()
    seed.analyze()

    regulars = viewer_client.get("/api/club/regulars").json()
    active = viewer_client.get("/api/shooters", params={"active": "true"}).json()

    assert regulars["as_of"] == W[0].isoformat()
    assert [c["display_name"] for c in regulars["core"]] == ["Oakley, Ann"]
    assert [s["shooter_id"] for s in active] == [ann]


def test_shooter_insights_default_as_of_is_the_latest_scored_sunday(
    seed: Any, viewer_client: TestClient
) -> None:
    ann, _ = _seed_club(seed)

    body = viewer_client.get(f"/api/shooters/{ann}/insights").json()

    assert body["as_of"] == W[0].isoformat()


def test_latest_scored_day_falls_back_to_today_without_scores(viewer_client: TestClient) -> None:
    assert viewer_client.get("/api/club/regulars").json()["as_of"] == "2027-03-01"
