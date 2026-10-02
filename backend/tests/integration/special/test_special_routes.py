"""The API with a special Sunday (Plan 17 Task 5, Review Focus 1, 2 and 3).

Score routes answer exactly as in the regular world; appearance routes count the special Sunday.
"""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import clear_cache

SPECIAL, BEFORE, AFTER = "2026-09-20", "2026-09-13", "2026-09-27"
SCORE_LISTS = (
    "highest_scores",
    "perfect_rounds",
    "biggest_adjusted",
    "biggest_jumps",
    "highest_ratings",
)


def _get(client: TestClient, url: str) -> Any:
    response = client.get(url)
    assert response.status_code == 200, response.text
    return response.json()


def _without_round_ids(body: Any) -> Any:
    """Round ids are surrogate keys that differ between the two worlds' databases."""
    if isinstance(body, dict):
        return {k: _without_round_ids(v) for k, v in body.items() if k != "round_id"}
    if isinstance(body, list):
        return [_without_round_ids(v) for v in body]
    return body


def _both(base: TestClient, special: TestClient, url: str) -> tuple[Any, Any]:
    clear_cache()
    left = _get(base, url)
    clear_cache()
    return _without_round_ids(left), _without_round_ids(_get(special, url))


def _id(client: TestClient, name: str) -> int:
    (match,) = [
        s
        for s in _get(client, f"/api/shooters?q={name.split(',')[0]}")
        if s["display_name"] == name
    ]
    return int(match["shooter_id"])


