"""GET /api/admin/recap/{date} (Plan 19 §3.3.1, §5.2)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from sunday_clays.analytics import club_milestones as cm
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.insights.store import load_rows
from sunday_clays.analytics.insights.templates import natural_name, plain
from sunday_clays.analytics.recap_insights import ELIGIBLE, recap_text_problems
from sunday_clays.config import get_settings
from sunday_clays.domain.features import set_switch
from sunday_clays.models import Event

LATEST = "2026-09-27"
SPECIAL = "2026-09-20"


def one_shooter(session: Session) -> tuple[int, str]:
    shooter, name = session.execute(
        text(
            "SELECT a.shooter_id, p.display_name FROM achievements_awarded a "
            "JOIN shooter_profiles p ON p.shooter_id = a.shooter_id "
            "WHERE a.event_date = :d ORDER BY a.shooter_id LIMIT 1"
        ),
        {"d": LATEST},
    ).one()
    return int(shooter), str(name)


def award(session: Session, shooter: int, *codes: str, day: str = LATEST) -> None:
    for code in codes:
        session.execute(
            text(
                "INSERT INTO achievements_awarded (shooter_id, code, event_date)"
                " VALUES (:s, :c, :d) ON CONFLICT DO NOTHING"
            ),
            {"s": shooter, "c": code, "d": day},
        )
    clear_cache()


def club_lines(recap: dict[str, list[str]]) -> list[str]:
    return [line for line in recap["milestones"] if line.startswith("Club: ")]


def test_regular_recap_shape(fx_admin_client: TestClient) -> None:
    recap = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()
    # The club newsletter covers these; the recap no longer carries them (owner, 2026-10-05).
    for gone in ("podium", "pbs", "first_timers", "trophies"):
        assert gone not in recap
    assert isinstance(recap["milestones"], list)
    assert recap["kind"] == "regular"
    assert recap["target_total"] == 50
    assert recap["link"] == f"https://sundayclays.claysmasher.com/l/events/{LATEST}"
    assert recap["three_bird_new"] is None
    assert recap["top_score"] is None


def test_milestones_are_tiered_trophies_as_first_last_lines(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    """One line per tiered trophy, `First Last: <Name> - <N>` (highest tier per family). One-offs,
    the D14 four, hidden families and a first Sunday (Events Attended - 1) are not listed."""
    shooter, name = one_shooter(fx_session)
    award(
        fx_session,
        shooter,
        "events:1",
        "clays_broken:2",
        "clays_broken:3",
        "doubleheader",
        "rain",
        "first_win",
        "station_top_gun",
        "iron_streak:1",
    )
    lines = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["milestones"]
    who = natural_name(name)
    assert f"{who}: Clays Broken - 1,000" in lines
    assert f"{who}: Clays Broken - 500" not in lines
    mine = [line for line in lines if line.startswith(f"{who}: ")]
    assert not any(
        w in line for line in mine for w in ("Events Attended - 1", "Doubleheader", "Rain", "Iron")
    )
    assert not any(w in line for line in lines for w in ("Bronze", "Silver", "Gold", "Platinum"))
    assert not any(line.startswith(f"{who}: Events Attended - 1") for line in lines)


def test_a_first_sunday_is_not_a_milestone(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    shooter, name = one_shooter(fx_session)
    fx_session.execute(
        text("DELETE FROM achievements_awarded WHERE shooter_id = :s AND event_date = :d"),
        {"s": shooter, "d": LATEST},
    )
    award(fx_session, shooter, "events:1")
    lines = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["milestones"]
    assert not [line for line in lines if line.startswith(f"{natural_name(name)}: ")]


def test_milestones_come_as_insight_sentences_then_trophies_then_the_club(
    fx_admin_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Order (R2): the Sunday's Clays Broken insight sentences, tiered trophy lines, club lines."""
    stored = [
        r
        for r in load_rows(fx_session)
        if r.kind == "pf.targets-milestone" and "sunday" in r.pages and r.variant == ""
    ]
    assert stored, "the fixture world has a single-shooter Clays Broken milestone Sunday"
    row = stored[0]
    day = row.anchor_date.isoformat()
    shooter, name = one_shooter(fx_session)
    assert shooter not in row.named_shooter_ids
    award(fx_session, shooter, "clays_broken:3", day=day)
    series = cm.club_milestones(fx_session, row.anchor_date).series
    crossed = next(p.rounds for p in series if p.event_date == row.anchor_date)
    thresholds = dict.fromkeys(cm.METRICS, ())
    thresholds["rounds"] = (series[0].rounds, crossed)
    monkeypatch.setattr(cm, "THRESHOLDS", thresholds)
    set_switch(fx_session, get_settings(), "club_milestones", True)
    clear_cache()
    recap = fx_admin_client.get(f"/api/admin/recap/{day}").json()
    sentence = plain(row.headline)
    lines = recap["milestones"]
    assert lines[0] == sentence
    assert sentence not in recap["insights"]  # never in "This week"
    assert recap_text_problems(sentence) == []
    assert len(lines) > 2
    assert lines[-1] == f"Club: {cm.milestone_label('rounds', crossed)} all time!"
    assert f"{natural_name(name)}: Clays Broken - 1,000" in lines[1:-1]


