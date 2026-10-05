"""GET /api/admin/recap/{date} (Plan 19 §3.3.1, §5.2)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from sunday_clays.analytics import club_milestones as cm
from sunday_clays.analytics.achievements.registry import trophy
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.insights.store import load_rows
from sunday_clays.analytics.insights.templates import plain
from sunday_clays.analytics.recap_insights import ELIGIBLE, recap_text_problems
from sunday_clays.analytics.recap_trophies import recap_trophy_items
from sunday_clays.analytics.summary import LEFT_OUT_TROPHY_CODES
from sunday_clays.config import get_settings
from sunday_clays.domain.features import set_switch
from sunday_clays.models import Event

LATEST = "2026-09-27"
SPECIAL = "2026-09-20"


def test_regular_recap_agrees_with_the_sunday_page(fx_admin_client: TestClient) -> None:
    recap = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()
    event = fx_admin_client.get(f"/api/events/{LATEST}").json()
    podium_names = sorted(n for place in recap["podium"] for n in place["names"])
    page_names = sorted(
        r["display_name"]
        for r in event["results"]
        if r["is_best_round"] and r["event_rank"] is not None and r["event_rank"] <= 3
    )
    assert podium_names == page_names
    page_pbs = {n["display_name"] for n in event["notables"] if n["kind"] == "pb"}
    assert {p["display_name"] for p in recap["pbs"]} == page_pbs
    for pb in recap["pbs"]:
        assert pb["score"] > pb["previous"]
    assert recap["kind"] == "regular"
    assert recap["target_total"] == 50
    assert recap["link"] == f"https://sundayclays.claysmasher.com/l/events/{LATEST}"
    assert recap["three_bird_new"] is None
    assert recap["top_score"] is None


def test_trophies_are_that_sundays_awards_minus_the_d14_four(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    """Counted against achievements_awarded, not against names, so removing the filter fails.
    Two D14 trophies are added on LATEST (one per registry category, competition and stations), so
    the test does not depend on what the fixture happens to award that day."""
    shooter = fx_session.execute(
        text("SELECT shooter_id FROM achievements_awarded WHERE event_date = :d LIMIT 1"),
        {"d": LATEST},
    ).scalar_one()
    for code in ("first_win", "station_top_gun"):
        fx_session.execute(
            text(
                "INSERT INTO achievements_awarded (shooter_id, code, event_date)"
                " VALUES (:s, :c, :d)"
                " ON CONFLICT DO NOTHING"
            ),
            {"s": shooter, "c": code, "d": LATEST},
        )
    codes = (
        fx_session.execute(
            text("SELECT code FROM achievements_awarded WHERE event_date = :d"), {"d": LATEST}
        )
        .scalars()
        .all()
    )
    left_out = [c for c in codes if c in LEFT_OUT_TROPHY_CODES]
    assert {"first_win", "station_top_gun"} <= set(left_out)
    recap = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()
    items = [i for t in recap["trophies"] for i in t["items"]]
    assert items
    for code in left_out:
        assert trophy(code) is not None
        assert not any(i.startswith(trophy(code).achievement.name) for i in items)  # type: ignore[union-attr]


def test_trophies_read_as_the_number_reached_per_shooter(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    """Each shooter's items are exactly the recap wording of that Sunday's awards (highest tier
    per family, never a metal). Two tiers of one family are forced onto one shooter."""
    shooter, name = fx_session.execute(
        text(
            "SELECT a.shooter_id, p.display_name FROM achievements_awarded a "
            "JOIN shooter_profiles p ON p.shooter_id = a.shooter_id "
            "WHERE a.event_date = :d LIMIT 1"
        ),
        {"d": LATEST},
    ).one()
    for code in ("events:3", "events:4"):
        fx_session.execute(
            text(
                "INSERT INTO achievements_awarded (shooter_id, code, event_date)"
                " VALUES (:s, :c, :d) ON CONFLICT DO NOTHING"
            ),
            {"s": shooter, "c": code, "d": LATEST},
        )
    codes = (
        fx_session.execute(
            text(
                "SELECT a.code FROM achievements_awarded a WHERE a.event_date = :d"
                " AND a.shooter_id = :s ORDER BY a.code"
            ),
            {"d": LATEST, "s": shooter},
        )
        .scalars()
        .all()
    )
    mine = next(
        t
        for t in fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["trophies"]
        if t["display_name"] == name
    )
    expected = recap_trophy_items([c for c in codes if c != "three_bird_shoot"])
    assert mine["items"] == expected
    assert "Events Attended - 50" in expected
    assert "Events Attended - 25" not in expected
    every = " ".join(
        i
        for t in fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["trophies"]
        for i in t["items"]
    )
    assert not any(w in every for w in ("Bronze", "Silver", "Gold", "Platinum", "Diamond", "—"))


def test_this_week_insights_are_stored_sunday_rows_in_plain_words(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    recap = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()
    stored = {
        plain(r.headline)
        for r in load_rows(fx_session)
        if r.anchor_date == date.fromisoformat(LATEST) and "sunday" in r.pages
    }
    assert 1 <= len(recap["insights"]) <= 5
    for sentence in recap["insights"]:
        assert sentence in stored  # the named headline, as the Sunday page stores it
        assert recap_text_problems(sentence) == [], sentence
    kinds = {
        r.kind
        for r in load_rows(fx_session)
        if r.anchor_date == date.fromisoformat(LATEST) and plain(r.headline) in recap["insights"]
    }
    assert kinds <= set(ELIGIBLE)


def test_this_week_insights_rotate_kinds_across_the_last_twelve_weeks(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    """A kind in the previous 12 weeks' picks comes back only as a fill (fewer than 3 fresh)."""
    held = fx_admin_client.get("/api/events").json()
    days = sorted(e["event_date"] for e in held if e["kind"] == "regular")[-20:]
    rows = load_rows(fx_session)
    by_day: dict[str, set[str]] = {}
    for d in days:
        sentences = fx_admin_client.get(f"/api/admin/recap/{d}").json()["insights"]
        by_day[d] = {
            r.kind
            for r in rows
            if r.anchor_date == date.fromisoformat(d) and plain(r.headline) in sentences
        }
    checked = skipped_something = 0
    for i in range(len(days) - 8, len(days)):
        recent = set().union(*(by_day[w] for w in days[max(0, i - 12) : i]))
        offered = {r.kind for r in rows if r.anchor_date == date.fromisoformat(days[i])}
        picked = by_day[days[i]]
        checked += bool(picked)
        skipped_something += bool(offered & set(ELIGIBLE) & recent)
        if picked & recent:
            assert len(picked - recent) < 3, (days[i], picked, recent)
        # Repeats are fills only: a week never shows more than 3 unless every one is fresh.
        assert len(picked) <= max(3, len(picked - recent)), (days[i], picked, recent)
    assert checked >= 4, "the fixture world has insights on most recent Sundays"
    assert skipped_something >= 1, "the 12-week skip had a kind to skip at least once"


