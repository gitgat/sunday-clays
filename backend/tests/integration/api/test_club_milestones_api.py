"""GET /api/club/milestones (Plan 19 §3.5.2, §5.2)."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import club_milestones as cm
from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.config import get_settings
from sunday_clays.domain.features import set_switch

SPECIAL = "2026-09-20"


def _on(session: Session) -> None:
    set_switch(session, get_settings(), "club_milestones", True)


def test_viewer_gets_404_while_off_and_admin_gets_200(
    fx_viewer_client: TestClient, fx_admin_client: TestClient
) -> None:
    off = fx_viewer_client.get("/api/club/milestones")
    assert off.status_code == 404
    assert off.json() == {"detail": "Not Found"}
    assert fx_admin_client.get("/api/club/milestones").status_code == 200


def test_as_of_defaults_to_the_latest_scored_sunday(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    _on(fx_session)
    body = fx_viewer_client.get("/api/club/milestones").json()
    latest = fx_session.execute(
        text("SELECT max(event_date) FROM events WHERE has_scores")
    ).scalar()
    assert body["as_of"] == latest.isoformat()
    assert body["series"][-1]["event_date"] <= body["as_of"]
    assert {"milestones", "latest", "next", "series"} <= set(body)


def test_special_sunday_adds_held_and_shooters_not_clays(
    fx_special_viewer_client: TestClient, fx_special_session: Session
) -> None:
    _on(fx_special_session)
    series = {
        r["event_date"]: r
        for r in fx_special_viewer_client.get("/api/club/milestones").json()["series"]
    }
    before = series["2026-09-13"]
    special = series[SPECIAL]
    assert special["clays_thrown"] == before["clays_thrown"]
    assert special["rounds"] == before["rounds"]
    assert special["sundays_held"] == before["sundays_held"] + 1
    assert special["shooters"] == before["shooters"] + 1  # Kim, Pat is new


def test_fx_world_is_the_special_world_without_its_special_sunday(
    fx_viewer_client: TestClient,
    fx_session: Session,
    fx_special_viewer_client: TestClient,
    fx_special_session: Session,
) -> None:
    _on(fx_session)
    _on(fx_special_session)
    plain = {
        r["event_date"]: r for r in fx_viewer_client.get("/api/club/milestones").json()["series"]
    }
    clear_cache()
    special = {
        r["event_date"]: r
        for r in fx_special_viewer_client.get("/api/club/milestones").json()["series"]
    }
    assert SPECIAL not in plain
    for day, row in plain.items():
        if day < SPECIAL:
            assert special[day] == row, day
        else:
            assert special[day]["clays_thrown"] == row["clays_thrown"]
            assert special[day]["rounds"] == row["rounds"]


def test_no_leak_for_every_held_sunday(fx_session: Session) -> None:
    calendar = frames.load_calendar(fx_session)
    held = sorted(calendar.loc[calendar["results_complete"].astype(bool), "event_date"])
    full = cm.club_milestones(fx_session, held[-1])
    for day in held:
        cut = cm.club_milestones(fx_session, day)
        assert list(cut.milestones) == [m for m in full.milestones if m.event_date <= day]
        position = next(i for i, r in enumerate(full.series) if r.event_date == day)
        for n in cut.next:
            assert n.current == getattr(full.series[position], n.metric)


def test_as_of_before_the_first_sunday_is_empty(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    _on(fx_session)
    body = fx_viewer_client.get("/api/club/milestones", params={"as_of": "1990-01-07"}).json()
    assert body["milestones"] == []
    assert body["latest"] is None
    assert body["series"] == []
    assert date.fromisoformat(body["as_of"]) == date(1990, 1, 7)
