"""Home hero and "Shooter to know" rotation (spec §3.4), stored in `insight_picks`.

Computed Sunday by Sunday in date order, each Sunday using only the picks of earlier Sundays, so
a pick never changes once later data arrives unless the rows for that Sunday change. Pure: the
s60 step calls `compute_picks`, the home API reads the stored picks.

Evergreen rows are only known as of the latest Sunday, so past Sundays pick among anchored rows;
the latest Sunday also considers evergreen rows.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from sunday_clays.analytics.insights.rank import recency
from sunday_clays.analytics.insights.select import (
    HOME_SUNDAYS,
    PINNED_HOME,
    is_rollup,
    not_expired,
)
from sunday_clays.analytics.insights.store import InsightRow, Pick

HERO, SPOTLIGHT = "hero", "spotlight"
HERO_MIN_STRENGTH = 1.2
HERO_KIND_GAP = 4  # a kind is not hero again within the next 4 Sundays
HERO_SHOOTER_GAP = 3  # nor a shooter within the next 3
SPOTLIGHT_WINDOW = 26
SPOTLIGHT_GAP = 8
SPOTLIGHT_MIN_CANDIDATES = 3


def home_candidates(
    rows: Sequence[InsightRow], ref: date, held: Sequence[date], *, latest: bool
) -> list[InsightRow]:
    """Home rows as they stood on `ref`, ranked with recency relative to `ref`. `rows` may be
    pre-filtered to the rows anchored on the last 2 held Sundays up to `ref` (plus evergreen)."""
    last = [d for d in held if d <= ref][-HOME_SUNDAYS:]
    pool = [
        r
        for r in rows
        if "home" in r.pages
        and r.kind != PINNED_HOME
        and ((r.anchor_date is None and latest) or r.anchor_date in last)
        and not_expired(r, "home", ref, held)
    ]
    return sorted(pool, key=lambda r: (-score_at(r, ref, held), r.key))


def score_at(row: InsightRow, ref: date, held: Sequence[date]) -> float:
    return row.base_score * recency(row.anchor_date, ref, held)


def pick_hero(
    candidates: Sequence[InsightRow], earlier: Sequence[InsightRow | None]
) -> InsightRow | None:
    """`earlier`: the heroes of the previous Sundays, most recent last (None = no hero)."""
    kinds = {r.kind for r in earlier[-HERO_KIND_GAP:] if r is not None}
    shooters = {
        sid for r in earlier[-HERO_SHOOTER_GAP:] if r is not None for sid in r.named_shooter_ids
    }
    return next(
        (
            r
            for r in candidates
            if r.strength >= HERO_MIN_STRENGTH
            and r.kind not in kinds
            and not set(r.named_shooter_ids) & shooters
        ),
        None,
    )


def pick_spotlight(
    rows: Sequence[InsightRow], ref: date, held: Sequence[date], earlier: Sequence[int | None]
) -> InsightRow | None:
    """`earlier`: the spotlit shooter of each previous Sunday, most recent last."""
    best: dict[int, InsightRow] = {}
    for r in sorted(rows, key=lambda r: (-score_at(r, ref, held), r.key)):
        if (
            r.anchor_date == ref
            and r.subject_type == "shooter"
            and r.polarity == "positive"
            and r.home_slot == "person"
            and not is_rollup(r)
        ):
            best.setdefault(int(r.subject_id), r)
    if len(best) < SPOTLIGHT_MIN_CANDIDATES:
        return None
    recent = {sid for sid in earlier[-SPOTLIGHT_GAP:] if sid is not None}
    window = [sid for sid in earlier[-SPOTLIGHT_WINDOW:] if sid is not None]
    open_ = [sid for sid in best if sid not in recent]
    if not open_:
        return None
    ranked_ids = sorted(
        open_, key=lambda sid: (window.count(sid), -score_at(best[sid], ref, held), best[sid].key)
    )
    return best[ranked_ids[0]]


def compute_picks(rows: Sequence[InsightRow], held: Sequence[date]) -> list[Pick]:
    by_day: dict[date | None, list[InsightRow]] = defaultdict(list)
    for r in rows:
        by_day[r.anchor_date].append(r)
    heroes: list[InsightRow | None] = []
    spotlit: list[int | None] = []
    picks: list[Pick] = []
    for i, day in enumerate(held):
        latest = i == len(held) - 1
        near = [r for d in held[max(0, i - HOME_SUNDAYS + 1) : i + 1] for r in by_day[d]]
        pool = near + by_day[None] if latest else near
        hero = pick_hero(home_candidates(pool, day, held, latest=latest), heroes)
        heroes.append(hero)
        if hero is not None:
            picks.append(Pick(day, HERO, hero.key))
        spot = pick_spotlight(by_day[day], day, held, spotlit)
        spotlit.append(int(spot.subject_id) if spot is not None else None)
        if spot is not None:
            picks.append(Pick(day, SPOTLIGHT, spot.key))
    return picks


def picked(
    rows: Sequence[InsightRow], picks: Sequence[Pick], day: date
) -> tuple[InsightRow | None, InsightRow | None]:
    """(hero, spotlight) stored for `day`."""
    by_key = {r.key: r for r in rows}
    found = {p.slot: by_key.get(p.insight_key) for p in picks if p.sunday == day}
    return found.get(HERO), found.get(SPOTLIGHT)
