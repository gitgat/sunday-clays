"""Ranking inputs (spec §3.4): rank_score = care x min(strength, 2) x recency x rarity."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date

from sunday_clays.analytics.insights.context import InsightFrames, is_active
from sunday_clays.analytics.insights.types import ROLLUP, SubjectType

RECENCY_TOP = 1.5  # an insight about the reference Sunday itself
RECENCY_DECAY = 0.8  # x 0.8 for each held Sunday between the anchor and the reference Sunday
STRENGTH_CAP = 2.0
RARITY_WINDOW = 52  # held Sundays that define "recent" for the rarity shares


def sundays_between(anchor: date, ref: date, held: Sequence[date]) -> int:
    """Held Sundays in (anchor, ref]; 0 when the anchor is the reference Sunday."""
    return bisect_right(held, ref) - bisect_right(held, anchor)


def recency(anchor: date | None, ref: date, held: Sequence[date]) -> float:
    if anchor is None:
        return 1.0
    return RECENCY_TOP * RECENCY_DECAY ** sundays_between(anchor, ref, held)


def rarity(share_: float) -> float:
    """clamp(0.5 + log2(1 / share) / 2, 1, 3): 3 of 84 -> 2.9, 23 of 84 -> 1.4, >= half -> 1."""
    if share_ <= 0:
        return 3.0
    return min(3.0, max(1.0, 0.5 + math.log2(1 / share_) / 2))


def base_score(care: int, strength: float, rarity_: float) -> float:
    """rank_score without recency; the Sunday page applies its own recency of 1.5."""
    return care * min(strength, STRENGTH_CAP) * rarity_


def share_key(kind_id: str, anchored: bool) -> tuple[str, bool]:
    return (kind_id, anchored)


def shares(
    facts: Sequence[tuple[str, SubjectType, date | None, str, str]],
    fr: InsightFrames,
    ref: date,
) -> Mapping[tuple[str, bool], float]:
    """Per (kind, anchored?): the share of eligible subjects that got it (spec §3.4 rarity).

    `facts` holds (kind_id, subject_type, anchor_date, subject_id, variant) per Fact. Eligible:
    evergreen shooter kinds, the active shooters as of `ref`; anchored shooter kinds, the
    shooter-Sundays of the last 52 held Sundays up to `ref`; Sunday kinds, those Sundays; club,
    season and station kinds share 1 (rarity 1).
    """
    held = [d for d in fr.held_dates() if d <= ref]
    window = set(held[-RARITY_WINDOW:])
    shooter_sundays = sum(s.n for s in fr.sundays if s.date in window) or 1
    active = sum(1 for sid in fr.histories if is_active(fr.history_until(sid, ref), ref))
    hits: dict[tuple[str, bool], set[tuple[str, date | None]]] = defaultdict(set)
    subject_of: dict[tuple[str, bool], SubjectType] = {}
    for kind_id, subject, anchor, subject_id, variant in facts:
        if variant == ROLLUP:
            continue
        key = share_key(kind_id, anchor is not None)
        subject_of[key] = subject
        if anchor is None or anchor in window:
            hits[key].add((subject_id, anchor))
    out: dict[tuple[str, bool], float] = {}
    for key, subject in subject_of.items():
        n = len(hits.get(key, set()))
        if subject is SubjectType.SHOOTER and not key[1]:
            out[key] = n / max(active, 1)
        elif subject is SubjectType.SHOOTER:
            out[key] = n / shooter_sundays
        elif subject is SubjectType.SUNDAY:
            out[key] = len({a for _s, a in hits.get(key, set())}) / max(len(window), 1)
        else:
            out[key] = 1.0
    return out
