from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.routes import _filters

TODAY = date(2026, 9, 27)


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: TODAY)


def test_regulars_route_defaults_to_today(seed: Any, viewer_client: TestClient) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    for k in range(4):
        d = TODAY - timedelta(days=7 * k)
        seed.round(d, ann, 30)
        if k == 0:
            seed.round(d, bob, 30)
    seed.finish()

    today = viewer_client.get("/api/club/regulars").json()
    past = viewer_client.get("/api/club/regulars", params={"as_of": "2026-09-13"}).json()

    assert (today["as_of"], today["n_held_window"]) == ("2026-09-27", 4)
    assert [c["display_name"] for c in today["core"]] == ["Oakley, Ann"]
    assert (past["n_held_window"], [c["events_attended"] for c in past["core"]]) == (
        2,
        [2],
    )


def test_conversion_parity_and_trends_routes(seed: Any, viewer_client: TestClient) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    seed.round(date(2026, 8, 30), ann, 40, status="guest")
    seed.round(date(2026, 8, 30), bob, 30)
    seed.round(date(2026, 9, 6), ann, 35, status="member")
    seed.round(date(2026, 9, 6), bob, 36)
    seed.finish()
    seed.analyze()

    conversion = viewer_client.get("/api/club/conversion").json()
    parity = viewer_client.get("/api/club/parity", params={"by": "year"}).json()
    trends = viewer_client.get("/api/club/trends").json()

    assert conversion == [
        {"year": 2026, "new_guests": 1, "converted": 1, "median_days_to_convert": 7.0}
    ]
    assert (
        parity[0]["year"],
        parity[0]["n_events"],
        parity[0]["distinct_winners"],
    ) == (2026, 2, 2)
    # 08-30 is both shooters' first event, so they share the prior and it has no favorite;
    # on 09-06 Ann (40 before) is the favorite and Bob wins.
    assert parity[0]["favorite_win_rate"] == 0.0
    assert trends["as_of"] == "2026-09-27"
    assert [(y["year"], y["events_held"]) for y in trends["years"]] == [(2026, 2)]
    assert [e["event_date"] for e in trends["events"]] == ["2026-08-30", "2026-09-06"]
    assert len(trends["months"]) == 12
    assert viewer_client.get("/api/club/parity", params={"by": "month"}).status_code == 422


def test_club_insights_on_committed_fixtures(fx_viewer_client: TestClient) -> None:
    regulars = fx_viewer_client.get("/api/club/regulars").json()
    assert (regulars["n_held_window"], len(regulars["core"])) == (48, 18)
    assert [x["display_name"] for x in regulars["lapsed"]] == ["Nesbitt, Rolf"]
    conversion = {c["year"]: c for c in fx_viewer_client.get("/api/club/conversion").json()}
    assert sum(c["new_guests"] for c in conversion.values()) == 114
    assert {y: c["converted"] for y, c in conversion.items() if c["converted"]} == {
        2022: 2,
        2023: 1,
        2024: 1,
        2025: 2,
        2026: 1,
    }
    assert all(c["converted"] <= c["new_guests"] for c in conversion.values())
    trends = fx_viewer_client.get("/api/club/trends").json()
    assert sum(y["events_held"] for y in trends["years"]) == 310
    assert len(trends["events"]) == 310


def test_club_insights_on_empty_live_tables(viewer_client: TestClient) -> None:
    regulars = viewer_client.get("/api/club/regulars").json()
    trends = viewer_client.get("/api/club/trends").json()

    assert regulars == {"as_of": "2026-09-27", "n_held_window": 0, "core": [], "lapsed": []}
    assert viewer_client.get("/api/club/conversion").json() == []
    assert viewer_client.get("/api/club/parity").json() == []
    assert (trends["years"], trends["events"]) == ([], [])
    assert trends["months"] == [
        {"month": m, "n_events": 0, "mean_head_count": None, "mean_median": None}
        for m in range(1, 13)
    ]


