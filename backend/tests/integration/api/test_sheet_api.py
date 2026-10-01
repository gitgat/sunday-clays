"""GET /api/sheet/* on the fx world (Plan 14 Task 2): issues, numbers, posts and their keys."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import sheet
from sunday_clays.analytics.yir import OnThisDayItem
from sunday_clays.api.routes import sheet as sheet_routes

LATEST = date(2026, 9, 27)


def _held(fx_session: Session) -> list[date]:
    return list(
        fx_session.scalars(
            text("SELECT event_date FROM events WHERE results_complete ORDER BY event_date")
        )
    )


def _all_posts(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [*body["posts"], *(p for g in body["more"] for p in g["posts"])]


def test_latest_is_the_newest_held_sunday(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    held = _held(fx_session)
    body = fx_viewer_client.get("/api/sheet/latest").json()
    assert body["masthead"] == {
        "date": LATEST.isoformat(),
        "issue": len(held),
        "previous": held[-2].isoformat(),
        "next": None,
        "latest": True,
        "newer": None,
    }
    assert fx_viewer_client.get(f"/api/sheet/{LATEST.isoformat()}").json() == body


def test_the_first_issue_has_no_previous(fx_viewer_client: TestClient, fx_session: Session) -> None:
    held = _held(fx_session)
    masthead = fx_viewer_client.get(f"/api/sheet/{held[0].isoformat()}").json()["masthead"]
    assert (masthead["issue"], masthead["previous"], masthead["next"]) == (
        1,
        None,
        held[1].isoformat(),
    )
    assert masthead["latest"] is False


def test_a_sunday_without_a_sheet_is_404(fx_viewer_client: TestClient, fx_session: Session) -> None:
    not_held = fx_session.scalar(
        text("SELECT event_date FROM events WHERE NOT results_complete ORDER BY event_date LIMIT 1")
    )
    for day in ("2026-09-26", str(not_held)):
        response = fx_viewer_client.get(f"/api/sheet/{day}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "sheet_not_found"


def test_the_four_numbers_match_the_sunday(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    event = fx_viewer_client.get(f"/api/events/{LATEST.isoformat()}").json()
    awards = fx_viewer_client.get(f"/api/events/{LATEST.isoformat()}/achievements").json()
    assert body["numbers"] == {
        "shooters": event["n_shooters"],
        "median": event["median"],
        "top_score": event["top_score"],
        "trophies": len(awards["awards"]),
    }


def test_posts_map_to_their_types_and_trophies_match_the_sunday(
    fx_viewer_client: TestClient,
) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    posts = _all_posts(body)
    assert 8 <= len(body["posts"]) <= sheet.FEED_CAP
    for p in posts:
        if p["insight"] is not None:
            assert p["post_key"] == p["insight"]["key"]
            assert p["type"] == sheet.post_type(p["insight"]["kind"])
            assert p["see_why"]["kind"] == "chart"
    awards = fx_viewer_client.get(f"/api/events/{LATEST.isoformat()}/achievements").json()
    trophy_posts = {p["trophy"]["code"]: p for p in posts if p["type"] == "trophy"}
    assert set(trophy_posts) == {a["code"] for a in awards["awards"]}
    for code, p in trophy_posts.items():
        assert p["post_key"] == f"trophy:{code}:{LATEST.isoformat()}"
        assert p["see_why"] == {
            "kind": "link",
            "label": f"{p['trophy']['title']} in the Trophy Room",
            "chart": None,
            "href": f"/achievements/{code}",
        }
        holders = {a["shooter_id"] for a in awards["awards"] if a["code"] == code}
        assert {h["shooter_id"] for h in p["trophy"]["holders"]} == holders


def test_the_feed_never_runs_a_type_three_times_while_another_is_left(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    for day in _held(fx_session)[-8:]:
        body = fx_viewer_client.get(f"/api/sheet/{day.isoformat()}").json()
        feed = [p["type"] for p in body["posts"]]
        rest = [p["type"] for p in _all_posts(body)[len(feed) :] if p["type"] in sheet.FEED_TYPES]
        for i in range(2, len(feed)):
            if feed[i] == feed[i - 1] == feed[i - 2]:
                assert set(feed[i:]) | set(rest) == {feed[i]}, (day, feed)


def test_named_shooter_posts_are_positive_or_neutral(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    for day in _held(fx_session)[-8:]:
        body = fx_viewer_client.get(f"/api/sheet/{day.isoformat()}").json()
        # A lead carries no id list, so its names are the shooter segments of its headline.
        for key in ("headline", "spotlight"):
            lead = body[key]
            if lead is not None and any(seg["t"] == "shooter" for seg in lead["headline"]):
                assert lead["polarity"] in {"positive", "neutral"}, (day, lead["key"])
        for post in _all_posts(body):
            if post["named_shooter_ids"] and post["insight"] is not None:
                assert post["insight"]["polarity"] in {"positive", "neutral"}, (
                    day,
                    post["post_key"],
                )


def test_more_is_grouped_by_family(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    families = [g["family"] for g in body["more"]]
    assert len(families) == len(set(families))
    for group in body["more"]:
        assert group["posts"]
        assert {p["family"] for p in group["posts"]} == {group["family"]}


def test_the_headline_is_the_hero_pick_and_the_recap_its_deck(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    hero = fx_session.scalar(
        text("SELECT insight_key FROM insight_picks WHERE sunday = :d AND slot = 'hero'"),
        {"d": LATEST},
    )
    assert body["headline"]["key"] == hero
    assert body["recap"]["kind"] == "home.sunday-recap"
    keys = {p["post_key"] for p in _all_posts(body)}
    assert body["headline"]["key"] not in keys
    assert body["recap"]["key"] not in keys


def test_every_post_key_resolves_and_nothing_else_does(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    held = _held(fx_session)
    for day in (held[-1], held[-5]):
        body = fx_viewer_client.get(f"/api/sheet/{day.isoformat()}").json()
        for p in _all_posts(body):
            assert sheet_routes.resolves(fx_session, p["post_key"]), p["post_key"]
    latest = fx_viewer_client.get("/api/sheet/latest").json()
    for key in (
        latest["headline"]["key"],
        "trophy:no_such_trophy:2026-09-27",
        "otd:2026-09-27:9",
        "otd:2026-09-26:1",
        "deadbeefdeadbeefdead",
    ):
        assert not sheet_routes.resolves(fx_session, key), key


def test_without_a_held_sunday_there_is_no_sheet(
    viewer_client: TestClient, session: Session
) -> None:
    response = viewer_client.get("/api/sheet/latest")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "sheet_not_found"
    assert sheet_routes.post_issue_date(session, "otd:2026-09-27:1") is None


@pytest.mark.parametrize(
    ("has_scores", "head_count", "n_shooters"), [(False, 14, 0), (True, None, 6)]
)
def test_a_newer_sunday_without_full_results_is_on_the_latest_issue_only(
    session: Session, has_scores: bool, head_count: int | None, n_shooters: int
) -> None:
    """Home's Latest Sunday card followed the newest Sunday; the Sheet keeps the latest held issue
    and points at a newer attendance-only or partly scored one."""
    insert = text(
        "INSERT INTO events (event_date, round_type, round_type_source, head_count, n_rounds,"
        " n_shooters, has_scores, has_stations, results_complete)"
        " VALUES (:d, 'sporting', 'none', :hc, 0, :n, :hs, false, :rc)"
    )
    held = [date(2026, 9, 13), date(2026, 9, 20)]
    for day in held:
        session.execute(insert, {"d": day, "hc": None, "n": 0, "hs": True, "rc": True})
    newer = {"d": LATEST, "hc": head_count, "n": n_shooters, "hs": has_scores, "rc": False}
    session.execute(insert, newer)

    def issue(day: date) -> sheet.Issue:
        return sheet.assemble(
            day,
            held,
            [],
            hero=None,
            spotlight=None,
            awards=[],
            catalog={},
            on_this_day=[],
            supersedes=lambda _kind: frozenset(),
        )

    out = sheet_routes.newer_sunday(session, issue(held[-1]))
    assert out is not None
    assert out.model_dump() == {
        "date": LATEST,
        "has_scores": has_scores,
        "head_count": head_count,
        "n_shooters": n_shooters,
    }
    assert sheet_routes.newer_sunday(session, issue(held[0])) is None


def test_the_latest_issue_has_no_newer_sunday_when_it_is_the_newest(
    fx_session: Session,
) -> None:
    held = _held(fx_session)
    issue = sheet_routes.build_issue(fx_session, held[-1])
    assert sheet_routes.newer_sunday(fx_session, issue) is None


def test_the_latest_issue_carries_on_this_day_whenever_it_has_a_look_back(
    fx_viewer_client: TestClient,
) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    present = {p["type"] for p in _all_posts(body) if p["type"] in sheet.FEED_TYPES}
    assert {p["type"] for p in body["posts"]} == present


def test_a_post_without_a_source_is_a_bug_not_a_link() -> None:
    orphan = sheet.Post("k", "other", "form", 1.0, (), ())
    with pytest.raises(ValueError, match="post k has no source"):
        sheet_routes.see_why(orphan)


def test_the_body_never_carries_bump_counts_and_is_etagged(
    fx_viewer_client: TestClient,
) -> None:
    first = fx_viewer_client.get("/api/sheet/latest")
    assert '"bumps"' not in first.text
    assert '"bumped"' not in first.text
    etag = first.headers["etag"]
    again = fx_viewer_client.get("/api/sheet/latest", headers={"If-None-Match": etag})
    assert again.status_code == 304


def test_an_on_this_day_post_links_to_that_sundays_results() -> None:
    item = OnThisDayItem(
        years_ago=2,
        event_date=date(2024, 9, 29),
        has_scores=True,
        head_count=None,
        n_shooters=31,
        top_score=48,
        median=40.0,
        winners=(),
    )
    (post,) = sheet.otd_posts([item], LATEST)
    assert sheet_routes.see_why(post).model_dump() == {
        "kind": "link",
        "label": "That Sunday's results",
        "chart": None,
        "href": "/events/2024-09-29",
    }


def test_the_trophies_number_counts_every_award_that_day(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    """Including an award whose trophy has left the catalog (it has no post)."""
    before = fx_viewer_client.get("/api/sheet/latest").json()["numbers"]["trophies"]
    shooter = fx_session.scalar(
        text("SELECT min(shooter_id) FROM rounds WHERE event_date = :d"), {"d": LATEST}
    )
    fx_session.execute(
        text(
            "INSERT INTO achievements_awarded (shooter_id, code, event_date, round_id, details) "
            "VALUES (:s, 'retired_code', :d, NULL, CAST('{}' AS jsonb))"
        ),
        {"s": shooter, "d": LATEST},
    )
    issue = sheet_routes.build_issue(fx_session, LATEST)
    assert sheet_routes._numbers(fx_session, issue).trophies == before + 1
