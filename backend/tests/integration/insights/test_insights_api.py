"""GET /api/insights/* and the admin kinds route on the fx world (spec §3.7)."""

from datetime import date

from sqlalchemy import text

from sunday_clays.analytics.insights.engine import readiness_of
from sunday_clays.analytics.insights.store import readiness_from_db
from sunday_clays.analytics.steps.s60_insights import build_frames
from sunday_clays.api.routes import insights as insights_routes
from sunday_clays.api.routes.insights import supersedes_of

LATEST = date(2026, 9, 27)


def _held(fx_session) -> list[date]:
    return list(
        fx_session.scalars(
            text("SELECT event_date FROM events WHERE results_complete ORDER BY event_date")
        )
    )


def test_profile_feed_pins_the_digest_line_for_any_viewer(fx_viewer_client, fx_session):
    sid = fx_session.scalar(
        text("SELECT subject_id FROM insights WHERE kind = 'pf.digest-line' ORDER BY key LIMIT 1")
    )
    body = fx_viewer_client.get(f"/api/insights/shooters/{sid}").json()
    assert body["pinned"]["kind"] == "pf.digest-line"
    assert body["pinned"]["headline_you"] is not None  # the client shows it only for "Me" (D11)
    assert body["pinned"]["is_new"] is False
    assert body["as_of"] == _held(fx_session)[-1].isoformat()
    assert len(body["top"]) <= 3
    for item in body["top"]:
        assert item["chart"]["window"]["from"] <= item["chart"]["window"]["to"]
        assert item["headline_text"] == "".join(s["v"] for s in item["headline"])


def test_profile_feed_all_lifts_the_more_cap(fx_viewer_client, fx_session):
    sid = fx_session.scalar(
        text("SELECT subject_id FROM insights WHERE kind = 'pf.digest-line' ORDER BY key LIMIT 1")
    )
    capped = fx_viewer_client.get(f"/api/insights/shooters/{sid}").json()
    everything = fx_viewer_client.get(
        f"/api/insights/shooters/{sid}", params={"all": "true"}
    ).json()
    assert everything["n_more"] == capped["n_more"]
    assert len(everything["more"]) == everything["n_more"]
    assert everything["more"][: len(capped["more"])] == capped["more"]


def test_unknown_shooter_is_404(fx_viewer_client):
    response = fx_viewer_client.get("/api/insights/shooters/999999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"


def test_sunday_feed_rolls_up_and_lists_kudos(fx_viewer_client, fx_session):
    day = fx_session.scalar(
        text(
            "SELECT anchor_date FROM insights WHERE variant = 'rollup' "
            "ORDER BY anchor_date DESC LIMIT 1"
        )
    )
    body = fx_viewer_client.get(f"/api/insights/sundays/{day.isoformat()}").json()
    assert body["as_of"] == day.isoformat()
    kinds = [i["kind"] for i in body["top"]] + [i["kind"] for i in body["more"]]
    assert kinds
    ids = [chip["shooter_id"] for chip in body["kudos"]]
    assert len(ids) == len(set(ids))  # one chip per shooter
    assert all(chip["insight"]["kudos"] for chip in body["kudos"])


def test_sunday_without_full_results_has_an_empty_feed_and_no_date_is_404(
    fx_viewer_client, fx_session
):
    partial = fx_session.scalar(
        text("SELECT event_date FROM events WHERE NOT results_complete ORDER BY 1 LIMIT 1")
    )
    body = fx_viewer_client.get(f"/api/insights/sundays/{partial.isoformat()}").json()
    assert (body["top"], body["kudos"], body["more"]) == ([], [], [])
    missing = fx_viewer_client.get("/api/insights/sundays/2026-09-28")
    assert missing.status_code == 404


def test_home_feed_is_anchored_to_the_latest_sunday(fx_viewer_client, fx_session):
    body = fx_viewer_client.get("/api/insights/home").json()
    latest = _held(fx_session)[-1]
    assert body["as_of"] == latest.isoformat()
    assert len(body["top"]) <= 4
    named = [sid for item in body["top"] for sid in _named(fx_session, item["key"])]
    assert len(named) == len(set(named))  # one named story per shooter


def _named(fx_session, key: str) -> list[int]:
    return list(
        fx_session.scalar(text("SELECT named_shooter_ids FROM insights WHERE key = :k"), {"k": key})
    )


def test_viewer_feeds_get_an_etag(fx_viewer_client):
    first = fx_viewer_client.get("/api/insights/home")
    tag = first.headers["ETag"]
    again = fx_viewer_client.get("/api/insights/home", headers={"If-None-Match": tag})
    assert again.status_code == 304


def test_admin_kinds_needs_admin_and_is_not_cached(fx_viewer_client, fx_admin_client):
    assert fx_viewer_client.get("/api/admin/insights/kinds").status_code == 403
    response = fx_admin_client.get("/api/admin/insights/kinds")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "ETag" not in response.headers
    rows = {r["kind"]: r for r in response.json()}
    assert rows["pf.pb"]["count"] > 0
    assert rows["pf.pb"]["dormant"] is False


def test_sunday_feed_gets_an_etag(fx_viewer_client, fx_session):
    day = _held(fx_session)[-1].isoformat()
    first = fx_viewer_client.get(f"/api/insights/sundays/{day}")
    again = fx_viewer_client.get(
        f"/api/insights/sundays/{day}", headers={"If-None-Match": first.headers["ETag"]}
    )
    assert again.status_code == 304


def test_empty_world_feeds_are_empty_with_no_as_of(viewer_client, session):
    session.execute(text("INSERT INTO shooters (id, display_name) VALUES (1, 'Sam')"))
    session.execute(
        text(
            "INSERT INTO shooter_profiles (shooter_id, display_name, status, first_event, "
            "last_event, n_rounds, n_events, left_censored) "
            "VALUES (1, 'Sam', 'active', '2026-01-04', '2026-01-04', 1, 1, false)"
        )
    )
    session.flush()
    for url in ("/api/insights/home", "/api/insights/shooters/1"):
        body = viewer_client.get(url).json()
        assert body["as_of"] is None
        assert (body["top"], body["kudos"], body["more"]) == ([], [], [])
        assert body["pinned"] is None


def test_club_feed_is_empty_before_any_sunday(viewer_client):
    body = viewer_client.get("/api/insights/club").json()
    assert (body["top"], body["more"]) == ([], [])
    assert body["as_of"] is None


def test_supersedes_of_a_removed_kind_is_empty():
    assert supersedes_of("no.such-kind") == frozenset()


def test_kudos_chip_without_a_profile_is_dropped(fx_viewer_client, fx_session, monkeypatch):
    day = fx_session.scalar(
        text(
            "SELECT anchor_date FROM insights WHERE variant = 'rollup' "
            "ORDER BY anchor_date DESC LIMIT 1"
        )
    )
    url = f"/api/insights/sundays/{day.isoformat()}"
    assert fx_viewer_client.get(url).json()["kudos"]
    monkeypatch.setattr(insights_routes, "names", lambda session, ids: {})
    assert fx_viewer_client.get(url).json()["kudos"] == []


def test_admin_readiness_matches_the_engine_on_the_fx_world(fx_session):
    assert readiness_from_db(fx_session) == readiness_of(build_frames(fx_session))
