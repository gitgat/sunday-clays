"""Hero and spotlight rotation over a scripted history (spec §3.4)."""

from dataclasses import replace
from datetime import date, timedelta

from sunday_clays.analytics.insights import picks as pk
from sunday_clays.analytics.insights.store import InsightRow

HELD = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(10)]


def row(key: str, day: date | None, **changes) -> InsightRow:
    base = InsightRow(
        key=key,
        value_hash="h",
        generation=1,
        first_generation=1,
        kind="pf.pb",
        family="milestone",
        home_slot="person",
        subject_type="shooter",
        subject_id="1",
        anchor_date=day,
        variant="",
        pages=("home", "sunday"),
        expires={"home": 3},
        named_shooter_ids=(1,),
        polarity="positive",
        kudos=True,
        template_id="pf.pb::0",
        params={},
        strength=1.5,
        base_score=5.0,
        rank_score=5.0,
        headline=[],
        headline_you=None,
        how=[],
        how_you=None,
        chart={},
    )
    return replace(base, **changes)


def hero_kinds_and_shooters(rows):
    by_key = {r.key: r for r in rows}
    heroes = [by_key[p.insight_key] for p in pk.compute_picks(rows, HELD) if p.slot == pk.HERO]
    return [r.kind for r in heroes], [r.named_shooter_ids[0] for r in heroes]


def test_a_kind_is_not_hero_again_for_four_sundays():
    rows = [
        row(
            f"k{k}d{i}",
            day,
            kind=f"k{k}",
            base_score=10.0 - k,
            subject_id=str(10 * i + k),
            named_shooter_ids=(10 * i + k,),
        )
        for i, day in enumerate(HELD)
        for k in range(6)
    ]
    kinds, _ = hero_kinds_and_shooters(rows)
    assert kinds == ["k0", "k1", "k2", "k3", "k4"] * 2


def test_a_shooter_is_not_hero_again_for_three_sundays():
    rows = [
        row(
            f"s{sid}d{i}",
            day,
            kind=f"kind{i}{sid}",
            base_score=10.0 - sid,
            subject_id=str(sid),
            named_shooter_ids=(sid,),
        )
        for i, day in enumerate(HELD)
        for sid in range(1, 6)
    ]
    _, shooters = hero_kinds_and_shooters(rows)
    assert shooters == [1, 2, 3, 4, 1, 2, 3, 4, 1, 2]


def test_weak_rows_are_never_hero():
    rows = [row("weak", HELD[0], strength=1.1)]
    assert pk.compute_picks(rows, HELD[:1]) == []


def test_spotlight_needs_three_candidates_and_rotates_fairly():
    rows = []
    for i, day in enumerate(HELD):
        for sid in (1, 2, 3):
            rows.append(
                row(
                    f"s{sid}d{i}",
                    day,
                    kind="pf.hot-form",
                    family="form",
                    subject_id=str(sid),
                    named_shooter_ids=(sid,),
                    base_score=float(sid),
                )
            )
    spots = [p for p in pk.compute_picks(rows, HELD) if p.slot == pk.SPOTLIGHT]
    names = [p.insight_key.split("d")[0] for p in spots]
    assert names[:3] == ["s3", "s2", "s1"]  # the fewest spotlights first, then the best row
    two = [r for r in rows if r.subject_id != "3"]
    assert [p for p in pk.compute_picks(two, HELD) if p.slot == pk.SPOTLIGHT] == []


def test_picked_returns_the_stored_rows_for_a_sunday():
    rows = [row("a", HELD[0]), row("b", HELD[0], subject_id="2", named_shooter_ids=(2,))]
    picks = [pk.Pick(HELD[0], pk.HERO, "a")]
    assert pk.picked(rows, picks, HELD[0]) == (rows[0], None)