def test_trends_before_metrics_exist(seed: Any, viewer_client: TestClient) -> None:
    # Held events without event_metrics (s10 not run): years count them, the per-event
    # series leaves them out instead of failing.
    ann = seed.shooter("Oakley, Ann")
    seed.round(date(2026, 9, 6), ann, 30)
    seed.finish()

    response = viewer_client.get("/api/club/trends")

    assert response.status_code == 200
    body = response.json()
    assert [(y["year"], y["events_held"]) for y in body["years"]] == [(2026, 1)]
    assert body["events"] == []


def test_club_insights_fixture_details(fx_viewer_client: TestClient) -> None:
    # Computed independently from scores_2026-09-27.xlsx (openpyxl, no app code).
    regulars = fx_viewer_client.get("/api/club/regulars").json()
    assert [(c["display_name"], c["events_attended"]) for c in regulars["core"]] == [
        ("Abernathy, Preston", 46),
        ("Kaplan, Noel", 44),
        ("Hadley, Ike", 42),
        ("Kolmanov, Dmitri", 42),
        ("Waldrop, Quentin", 42),
        ("Fullerton, Tate", 38),
        ("McMurtry, Zeb", 38),
        ("Meadows, Russell", 34),
        ("Cadogan, Desmond", 32),
        ("Alderman, Marlon", 31),
        ("Devlin, Sid", 31),
        ("McGinnis, Alvin", 30),
        ("Nordquist, Sherman", 29),
        ("Dodgson, Nick", 27),
        ("Odell, Norman", 27),
        ("Pomeroy, Leroy", 26),
        ("Stockton, Ethan", 26),
        ("Rookwood, Derek", 25),
    ]
    assert [x["last_event"] for x in regulars["lapsed"]] == ["2026-05-31"]
    conversion = fx_viewer_client.get("/api/club/conversion").json()
    # Cohorts by the year of the first guest round.
    assert [
        (c["year"], c["new_guests"], c["converted"], c["median_days_to_convert"])
        for c in conversion
    ] == [
        (2020, 10, 0, None),
        (2021, 11, 0, None),
        (2022, 8, 2, 798.0),
        (2023, 14, 1, 1029.0),
        (2024, 11, 1, 112.0),
        (2025, 31, 2, 224.0),
        (2026, 29, 1, 217.0),
    ]
    years = fx_viewer_client.get("/api/club/trends").json()["years"]
    assert [(y["year"], y["events_held"], y["ytd_events"]) for y in years] == [
        (2018, 0, 0),
        (2019, 0, 0),
        (2020, 39, 26),
        (2021, 46, 34),
        (2022, 45, 34),
        (2023, 49, 35),
        (2024, 47, 34),
        (2025, 48, 35),
        (2026, 36, 36),
    ]
    assert [y["ytd_events_yoy"] for y in years] == pytest.approx(
        [None, None, None, 8 / 26, 0.0, 1 / 34, -1 / 35, 1 / 34, 1 / 35]
    )


def test_parity_on_committed_fixtures(fx_viewer_client: TestClient) -> None:
    # Computed independently from scores_2026-09-27.xlsx (openpyxl, no app code): per date,
    # every shooter whose best round equals the day's top score wins. Every score date counts,
    # held or not (C7 ranks non-held dates too): 2024 has 47 held events plus 2024-11-10.
    parity = fx_viewer_client.get("/api/club/parity", params={"by": "year"}).json()

    assert [(p["year"], p["n_events"], p["distinct_winners"]) for p in parity] == [
        (2020, 39, 14),
        (2021, 46, 22),
        (2022, 45, 22),
        (2023, 49, 22),
        (2024, 48, 21),
        (2025, 48, 23),
        (2026, 36, 18),
    ]
    assert [p["top3_share"] for p in parity] == pytest.approx(
        [27 / 45, 25 / 59, 23 / 54, 25 / 60, 26 / 66, 23 / 59, 17 / 44]
    )
    assert all(0.0 <= p["favorite_win_rate"] <= 1.0 for p in parity)
