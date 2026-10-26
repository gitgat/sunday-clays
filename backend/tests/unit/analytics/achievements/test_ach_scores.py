"""Scoring trophies (Plan 10 T3): round_score, comeback, above_average_3."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics.achievements import registry


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def awards(code, ctx):
    return sorted(
        (w.shooter_id, w.code, w.event_date) for w in registry.evaluate_one(registry.get(code), ctx)
    )


def round_score_ctx(b):
    return (
        b()
        .round(1, sun(0), 38)
        .round(1, sun(1), 33)
        .round(1, sun(2), 41)
        .round(2, sun(0), 29)
        .build()
    )


def comeback_ctx(b):
    builder = b()
    for sid in (1, 2, 3, 4):
        for i in range(4 if sid == 3 else 5):
            builder.round(sid, sun(i), 30)  # rounds 1-5 (s1), 6-10 (s2), 11-14 (s3), 15-19 (s4)
    # rounds 20, 21: 45 = 30 + 15 qualifies; 46 < 45 + 15 (sun(6) compares with sun(5), not sun(4))
    builder.round(1, sun(5), 45).round(1, sun(6), 46)
    builder.round(2, sun(5), 44)  # round 22: 44 < 30 + 15 (a gain of 14)
    builder.round(3, sun(4), 45)  # round 23: only 4 earlier rounds
    # rounds 24-27: both sun(5) rounds clear 30 + 15, one award on the best (46); sun(7) compares
    # with sun(6)'s 30, not the career best 46
    builder.round(4, sun(5), 45).round(4, sun(5), 46).round(4, sun(6), 30).round(4, sun(7), 45)
    return builder.build()


def above_ctx(b):
    builder = b()
    for i in range(10):
        builder.round(1, sun(i), 30)
    for i, score in zip(range(10, 16), [31, 32, 29, 33, 34, 35], strict=True):
        builder.round(1, sun(i), score)
    for i in range(9):
        builder.round(2, sun(i), 30)
    for i in range(9, 12):
        builder.round(2, sun(i), 40)  # sun(9) has only 9 earlier rounds, so the run is 2 long
    return builder.build()


def test_round_score_awards_each_crossed_tier(ctx_builder):
    assert awards("round_score", round_score_ctx(ctx_builder)) == [
        (1, "round_score:1", sun(0)),
        (1, "round_score:2", sun(0)),
        (1, "round_score:3", sun(2)),
    ]


def test_comeback_once_per_day_uses_best_round(ctx_builder):
    got = sorted(
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_one(registry.get("comeback"), comeback_ctx(ctx_builder))
    )
    assert got == [(1, sun(5), 20), (4, sun(5), 25), (4, sun(7), 27)]


def test_above_average_needs_three_straight_events_with_ten_prior_rounds(ctx_builder):
    assert awards("above_average_3", above_ctx(ctx_builder)) == [(1, "above_average_3", sun(15))]


def test_scoring_trophies_handle_an_empty_context(ctx_builder):
    ctx = ctx_builder().build()
    assert registry.get("round_score").value(ctx).empty
    assert awards("comeback", ctx) == []
    assert awards("above_average_3", ctx) == []


def excluded_round_score_ctx(b):
    return (
        b()
        .event(sun(1), stats_excluded=True)
        .round(1, sun(0), 38)
        .round(1, sun(1), 50)
        .round(1, sun(2), 41)
        .round(2, sun(1), 50)
        .build()
    )


def test_round_score_ignores_an_excluded_sunday(ctx_builder):
    ctx = excluded_round_score_ctx(ctx_builder)
    assert awards("round_score", ctx) == [
        (1, "round_score:1", sun(0)),
        (1, "round_score:2", sun(0)),
        (1, "round_score:3", sun(2)),
    ]
    assert list(registry.get("round_score").value(ctx)["event_date"]) == [
        pd.Timestamp(sun(0)),
        pd.Timestamp(sun(2)),
    ]
    [item] = [p for p in registry.progress(ctx, 2, None) if p.code == "round_score"]
    assert item.value == 0.0


def excluded_comeback_ctx(b):
    builder = b().event(sun(5), stats_excluded=True)
    for i in range(5):
        builder.round(1, sun(i), 30)
    return builder.round(1, sun(5), 50).round(1, sun(6), 45).build()


def test_comeback_skips_back_over_an_excluded_sunday(ctx_builder):
    got = [
        (w.event_date, w.round_id, dict(w.details))
        for w in registry.evaluate_one(registry.get("comeback"), excluded_comeback_ctx(ctx_builder))
    ]
    assert got == [(sun(6), 7, {"best": 45, "previous_best": 30})]


def excluded_above_ctx(b):
    builder = b().event(sun(11), stats_excluded=True)
    for sid in (1, 2):
        for i in range(10):
            builder.round(sid, sun(i), 30)
    builder.round(1, sun(10), 31).round(1, sun(11), 20).round(1, sun(12), 32).round(1, sun(13), 33)
    builder.round(2, sun(10), 31).round(2, sun(11), 50).round(2, sun(12), 32)
    return builder.build()


def test_above_average_run_skips_an_excluded_sunday_and_never_counts_it(ctx_builder):
    assert awards("above_average_3", excluded_above_ctx(ctx_builder)) == [
        (1, "above_average_3", sun(13))
    ]


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("round_score", round_score_ctx, sun(1)),
        ("comeback", comeback_ctx, sun(6)),
        ("above_average_3", above_ctx, sun(14)),
        ("round_score", excluded_round_score_ctx, sun(1)),
        ("comeback", excluded_comeback_ctx, sun(5)),
        ("above_average_3", excluded_above_ctx, sun(12)),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0