def test_milestones_only_when_their_switch_is_on(
    fx_admin_client: TestClient, fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Thresholds are patched so one crossing lands on LATEST and one on an earlier Sunday.
    Kills: dropping the switch check (off must be []), dropping the date filter (the earlier
    crossing would show), and never calling club_milestones (on must be the exact label)."""
    series = cm.club_milestones(fx_session, date.fromisoformat(LATEST)).series
    assert series[-1].event_date == date.fromisoformat(LATEST)
    crossed = series[-1].rounds
    assert series[-2].rounds < crossed  # LATEST had rounds, so this threshold is crossed on it
    thresholds = dict.fromkeys(cm.METRICS, ())
    thresholds["rounds"] = (series[0].rounds, crossed)  # the first: crossed on the first Sunday
    monkeypatch.setattr(cm, "THRESHOLDS", thresholds)
    clear_cache()
    assert fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["club_milestones"] == []
    set_switch(fx_session, get_settings(), "club_milestones", True)
    clear_cache()
    on = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["club_milestones"]
    assert on == [cm.milestone_label("rounds", crossed)]


def test_special_recap(fx_special_admin_client: TestClient, fx_special_session: Session) -> None:
    recap = fx_special_admin_client.get(f"/api/admin/recap/{SPECIAL}").json()
    awarded = fx_special_session.execute(
        text(
            "SELECT count(*) FROM achievements_awarded"
            " WHERE code = 'three_bird_shoot' AND event_date = :d"
        ),
        {"d": SPECIAL},
    ).scalar_one()
    held = fx_special_session.execute(
        text(
            "SELECT count(*) FROM achievements_awarded"
            " WHERE code = 'three_bird_shoot' AND event_date <= :d"
        ),
        {"d": SPECIAL},
    ).scalar_one()
    assert (recap["kind"], recap["label"], recap["target_total"]) == ("special", "3-Bird Shoot", 60)
    assert recap["three_bird_new"] == awarded
    assert recap["three_bird_holders"] == held
    assert recap["podium"] == []
    assert recap["pbs"] == []
    assert recap["insights"] == []
    assert recap["top_score"] == 55
    assert "Kim, Pat" in recap["first_timers"]


def test_a_turkey_shoot_has_no_three_bird_counts(
    fx_special_admin_client: TestClient, fx_special_session: Session
) -> None:
    fx_special_session.execute(
        update(Event)
        .where(Event.event_date == date.fromisoformat(SPECIAL))
        .values(label="Turkey Shoot")
    )
    clear_cache()
    recap = fx_special_admin_client.get(f"/api/admin/recap/{SPECIAL}").json()
    assert recap["three_bird_new"] is None
    assert recap["three_bird_holders"] is None


def test_errors(
    fx_admin_client: TestClient, fx_viewer_client: TestClient, fx_session: Session
) -> None:
    missing = fx_admin_client.get("/api/admin/recap/1999-01-03")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "event_not_found"
    fx_session.execute(
        update(Event)
        .where(Event.event_date == date.fromisoformat(LATEST))
        .values(results_complete=False)
    )
    clear_cache()
    not_ready = fx_admin_client.get(f"/api/admin/recap/{LATEST}")
    assert not_ready.status_code == 409
    assert not_ready.json()["error"] == {
        "code": "recap_not_ready",
        "message": "This Sunday has no full results yet.",
    }
    assert fx_viewer_client.get(f"/api/admin/recap/{LATEST}").status_code == 403