@pytest.mark.parametrize(
    "url",
    [
        "/api/leaderboards?period=all_time&metric=avg_score",
        f"/api/leaderboards?period=ytd&metric=best_score&as_of={AFTER}",
        "/api/leaderboards?period=all_time&metric=wins",
        "/api/leaderboards?period=all_time&metric=rounds",
        f"/api/leaderboards?period=rolling_12&metric=season_points&as_of={AFTER}",
        "/api/leaderboards?period=all_time&metric=events&gauge=unspecified",
        "/api/club/distribution",
        "/api/club/first-rounds",
        "/api/club/parity",
        "/api/club/conversion",
        f"/api/club/regulars?as_of={AFTER}",
        "/api/stations",
        "/api/weather/effects",
        f"/api/on-this-day?date={AFTER}",
    ],
)
def test_score_routes_answer_exactly_as_without_the_special_sunday(
    url: str, fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    base, special = _both(fx_viewer_client, fx_special_viewer_client, url)
    assert special == base


def test_a_shooters_score_views_are_unchanged(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    for tail in ("rounds", "rating", "splits?by=year", "stations"):
        base, special = _both(
            fx_viewer_client, fx_special_viewer_client, f"/api/shooters/{hadley}/{tail}"
        )
        assert special == base, tail
    query = {"metric": "score", "agg": "avg", "group_by": ["year"]}
    attendance = {"metric": "attendance", "agg": "avg", "group_by": ["year"]}
    for spec in (query, attendance):  # Explorer stays on scored Sundays (Decision 8)
        clear_cache()
        base_response = fx_viewer_client.post("/api/explore", json=spec)
        assert base_response.status_code == 200, base_response.text
        clear_cache()
        assert (
            fx_special_viewer_client.post("/api/explore", json=spec).json() == base_response.json()
        )


def test_insight_feeds_reference_regular_sundays_only(
    fx_viewer_client: TestClient,
    fx_special_viewer_client: TestClient,
    fx_session: Session,
    fx_special_session: Session,
) -> None:
    """The feeds' reference Sunday, home window and expiry count regular held Sundays only
    (Decision 12): the special Sunday never ages an insight or becomes the reference.

    The home feed cannot be compared whole: Decision 7's appearance and club-turnout kinds
    legitimately change in it. A shooter who skipped the special Sunday has no such kind, so that
    profile feed must match exactly; if it does not, find the kind that moved before touching
    this test."""
    from sunday_clays.api.routes.insights import held_dates

    held = held_dates(fx_special_session)
    assert held == held_dates(fx_session)
    assert date.fromisoformat(SPECIAL) not in held

    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/insights/home")
    assert special["as_of"] == base["as_of"] != SPECIAL

    at_special = {
        r["shooter_id"] for r in _get(fx_special_viewer_client, f"/api/events/{SPECIAL}")["results"]
    }
    skipped = min(
        r["shooter_id"]
        for r in _get(fx_viewer_client, f"/api/events/{AFTER}")["results"]
        if r["shooter_id"] not in at_special
    )
    url = f"/api/insights/shooters/{skipped}?all=true"
    base, special = _both(fx_viewer_client, fx_special_viewer_client, url)
    base.pop("data_version")
    special.pop("data_version")
    assert special == base

    feed = _get(fx_special_viewer_client, f"/api/insights/sundays/{SPECIAL}")
    assert (feed["hero"], feed["top"], feed["kudos"], feed["more"]) == (None, [], [], [])


def test_records_keep_score_lists_and_count_the_special_sunday_in_sundays_and_runs(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    base, special = _both(
        fx_viewer_client, fx_special_viewer_client, f"/api/records?as_of={AFTER}&limit=all"
    )
    for name in SCORE_LISTS:
        assert special[name] == base[name], name
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    kim = _id(fx_special_viewer_client, "Kim, Pat")

    def value(body: dict[str, Any], name: str, sid: int) -> float | None:
        return next((r["value"] for r in body[name] if r["shooter_id"] == sid), None)

    assert value(special, "most_events", hadley) == value(base, "most_events", hadley) + 1
    assert value(special, "most_events", kim) == 1
    assert value(special, "longest_streaks", kim) == 1


def test_the_sundays_board_counts_the_special_sunday(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    url = f"/api/leaderboards?period=ytd&metric=events&as_of={AFTER}"
    base, special = _both(fx_viewer_client, fx_special_viewer_client, url)
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    kim = _id(fx_special_viewer_client, "Kim, Pat")
    before = {r["shooter_id"]: r["value"] for r in base["rows"]}
    after = {r["shooter_id"]: r["value"] for r in special["rows"]}

    assert after[hadley] == before[hadley] + 1
    assert after[kim] == 1
    assert kim not in before
    assert special["event_dates"] == base["event_dates"]  # the scored Sundays


def test_the_sunday_payloads_mark_the_special_sunday(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/events?year=2026")
    extra = [e for e in special if e["event_date"] == SPECIAL]
    assert [e for e in special if e["event_date"] != SPECIAL] == base
    (row,) = extra
    assert (row["kind"], row["label"], row["target_total"]) == ("special", "Three Clay Shoot", 60)
    assert (row["n_shooters"], row["median"], row["top_score"], row["winners"]) == (
        5,
        None,
        None,
        [],
    )
    assert {e["kind"] for e in base} == {"regular"}

    clear_cache()
    assert fx_viewer_client.get(f"/api/events/{SPECIAL}").status_code == 404
    clear_cache()
    detail = _get(fx_special_viewer_client, f"/api/events/{SPECIAL}")
    assert (detail["kind"], detail["label"], detail["target_total"]) == (
        "special",
        "Three Clay Shoot",
        60,
    )
    assert [(r["display_name"], r["score"]) for r in detail["results"]] == [
        ("Hadley, Ike", 55),
        ("Kaplan, Noel", 51),
        ("Devlin, Sid", 48),
        ("Abernathy, Preston", 44),
        ("Kim, Pat", 39),
    ]
    assert {
        (r["event_rank"], r["adjusted"], r["rating_delta"], r["is_best_round"])
        for r in detail["results"]
    } == {(None, None, None, True)}
    assert [s["label"] for s in detail["stations"]["layout"]] == [str(n) for n in range(1, 11)]
    assert {s["target_count"] for s in detail["stations"]["layout"]} == {6}
    assert sorted(e["total"] for e in detail["stations"]["entries"]) == [39, 44, 48, 51, 55]
    assert [(n["kind"], n["display_name"]) for n in detail["notables"]] == [
        ("first_timer", "Kim, Pat")
    ]
    assert detail["vs_prev"] is None
    assert detail["median"] is None
    assert detail["difficulty"] is None

    base_after, special_after = _both(
        fx_viewer_client, fx_special_viewer_client, f"/api/events/{AFTER}"
    )
    assert special_after == base_after
    assert special_after["vs_prev"]["prev_date"] == BEFORE  # never the special Sunday

    base_rows, special_rows = _both(
        fx_viewer_client, fx_special_viewer_client, "/api/club/attendance"
    )
    assert [r for r in special_rows if r["event_date"] != SPECIAL] == base_rows
    (attendance,) = [r for r in special_rows if r["event_date"] == SPECIAL]
    assert (attendance["kind"], attendance["n_shooters"], attendance["target_total"]) == (
        "special",
        5,
        60,
    )


def test_odometer_counts_the_special_sunday(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    base, special = _both(fx_viewer_client, fx_special_viewer_client, f"/api/shooters/{hadley}")

    for key in ("clays_thrown", "clays_broken", "hit_pct", "rounds"):  # trophies move (Task 4)
        assert special["odometer"][key] == base["odometer"][key], key
    assert special["odometer"]["events"] == base["odometer"]["events"] + 1
    assert special["odometer"]["years_active"] == base["odometer"]["years_active"]
    assert special["odometer"]["current_streak"] == base["odometer"]["current_streak"] + 1
    assert special["stats"] == base["stats"]
    assert special["pbs"] == base["pbs"]
    clear_cache()
    assert _get(fx_viewer_client, f"/api/shooters/{hadley}/special") == []
    clear_cache()
    assert _get(fx_special_viewer_client, f"/api/shooters/{hadley}/special") == [
        {
            "round_id": special_round_id(fx_special_viewer_client, hadley),
            "event_date": SPECIAL,
            "label": "Three Clay Shoot",
            "target_total": 60,
            "score": 55,
        }
    ]
    base_dir, special_dir = _both(fx_viewer_client, fx_special_viewer_client, "/api/shooters")
    row = {s["shooter_id"]: s for s in special_dir}
    was = {s["shooter_id"]: s for s in base_dir}
    assert row[hadley]["n_events"] == was[hadley]["n_events"] + 1
    assert row[hadley]["n_rounds"] == was[hadley]["n_rounds"]


def special_round_id(client: TestClient, shooter_id: int) -> int:
    detail = _get(client, f"/api/events/{SPECIAL}")
    return next(int(r["round_id"]) for r in detail["results"] if r["shooter_id"] == shooter_id)


def test_a_special_only_shooter_has_a_working_profile(
    fx_special_viewer_client: TestClient,
) -> None:
    client = fx_special_viewer_client
    kim = _id(client, "Kim, Pat")

    (listed,) = [s for s in _get(client, "/api/shooters") if s["shooter_id"] == kim]
    assert (listed["n_rounds"], listed["n_events"], listed["active"], listed["mu"]) == (
        0,
        1,
        False,
        None,
    )
    detail = _get(client, f"/api/shooters/{kim}")
    assert detail["stats"]["n_rounds"] == 0
    assert detail["stats"]["avg_score"] is None
    assert detail["stats"]["best_score"] is None
    odometer = detail["odometer"]
    assert (odometer["events"], odometer["rounds"], odometer["clays_thrown"]) == (1, 0, 0)
    assert odometer["hit_pct"] is None
    assert (odometer["current_streak"], odometer["longest_streak"]) == (0, 1)
    assert detail["pbs"] == []
    assert _get(client, f"/api/shooters/{kim}/rounds") == []
    assert _get(client, f"/api/shooters/{kim}/rating")["points"] == []
    assert _get(client, f"/api/shooters/{kim}/splits?by=year") == []
    insights = _get(client, f"/api/shooters/{kim}/insights")
    assert insights["n_rounds"] == 0
    assert (insights["milestone"]["next_events"], insights["milestone"]["events_to_go"]) == (10, 9)
    assert [s["score"] for s in _get(client, f"/api/shooters/{kim}/special")] == [39]
    assert _get(client, f"/api/yir/2026/shooters/{kim}")["totals"]["events"] == 1
    assert client.get(f"/api/shooters/{kim}/stations").status_code == 200


def test_club_turnout_cohorts_trends_and_year_count_the_special_sunday(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    window = f"/api/club/summary?since=2026-09-01&as_of={AFTER}"
    base, special = _both(fx_viewer_client, fx_special_viewer_client, window)
    for key in (
        "n_rounds",
        "avg_score",
        "median_score",
        "top_score",
        "n_perfect",
        "clays_thrown",
        "clays_broken",
        "n_scored_events",
        "first_event",
        "last_event",
        "avg_head_count",
        "status_by_year",
    ):
        assert special[key] == base[key], key
    assert special["n_events"] == base["n_events"] + 1
    assert special["n_held_events"] == base["n_held_events"] + 1
    assert special["n_shooters"] == base["n_shooters"] + 1  # Kim, Pat

    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/club/cohorts")
    new = {c["year"]: c["n_new"] for c in special}
    old = {c["year"]: c["n_new"] for c in base}
    assert new[2026] == old[2026] + 1
    assert {y: n for y, n in new.items() if y != 2026} == {
        y: n for y, n in old.items() if y != 2026
    }

    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/club/trends")
    year = {y["year"]: y for y in special["years"]}[2026]
    was = {y["year"]: y for y in base["years"]}[2026]
    assert year["events_held"] == was["events_held"] + 1
    assert year["unique_shooters"] == was["unique_shooters"] + 1
    assert year["ytd_rounds"] == was["ytd_rounds"]
    assert special["events"] == base["events"]
    september = {m["month"]: m for m in special["months"]}[9]
    assert september["n_events"] == {m["month"]: m for m in base["months"]}[9]["n_events"] + 1
    assert september["mean_median"] == {m["month"]: m for m in base["months"]}[9]["mean_median"]

    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/yir/2026")
    assert special["totals"]["held_events"] == base["totals"]["held_events"] + 1
    assert special["totals"]["shooters"] == base["totals"]["shooters"] + 1
    for key in ("rounds", "clays_thrown", "clays_broken", "avg_score", "scored_events"):
        assert special["totals"][key] == base["totals"][key], key
    assert special["top_rounds"] == base["top_rounds"]
    assert special["perfect_rounds"] == base["perfect_rounds"]


def test_the_year_in_review_counts_a_special_only_shooter_as_a_newcomer(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/yir/2026")
    assert special["newcomers"] == base["newcomers"] + 1  # Kim, Pat's first Sunday


def test_the_special_list_is_a_404_for_an_unknown_shooter(
    fx_special_viewer_client: TestClient,
) -> None:
    response = fx_special_viewer_client.get("/api/shooters/999999/special")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"


def test_the_special_list_is_oldest_first(
    fx_special_viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pandas as pd

    from sunday_clays.analytics import frames

    hadley = _id(fx_special_viewer_client, "Hadley, Ike")
    shoots = [  # a newer Sunday listed first, and two rounds on one Sunday
        (3, date(2026, 9, 20), 1, 55, "Three Clay Shoot"),
        (1, date(2026, 3, 1), 2, 40, "Four Bird Shoot"),
        (2, date(2026, 3, 1), 1, 44, "Four Bird Shoot"),
    ]
    frame = pd.DataFrame(
        [
            {
                "round_id": rid,
                "event_date": day,
                "shooter_id": hadley,
                "name_key": "hadley ike",
                "display_name": "Hadley, Ike",
                "shooter_status": "member",
                "ordinal": ordinal,
                "score": score,
                "label": label,
                "target_total": 60,
            }
            for rid, day, ordinal, score, label in shoots
        ],
        columns=list(frames.SPECIAL_ROUND_COLUMNS),
    )
    monkeypatch.setattr(frames, "load_special_rounds", lambda session: frame)

    body = _get(fx_special_viewer_client, f"/api/shooters/{hadley}/special")

    assert [(r["event_date"], r["round_id"], r["score"]) for r in body] == [
        ("2026-03-01", 2, 44),
        ("2026-03-01", 1, 40),
        ("2026-09-20", 3, 55),
    ]


@pytest.mark.parametrize(
    ("model", "route"),
    [
        ("EventSummaryOut", "events"),
        ("EventDetailOut", "events"),
        ("AttendanceOut", "club"),
    ],
)
def test_the_special_fields_are_required_in_the_openapi_schema(model: str, route: str) -> None:
    """Required, so the frontend types are not optional (a regular Sunday answers regular)."""
    from sunday_clays.api.app import create_app

    schema = create_app().openapi()["components"]["schemas"][model]
    assert {"kind", "label", "target_total"} <= set(schema["required"]), route
