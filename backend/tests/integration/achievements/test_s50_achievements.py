"""Recompute step s50 writes achievements_awarded (Plan 10 T1)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pandas as pd
import pytest
from sqlalchemy import text

from sunday_clays.analytics import frames
from sunday_clays.analytics.achievements import context as context_module
from sunday_clays.analytics.achievements import registry
from sunday_clays.analytics.achievements.context import (
    STATION_COLUMNS,
    AchContext,
    build_context,
    load_station_entries,
)
from sunday_clays.analytics.achievements.registry import (
    Achievement,
    Award,
    Category,
    evaluate_all,
)
from sunday_clays.analytics.pipeline import discover_steps
from sunday_clays.analytics.steps import s50_achievements
from sunday_clays.analytics.steps.s50_achievements import STEP


def scalar(session: Any, sql: str, **params: Any) -> int:
    return int(session.execute(text(sql), params).scalar_one())


def test_step_is_discovered_at_order_50():
    assert ("achievements", 50) in [(s.name, s.order) for s in discover_steps()]


def test_build_context_reads_fixture_frames(fx_session):
    ctx = build_context(fx_session)
    assert len(ctx.rounds) == 7480
    assert len(ctx.events) == 360
    assert len(ctx.station_hits) == 259
    assert set(ctx.station_hits["target_count"]) == {7, 8}
    assert ctx.station_hits["shooter_id"].notna().all()


def test_s50_writes_every_evaluated_award(fx_session, toy_trophies):
    STEP.run(fx_session)
    stored = sorted(
        tuple(row)
        for row in fx_session.execute(
            text("SELECT shooter_id, code, event_date, round_id FROM achievements_awarded")
        ).all()
    )
    expected = sorted(
        (w.shooter_id, w.code, w.event_date, w.round_id)
        for w in evaluate_all(build_context(fx_session))
    )
    assert stored == expected
    ten_plus = scalar(
        fx_session,
        "SELECT count(*) FROM (SELECT shooter_id FROM rounds GROUP BY shooter_id "
        "HAVING count(DISTINCT event_date) >= 10) h",
    )
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'toy_events:2'")
        == ten_plus
        == 107
    )
    perfect = scalar(fx_session, "SELECT count(DISTINCT shooter_id) FROM rounds WHERE score = 50")
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'toy_perfect'")
        == perfect
        == 4
    )


def test_s50_replaces_previous_awards(fx_session, toy_trophies):
    shooter_id = scalar(fx_session, "SELECT min(shooter_id) FROM rounds")
    fx_session.execute(
        text(
            "INSERT INTO achievements_awarded (shooter_id, code, event_date, round_id, details) "
            "VALUES (:s, 'stale_code', DATE '2026-09-13', NULL, CAST('{}' AS jsonb))"
        ),
        {"s": shooter_id},
    )
    STEP.run(fx_session)
    first_run = scalar(fx_session, "SELECT count(*) FROM achievements_awarded")
    STEP.run(fx_session)
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'stale_code'")
        == 0
    )
    assert scalar(fx_session, "SELECT count(*) FROM achievements_awarded") == first_run


# --- Beyond the brief -----------------------------------------------------------------------------


def test_s50_with_no_achievements_empties_the_table(fx_session, toy_trophies, isolated_registry):
    STEP.run(fx_session)
    assert scalar(fx_session, "SELECT count(*) FROM achievements_awarded") > 0
    isolated_registry.clear()
    STEP.run(fx_session)
    assert scalar(fx_session, "SELECT count(*) FROM achievements_awarded") == 0


def test_s50_stores_award_details_as_json(fx_session, toy_trophies):
    STEP.run(fx_session)
    details = fx_session.execute(
        text(
            "SELECT details FROM achievements_awarded WHERE code = 'toy_events:2' "
            "ORDER BY shooter_id LIMIT 1"
        )
    ).scalar_one()
    assert details == {"threshold": 10.0, "value": 10.0}


def _perfect_with_numpy_details(ctx: AchContext) -> Iterator[Award]:
    perfect = ctx.rounds[ctx.rounds["score"] == 50]
    for sid, ts, rid, score in zip(
        perfect["shooter_id"],
        perfect["event_ts"],
        perfect["round_id"],
        perfect["score"].to_numpy(),
        strict=True,
    ):
        yield Award(
            int(sid), "toy_numpy", ts.date(), int(rid), {"score": score, "clean": score == 50}
        )


def test_s50_stores_numpy_details_as_plain_json(fx_session, isolated_registry):
    """A definition that reads details off a frame hands s50 numpy scalars (np.int64, np.bool_)."""
    registry.register(
        Achievement(
            code="toy_numpy",
            name="Toy Numpy",
            description="Shot a 50.",
            category=Category.SCORING,
            art_key="toy_numpy",
            evaluate=_perfect_with_numpy_details,
        )
    )
    STEP.run(fx_session)
    stored = fx_session.execute(
        text("SELECT DISTINCT details FROM achievements_awarded WHERE code = 'toy_numpy'")
    ).scalars()
    assert list(stored) == [{"clean": True, "score": 50}]


def test_s50_clears_the_memo_before_reading(fx_session, isolated_registry, monkeypatch):
    calls: list[str] = []
    real_build = s50_achievements.build_context

    def build(session: Any) -> Any:
        calls.append("build_context")
        return real_build(session)

    monkeypatch.setattr(s50_achievements, "clear_cache", lambda: calls.append("clear_cache"))
    monkeypatch.setattr(s50_achievements, "build_context", build)
    STEP.run(fx_session)
    assert calls == ["clear_cache", "build_context"]


def test_build_context_reads_live_tables_not_the_loader_memo(fx_session):
    """D5: data_version is bumped only after the last step, so a memo hit could be stale."""
    round_id = scalar(fx_session, "SELECT min(id) FROM rounds WHERE score < 50")
    stale = frames.load_rounds(fx_session)  # memoized at the current data_version
    fx_session.execute(text("UPDATE rounds SET score = 50 WHERE id = :r"), {"r": round_id})
    assert frames.load_rounds(fx_session).equals(stale)  # the memo still serves the old frame
    live = build_context(fx_session).rounds.set_index("round_id")
    assert live.at[round_id, "score"] == 50


@pytest.mark.parametrize("empty", [False, True])
def test_station_entries_match_plan06_station_hits(fx_session, empty):
    if empty:
        fx_session.execute(text("DELETE FROM station_hits"))
    ours = load_station_entries(fx_session)
    theirs = frames.load_station_hits(fx_session)[list(STATION_COLUMNS)]
    assert len(ours) == (0 if empty else 259)
    pd.testing.assert_frame_equal(ours, theirs)


def test_cached_context_is_a_fresh_copy_per_call(fx_session):
    first = context_module.cached_context(fx_session)
    second = context_module.cached_context(fx_session)
    assert first is not second
    assert first.rounds is not second.rounds
    pd.testing.assert_frame_equal(first.rounds, second.rounds)


def test_progress_many_matches_progress_for_every_fixture_shooter(fx_session):
    registry.load_all()
    ctx = build_context(fx_session)
    ids = sorted(int(s) for s in ctx.rounds["shooter_id"].unique())
    mid = sorted(ctx.rounds["event_date"].unique())[len(ctx.rounds["event_date"].unique()) // 2]
    for as_of in (None, mid):
        many = registry.progress_many(ctx, ids, as_of)
        assert many == {sid: registry.progress(ctx, sid, as_of) for sid in ids}
