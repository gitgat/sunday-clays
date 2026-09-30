"""Evaluate, clamp, roll up and render (spec §3.1-§3.5)."""

import logging
from dataclasses import replace
from datetime import date

from sunday_clays.analytics.insights.engine import (
    apply_rollups,
    build_rows,
    clamp,
    evaluate_all,
    insight_key,
    phrasing,
)
from sunday_clays.analytics.insights.registry import Kind
from sunday_clays.analytics.insights.templates import Int, NameList, Shooter, T, named
from sunday_clays.analytics.insights.types import (
    DEFAULT_EXPIRES,
    ROLLUP,
    ChartLink,
    Fact,
    Family,
    Highlight,
    HomeSlot,
    P,
    Polarity,
    Requires,
    SubjectType,
    Window,
    cell,
)

LABEL = T(named(Shooter("s"), "'s scores"), you=named("Your scores"))


def _chart(fact: Fact) -> ChartLink:
    day = fact.anchor_date or date(2024, 1, 7)
    return ChartLink(type="page", label=LABEL, window=Window(day, day), highlight=Highlight((day,)))


def kind(evaluate, **changes) -> Kind:
    fields = {
        "id": "pf.stub",
        "family": Family.MILESTONE,
        "home_slot": HomeSlot.MILESTONE,
        "subject": SubjectType.SHOOTER,
        "pages": frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        "polarity": Polarity.POSITIVE,
        "care": 4,
        "anchored": True,
        "kudos": True,
        "guard": {},
        "params": frozenset({"s", "n", "names", "day"}),
        "templates": {
            "": (
                T(
                    named(Shooter("s"), " hit ", Int("n"), "."),
                    you=named("You hit ", Int("n"), "."),
                ),
                T(
                    named(Shooter("s"), " got ", Int("n"), "."),
                    you=named("You got ", Int("n"), "."),
                ),
            ),
            ROLLUP: (T(named("Today: ", NameList("names"), ".")),),
        },
        "how": {"": (T(named("Counted."), you=named("Your rounds, counted.")),)},
        "labels": (LABEL,),
        "chart": _chart,
        "proof": (cell("n"),),
        "evaluate": evaluate,
    }
    fields.update(changes)
    return Kind(**fields)


def facts_for(sids, day, strength=1.5):
    def evaluate(fr, scope):
        for sid in sids:
            yield Fact(
                subject_id=str(sid),
                anchor_date=day,
                variant="",
                pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
                params={"s": sid, "n": 40 + sid, "day": day},
                strength=strength,
                named_shooter_ids=(sid,),
            )

    return evaluate


def _world(make_world, sun):
    world = make_world()
    for sid in (1, 2, 3):
        world.series(sid, 0, [30, 35, 40])
    return world.frames()


def test_clamp_raises_strength_to_one_and_logs(caplog):
    fact = Fact(
        subject_id="1", anchor_date=None, variant="", pages=frozenset(), params={}, strength=0.4
    )
    with caplog.at_level(logging.WARNING):
        assert clamp(kind(facts_for([], None)), fact).strength == 1.0
    assert "insights.clamp kind=pf.stub" in caplog.text


def test_facts_outside_the_scope_are_dropped_and_dormant_kinds_skipped(make_world, sun):
    fr = _world(make_world, sun)
    inside = kind(facts_for([1], sun(2)))
    outside = kind(facts_for([1], sun(9)), id="pf.stub-two")
    dormant = kind(facts_for([1], sun(2)), id="pf.stub-three", requires=Requires(trophy_awards=1))
    pairs = evaluate_all(fr, kinds=[inside, outside, dormant])
    assert [(p.kind.id, p.fact.anchor_date) for p in pairs] == [("pf.stub", sun(2))]


