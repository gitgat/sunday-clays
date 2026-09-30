from datetime import date, timedelta
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.api.app import create_app
from sunday_clays.station_label import label_number, parse_label

D1 = date(2026, 8, 30)
D2 = date(2026, 9, 6)
D3 = date(2026, 9, 13)


def test_detail_path_is_the_c8_template() -> None:
    # C8 fixes `/api/events/{date}`; Plan 08 indexes `paths['/api/events/{date}']` and
    # sends `params: {path: {date}}`, so the generated key and param name are the contract.
    detail = create_app().openapi()["paths"]["/api/events/{date}"]["get"]
    assert [p["name"] for p in detail["parameters"] if p["in"] == "path"] == ["date"]


def test_list_events_in_date_order_with_attendance_only_and_tied_winners(
    seed: Any, viewer_client: TestClient
) -> None:
    ann, bob, cat = (seed.shooter(n) for n in ("Oakley, Ann", "Pratt, Bob", "Quinn, Cat"))
    seed.event(D1, head_count=3)
    seed.event(D2, held=False, has_scores=False, head_count=9)
    for sid, score in ((ann, 40), (bob, 35), (cat, 30)):
        seed.round(D1, sid, score)
    for sid, score in ((ann, 44), (bob, 44), (cat, 30)):
        seed.round(D3, sid, score)
    seed.finish()
    seed.analyze()

    body = viewer_client.get("/api/events").json()

    assert [e["event_date"] for e in body] == ["2026-08-30", "2026-09-06", "2026-09-13"]
    attendance_only = body[1]
    assert (attendance_only["has_scores"], attendance_only["head_count"]) == (False, 9)
    assert attendance_only["winners"] == []
    assert [w["display_name"] for w in body[2]["winners"]] == [
        "Oakley, Ann",
        "Pratt, Bob",
    ]
    assert body[0]["median"] == 35.0
    assert body[0]["top_score"] == 40


def test_list_events_on_empty_live_tables(viewer_client: TestClient) -> None:
    # Review Focus 4: empty live tables give an empty list, never a 500.
    assert viewer_client.get("/api/events").json() == []
    assert viewer_client.get("/api/events", params={"year": 2026}).json() == []


