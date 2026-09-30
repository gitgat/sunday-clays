"""GET /api/records on the committed fixtures (golden values: Decision D22)."""

from dataclasses import fields
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, records
from sunday_clays.api.app import create_app
from sunday_clays.api.routes import _filters
from sunday_clays.api.routes import records as records_route
from sunday_clays.api.routes.records import RecordsOut
from sunday_clays.domain.round_type import RoundType

LISTS = (
    "highest_scores",
    "perfect_rounds",
    "biggest_adjusted",
    "biggest_jumps",
    "most_events",
    "longest_streaks",
    "highest_ratings",
)
TODAY = date(2026, 9, 27)


def get_records(client: TestClient, **params: str | list[str]) -> dict[str, Any]:
    response = client.get("/api/records", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
def today(monkeypatch: pytest.MonkeyPatch) -> date:
    monkeypatch.setattr(_filters, "today_local", lambda tz: TODAY)
    return TODAY


def test_records_golden(fx_viewer_client: TestClient, today: date) -> None:
    body = get_records(fx_viewer_client)
    assert body["as_of"] == today.isoformat()
    assert [r["event_date"] for r in body["perfect_rounds"]] == [
        "2025-08-03",
        "2024-11-10",
        "2024-02-25",
        "2023-08-06",
        "2022-12-04",
        "2021-01-17",
    ]
    assert body["totals"]["perfect_rounds"] == 6
    assert [(r["rank"], r["value"]) for r in body["highest_scores"]] == [(1, 50.0)] * 6 + [
        (7, 49.0)
    ] * 4
    assert body["most_events"][0]["value"] == 285.0
    assert body["longest_streaks"][0]["value"] == 56.0
    top = body["biggest_adjusted"][0]
    assert (top["value"], top["event_date"]) == (18.0, "2026-06-07")
    jump = body["biggest_jumps"][0]
    assert (
        jump["prev_event_date"],
        jump["event_date"],
        jump["from_score"],
        jump["to_score"],
        jump["value"],
    ) == ("2021-03-14", "2021-03-21", 11, 41, 30.0)
    ratings = [r["value"] for r in body["highest_ratings"]]
    assert len(ratings) == 10
    assert ratings == sorted(ratings, reverse=True)


def test_highest_ratings_match_each_shooters_peak_mu_after_five_rounds(
    fx_viewer_client: TestClient, fx_session: Session, today: date
) -> None:
    history = frames.load_rating_history(fx_session)
    rounds = frames.load_rounds(fx_session)
    counts = rounds.groupby(["shooter_id", "event_date"]).size().rename("n").reset_index()
    counts["seen"] = counts.groupby("shooter_id")["n"].cumsum()
    seen = history.merge(
        counts[["shooter_id", "event_date", "seen"]], on=["shooter_id", "event_date"]
    )
    seen = seen[seen["seen"] >= 5]
    peak = seen.groupby("shooter_id")["mu"].transform("max")
    peaks = (
        seen[seen["mu"].eq(peak)]
        .groupby("shooter_id")
        .agg(mu=("mu", "first"), day=("event_date", "min"))
    )
    expected = {int(sid): (round(float(r.mu), 2), r.day.isoformat()) for sid, r in peaks.iterrows()}
    rows = get_records(fx_viewer_client)["highest_ratings"]
    assert [r["value"] for r in rows] == sorted((v for v, _ in expected.values()), reverse=True)[
        :10
    ]
    for row in rows:
        assert (row["value"], row["event_date"]) == expected[row["shooter_id"]]


def key(display_name: str) -> str:
    """The workbook identity of a holder, whatever form shooter_profiles displays."""
    return " ".join(display_name.replace(",", " ").casefold().split())


def test_records_golden_holders(fx_viewer_client: TestClient, today: date) -> None:
    body = get_records(fx_viewer_client)
    assert [key(r["display_name"]) for r in body["perfect_rounds"]] == [
        "grimsby gregor",
        "blakeslee ryder",  # 2024-11-10 is not a held event: its rounds still count as records
        "blakeslee ryder",
        "fullerton tate",
        "fullerton tate",
        "linwood luther",
    ]
    assert [(key(r["display_name"]), r["value"]) for r in body["most_events"][:3]] == [
        ("abernathy preston", 285.0),
        ("hadley ike", 267.0),
        ("mcmurtry zeb", 260.0),
    ]
    assert [(key(r["display_name"]), r["value"]) for r in body["longest_streaks"][:3]] == [
        ("eldridge tucker", 56.0),
        ("abernathy preston", 46.0),
        ("mcmurtry zeb", 45.0),
    ]
    assert [
        (r["event_date"], key(r["display_name"]), r["value"]) for r in body["biggest_adjusted"][:3]
    ] == [
        ("2026-06-07", "blakeslee ryder", 18.0),
        ("2021-01-17", "linwood luther", 17.0),
        ("2020-11-29", "townsend abel", 16.0),
    ]
    assert [
        (j["prev_event_date"], j["event_date"], j["from_score"], j["to_score"])
        for j in body["biggest_jumps"][:3]
    ] == [
        ("2021-03-14", "2021-03-21", 11, 41),
        ("2026-05-03", "2026-05-10", 21, 43),
        ("2025-04-27", "2025-05-11", 25, 46),  # 2025-05-04 had no scores
    ]


def test_round_type_filter_restricts_rounds(fx_viewer_client: TestClient, today: date) -> None:
    body = get_records(fx_viewer_client, round_type="super_sporting")
    allowed = {"2026-09-06", "2026-09-13"}
    assert {r["event_date"] for r in body["highest_scores"]} <= allowed
    assert body["highest_scores"][0]["value"] == 48.0
    assert body["perfect_rounds"] == []
    assert max(r["value"] for r in body["most_events"]) == 2.0
    assert max(r["value"] for r in body["longest_streaks"]) == 2.0
    assert all({j["prev_event_date"], j["event_date"]} <= allowed for j in body["biggest_jumps"])
    assert body["highest_ratings"] == get_records(fx_viewer_client)["highest_ratings"]


def test_records_on_an_empty_database(viewer_client: TestClient, today: date) -> None:
    body = get_records(viewer_client)
    assert body["as_of"] == "2026-09-27"
    assert all(body[name] == [] for name in LISTS)


def test_round_types_reach_the_memo_sorted_and_deduplicated(
    viewer_client: TestClient, today: date, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[date, tuple[RoundType, ...]]] = []
    real = records_route.records_for

    def spy(
        session: Session,
        as_of: date,
        round_types: tuple[RoundType, ...],
        since: date | None,
        limit: int | None,
    ) -> Any:
        seen.append((as_of, round_types))
        return real(session, as_of, round_types, since, limit)

    monkeypatch.setattr(records_route, "records_for", spy)
    get_records(viewer_client, round_type=["super_sporting", "sporting", "super_sporting"])
    get_records(viewer_client)
    assert seen == [
        (today, (RoundType.SPORTING, RoundType.SUPER_SPORTING)),
        (today, ()),
    ]


def test_limit_all_lists_every_row_and_totals_count_them(
    fx_viewer_client: TestClient, fx_session: Session, today: date
) -> None:
    default = get_records(fx_viewer_client)
    assert all(len(default[name]) <= 10 for name in LISTS)
    body = get_records(fx_viewer_client, limit="all")
    rounds = frames.load_rounds(fx_session)
    shooters = rounds[rounds["event_date"] <= today]["shooter_id"].nunique()
    assert len(body["most_events"]) == shooters > 10
    assert len(body["longest_streaks"]) > 10
    assert len(body["highest_scores"]) == body["totals"]["highest_scores"] > 10
    assert body["most_events"][:10] == default["most_events"]
    # The default page reports the same totals as the full one, so "Show all N" knows N.
    assert default["totals"] == body["totals"]
    for name in LISTS:
        assert len(body[name]) == body["totals"][name], name


def test_limit_n_returns_the_top_n_and_the_tie_cut(
    fx_viewer_client: TestClient, today: date
) -> None:
    body = get_records(fx_viewer_client, limit="8")
    assert len(body["highest_scores"]) == 8
    # Fixture: six 50s and then 49s. The 8th row is a 49, and more 49s were cut.
    assert body["highest_scores"][-1]["value"] == 49.0
    assert body["tied_more"]["highest_scores"] > 0
    full = get_records(fx_viewer_client, limit="all")
    assert body["tied_more"]["highest_scores"] == sum(
        1 for r in full["highest_scores"][8:] if r["value"] == 49.0
    )
    assert full["tied_more"] == dict.fromkeys(LISTS, 0)


@pytest.mark.parametrize("limit", ["0", "-1", "ten", "", "1000"])
def test_limit_must_be_all_or_a_count(viewer_client: TestClient, limit: str) -> None:
    response = viewer_client.get("/api/records", params={"limit": limit})
    assert response.status_code == 422


def test_limit_above_500_is_rejected_with_a_domain_error(viewer_client: TestClient) -> None:
    ok = viewer_client.get("/api/records", params={"limit": "500"})
    assert ok.status_code == 200
    bad = viewer_client.get("/api/records", params={"limit": "501"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "invalid_limit"


def test_the_default_end_is_the_latest_scored_sunday_not_the_clock(
    fx_viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: date(2030, 1, 1))
    assert get_records(fx_viewer_client)["as_of"] == "2026-09-27"


def test_unknown_round_type_is_422(viewer_client: TestClient) -> None:
    assert viewer_client.get("/api/records", params={"round_type": "trap"}).status_code == 422


def test_records_for_matches_the_past_only_world(fx_session: Session) -> None:
    """No leak on the real fixtures: later Sundays never change the records as of a date."""
    as_of = date(2024, 6, 30)
    rounds = frames.load_rounds(fx_session)
    events = frames.load_events(fx_session)
    history = frames.load_rating_history(fx_session)
    for round_types in ((), (RoundType.SPORTING,)):
        past = records.compute_records(
            rounds[rounds["event_date"] <= as_of],
            events[events["event_date"] <= as_of],
            history[history["event_date"] <= as_of],
            as_of=as_of,
            round_types=round_types,
        )
        assert past.perfect_rounds  # the slice is not vacuous
        assert records.records_for(fx_session, as_of, round_types) == past


def test_records_schema_pins_every_dataclass_field() -> None:
    schemas = create_app().openapi()["components"]["schemas"]
    pairs = {
        "RecordRoundOut": records.RoundRecord,
        "RecordJumpOut": records.JumpRecord,
        "RecordShooterOut": records.ShooterRecord,
        "RecordRatingOut": records.RatingRecord,
        "RecordsOut": records.Records,
    }
    for name, cls in pairs.items():
        expected = {f.name for f in fields(cls)}
        assert set(schemas[name]["properties"]) == expected, name
        # `since` is optional so existing frontend mocks keep typechecking; the rest is pinned.
        optional = {"since"} if name == "RecordsOut" else set()
        assert set(schemas[name]["required"]) == expected - optional, name


def test_as_of_slices_the_records_and_matches_the_analytics(
    fx_viewer_client: TestClient, fx_session: Session, today: date
) -> None:
    body = get_records(fx_viewer_client, as_of="2025-12-31")
    assert body["as_of"] == "2025-12-31"
    assert body["since"] is None
    expected = RecordsOut.model_validate(records.records_for(fx_session, date(2025, 12, 31), ()))
    assert body == expected.model_dump(mode="json")
    assert all(r["event_date"] <= "2025-12-31" for r in body["highest_scores"])


def test_since_limits_records_to_the_range(fx_viewer_client: TestClient, today: date) -> None:
    everything = get_records(fx_viewer_client)
    body = get_records(fx_viewer_client, since="2026-01-01")
    assert body["since"] == "2026-01-01"
    for name in ("highest_scores", "perfect_rounds", "biggest_adjusted", "highest_ratings"):
        assert all(r["event_date"] >= "2026-01-01" for r in body[name]), name
    assert all(j["prev_event_date"] >= "2026-01-01" for j in body["biggest_jumps"])
    assert body["highest_scores"]
    assert body["most_events"][0]["value"] <= everything["most_events"][0]["value"]
    assert body["most_events"][0]["value"] <= 40  # at most this year's Sundays
    assert body["longest_streaks"][0]["value"] <= everything["longest_streaks"][0]["value"]


def test_since_after_as_of_is_400(viewer_client: TestClient, today: date) -> None:
    for params in ({"since": "2026-09-28"}, {"since": "2026-03-02", "as_of": "2026-03-01"}):
        response = viewer_client.get("/api/records", params=params)
        assert response.status_code == 400
        assert response.json() == {
            "error": {"code": "invalid_range", "message": "'since' must be on or before 'as_of'"}
        }
    assert get_records(viewer_client, since="2026-09-27")["since"] == "2026-09-27"


def test_since_and_as_of_reach_the_memo_per_distinct_request(
    viewer_client: TestClient, today: date, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[date, tuple[RoundType, ...], date | None]] = []
    real = records_route.records_for

    def spy(
        session: Session,
        as_of: date,
        round_types: tuple[RoundType, ...],
        since: date | None,
        limit: int | None,
    ) -> Any:
        seen.append((as_of, round_types, since))
        return real(session, as_of, round_types, since, limit)

    monkeypatch.setattr(records_route, "records_for", spy)
    get_records(viewer_client, since="2026-01-01", as_of="2026-06-01", round_type="sporting")
    get_records(viewer_client)
    assert seen == [
        (date(2026, 6, 1), (RoundType.SPORTING,), date(2026, 1, 1)),
        (today, (), None),
    ]


def test_identical_since_requests_share_one_computation(
    viewer_client: TestClient, today: date, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[date | None] = []
    real = records.compute_records

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs.get("since"))
        return real(*args, **kwargs)

    monkeypatch.setattr(records, "compute_records", spy)
    params = {"since": "2026-01-02", "as_of": "2026-06-01", "round_type": "sporting"}
    first = viewer_client.get("/api/records", params=params).json()
    second = viewer_client.get("/api/records", params=params).json()
    assert first == second
    assert calls == [date(2026, 1, 2)]
    get_records(viewer_client, since="2026-01-03", as_of="2026-06-01", round_type="sporting")
    assert calls == [date(2026, 1, 2), date(2026, 1, 3)]
