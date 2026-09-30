from datetime import date
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from sunday_clays.analytics import cohorts
from sunday_clays.api.app import create_app

D1 = date(2025, 8, 31)
D2 = date(2026, 9, 6)
D3 = date(2026, 9, 13)


def test_club_openapi_paths_and_response_schemas() -> None:
    # Plan 08 T3 indexes these C8 path keys and checks these component names in schema.d.ts.
    spec = create_app().openapi()
    routes = {  # path: (query params, response model, is a list)
        "/api/club/summary": (["round_type", "since", "as_of"], "ClubSummaryOut", False),
        "/api/club/attendance": ([], "AttendanceOut", True),
        "/api/club/cohorts": ([], "CohortOut", True),
        "/api/club/distribution": (["by", "round_type", "since", "as_of"], "DistributionOut", True),
    }
    for path, (query, model, is_list) in routes.items():
        op = spec["paths"][path]["get"]
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        assert [p["name"] for p in op.get("parameters", [])] == query, path
        assert schema.get("type") == ("array" if is_list else None), path
        assert (schema["items"] if is_list else schema) == {"$ref": f"#/components/schemas/{model}"}

    components = spec["components"]["schemas"]
    fields = {  # Plan 08 T3 Consumes, field for field
        "ClubSummaryOut": [
            "first_event",
            "last_event",
            "n_events",
            "n_scored_events",
            "n_held_events",
            "n_rounds",
            "n_shooters",
            "avg_score",
            "median_score",
            "top_score",
            "n_perfect",
            "clays_thrown",
            "clays_broken",
            "avg_head_count",
            "shooters_by_status",
            "status_by_year",
        ],
        "StatusYearOut": [
            "year",
            "member_rounds",
            "guest_rounds",
            "deceased_rounds",
            "unrecorded_rounds",
        ],
        "AttendanceOut": [
            "event_date",
            "head_count",
            "n_rounds",
            "n_shooters",
            "has_scores",
            "results_complete",
        ],
        "CohortOut": ["year", "n_new", "n_returned", "retention"],
        "RetentionOut": ["offset", "n_active", "share"],
        "DistributionOut": ["key", "n", "mean", "median", "p10", "p25", "p75", "p90", "counts"],
    }
    for model, names in fields.items():
        assert (list(components[model]["properties"]), components[model]["required"]) == (
            names,
            names,
        ), model
    nested = {
        ("ClubSummaryOut", "status_by_year"): "StatusYearOut",
        ("CohortOut", "retention"): "RetentionOut",
    }
    for (model, field), item in nested.items():
        prop = components[model]["properties"][field]
        assert prop["items"] == {"$ref": f"#/components/schemas/{item}"}


