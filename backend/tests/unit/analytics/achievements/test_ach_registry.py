"""Registry: metals, tiers, registration, evaluation rules, progress, discovery (Plan 10 T1)."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import achievements as achievements_pkg
from sunday_clays.analytics.achievements import registry
from sunday_clays.analytics.achievements.context import AchContext
from sunday_clays.analytics.achievements.registry import Achievement, Award, Category, Metal, Tier


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def rounds_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    return pd.DataFrame(
        {
            "shooter_id": days["shooter_id"],
            "event_date": days["event_ts"],
            "value": days["cum_rounds"].astype(float),
        }
    )


def forty_plus(code: str) -> Callable[[AchContext], Iterator[Award]]:
    def evaluate(ctx: AchContext) -> Iterator[Award]:
        hits = ctx.rounds[ctx.rounds["score"] >= 40].sort_values("round_id")
        for sid, day, rid in zip(
            hits["shooter_id"], hits["event_date"], hits["round_id"], strict=True
        ):
            yield Award(int(sid), code, day, int(rid), {"score": 40})

    return evaluate


def toy_tiered(code: str = "toy_rounds") -> Achievement:
    return Achievement(
        code=code,
        name="Toy Rounds",
        description="Rounds shot.",
        category=Category.MILESTONE,
        art_key=code,
        tiers=registry.make_tiers((1, 2, 5), "rounds", singular="round"),
        value=rounds_value,
    )


def toy_one_off(code: str = "toy_forty", *, repeatable: bool = False) -> Achievement:
    return Achievement(
        code=code,
        name="Toy Forty",
        description="Shot 40+.",
        category=Category.SCORING,
        art_key=code,
        evaluate=forty_plus(code),
        repeatable=repeatable,
    )


@pytest.mark.parametrize(
    ("n_tiers", "expected"),
    [
        (3, [Metal.BRONZE, Metal.SILVER, Metal.GOLD]),
        (4, [Metal.BRONZE, Metal.SILVER, Metal.GOLD, Metal.PLATINUM]),
        (5, [Metal.BRONZE, Metal.SILVER, Metal.GOLD, Metal.PLATINUM, Metal.DIAMOND]),
        (6, [Metal.BRONZE, Metal.BRONZE, Metal.SILVER, Metal.GOLD, Metal.PLATINUM, Metal.DIAMOND]),
        (8, [Metal.BRONZE] * 4 + [Metal.SILVER, Metal.GOLD, Metal.PLATINUM, Metal.DIAMOND]),
    ],
)
def test_metal_for_puts_extra_lowest_tiers_at_bronze(n_tiers, expected):
    assert [registry.metal_for(level, n_tiers) for level in range(1, n_tiers + 1)] == expected


def test_make_tiers_formats_labels_with_thousands_and_singular():
    assert registry.make_tiers((1, 1000, 10000), "events", singular="event") == (
        Tier(1, 1.0, Metal.BRONZE, "1 event"),
        Tier(2, 1000.0, Metal.SILVER, "1,000 events"),
        Tier(3, 10000.0, Metal.GOLD, "10,000 events"),
    )


def test_register_rejects_duplicate_code(isolated_registry):
    registry.register(toy_tiered())
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(toy_tiered())


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        (
            Achievement(
                code="",
                name="x",
                description="x",
                category=Category.SCORING,
                art_key="x",
                evaluate=forty_plus(""),
            ),
            "invalid achievement code",
        ),
        (
            Achievement(
                code="a:b",
                name="x",
                description="x",
                category=Category.SCORING,
                art_key="x",
                evaluate=forty_plus("a:b"),
            ),
            "invalid achievement code",
        ),
        (
            Achievement(
                code="tiered_without_value",
                name="x",
                description="x",
                category=Category.MILESTONE,
                art_key="x",
                tiers=registry.make_tiers((1,), "x"),
            ),
            "needs a value function",
        ),
        (
            Achievement(
                code="one_off_without_evaluate",
                name="x",
                description="x",
                category=Category.SCORING,
                art_key="x",
            ),
            "needs an evaluate function",
        ),
    ],
)
def test_register_rejects_malformed_definitions(isolated_registry, bad, match):
    with pytest.raises(ValueError, match=match):
        registry.register(bad)


@pytest.mark.parametrize(
    "tiers",
    [
        pytest.param(((1, 5.0), (2, 2.0)), id="threshold-descends"),
        pytest.param(((1, 2.0), (2, 2.0)), id="threshold-repeats"),
        pytest.param(((2, 1.0), (1, 2.0)), id="level-descends"),
        pytest.param(((1, 1.0), (1, 2.0)), id="level-repeats"),
        pytest.param(((1, 1.0), (2, 2.0), (3, 2.0)), id="later-pair"),
    ],
)
def test_register_rejects_tiers_not_strictly_ascending(isolated_registry, tiers):
    """progress reads the last crossed tier as earned and the first uncrossed one as next."""
    bad = replace(
        toy_tiered(),
        tiers=tuple(Tier(level, threshold, Metal.BRONZE, "x") for level, threshold in tiers),
    )
    with pytest.raises(ValueError, match="strictly ascend"):
        registry.register(bad)
    assert "toy_rounds" not in isolated_registry


def test_get_unknown_code_raises_key_error(isolated_registry):
    with pytest.raises(KeyError, match="nope"):
        registry.get("nope")


def test_evaluate_all_awards_every_crossed_tier_at_first_event(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    ctx = (
        ctx_builder()
        .round(1, sun(0), 30)
        .round(1, sun(0), 31)
        .round(1, sun(1), 32)
        .round(2, sun(1), 33)
        .build()
    )
    got = [
        (w.event_date, w.code, w.shooter_id, w.round_id, dict(w.details))
        for w in registry.evaluate_all(ctx)
    ]
    assert got == [
        (sun(0), "toy_rounds:1", 1, None, {"value": 2.0, "threshold": 1.0}),
        (sun(0), "toy_rounds:2", 1, None, {"value": 2.0, "threshold": 2.0}),
        (sun(1), "toy_rounds:1", 2, None, {"value": 1.0, "threshold": 1.0}),
    ]


def forty_ctx(ctx_builder):
    return (
        ctx_builder()
        .round(1, sun(0), 45)
        .round(1, sun(0), 41)
        .round(1, sun(2), 42)
        .round(2, sun(1), 39)
        .build()
    )


def test_non_repeatable_one_off_keeps_only_first_award(isolated_registry, ctx_builder):
    registry.register(toy_one_off())
    got = [
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_all(forty_ctx(ctx_builder))
    ]
    assert got == [(1, sun(0), 1)]


def test_repeatable_one_off_keeps_one_award_per_day(isolated_registry, ctx_builder):
    registry.register(toy_one_off(repeatable=True))
    got = [
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_all(forty_ctx(ctx_builder))
    ]
    assert got == [(1, sun(0), 1), (1, sun(2), 3)]


def test_one_off_returning_a_foreign_code_is_rejected(isolated_registry, ctx_builder):
    registry.register(
        Achievement(
            code="toy_bad",
            name="x",
            description="x",
            category=Category.SCORING,
            art_key="x",
            evaluate=forty_plus("other"),
        )
    )
    with pytest.raises(ValueError, match="other"):
        registry.evaluate_all(ctx_builder().round(1, sun(0), 45).build())


def test_evaluate_all_orders_by_date_then_code_then_shooter(isolated_registry, ctx_builder):
    registry.register(toy_one_off("toy_b"))
    registry.register(toy_one_off("toy_a"))
    ctx = ctx_builder().round(2, sun(0), 45).round(1, sun(0), 44).round(3, sun(1), 50).build()
    assert [(w.event_date, w.code, w.shooter_id) for w in registry.evaluate_all(ctx)] == [
        (sun(0), "toy_a", 1),
        (sun(0), "toy_a", 2),
        (sun(0), "toy_b", 1),
        (sun(0), "toy_b", 2),
        (sun(1), "toy_a", 3),
        (sun(1), "toy_b", 3),
    ]


def test_progress_reports_next_tier_and_fraction(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    registry.register(toy_one_off())
    ctx = ctx_builder().round(1, sun(0), 30).round(1, sun(0), 31).round(1, sun(1), 32).build()
    [p] = registry.progress(ctx, 1, None)
    assert (p.code, p.value, p.earned_level, p.earned_metal, p.earned_label) == (
        "toy_rounds",
        3.0,
        2,
        Metal.SILVER,
        "2 rounds",
    )
    assert (p.next_level, p.next_threshold, p.next_label, p.next_metal) == (
        3,
        5.0,
        "5 rounds",
        Metal.GOLD,
    )
    assert p.fraction == pytest.approx(0.6)


def test_progress_of_a_maxed_family_has_no_next_tier(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    builder = ctx_builder()
    for i in range(6):
        builder.round(1, sun(i), 30)
    [p] = registry.progress(builder.build(), 1, None)
    assert (
        p.value,
        p.earned_level,
        p.earned_metal,
        p.next_level,
        p.next_threshold,
        p.fraction,
    ) == (
        6.0,
        3,
        Metal.GOLD,
        None,
        None,
        1.0,
    )


def test_progress_for_a_shooter_without_rounds_starts_at_zero(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    [p] = registry.progress(ctx_builder().round(1, sun(0), 30).build(), 99, None)
    assert (p.value, p.earned_level, p.earned_metal, p.earned_label, p.next_level, p.fraction) == (
        0.0,
        0,
        None,
        None,
        1,
        0.0,
    )


def test_progress_as_of_matches_sliced_context(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    ctx = (
        ctx_builder()
        .round(1, sun(0), 30)
        .round(1, sun(0), 31)
        .round(1, sun(1), 32)
        .round(1, sun(2), 33)
        .round(1, sun(2), 34)
        .round(1, sun(2), 35)
        .build()
    )
    assert registry.progress(ctx, 1, sun(0)) == registry.progress(ctx.until(sun(0)), 1, None)
    [p] = registry.progress(ctx, 1, sun(0))
    assert p.value == 2.0


def test_progress_many_matches_progress_per_shooter(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    ctx = (
        ctx_builder()
        .round(1, sun(0), 30)
        .round(1, sun(1), 32)
        .round(2, sun(1), 40)
        .round(2, sun(2), 41)
        .round(2, sun(3), 42)
        .build()
    )
    ids = [1, 2, 99]
    for as_of in (None, sun(0), sun(1)):
        assert registry.progress_many(ctx, ids, as_of) == {
            sid: registry.progress(ctx, sid, as_of) for sid in ids
        }
    assert registry.progress_many(ctx, [], None) == {}


def test_progress_many_on_an_empty_context_starts_everyone_at_zero(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    [p] = registry.progress_many(ctx_builder().build(), [7], None)[7]
    assert p.value == 0.0
    assert p.earned_level == 0


def test_trophies_list_tiers_and_one_offs_in_category_order(isolated_registry):
    registry.register(toy_one_off())
    registry.register(toy_tiered())
    assert [t.code for t in registry.trophies()] == [
        "toy_rounds:1",
        "toy_rounds:2",
        "toy_rounds:3",
        "toy_forty",
    ]
    found = registry.trophy("toy_rounds:2")
    assert found is not None
    assert found.tier is not None
    assert found.tier.label == "2 rounds"
    assert registry.trophy("toy_rounds:9") is None


@pytest.mark.parametrize(
    ("holders", "n_shooters", "pct"), [(65, 332, 19.6), (1, 3, 33.3), (0, 0, 0.0)]
)
def test_rarity_pct_rounds_to_one_decimal(holders, n_shooters, pct):
    assert registry.rarity_pct(holders, n_shooters) == pct


def test_load_all_imports_new_sibling_modules(isolated_registry, tmp_path, monkeypatch):
    (tmp_path / "toy_sibling.py").write_text(
        "from sunday_clays.analytics.achievements.registry import Achievement, Category, register\n"
        "register(Achievement(code='toy_sibling', name='Toy', description='Toy.', "
        "category=Category.CALENDAR, art_key='toy_sibling', evaluate=lambda ctx: iter(())))\n"
    )
    monkeypatch.setattr(achievements_pkg, "__path__", [str(tmp_path)])
    try:
        registry.load_all()
        assert "toy_sibling" in isolated_registry
    finally:
        sys.modules.pop("sunday_clays.analytics.achievements.toy_sibling", None)


# --- Beyond the brief -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        (
            Achievement(
                code="tiered_without_value",
                name="x",
                description="x",
                category=Category.MILESTONE,
                art_key="x",
                tiers=registry.make_tiers((1,), "x"),
            ),
            "has no value function",
        ),
        (
            Achievement(
                code="one_off_without_evaluate",
                name="x",
                description="x",
                category=Category.SCORING,
                art_key="x",
            ),
            "has no evaluate function",
        ),
    ],
)
def test_evaluate_one_rejects_unregistered_malformed_definitions(ctx_builder, bad, match):
    """evaluate_one is public (the no_leak fixture calls it), so it cannot rely on register()."""
    with pytest.raises(ValueError, match=match):
        registry.evaluate_one(bad, ctx_builder().round(1, sun(0), 45).build())


def test_tiered_value_with_no_rows_awards_nothing(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    assert registry.evaluate_all(ctx_builder().build()) == []


def test_award_is_hashable_with_dict_details_and_defaults_to_empty():
    """D2: details is excluded from the hash (a dict is unhashable) and defaults to a fresh {}."""
    assert hash(Award(1, "toy", sun(0), None, {"x": 1})) == hash(Award(1, "toy", sun(0)))
    first, second = Award(1, "toy", sun(0)), Award(2, "toy", sun(0))
    assert dict(first.details) == {}
    assert first.details is not second.details


def test_no_leak_fixture_checks_awards_and_value_series(isolated_registry, ctx_builder, no_leak):
    registry.register(toy_tiered())
    registry.register(toy_one_off(repeatable=True))
    ctx = (
        ctx_builder()
        .round(1, sun(0), 45)
        .round(1, sun(1), 30)
        .round(2, sun(1), 41)
        .round(1, sun(2), 42)
        .round(1, sun(3), 31)
        .round(1, sun(3), 32)
        .build()
    )
    assert no_leak("toy_rounds", ctx, sun(1)) == (3, 1)  # 1:1 and 2:1 by sun(1); 3 at sun(3)
    assert no_leak("toy_forty", ctx, sun(1)) == (2, 1)
    assert no_leak("toy_rounds", ctx, sun(-1)) == (0, 4)  # a cut before any data


def details_off_frame(code: str, extra: Callable[[date], dict[str, object]]) -> Achievement:
    """A one-off whose details come off the frame as numpy scalars, plus `extra(day)`."""

    def evaluate(ctx: AchContext) -> Iterator[Award]:
        for sid, day, score in zip(
            ctx.rounds["shooter_id"],
            ctx.rounds["event_date"],
            ctx.rounds["score"].to_numpy(),
            strict=True,
        ):
            yield Award(
                int(sid), code, day, None, {"score": score, "clean": score == 50, **extra(day)}
            )

    return Achievement(
        code=code,
        name="Toy Details",
        description="Details off a frame.",
        category=Category.SCORING,
        art_key=code,
        evaluate=evaluate,
        repeatable=True,
    )


def test_no_leak_serializes_details_as_s50_does(isolated_registry, ctx_builder, no_leak):
    """The harness keys awards with s50's serializer: numpy scalars pass, and details s50 could
    not store (here a date) fail in the unit test instead of first failing inside the pipeline."""
    registry.register(details_off_frame("toy_numpy", lambda day: {}))
    registry.register(details_off_frame("toy_dated", lambda day: {"when": day}))
    ctx = ctx_builder().round(1, sun(0), 50).round(2, sun(1), 41).build()
    assert no_leak("toy_numpy", ctx, sun(0)) == (1, 1)
    with pytest.raises(TypeError, match="date is not JSON serializable"):
        no_leak("toy_dated", ctx, sun(0))
