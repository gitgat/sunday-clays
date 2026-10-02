"""Trophies and insights in the special world (Plan 17 Task 4, Review Focus 1 and 3)."""

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.achievements.context import build_context
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.cohorts import cohort_returns
from sunday_clays.analytics.insights.attendance import held_run
from sunday_clays.analytics.insights.club import head_counts, special_turnout
from sunday_clays.analytics.insights.store import load_rows
from sunday_clays.analytics.steps.s60_insights import build_frames

SPECIAL, AFTER = date(2026, 9, 20), date(2026, 9, 27)
APPEARANCE_TROPHIES = {
    "events",
    "years_active",
    "big_year",
    "iron_streak",
    "new_year",
    "welcome_back",
    "four_seasons",
    "perfect_month",
    "anniversary_1",
    "anniversary_5",
}
APPEARANCE_INSIGHTS = {
    "pf.attendance-streak",
    "rec.streak-chase",
    "pf.sunday-milestone",
    "pf.shooter-anniversary",
    "pf.next-trophy",
    "pf.trophy-rare",
    "cl.turnout-trend",
    "cl.year-wrap",
    "cl.newcomers",
}


def _awards(session: Session) -> set[tuple[int, str, date]]:
    rows = session.execute(text("SELECT shooter_id, code, event_date FROM achievements_awarded"))
    return {(int(s), str(c), d) for s, c, d in rows}


def _family(code: str) -> str:
    return code.split(":", 1)[0]


def _shooter(session: Session, name: str) -> int:
    return int(
        session.execute(
            text("SELECT shooter_id FROM shooter_profiles WHERE display_name = :n"), {"n": name}
        ).scalar_one()
    )


def test_score_trophies_are_unchanged_by_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    changed = _awards(fx_session) ^ _awards(fx_special_session)

    assert changed, "the special Sunday must move some appearance trophy"
    assert {_family(code) for _, code, _ in changed} <= APPEARANCE_TROPHIES


def test_a_shooter_new_at_the_special_sunday_earns_events_attended_and_nothing_scored(
    fx_special_session: Session,
) -> None:
    kim = _shooter(fx_special_session, "Kim, Pat")
    rows = fx_special_session.execute(
        text("SELECT code, event_date, round_id FROM achievements_awarded WHERE shooter_id = :s"),
        {"s": kim},
    ).all()

    assert ("events", SPECIAL) in {(_family(c), d) for c, d, _ in rows}
    assert {_family(c) for c, _, _ in rows} <= APPEARANCE_TROPHIES
    assert all(rid is None for _, _, rid in rows)


def test_the_trophy_context_sees_the_special_sunday_as_an_appearance(
    fx_special_session: Session,
) -> None:
    clear_cache()
    ctx = build_context(fx_special_session)
    hadley = _shooter(fx_special_session, "Hadley, Ike")

    days = ctx.attendance_days[ctx.attendance_days["shooter_id"] == hadley]
    special = days[days["event_date"] == SPECIAL].iloc[0]
    assert bool(special["special"]) is True
    assert pd.isna(special["best_round_id"])
    assert SPECIAL not in set(ctx.shooter_days["event_date"])


def test_insight_runs_and_counts_include_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    clear_cache()
    base = build_frames(fx_session)
    clear_cache()
    special = build_frames(fx_special_session)
    hadley = _shooter(fx_special_session, "Hadley, Ike")

    base_days = base.history_until(hadley, AFTER)
    special_days = special.history_until(hadley, AFTER)
    assert held_run(special, special_days)[0] == held_run(base, base_days)[0] + 1
    assert special.appearances_through(hadley, AFTER) == base.appearances_through(hadley, AFTER) + 1
    assert special_days[-1].k == base_days[-1].k + 1
    # insights never anchor on a special Sunday (round ids differ between the worlds)
    assert [s.date for s in special.sundays] == [s.date for s in base.sundays]


def test_only_appearance_insights_change(fx_session: Session, fx_special_session: Session) -> None:
    def rows(session: Session) -> set[tuple[Any, ...]]:
        return {(r.key, r.value_hash, r.kind) for r in load_rows(session)}

    changed = rows(fx_session) ^ rows(fx_special_session)

    assert {kind for _, _, kind in changed} <= APPEARANCE_INSIGHTS
    assert all(r.anchor_date != SPECIAL for r in load_rows(fx_special_session))


def test_club_turnout_and_newcomers_count_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    clear_cache()
    base = build_frames(fx_session)
    clear_cache()
    special = build_frames(fx_special_session)
    start = base.sundays[0].date

    assert special_turnout(base, start, AFTER) == []
    # the weekly workbook has no head count for 2026-09-20, so its turnout is its 5 shooters
    assert special_turnout(special, start, AFTER) == [(SPECIAL, 5.0)]
    assert head_counts(special, start, AFTER) == sorted(
        [*head_counts(base, start, AFTER), (SPECIAL, 5.0)]
    )

    def new_in_2026(fr: Any) -> int:
        returns = cohort_returns(fr.appearances, fr.shooters)
        return int(returns.loc[returns["cohort_year"] == 2026, "n_cohort"].iloc[0])

    assert new_in_2026(special) == new_in_2026(base) + 1  # Kim, Pat