def test_summary_counts(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob", status="guest")
    seed.event(date(2026, 8, 30), held=False, has_scores=False, head_count=8)
    seed.event(D2, head_count=4)
    seed.round(D2, ann, 50)
    seed.round(D2, ann, 30)
    seed.round(D2, bob, 40)
    seed.finish()

    body = viewer_client.get("/api/club/summary").json()

    assert (body["n_events"], body["n_scored_events"], body["n_held_events"]) == (
        2,
        1,
        1,
    )
    assert (body["n_rounds"], body["n_shooters"], body["top_score"]) == (3, 2, 50)
    assert (body["avg_score"], body["median_score"], body["n_perfect"]) == (
        40.0,
        40.0,
        1,
    )
    assert (body["clays_thrown"], body["clays_broken"]) == (150, 120)
    assert body["avg_head_count"] == 6.0
    assert body["shooters_by_status"] == {"member": 1, "guest": 1}
    assert (body["first_event"], body["last_event"]) == ("2026-09-06", "2026-09-06")


def test_member_guest_split_uses_row_status(seed: Any, viewer_client: TestClient) -> None:
    # current profile statuses differ from the row statuses: Ann is a member now,
    # Bob's profile says deceased (no set_status rule involved)
    convert = seed.shooter("Oakley, Ann", status="member")
    override = seed.shooter("Pratt, Bob", status="deceased")
    seed.round(D1, convert, 30, status="guest")
    seed.round(D2, convert, 31, status="member")
    seed.round(D2, override, 32, status="member")
    seed.round(D3, override, 33, status=None)
    seed.finish()

    years = viewer_client.get("/api/club/summary").json()["status_by_year"]

    assert years == [
        {
            "year": 2025,
            "member_rounds": 0,
            "guest_rounds": 1,
            "deceased_rounds": 0,
            "unrecorded_rounds": 0,
        },
        {
            "year": 2026,
            "member_rounds": 2,
            "guest_rounds": 0,
            "deceased_rounds": 0,
            "unrecorded_rounds": 1,
        },
    ]


def test_round_type_filter_restricts_rounds(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.event(D2, round_type="sporting")
    seed.event(D3, round_type="super_sporting")
    seed.round(D2, ann, 20)
    seed.round(D3, ann, 44)
    seed.finish()
    params = {"round_type": "super_sporting"}

    summary = viewer_client.get("/api/club/summary", params=params).json()
    dist = viewer_client.get("/api/club/distribution", params=params).json()

    assert (summary["n_rounds"], summary["n_events"], summary["top_score"]) == (
        1,
        1,
        44,
    )
    assert [(d["key"], d["n"], d["mean"]) for d in dist] == [("2026", 1, 44.0)]


def test_attendance_lists_every_event_with_head_count_and_rows(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.event(date(2018, 12, 30), held=False, has_scores=False, head_count=7)
    seed.event(D2, head_count=12)
    seed.round(D2, ann, 30)
    seed.round(D2, ann, 31)
    seed.round(D3, ann, 29)  # scored date with no attendance row: head_count is NULL
    seed.finish()

    body = viewer_client.get("/api/club/attendance").json()

    assert body == [
        {
            "event_date": "2018-12-30",
            "head_count": 7,
            "n_rounds": 0,
            "n_shooters": 0,
            "has_scores": False,
            "results_complete": False,
        },
        {
            "event_date": "2026-09-06",
            "head_count": 12,
            "n_rounds": 2,
            "n_shooters": 1,
            "has_scores": True,
            "results_complete": True,
        },
        {
            "event_date": "2026-09-13",
            "head_count": None,
            "n_rounds": 1,
            "n_shooters": 1,
            "has_scores": True,
            "results_complete": True,
        },
    ]


def test_cohorts_endpoint_excludes_left_censored(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    old = seed.shooter("Pratt, Bob", left_censored=True)
    seed.round(D1, ann, 30)
    seed.round(D2, ann, 30)
    seed.round(D1, old, 30)
    seed.finish()

    body = viewer_client.get("/api/club/cohorts").json()

    assert body == [
        {
            "year": 2025,
            "n_new": 1,
            "n_returned": 1,
            "retention": [
                {"offset": 0, "n_active": 1, "share": 1.0},
                {"offset": 1, "n_active": 1, "share": 1.0},
            ],
        },
    ]


def test_cohorts_endpoint_builds_the_cohort_members_once(
    seed: Any, viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    seed.round(D1, ann, 30)
    seed.round(D2, ann, 30)
    seed.round(D2, bob, 30)
    seed.finish()
    calls: list[int] = []
    build = cohorts._cohort_members

    def counting(rounds: pd.DataFrame, shooters: pd.DataFrame) -> Any:
        calls.append(len(rounds))
        return build(rounds, shooters)

    monkeypatch.setattr(cohorts, "_cohort_members", counting)

    body = viewer_client.get("/api/club/cohorts").json()

    assert calls == [3]  # one pass over the 3 rounds serves retention and returns
    assert [(c["year"], c["n_new"], c["n_returned"], len(c["retention"])) for c in body] == [
        (2025, 1, 1, 2),
        (2026, 1, 0, 1),
    ]


def test_distribution_histogram_and_percentiles(seed: Any, viewer_client: TestClient) -> None:
    ids = [seed.shooter(f"Shooter, {c}") for c in "ABCDE"]
    for sid, score in zip(ids, (10, 20, 30, 40, 50), strict=True):
        seed.round(D2, sid, score)
    seed.finish()

    (year,) = viewer_client.get("/api/club/distribution", params={"by": "year"}).json()

    assert (year["key"], year["n"], year["median"]) == ("2026", 5, 30.0)
    assert (year["p10"], year["p25"], year["p75"], year["p90"]) == (
        14.0,
        20.0,
        40.0,
        46.0,
    )
    assert len(year["counts"]) == 51
    assert [i for i, c in enumerate(year["counts"]) if c] == [10, 20, 30, 40, 50]
    assert viewer_client.get("/api/club/distribution", params={"by": "month"}).status_code == 422


def test_club_on_empty_slices(seed: Any, viewer_client: TestClient) -> None:
    empty = {
        "/api/club/summary": {
            "first_event": None,
            "last_event": None,
            "n_events": 0,
            "n_scored_events": 0,
            "n_held_events": 0,
            "n_rounds": 0,
            "n_shooters": 0,
            "avg_score": None,
            "median_score": None,
            "top_score": None,
            "n_perfect": 0,
            "clays_thrown": 0,
            "clays_broken": 0,
            "avg_head_count": None,
            "shooters_by_status": {},
            "status_by_year": [],
        },
        "/api/club/attendance": [],
        "/api/club/cohorts": [],
        "/api/club/distribution": [],
    }
    for path, expected in empty.items():  # empty live tables
        assert viewer_client.get(path).json() == expected, path

    ann = seed.shooter("Oakley, Ann")
    seed.event(D2, round_type="sporting", head_count=3)
    seed.round(D2, ann, 30)
    seed.finish()
    no_match = {"round_type": "super_sporting"}  # every round filtered out

    summary = viewer_client.get("/api/club/summary", params=no_match).json()
    dist = viewer_client.get("/api/club/distribution", params=no_match).json()

    assert summary == empty["/api/club/summary"]
    assert dist == []


def test_club_on_committed_fixtures(fx_viewer_client: TestClient) -> None:
    summary = fx_viewer_client.get("/api/club/summary").json()
    assert (summary["n_rounds"], summary["n_shooters"], summary["n_perfect"]) == (
        7480,
        332,
        6,
    )
    assert summary["clays_broken"] == 261461
    assert summary["avg_head_count"] == pytest.approx(22.5583, abs=1e-3)
    first_year = summary["status_by_year"][0]
    assert (
        first_year["year"],
        first_year["member_rounds"],
        first_year["guest_rounds"],
        first_year["deceased_rounds"],
    ) == (2020, 793, 16, 34)
    cohorts = fx_viewer_client.get("/api/club/cohorts").json()
    assert {c["year"]: c["n_new"] for c in cohorts} == {
        2020: 44,
        2021: 34,
        2022: 27,
        2023: 46,
        2024: 35,
        2025: 57,
        2026: 41,
    }
    dist = fx_viewer_client.get("/api/club/distribution").json()
    assert [(d["key"], d["n"]) for d in dist][:2] == [("2020", 843), ("2021", 1047)]
    assert len(fx_viewer_client.get("/api/club/attendance").json()) == 360


def test_club_fixture_goldens_beyond_counts(fx_viewer_client: TestClient) -> None:
    """More values computed independently from scores_2026-09-27.xlsx (openpyxl + numpy).

    Events = score dates plus attendance dates with a Count (C3); held = scored with
    n_shooters >= head_count / 2 (C4; only 2024-11-10 is not); current status per C4.
    """
    summary = fx_viewer_client.get("/api/club/summary").json()
    assert (summary["n_events"], summary["n_scored_events"], summary["n_held_events"]) == (
        360,
        311,
        310,
    )
    assert (summary["first_event"], summary["last_event"]) == ("2020-01-05", "2026-09-27")
    assert summary["avg_score"] == pytest.approx(34.954679, abs=1e-6)
    assert (summary["median_score"], summary["top_score"]) == (36.0, 50)
    assert summary["clays_thrown"] == 374000
    assert summary["shooters_by_status"] == {"member": 214, "guest": 109, "deceased": 9}
    assert [y["year"] for y in summary["status_by_year"]] == list(range(2020, 2027))
    assert summary["status_by_year"][-1] == {
        "year": 2026,
        "member_rounds": 915,
        "guest_rounds": 54,
        "deceased_rounds": 0,
        "unrecorded_rounds": 0,
    }
    cohorts = {c["year"]: c for c in fx_viewer_client.get("/api/club/cohorts").json()}
    assert {y: c["n_returned"] for y, c in cohorts.items()} == {
        2020: 35,
        2021: 23,
        2022: 19,
        2023: 31,
        2024: 18,
        2025: 24,
        2026: 15,
    }
    assert [r["n_active"] for r in cohorts[2020]["retention"]] == [44, 24, 26, 21, 19, 13, 12]
    assert [r["offset"] for r in cohorts[2026]["retention"]] == [0]
    first = fx_viewer_client.get("/api/club/distribution").json()[0]
    assert (first["median"], first["p10"], first["p25"], first["p75"], first["p90"]) == (
        35.0,
        24.0,
        30.0,
        39.0,
        42.0,
    )
    assert first["mean"] == pytest.approx(33.7722, abs=1e-4)
    assert sum(first["counts"]) == 843
