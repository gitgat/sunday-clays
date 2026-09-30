"""Competition trophies (Plan 10 T3): first_win, podium."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.achievements import registry


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def awards(code, ctx):
    return sorted(
        (w.shooter_id, w.code, w.event_date) for w in registry.evaluate_one(registry.get(code), ctx)
    )


def field(builder, day, scores, first_sid=1):
    for offset, score in enumerate(scores):
        builder.round(first_sid + offset, day, score)
    return builder


def win_ctx(b):
    builder = b()
    field(builder, sun(0), [45, 45, 40, 35, 30])  # shooters 1-5, a tie for first
    field(builder, sun(1), [44, 43, 42, 41])  # only 4 shooters
    # shooter 1 wins again; shooters 2-3 already have podiums
    field(builder, sun(2), [50, 20, 19, 18, 17])
    field(builder, sun(3), [30, 31, 32, 33, 49])  # shooter 5 wins
    return builder.build()


def test_first_win_ties_count(ctx_builder):
    assert awards("first_win", win_ctx(ctx_builder)) == [
        (1, "first_win", sun(0)),
        (2, "first_win", sun(0)),
        (5, "first_win", sun(3)),
    ]


def test_podium_needs_top_three_in_a_field_of_five(ctx_builder):
    assert awards("podium", win_ctx(ctx_builder)) == [
        (1, "podium", sun(0)),
        (2, "podium", sun(0)),
        (3, "podium", sun(0)),
        (4, "podium", sun(3)),
        (5, "podium", sun(3)),
    ]


def test_competition_trophies_handle_an_empty_context(ctx_builder):
    ctx = ctx_builder().build()
    for code in ("first_win", "podium"):
        assert awards(code, ctx) == []


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("first_win", win_ctx, sun(2)),
        ("podium", win_ctx, sun(2)),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0
