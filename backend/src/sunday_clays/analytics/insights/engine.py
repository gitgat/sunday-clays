"""Evaluate every kind, clamp, roll up, rank and render rows (spec §3.2 steps 3-5).

Nothing here asserts on data: s60 runs inside the upload's transaction, so an out-of-range
strength is clamped and logged, never raised (spec §3.2).
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from sunday_clays.analytics.insights import rank
from sunday_clays.analytics.insights.context import InsightFrames
from sunday_clays.analytics.insights.registry import Kind, all_kinds
from sunday_clays.analytics.insights.store import InsightRow, to_json
from sunday_clays.analytics.insights.templates import Template, plain, render, template_slots
from sunday_clays.analytics.insights.types import (
    ROLLUP,
    ChartLink,
    Fact,
    Page,
    Readiness,
    Scope,
    SubjectType,
)

log = logging.getLogger(__name__)

ROLLUP_PAGES = frozenset({Page.SUNDAY, Page.HOME})
ROLLUP_NAMES = 5


@dataclass(frozen=True)
class Pair:
    kind: Kind
    fact: Fact


def readiness_of(fr: InsightFrames) -> Readiness:
    """Inputs dormant kinds wait for (spec §4.5)."""
    stations = fr.stations
    station_sundays = int(stations["event_date"].nunique()) if len(stations) else 0
    return Readiness(
        station_sundays=station_sundays,
        trophy_awards=len(fr.awards),
    )


def clamp(kind: Kind, fact: Fact) -> Fact:
    """strength >= 1 is a registry property (tested per kind); production clamps and logs."""
    if fact.strength >= 1:
        return fact
    log.warning(
        "insights.clamp kind=%s subject=%s anchor=%s strength=%.3f",
        kind.id,
        fact.subject_id,
        fact.anchor_date,
        fact.strength,
    )
    return replace(fact, strength=1.0)


def evaluate_all(
    fr: InsightFrames,
    *,
    kinds: Sequence[Kind] | None = None,
    sundays: Iterable[date] | None = None,
) -> list[Pair]:
    """Every Fact of every ready kind, in deterministic (kind, subject, anchor, variant) order."""
    if fr.as_of is None:
        return []
    scope = Scope(
        sundays=frozenset(fr.held_dates() if sundays is None else sundays), as_of=fr.as_of
    )
    readiness = readiness_of(fr)
    out: list[Pair] = []
    for kind in all_kinds() if kinds is None else kinds:
        if kind.requires.unmet(readiness) is not None:
            continue
        for fact in kind.evaluate(fr, scope):
            if fact.anchor_date is not None and fact.anchor_date not in scope.sundays:
                log.warning("insights.out_of_scope kind=%s anchor=%s", kind.id, fact.anchor_date)
                continue
            out.append(Pair(kind, clamp(kind, fact)))
    return sorted(
        out,
        key=lambda p: (
            p.kind.id,
            p.fact.subject_id,
            p.fact.anchor_date or date.min,
            p.fact.variant,
        ),
    )


def apply_rollups(pairs: Sequence[Pair]) -> list[Pair]:
    """Shooter rows of one kind anchored to one Sunday become one Sunday/home card (spec §3.4).

    Two or more rows on the Sunday or home page -> a roll-up Fact (variant 'rollup', up to five
    names by strength) and those rows keep only their other pages (the profile). The rows stay:
    they feed the kudos strip and the profile.
    """
    groups: dict[tuple[str, date], list[int]] = defaultdict(list)
    for i, p in enumerate(pairs):
        if (
            p.kind.subject is SubjectType.SHOOTER
            and p.fact.anchor_date is not None
            and p.fact.pages & ROLLUP_PAGES
        ):
            groups[(p.kind.id, p.fact.anchor_date)].append(i)
    out = list(pairs)
    for (_kind_id, day), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        chosen = sorted(members, key=lambda i: (-out[i].fact.strength, out[i].fact.subject_id))
        top = [int(out[i].fact.subject_id) for i in chosen[:ROLLUP_NAMES]]
        pages = frozenset().union(*(out[i].fact.pages for i in members)) & ROLLUP_PAGES
        kind = out[members[0]].kind
        out.append(
            Pair(
                kind,
                Fact(
                    subject_id=day.isoformat(),
                    anchor_date=day,
                    variant=ROLLUP,
                    pages=pages,
                    params={"names": top, "rollup_count": len(members), "day": day},
                    strength=max(out[i].fact.strength for i in members),
                    named_shooter_ids=tuple(top),
                ),
            )
        )
        for i in members:
            out[i] = Pair(out[i].kind, replace(out[i].fact, pages=out[i].fact.pages - ROLLUP_PAGES))
    return out


def _sha(*parts: object) -> str:
    joined = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(joined.encode(), usedforsecurity=False).hexdigest()[:20]


def insight_key(
    kind_id: str, subject_type: str, subject_id: str, anchor: date | None, variant: str
) -> str:
    """Stable identity (spec §3.1); a roll-up is keyed by (kind, 'rollup', anchor)."""
    if variant == ROLLUP:
        return _sha(kind_id, "rollup", anchor)
    return _sha(kind_id, subject_type, subject_id, anchor, variant)


def phrasing(key: str, n: int) -> int:
    """Stable for the life of the insight: no recompute rewords an old card (spec §3.4)."""
    return int(key[:8], 16) % n


def _value_hash(template: Template, params: Mapping[str, object]) -> str:
    used = sorted({s.param for s in template_slots(template)})
    return _sha(to_json({name: params.get(name) for name in used}))


def _label(
    t: Template, params: Mapping[str, object], names: Mapping[int, str], you: bool
) -> str | None:
    if you and t.you is None:
        return None
    return plain(render(t, params, names, you=you))


def chart_json(
    link: ChartLink, params: Mapping[str, object], names: Mapping[int, str], *, person: bool
) -> dict[str, Any]:
    return {
        "type": link.type,
        "label": _label(link.label, params, names, you=False),
        "label_you": _label(link.label, params, names, you=True) if person else None,
        "spec": None if link.spec is None else link.spec.model_dump(mode="json"),
        "chart_type": link.chart_type,
        "route": link.route,
        "anchor": link.anchor,
        "params": dict(link.params),
        "highlight": link.highlight.to_json(),
        "ref": link.ref,
        "compare": None if link.compare is None else link.compare.model_dump(mode="json"),
        "window": link.window.to_json(),
        "also": [chart_json(a, params, names, person=person) for a in link.also],
    }


def build_rows(
    pairs: Sequence[Pair],
    fr: InsightFrames,
    *,
    generation: int,
    previous: Mapping[str, tuple[str, int]],
) -> list[InsightRow]:
    """Render every Pair into an `insights` row (spec §3.1, §3.5, §3.6)."""
    if fr.as_of is None:
        return []
    ref = fr.as_of
    held = fr.held_dates()
    names = fr.names
    subject_types = [
        SubjectType.SUNDAY if p.fact.variant == ROLLUP else p.kind.subject for p in pairs
    ]
    share = rank.shares(
        [
            (p.kind.id, st, p.fact.anchor_date, p.fact.subject_id, p.fact.variant)
            for p, st in zip(pairs, subject_types, strict=True)
        ],
        fr,
        ref,
    )
    rows: list[InsightRow] = []
    seen: set[str] = set()
    for p, subject_type in zip(pairs, subject_types, strict=True):
        kind, fact = p.kind, p.fact
        key = insight_key(kind.id, subject_type, fact.subject_id, fact.anchor_date, fact.variant)
        if key in seen:  # never abort the upload's transaction on a kind bug (uq_insights_key)
            log.warning("insights.duplicate_key kind=%s key=%s", kind.id, key)
            continue
        seen.add(key)
        templates = kind.templates[fact.variant]
        index = phrasing(key, len(templates))
        template = templates[index]
        person = subject_type is SubjectType.SHOOTER
        bullets = kind.how.get(fact.variant) or kind.how[""]
        value_hash = _value_hash(template, fact.params)
        prev = previous.get(key)
        first = prev[1] if prev is not None and prev[0] == value_hash else generation
        kind_share = share.get(rank.share_key(kind.id, fact.anchor_date is not None), 1.0)
        rarity = (
            1.0
            if subject_type in (SubjectType.CLUB, SubjectType.SEASON, SubjectType.STATION)
            else rank.rarity(kind_share)
        )
        base = rank.base_score(kind.care_for(fact.variant), fact.strength, rarity)
        rows.append(
            InsightRow(
                key=key,
                value_hash=value_hash,
                generation=generation,
                first_generation=first,
                kind=kind.id,
                family=kind.family.value,
                home_slot=None if kind.home_slot is None else kind.home_slot.value,
                subject_type=subject_type.value,
                subject_id=fact.subject_id,
                anchor_date=fact.anchor_date,
                variant=fact.variant,
                pages=tuple(sorted(page.value for page in fact.pages)),
                expires={page.value: n for page, n in kind.expires.items()}
                if fact.anchor_date is not None
                else {},
                named_shooter_ids=tuple(fact.named_shooter_ids),
                polarity=kind.polarity.value,
                kudos=kind.kudos and fact.variant != ROLLUP,
                template_id=f"{kind.id}:{fact.variant}:{index}",
                params=dict(fact.params),
                strength=float(fact.strength),
                base_score=base,
                rank_score=base * rank.recency(fact.anchor_date, ref, held),
                headline=render(template, fact.params, names),
                headline_you=render(template, fact.params, names, you=True) if person else None,
                how=[render(b, fact.params, names) for b in bullets],
                how_you=[render(b, fact.params, names, you=True) for b in bullets]
                if person
                else None,
                chart=chart_json(kind.chart(fact), fact.params, names, person=person),
            )
        )
    return rows