def test_two_or_more_same_sunday_rows_roll_up_and_keep_their_profile_page(make_world, sun):
    fr = _world(make_world, sun)
    stub = kind(facts_for([1, 2, 3], sun(2)))
    pairs = apply_rollups(evaluate_all(fr, kinds=[stub]))
    rollups = [p.fact for p in pairs if p.fact.variant == ROLLUP]
    assert len(rollups) == 1
    assert rollups[0].params["names"] == [1, 2, 3]
    assert rollups[0].pages == frozenset({P.SUNDAY, P.HOME})
    singles = [p.fact for p in pairs if p.fact.variant == ""]
    assert all(f.pages == frozenset({P.PROFILE}) for f in singles)


def test_one_row_does_not_roll_up(make_world, sun):
    fr = _world(make_world, sun)
    pairs = apply_rollups(evaluate_all(fr, kinds=[kind(facts_for([1], sun(2)))]))
    assert [p.fact.variant for p in pairs] == [""]


def test_rows_render_both_person_forms_with_stable_keys_and_phrasing(make_world, sun):
    fr = _world(make_world, sun)
    pairs = evaluate_all(fr, kinds=[kind(facts_for([1], sun(2)))])
    rows = build_rows(pairs, fr, generation=7, previous={})
    row = rows[0]
    key = insight_key("pf.stub", "shooter", "1", sun(2), "")
    assert row.key == key
    assert row.template_id == f"pf.stub::{phrasing(key, 2)}"
    assert row.headline_you is not None
    assert "".join(s["v"] for s in row.headline_you).startswith("You ")
    assert row.chart["label"] == "Pat Shooter1's scores"
    assert row.chart["label_you"] == "Your scores"
    assert row.chart["window"] == {"from": sun(2).isoformat(), "to": sun(2).isoformat()}
    assert row.expires == {page.value: n for page, n in DEFAULT_EXPIRES.items()}
    assert (row.generation, row.first_generation) == (7, 7)
    assert row.rank_score == row.base_score * 1.5  # anchored at the latest Sunday


def test_first_generation_carries_over_only_when_the_headline_numbers_are_unchanged(
    make_world, sun
):
    fr = _world(make_world, sun)
    pairs = evaluate_all(fr, kinds=[kind(facts_for([1], sun(2)))])
    first = build_rows(pairs, fr, generation=3, previous={})[0]
    same = build_rows(pairs, fr, generation=4, previous={first.key: (first.value_hash, 3)})[0]
    assert same.first_generation == 3
    assert not same.is_new_since(None)
    changed_pairs = [
        replace(p, fact=replace(p.fact, params={**p.fact.params, "n": 99})) for p in pairs
    ]
    changed = build_rows(
        changed_pairs, fr, generation=4, previous={first.key: (first.value_hash, 3)}
    )[0]
    assert changed.first_generation == 4
    assert changed.is_new_since(None)


def test_evergreen_rows_never_expire(make_world, sun):
    fr = _world(make_world, sun)

    def evergreen(fr_, scope):
        yield Fact(
            subject_id="1",
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={"s": 1, "n": 3},
            strength=1.0,
            named_shooter_ids=(1,),
        )

    rows = build_rows(evaluate_all(fr, kinds=[kind(evergreen)]), fr, generation=1, previous={})
    assert rows[0].expires == {}
    assert rows[0].rank_score == rows[0].base_score


def test_a_duplicate_key_keeps_the_first_row_and_logs(make_world, sun, caplog):
    """A kind bug must not abort the upload through uq_insights_key (final review M-2)."""
    fr = _world(make_world, sun)

    def twice(fr_, scope):
        yield from facts_for([1], sun(2))(fr_, scope)
        yield from facts_for([1], sun(2), strength=3.0)(fr_, scope)

    pairs = evaluate_all(fr, kinds=[kind(twice)])
    assert len(pairs) == 2
    with caplog.at_level(logging.WARNING):
        rows = build_rows(pairs, fr, generation=1, previous={})
    assert len(rows) == 1
    assert rows[0].strength == 1.5
    assert "insights.duplicate_key kind=pf.stub" in caplog.text