def test_route_orders_events_itself(
    seed: Any, viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # D16's ascending list and vs_prev's "previous held event" belong to the route, not to
    # load_events' SQL ORDER BY: serve the loader's frame newest-first and expect the same.
    load_events = frames.load_events

    def newest_first(session: Session) -> pd.DataFrame:
        return load_events(session).iloc[::-1]

    monkeypatch.setattr(frames, "load_events", newest_first)
    ann = seed.shooter("Oakley, Ann")
    for d, score in ((D1 - timedelta(days=7), 30), (D1, 35), (D2, 40), (D3, 45)):
        seed.round(d, ann, score)
    seed.finish()
    seed.analyze()

    listed = viewer_client.get("/api/events").json()
    vs_prev = viewer_client.get(f"/api/events/{D3}").json()["vs_prev"]

    assert [e["event_date"] for e in listed] == [
        "2026-08-23",
        "2026-08-30",
        "2026-09-06",
        "2026-09-13",
    ]
    assert (vs_prev["prev_date"], vs_prev["top_score_delta"]) == ("2026-09-06", 5)


def test_list_events_year_filter(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(date(2025, 12, 28), ann, 30)
    seed.round(date(2026, 1, 4), ann, 31)
    seed.finish()

    body = viewer_client.get("/api/events", params={"year": 2026}).json()

    assert [e["event_date"] for e in body] == ["2026-01-04"]


def test_list_events_from_to_window_is_inclusive_and_open_ended(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    for d in (D1, D2, D3):
        seed.round(d, ann, 30)
    seed.finish()

    both = viewer_client.get("/api/events", params={"from": str(D1), "to": str(D2)}).json()
    only_from = viewer_client.get("/api/events", params={"from": str(D2)}).json()
    only_to = viewer_client.get("/api/events", params={"to": str(D2)}).json()
    inside_year = viewer_client.get(
        "/api/events", params={"year": 2026, "from": str(D2), "to": str(D3)}
    ).json()

    assert [e["event_date"] for e in both] == ["2026-08-30", "2026-09-06"]
    assert [e["event_date"] for e in only_from] == ["2026-09-06", "2026-09-13"]
    assert [e["event_date"] for e in only_to] == ["2026-08-30", "2026-09-06"]
    assert [e["event_date"] for e in inside_year] == ["2026-09-06", "2026-09-13"]


def test_round_type_filter_restricts_rounds(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    for d, rt in ((D1, "sporting"), (D2, "super_sporting"), (D3, "sporting")):
        seed.event(d, round_type=rt)
        seed.round(d, ann, 30)
    seed.finish()

    one = viewer_client.get("/api/events", params={"round_type": "sporting"}).json()
    two = viewer_client.get("/api/events", params={"round_type": "super_sporting"}).json()
    bad = viewer_client.get("/api/events", params={"round_type": "trap"})

    assert [e["event_date"] for e in one] == ["2026-08-30", "2026-09-13"]
    assert [e["event_date"] for e in two] == ["2026-09-06"]
    assert bad.status_code == 422


def test_event_detail_unknown_date_is_404(viewer_client: TestClient) -> None:
    r = viewer_client.get("/api/events/2001-01-07")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "event_not_found"


def test_event_detail_results_ranks_and_rating_delta(seed: Any, viewer_client: TestClient) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    seed.event(D3, head_count=2, round_type="sporting")
    seed.round(D3, ann, 44)
    seed.round(D3, ann, 30)
    seed.round(D3, bob, 42)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(f"/api/events/{D3}").json()

    assert (body["round_type"], body["round_type_source"], body["head_count"]) == (
        "sporting",
        "override",
        2,
    )
    assert body["has_scores"] is True
    assert body["difficulty"] == pytest.approx(0.0, abs=1e-6)
    assert [(r["display_name"], r["score"], r["event_rank"]) for r in body["results"]] == [
        ("Oakley, Ann", 44, 1),
        ("Pratt, Bob", 42, 2),
        ("Oakley, Ann", 30, None),
    ]
    # name_key + ordinal (with the date) is what the admin round picker sends in a
    # score_override / hide_round payload (C5); the seed stores name.casefold() minus ","
    assert [r["name_key"] for r in body["results"]] == [
        "oakley ann",
        "pratt bob",
        "oakley ann",
    ]
    assert [r["ordinal"] for r in body["results"]] == [1, 1, 2]
    first = body["results"][0]
    assert first["rating_delta"] == pytest.approx(first["mu_after"] - first["mu_before"])
    assert body["weather"] is None
    assert body["stations"] is None
    assert body["vs_prev"] is None


def test_event_detail_attendance_only(seed: Any, viewer_client: TestClient) -> None:
    seed.event(D2, held=False, has_scores=False, head_count=9)
    seed.finish()

    body = viewer_client.get(f"/api/events/{D2}").json()

    assert (body["has_scores"], body["head_count"], body["results"]) == (False, 9, [])
    assert body["median"] is None
    assert body["difficulty"] is None


def test_event_detail_weather_card(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D3, ann, 30)
    seed.weather(D3, temp_f=41.0, gust_mph=24.0, precip_in=0.1, condition="rain")
    seed.finish()

    weather = viewer_client.get(f"/api/events/{D3}").json()["weather"]

    assert (weather["temp_f"], weather["gust_mph"], weather["condition"]) == (
        41.0,
        24.0,
        "rain",
    )
    assert weather["pressure_hpa"] == 1015.0


def test_notables_personal_best_and_first_timers(seed: Any, viewer_client: TestClient) -> None:
    vet = seed.shooter("Oakley, Ann")
    short = seed.shooter("Pratt, Bob")
    rookie = seed.shooter("Quinn, Cat")
    returning = seed.shooter("Reyes, Dan", left_censored=True)
    for week in range(5):
        seed.round(D3 - timedelta(days=7 * (week + 1)), vet, 40 - week)
    for week in range(4):
        seed.round(D3 - timedelta(days=7 * (week + 1)), short, 20)
    seed.round(D3, vet, 41)
    seed.round(D3, short, 45)
    seed.round(D3, rookie, 30)
    seed.round(D3, returning, 30)
    seed.finish()
    seed.analyze()

    notables = viewer_client.get(f"/api/events/{D3}").json()["notables"]

    assert [(n["kind"], n["display_name"], n["value"]) for n in notables] == [
        ("pb", "Oakley, Ann", 41.0),
        ("first_timer", "Quinn, Cat", None),
    ]


def test_no_personal_best_when_only_matching_the_prior_best(
    seed: Any, viewer_client: TestClient
) -> None:
    # C12 personal_bests: the day's best must be strictly greater than every earlier round.
    vet = seed.shooter("Oakley, Ann")
    for week in range(5):
        seed.round(D3 - timedelta(days=7 * (week + 1)), vet, 40 - week)
    seed.round(D3, vet, 40)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(f"/api/events/{D3}").json()

    assert body["results"][0]["is_best_round"] is True
    assert body["notables"] == []


def _five_regulars(seed: Any) -> list[int]:
    ids = [seed.shooter(f"Shooter, {c}") for c in "ABCDE"]
    for week in range(1, 5):
        for sid, score in zip(ids, (45, 40, 35, 30, 25), strict=True):
            seed.round(D3 - timedelta(days=7 * week), sid, score)
    return ids


def test_notables_no_leak(seed: Any, viewer_client: TestClient) -> None:
    # Review Focus 5: D3's notables are the same whether or not later events exist.
    ids = _five_regulars(seed)
    seed.round(D3 - timedelta(days=35), ids[3], 30)  # D's 5th earlier round: a PB is possible
    rookie = seed.shooter("Quinn, Cat")
    for sid, score in zip([*ids, rookie], (44, 39, 34, 49, 24, 20), strict=True):
        seed.round(D3, sid, score)
    seed.finish()
    seed.analyze()
    before = viewer_client.get(f"/api/events/{D3}").json()["notables"]

    later = D3 + timedelta(days=7)
    # D beats their D3 score, the rookie returns and a new shooter first appears later on
    for sid, score in zip([*ids, rookie], (40, 41, 42, 50, 43, 45), strict=True):
        seed.round(later, sid, score)
    seed.round(later, seed.shooter("Reyes, Dan"), 30)
    seed.event(later + timedelta(days=7), held=False, has_scores=False, head_count=4)
    seed.finish()
    seed.analyze()
    after = viewer_client.get(f"/api/events/{D3}").json()["notables"]

    assert [(n["kind"], n["display_name"]) for n in before] == [
        ("pb", "Shooter, D"),
        ("first_timer", "Quinn, Cat"),
    ]
    assert after == before


def test_vs_prev_skips_non_held_events(seed: Any, viewer_client: TestClient) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    seed.event(D1, head_count=10)
    seed.event(D2, held=False, head_count=30)
    seed.event(D3, head_count=6)
    for d, a, b in ((D1, 40, 30), (D2, 20, 20), (D3, 44, 38)):
        seed.round(d, ann, a)
        seed.round(d, bob, b)
    seed.finish()
    seed.analyze()

    vs_prev = viewer_client.get(f"/api/events/{D3}").json()["vs_prev"]

    assert vs_prev["prev_date"] == "2026-08-30"
    assert vs_prev["head_count_delta"] == -4
    assert vs_prev["median_delta"] == pytest.approx(6.0)
    assert vs_prev["top_score_delta"] == 4
    assert vs_prev["difficulty_delta"] is not None


def _station_sheet(
    session: Session,
    d: date,
    targets: dict[int | str, int],
    entries: list[tuple[int, str, int | None, int | None, tuple[int, ...]]],
) -> None:
    """station_layouts + station_hits rows for one sheet; `entries` = (row, key, sid, rid, hits).

    `targets` keys are station labels: 1, 2 or "7A"."""
    for station, target_count in targets.items():
        label = str(parse_label(station))
        session.execute(
            text(
                "INSERT INTO station_layouts (event_date, station_no, station_label,"
                " target_count, source_import_id) VALUES (:d, :s, :l, :t, 1)"
            ),
            {"d": d, "s": label_number(label), "l": label, "t": target_count},
        )
    for entry_row, name_key, shooter_id, round_id, hits in entries:
        for station, n in zip(targets, hits, strict=True):
            label = str(parse_label(station))
            session.execute(
                text(
                    "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id,"
                    " entry_row, name_key, shooter_id, round_id, hits)"
                    " VALUES (:d, :s, :l, 1, :row, :k, :sid, :rid, :h)"
                ),
                {
                    "d": d,
                    "s": label_number(label),
                    "l": label,
                    "row": entry_row,
                    "k": name_key,
                    "sid": shooter_id,
                    "rid": round_id,
                    "h": n,
                },
            )


def test_station_matrix_keeps_unlinked_entries(seed: Any, viewer_client: TestClient) -> None:
    # C4/C5: a stations-sheet name that matched no shooter keeps its row with null ids, and
    # its total is still the sum of its hits (Plan 08's StationMatrixOut renders such rows).
    ann = seed.shooter("Oakley, Ann")
    seed.event(D3, has_stations=True)
    ann_round = seed.round(D3, ann, 13)
    _station_sheet(
        seed.session,
        D3,
        {1: 7, 2: 8},
        [(1, "oakley ann", ann, ann_round, (6, 7)), (2, "stranger zed", None, None, (5, 4))],
    )
    seed.finish()

    stations = viewer_client.get(f"/api/events/{D3}").json()["stations"]

    assert stations["layout"] == [
        {"label": "1", "station_no": 1, "target_count": 7},
        {"label": "2", "station_no": 2, "target_count": 8},
    ]
    assert stations["entries"] == [
        {
            "entry_row": 1,
            "name_key": "oakley ann",
            "shooter_id": ann,
            "display_name": "Oakley, Ann",
            "round_id": ann_round,
            "hits": [
                {"label": "1", "station_no": 1, "hits": 6},
                {"label": "2", "station_no": 2, "hits": 7},
            ],
            "total": 13,
        },
        {
            "entry_row": 2,
            "name_key": "stranger zed",
            "shooter_id": None,
            "display_name": None,
            "round_id": None,
            "hits": [
                {"label": "1", "station_no": 1, "hits": 5},
                {"label": "2", "station_no": 2, "hits": 4},
            ],
            "total": 9,
        },
    ]


def test_station_matrix_lists_a_lettered_station_after_its_number(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.event(D3, has_stations=True)
    ann_round = seed.round(D3, ann, 20)
    _station_sheet(
        seed.session,
        D3,
        {8: 6, "7A": 8, 7: 6},
        [(1, "oakley ann", ann, ann_round, (6, 8, 6))],
    )
    seed.finish()

    stations = viewer_client.get(f"/api/events/{D3}").json()["stations"]

    assert [(s["label"], s["station_no"]) for s in stations["layout"]] == [
        ("7", 7),
        ("7A", 7),
        ("8", 8),
    ]
    [entry] = stations["entries"]
    assert [(h["label"], h["hits"]) for h in entry["hits"]] == [("7", 6), ("7A", 8), ("8", 6)]
    assert entry["total"] == 20


def test_station_event_on_committed_fixtures(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/events/2026-09-13").json()

    assert (body["round_type"], body["round_type_source"]) == (
        "super_sporting",
        "stations",
    )
    assert (body["head_count"], body["n_shooters"], body["top_score"]) == (13, 13, 42)
    assert body["median"] == 34.0
    layout = body["stations"]["layout"]
    assert [s["station_no"] for s in layout] == [4, 5, 6, 7, 8, 9, 10]
    assert [s["target_count"] for s in layout] == [7, 7, 7, 7, 7, 7, 8]
    entries = {e["name_key"]: e for e in body["stations"]["entries"]}
    assert len(entries) == 13
    hadley = entries["hadley ike"]
    assert hadley["total"] == 36
    assert len(hadley["hits"]) == 7
    hadley_result = next(r for r in body["results"] if r["round_id"] == hadley["round_id"])
    assert hadley_result["score"] == 34
    assert body["results"][0]["display_name"].startswith("Nordquist")
    assert body["vs_prev"]["prev_date"] == "2026-09-06"
    assert body["vs_prev"]["head_count_delta"] == -11
    assert body["vs_prev"]["top_score_delta"] == -6
