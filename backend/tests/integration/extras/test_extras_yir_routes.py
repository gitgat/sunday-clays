"""Plan 11 Task 4: Year in Review and On this day over the empty and committed-fixture worlds."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.routes import _filters

MONTHS_2025 = [
    (1, 4, 119, 35.0924),
    (2, 4, 117, 37.8889),
    (3, 5, 133, 35.9774),
    (4, 4, 100, 35.63),
    (5, 3, 60, 35.4167),
    (6, 5, 134, 37.3955),
    (7, 3, 79, 32.5063),
    (8, 4, 133, 34.6917),
    (9, 4, 93, 36.5699),
    (10, 4, 71, 34.8732),
    (11, 4, 139, 33.0504),
    (12, 4, 89, 33.0),
]


def _shooter_id(session: Session, name_key: str) -> int:
    return int(
        session.execute(
            text("SELECT shooter_id FROM shooter_aliases WHERE name_key = :k"), {"k": name_key}
        ).scalar_one()
    )


def _ok(client: TestClient, url: str, params: Any = None) -> Any:
    response = client.get(url, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _difficulty_day(session: Session, sign: int) -> tuple[str, float]:
    """The held 2025 day with the largest ``sign * difficulty`` (earliest date on ties)."""
    row = session.execute(
        text(
            "SELECT e.event_date, m.difficulty FROM events e"
            " JOIN event_metrics m ON m.event_date = e.event_date"
            " WHERE e.results_complete AND m.difficulty IS NOT NULL"
            " AND e.event_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'"
            " ORDER BY m.difficulty * :sign DESC, e.event_date LIMIT 1"
        ),
        {"sign": sign},
    ).one()
    return row[0].isoformat(), float(row[1])


def test_yir_before_any_import_is_empty(viewer_client: TestClient) -> None:
    body = _ok(viewer_client, "/api/yir/2025")
    assert (body["years"], body["events"], body["top_rounds"], body["previous"]) == (
        [],
        0,
        [],
        None,
    )
    assert body["totals"]["rounds"] == 0
    assert body["totals"]["avg_score"] is None
    assert [m["rounds"] for m in body["months"]] == [0] * 12
    assert _ok(viewer_client, "/api/on-this-day", {"date": "2026-09-27"}) == {
        "on": "2026-09-27",
        "items": [],
    }


def test_club_year_2025(fx_session: Session, fx_viewer_client: TestClient) -> None:
    body = _ok(fx_viewer_client, "/api/yir/2025")
    assert body["years"] == [2020, 2021, 2022, 2023, 2024, 2025, 2026]
    totals = body["totals"]
    assert (totals["scored_events"], totals["held_events"], totals["rounds"]) == (48, 48, 1267)
    assert (totals["shooters"], totals["clays_thrown"], totals["clays_broken"]) == (
        139,
        63350,
        44683,
    )
    assert totals["avg_score"] == pytest.approx(35.26677, abs=1e-5)
    assert (body["events"], body["newcomers"], body["perfect_rounds"]) == (50, 57, 1)
    assert [(r["display_name"], r["event_date"], r["score"]) for r in body["top_rounds"]] == [
        ("Grimsby, Gregor", "2025-08-03", 50)
    ]
    assert body["mean_head_count"] == pytest.approx(25.92, abs=1e-2)
    assert body["busiest"] == {"event_date": "2025-08-17", "value": 40.0}
    hard_day, hard_value = _difficulty_day(fx_session, 1)
    easy_day, easy_value = _difficulty_day(fx_session, -1)
    assert body["hardest"]["event_date"] == hard_day
    assert body["hardest"]["value"] == pytest.approx(hard_value)
    assert body["easiest"]["event_date"] == easy_day
    assert body["easiest"]["value"] == pytest.approx(easy_value)
    trophies = fx_session.execute(
        text(
            "SELECT count(*) FROM achievements_awarded"
            " WHERE event_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'"
        )
    ).scalar_one()
    assert body["trophies"] == trophies
    months = [(m["month"], m["events"], m["rounds"], m["avg_score"]) for m in body["months"]]
    assert [m[:3] for m in months] == [m[:3] for m in MONTHS_2025]
    assert [m[3] for m in months] == pytest.approx([m[3] for m in MONTHS_2025], abs=1e-4)
    previous = body["previous"]
    assert (previous["year"], previous["scored_events"], previous["held_events"]) == (2024, 48, 47)
    assert (previous["rounds"], previous["shooters"], previous["clays_broken"]) == (
        1193,
        125,
        41088,
    )
    assert previous["avg_score"] == pytest.approx(34.4409, abs=1e-4)


def test_club_year_2026_compares_with_2025(fx_viewer_client: TestClient) -> None:
    body = _ok(fx_viewer_client, "/api/yir/2026")
    assert (body["events"], body["totals"]["rounds"], body["totals"]["shooters"]) == (36, 969, 129)
    assert body["newcomers"] == 41
    assert {r["score"] for r in body["top_rounds"]} == {49}
    assert (body["previous"]["year"], body["previous"]["rounds"]) == (2025, 1267)


def test_shooter_year_grimsby_2025(fx_session: Session, fx_viewer_client: TestClient) -> None:
    grimsby = _shooter_id(fx_session, "grimsby gregor")
    body = _ok(fx_viewer_client, f"/api/yir/2025/shooters/{grimsby}")
    assert (body["shooter_id"], body["display_name"]) == (grimsby, "Grimsby, Gregor")
    totals = body["totals"]
    assert (totals["events"], totals["rounds"], totals["clays_broken"]) == (26, 27, 1169)
    assert totals["avg_score"] == pytest.approx(43.2963, abs=1e-4)
    assert (body["best"]["event_date"], body["best"]["score"]) == ("2025-08-03", 50)
    assert (body["wins"], body["podiums"], body["best_finish"]) == (7, 13, 1)
    assert body["pbs"] == [
        {"event_date": "2025-03-23", "score": 49},
        {"event_date": "2025-08-03", "score": 50},
    ]
    assert (body["attendance_rank"], body["n_shooters"]) == (19, 139)
    rating_end = fx_session.execute(
        text(
            "SELECT mu FROM rating_history WHERE shooter_id = :s"
            " AND event_date <= DATE '2025-12-31' ORDER BY event_date DESC LIMIT 1"
        ),
        {"s": grimsby},
    ).scalar_one()
    assert body["rating_end"] == pytest.approx(rating_end)
    previous = body["previous"]
    assert (previous["events"], previous["rounds"], previous["clays_broken"]) == (23, 23, 966)
    assert previous["avg_score"] == 42.0
    assert sum(m["rounds"] for m in body["months"]) == 27


def test_shooter_year_without_rounds_that_year(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    gilchrist = _shooter_id(fx_session, "gilchrist melvin")
    body = _ok(fx_viewer_client, f"/api/yir/2025/shooters/{gilchrist}")
    assert (body["totals"]["rounds"], body["wins"], body["best"], body["pbs"]) == (0, 0, None, [])
    assert (body["attendance_rank"], body["best_finish"]) == (None, None)
    hadley = _ok(
        fx_viewer_client, f"/api/yir/2025/shooters/{_shooter_id(fx_session, 'hadley ike')}"
    )
    assert (hadley["totals"]["events"], hadley["attendance_rank"]) == (44, 1)


def test_yir_rejects_unknown_shooter_and_out_of_range_year(fx_viewer_client: TestClient) -> None:
    missing = fx_viewer_client.get("/api/yir/2025/shooters/999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "shooter_not_found"
    assert fx_viewer_client.get("/api/yir/1999").status_code == 422


def _on_this_day(body: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [
        (
            i["years_ago"],
            i["event_date"],
            i["n_shooters"],
            i["top_score"],
            i["median"],
            sorted(w["display_name"] for w in i["winners"]),
        )
        for i in body["items"]
    ]


def test_on_this_day_lists_one_two_and_three_years_back(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    body = _ok(fx_viewer_client, "/api/on-this-day", {"date": "2026-09-27"})
    assert body["on"] == "2026-09-27"
    assert _on_this_day(body) == [
        (1, "2025-09-28", 23, 45, 36.0, ["Rookwood, Derek"]),
        (2, "2024-09-29", 25, 40, 33.0, ["Blakeslee, Ryder", "McMurtry, Zeb", "Yoder, Gavin"]),
        (3, "2023-09-24", 30, 47, 33.0, ["Quarles, Hector"]),
    ]
    head_counts = dict(
        fx_session.execute(
            text(
                "SELECT event_date, head_count FROM events"
                " WHERE event_date IN (DATE '2025-09-28', DATE '2024-09-29', DATE '2023-09-24')"
            )
        ).all()
    )
    for item in body["items"]:
        assert item["head_count"] == head_counts[date.fromisoformat(item["event_date"])]
        assert item["has_scores"] is True


def test_on_this_day_defaults_to_local_today(
    fx_viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Plan 06 T1: routes resolve "today" through _filters, and tests pin _filters.today_local.
    seen: list[str] = []

    def pinned_today(tz: str) -> date:
        seen.append(tz)
        return date(2026, 9, 27)

    monkeypatch.setattr(_filters, "today_local", pinned_today)
    body = _ok(fx_viewer_client, "/api/on-this-day")
    assert body["on"] == "2026-09-27"
    assert [i["event_date"] for i in body["items"]] == ["2025-09-28", "2024-09-29", "2023-09-24"]
    # settings.timezone; Plan 06's ETag middleware may also read today through _filters.
    assert set(seen) == {"America/Los_Angeles"}


def test_club_and_shooter_year_follow_round_type(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    every = _ok(fx_viewer_client, "/api/yir/2025")
    counts = dict(
        fx_session.execute(
            text(
                "SELECT e.round_type, count(*) FROM rounds r JOIN events e"
                " ON e.event_date = r.event_date"
                " WHERE e.event_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'"
                " GROUP BY e.round_type"
            )
        ).all()
    )
    assert sum(counts.values()) == every["totals"]["rounds"]
    for round_type, n in counts.items():
        body = _ok(fx_viewer_client, "/api/yir/2025", {"round_type": round_type})
        assert body["totals"]["rounds"] == n
        assert body["years"] == every["years"]
    both = _ok(fx_viewer_client, "/api/yir/2025", {"round_type": list(counts)})
    assert both["totals"] == every["totals"]
    grimsby = _shooter_id(fx_session, "grimsby gregor")
    total = 0
    for round_type in counts:
        mine = _ok(
            fx_viewer_client, f"/api/yir/2025/shooters/{grimsby}", {"round_type": round_type}
        )
        total += mine["totals"]["rounds"]
    assert total == 27
