"""The 10/25 case through the routes: one count, one stat, one station, one sequence (T6d)."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import clear_cache

SUNDAY, FIRST = "2026-10-25", "2026-08-23"
WINDOW = {"since": FIRST, "as_of": SUNDAY}


def _hadley(s: Session) -> int:
    return s.execute(
        text(
            "SELECT r.shooter_id FROM rounds r JOIN shooters h ON h.id = r.shooter_id "
            "WHERE r.event_date = :d AND h.display_name = 'Hadley, Ike'"
        ),
        {"d": SUNDAY},
    ).scalar_one()


def test_the_thrown_out_sunday_is_flagged_and_named(
    fx_thrown_out_viewer_client: TestClient,
) -> None:
    c = fx_thrown_out_viewer_client
    detail = c.get(f"/api/events/{SUNDAY}").json()
    assert (detail["stats_excluded"], detail["vs_prev"]) == (True, None)
    assert detail["thrown_out"] == [{"station_label": "11", "target_count": 7, "credited": True}]
    assert (detail["top_score"], detail["median"]) == (43, 35.0)
    listed = c.get("/api/events").json()
    assert (listed[-1]["event_date"], listed[-1]["stats_excluded"]) == (SUNDAY, True)


def test_scores_and_pbs_leave_the_free_targets_out(
    fx_thrown_out_viewer_client: TestClient, fx_thrown_out_session: Session
) -> None:
    c = fx_thrown_out_viewer_client
    body = c.get(f"/api/shooters/{_hadley(fx_thrown_out_session)}").json()
    assert (body["stats"]["n_excluded"], body["stats"]["n_rounds"]) == (1, 10)
    assert max(p["score"] for p in body["pbs"]) == 41
    records = c.get("/api/records", params=WINDOW).json()["highest_scores"]
    assert 43.0 not in [r["value"] for r in records]


def test_station_11_counts_only_real_shooting(
    fx_thrown_out_viewer_client: TestClient,
) -> None:
    stations = fx_thrown_out_viewer_client.get("/api/stations", params=WINDOW).json()["stations"]
    st11 = next(s for s in stations if s["label"] == "11")
    assert (st11["hits"], st11["n_targets"]) == (364, 567)


def test_standings_and_the_race_are_unchanged_by_the_flag(  # guard
    fx_thrown_out_viewer_client: TestClient, fx_thrown_out_session: Session
) -> None:
    c, s = fx_thrown_out_viewer_client, fx_thrown_out_session
    points = {"period": "ytd", "metric": "season_points", "as_of": SUNDAY}
    race = {"period": "ytd", "metric": "season_points", "top": 10, "from": FIRST, "to": SUNDAY}

    def read() -> tuple[object, object]:
        return (
            c.get("/api/leaderboards", params=points).json()["rows"],
            c.get("/api/leaderboards/history", params=race).json(),
        )

    before = read()
    s.execute(text("UPDATE events SET stats_excluded = false"))
    s.execute(text("UPDATE station_layouts SET dropped = false, dropped_source = NULL"))
    clear_cache()
    assert before == read()
