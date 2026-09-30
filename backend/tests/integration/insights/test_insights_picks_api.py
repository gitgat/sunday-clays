"""Hero and spotlight picks (spec §3.4) and the page feeds on the fx world."""

from sqlalchemy import text


def test_picks_point_at_stored_rows_and_rotate(fx_session):
    picks = fx_session.execute(
        text(
            "SELECT p.sunday, p.slot, i.kind, i.named_shooter_ids FROM insight_picks p "
            "JOIN insights i ON i.key = p.insight_key ORDER BY p.sunday"
        )
    ).all()
    held = list(
        fx_session.scalars(
            text("SELECT event_date FROM events WHERE results_complete ORDER BY event_date")
        )
    )
    hero_at = {day: (kind, list(ids)) for day, slot, kind, ids in picks if slot == "hero"}
    assert len(hero_at) > 100
    for j, day in enumerate(held):
        if day not in hero_at:
            continue
        kind, ids = hero_at[day]
        before = [hero_at[d] for d in held[max(0, j - 4) : j] if d in hero_at]
        assert kind not in {k for k, _ids in before}
        recent = [hero_at[d] for d in held[max(0, j - 3) : j] if d in hero_at]
        assert not set(ids) & {sid for _k, named in recent for sid in named}
    orphans = fx_session.scalar(
        text(
            "SELECT count(*) FROM insight_picks p LEFT JOIN insights i "
            "ON i.key = p.insight_key WHERE i.key IS NULL"
        )
    )
    assert orphans == 0


def test_home_feed_carries_the_latest_picks(fx_viewer_client, fx_session):
    body = fx_viewer_client.get("/api/insights/home").json()
    stored = dict(
        fx_session.execute(
            text(
                "SELECT slot, insight_key FROM insight_picks WHERE sunday = "
                "(SELECT max(event_date) FROM events WHERE results_complete)"
            )
        ).all()
    )
    assert "hero" in stored
    assert body["hero"]["key"] == stored["hero"]
    assert body["hero"]["key"] not in [i["key"] for i in body["top"]]
    if "spotlight" in stored:
        assert body["spotlight"]["key"] == stored["spotlight"]
    assert body["pinned"]["kind"] == "home.sunday-recap"


def test_club_feed_shows_club_rows_only(fx_viewer_client):
    body = fx_viewer_client.get("/api/insights/club").json()
    items = body["top"] + body["more"]
    assert items
    assert {i["subject_type"] for i in items} <= {"club"}
    assert len(body["top"]) <= 3
    assert len({i["family"] for i in body["top"]}) == len(body["top"])


def _page_items(client, path, **params):
    body = client.get(path, params=params).json()
    return body, body["top"] + body["more"]


def test_page_feeds_show_their_own_page_rows(fx_viewer_client, fx_session):
    for page in ("leaderboards", "records"):
        body, items = _page_items(fx_viewer_client, f"/api/insights/{page}")
        stored = fx_session.scalar(
            text("SELECT count(*) FROM insights WHERE :page = ANY(pages)"), {"page": page}
        )
        assert bool(items) == bool(stored), page
        for item in items:
            row_pages = fx_session.scalar(
                text("SELECT pages FROM insights WHERE key = :key"), {"key": item["key"]}
            )
            assert page in row_pages, (page, item["kind"])
        assert len(body["top"]) <= 3
        assert len({i["family"] for i in body["top"]}) == len(body["top"])


def test_leaderboards_feed_is_the_current_season_only(fx_viewer_client):
    current = fx_viewer_client.get("/api/insights/leaderboards").json()
    year = int(current["as_of"][:4])
    same = fx_viewer_client.get("/api/insights/leaderboards", params={"season": year}).json()
    assert same == current
    other = fx_viewer_client.get("/api/insights/leaderboards", params={"season": year - 1}).json()
    assert (other["top"], other["more"], other["n_more"]) == ([], [], 0)


def test_stations_feed_is_empty_while_dormant(fx_viewer_client, fx_session):
    sundays = fx_session.scalar(text("SELECT count(DISTINCT event_date) FROM station_hits"))
    assert sundays < 8  # the fx world has two Sundays of station sheets: the kinds are dormant
    body = fx_viewer_client.get("/api/insights/stations").json()
    assert body["top"] == []
    assert body["more"] == []