def test_a_shooter_with_a_clays_broken_sentence_has_no_clays_broken_trophy_line(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    """The same crossing is never said twice: the sentence (it has the total) wins, and the
    shooter's own `Clays Broken - N` line is left out; another shooter's line stays."""
    row = next(
        r
        for r in load_rows(fx_session)
        if r.kind == "pf.targets-milestone" and "sunday" in r.pages and r.variant == ""
    )
    day = row.anchor_date.isoformat()
    (sid,) = row.named_shooter_ids
    name = str(
        fx_session.execute(
            text("SELECT display_name FROM shooter_profiles WHERE shooter_id = :s"), {"s": sid}
        ).scalar_one()
    )
    other, other_name = fx_session.execute(
        text(
            "SELECT shooter_id, display_name FROM shooter_profiles WHERE shooter_id <> :s LIMIT 1"
        ),
        {"s": sid},
    ).one()
    award(fx_session, sid, "clays_broken:3", "events:25", day=day)
    award(fx_session, int(other), "clays_broken:3", day=day)
    lines = fx_admin_client.get(f"/api/admin/recap/{day}").json()["milestones"]
    who = natural_name(name)
    assert plain(row.headline) in lines
    assert [line for line in lines if who in line and "broken" in line.lower()] == [
        plain(row.headline)
    ]
    assert not [line for line in lines if line.startswith(f"{who}: Clays Broken")]
    assert f"{who}: Events Attended - 25" in lines  # other trophies stay
    assert f"{natural_name(str(other_name))}: Clays Broken - 1,000" in lines


def test_a_rolled_up_sunday_still_names_every_crossing_with_its_number(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    """On a Sunday the site rolls up ("New thousand-target marks: A, B and C."), the email still
    gives each person their own sentence with the number, never the roll-up, and no Clays Broken
    line for the same person."""
    roll = next(
        r
        for r in load_rows(fx_session)
        if r.kind == "pf.targets-milestone" and "sunday" in r.pages and r.variant == "rollup"
    )
    day = roll.anchor_date.isoformat()
    lines = fx_admin_client.get(f"/api/admin/recap/{day}").json()["milestones"]
    assert plain(roll.headline) not in lines
    for sid in roll.named_shooter_ids:
        who = natural_name(
            str(
                fx_session.execute(
                    text("SELECT display_name FROM shooter_profiles WHERE shooter_id = :s"),
                    {"s": sid},
                ).scalar_one()
            )
        )
        assert [line for line in lines if line.startswith(f"{who} has now broken")], who
        assert not [line for line in lines if line.startswith(f"{who}: Clays Broken")], who


def test_no_milestone_is_a_this_week_insight_and_back_strong_is_never_one(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    held = fx_admin_client.get("/api/events").json()
    days = sorted(e["event_date"] for e in held if e["kind"] == "regular")[-20:]
    rows = load_rows(fx_session)
    for d in days:
        recap = fx_admin_client.get(f"/api/admin/recap/{d}").json()
        kinds = {
            r.kind
            for r in rows
            if r.anchor_date == date.fromisoformat(d) and plain(r.headline) in recap["insights"]
        }
        assert not kinds & {"pf.targets-milestone", "pf.back-strong"}, d


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
    assert club_lines(fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()) == []
    set_switch(fx_session, get_settings(), "club_milestones", True)
    clear_cache()
    on = club_lines(fx_admin_client.get(f"/api/admin/recap/{LATEST}").json())
    assert on == [f"Club: {cm.milestone_label('rounds', crossed)} all time!"]


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
    assert recap["insights"] == []
    assert recap["top_score"] == 55
    assert isinstance(recap["milestones"], list)
    assert "podium" not in recap


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


def test_every_milestone_name_reads_first_last(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    """Owner, 2026-10-04: "First Last" everywhere in the email, like the "This week" sentences."""
    shooter, _ = one_shooter(fx_session)
    award(fx_session, shooter, "clays_broken:3")
    lines = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["milestones"]
    named = [line for line in lines if "Clays Broken" in line]
    assert named
    assert not [line for line in named if "," in line.split(":")[0]]


def test_a_busy_sunday_keeps_every_crossing_and_drops_their_own_trophy_lines(
    fx_admin_client: TestClient, fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two shooters cross on one Sunday (4,000 and 1,000): each keeps a sentence with their own
    number, neither has a separate `Clays Broken - N` line, and no roll-up text appears."""
    from sunday_clays.api.routes import admin_recap

    (a, a_name), (b, b_name) = [
        (int(s), str(n))
        for s, n in fx_session.execute(
            text(
                "SELECT shooter_id, display_name FROM shooter_profiles ORDER BY shooter_id LIMIT 2"
            )
        )
    ]
    a_line = f"{natural_name(a_name)} has now broken 4,000 targets on Sundays: 4,018 in all."
    b_line = f"{natural_name(b_name)} has now broken 1,000 targets on Sundays: 1,012 in all."
    monkeypatch.setattr(
        admin_recap, "targets_sentences", lambda _fr, _day: [(a, a_line), (b, b_line)]
    )
    award(fx_session, a, "clays_broken:6")
    award(fx_session, b, "clays_broken:3", "events:3")
    lines = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["milestones"]
    assert lines[:2] == [a_line, b_line]
    assert not [
        x
        for x in lines
        if "Clays Broken -" in x and x.split(":")[0] in {natural_name(a_name), natural_name(b_name)}
    ]
    assert f"{natural_name(b_name)}: Events Attended - 25" in lines
    assert not [x for x in lines if "thousand-target marks" in x]
