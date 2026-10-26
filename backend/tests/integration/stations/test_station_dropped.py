"""A thrown-out station leaves station stats and 404s when it was only ever thrown out (T4a)."""

from sqlalchemy import text


def _first_day(s):
    return s.execute(text("SELECT min(event_date) FROM station_layouts")).scalar_one()


def test_a_dropped_station_leaves_station_stats(fx_viewer_client, fx_session):
    first = _first_day(fx_session)
    fx_session.execute(
        text(
            "UPDATE station_layouts SET dropped = true"
            " WHERE station_label = '9' AND event_date = :d"
        ),
        {"d": first},
    )
    body = fx_viewer_client.get("/api/stations").json()
    st = {s["station_no"]: s for s in body["stations"]}
    assert (st[9]["hits"], st[9]["n_targets"], st[9]["n_rounds"], st[9]["n_events"]) == (
        44,
        91,
        13,
        1,
    )
    assert st[4]["n_events"] == 2
    assert body["n_events"] == 2
    assert (first.isoformat(), "9") not in {(e["event_date"], e["label"]) for e in body["by_event"]}
    detail = fx_viewer_client.get("/api/stations/9").json()
    assert first.isoformat() not in {e["event_date"] for e in detail["by_event"]}


def test_a_station_seen_only_thrown_out_is_not_listed_and_404s(fx_viewer_client, fx_session):
    fx_session.execute(text("UPDATE station_layouts SET dropped = true WHERE station_label = '10'"))
    body = fx_viewer_client.get("/api/stations").json()
    assert "10" not in {s["label"] for s in body["stations"]}
    assert all(c["label"] != "10" for c in body["matrix"])
    response = fx_viewer_client.get("/api/stations/10")
    assert (response.status_code, response.json()["error"]["code"]) == (404, "station_not_found")
    assert fx_viewer_client.get("/api/stations/9").status_code == 200


def test_a_lettered_station_seen_only_thrown_out_404s(fx_viewer_client, fx_session):
    first = _first_day(fx_session)
    fx_session.execute(
        text(
            "INSERT INTO station_layouts (event_date, station_label, station_no, target_count,"
            " source_import_id, dropped, dropped_source)"
            " SELECT event_date, '7A', station_no, target_count, source_import_id, true, 'auto'"
            " FROM station_layouts WHERE event_date = :d AND station_label = '7'"
        ),
        {"d": first},
    )
    fx_session.execute(
        text(
            "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id,"
            " entry_row, name_key, shooter_id, round_id, hits)"
            " SELECT h.event_date, h.station_no, '7A', h.sheet_id, h.entry_row, h.name_key,"
            " h.shooter_id, h.round_id, l.target_count"
            " FROM station_hits h JOIN station_layouts l"
            " ON l.event_date = h.event_date AND l.station_label = '7A'"
            " WHERE h.event_date = :d AND h.station_label = '7'"
        ),
        {"d": first},
    )
    assert fx_viewer_client.get("/api/stations/7A").status_code == 404
    assert fx_viewer_client.get("/api/stations/7").status_code == 200
