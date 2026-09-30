"""Achievement registry (C12): trophy definitions, tier metals, evaluation and tier progress.

Definitions live in sibling modules (participation, scores, conditions, competition, stations)
that call `register` at import time; `load_all` imports them. Tiered `value` functions must be
per-shooter separable (a shooter's series depends only on their own rows and the shared events
frame), because `progress` evaluates them on `ctx.for_shooter(shooter_id)`, and
`progress_many` on the whole context.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from itertools import pairwise
from typing import Any

import pandas as pd
from pydantic import BaseModel

from sunday_clays.analytics.achievements.context import AchContext

_PACKAGE = "sunday_clays.analytics.achievements"
_SKIP_MODULES = frozenset({"registry", "context"})


class Metal(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


class Category(StrEnum):
    MILESTONE = "milestone"
    SCORING = "scoring"
    CALENDAR = "calendar"
    CONDITIONS = "conditions"
    STATIONS = "stations"
    COMPETITION = "competition"


_METALS: tuple[Metal, ...] = tuple(Metal)
_CATEGORY_ORDER: dict[Category, int] = {category: i for i, category in enumerate(Category)}


@dataclass(frozen=True)
class Tier:
    level: int
    threshold: float
    metal: Metal
    label: str


@dataclass(frozen=True)
class Award:
    shooter_id: int
    code: str
    event_date: date
    round_id: int | None = None
    details: Mapping[str, Any] = field(default_factory=dict, hash=False)


@dataclass(frozen=True)
class Achievement:
    code: str
    name: str
    description: str
    category: Category
    art_key: str
    tiers: tuple[Tier, ...] = ()
    value: Callable[[AchContext], pd.DataFrame] | None = None
    evaluate: Callable[[AchContext], Iterable[Award]] | None = None
    repeatable: bool = False


@dataclass(frozen=True)
class Trophy:
    """One collectible trophy.

    A tier of a family (code `family:level`) or a one-off (the family code).
    """

    code: str
    achievement: Achievement
    tier: Tier | None


class ProgressOut(BaseModel):
    code: str
    name: str
    description: str
    category: Category
    art_key: str
    value: float
    earned_level: int
    earned_metal: Metal | None
    earned_label: str | None
    next_level: int | None
    next_threshold: float | None
    next_label: str | None
    next_metal: Metal | None
    fraction: float


_REGISTRY: dict[str, Achievement] = {}


def metal_for(level: int, n_tiers: int) -> Metal:
    """Level 1 bronze … 5 diamond; families with 6+ tiers put the extra lowest tiers at bronze."""
    extra = max(0, n_tiers - len(_METALS))
    return _METALS[max(0, level - 1 - extra)]


def make_tiers(
    thresholds: Sequence[int], unit: str, *, singular: str | None = None
) -> tuple[Tier, ...]:
    n_tiers = len(thresholds)
    return tuple(
        Tier(
            level=level,
            threshold=float(threshold),
            metal=metal_for(level, n_tiers),
            label=f"{threshold:,} {singular if threshold == 1 and singular else unit}",
        )
        for level, threshold in enumerate(thresholds, start=1)
    )


def register(a: Achievement) -> Achievement:
    if not a.code or ":" in a.code:
        raise ValueError(f"invalid achievement code {a.code!r}")
    if a.code in _REGISTRY:
        raise ValueError(f"duplicate achievement code {a.code!r}")
    if a.tiers and a.value is None:
        raise ValueError(f"tiered achievement {a.code!r} needs a value function")
    if any(hi.level <= lo.level or hi.threshold <= lo.threshold for lo, hi in pairwise(a.tiers)):
        raise ValueError(f"tiers of {a.code!r} must strictly ascend in level and threshold")
    if not a.tiers and a.evaluate is None:
        raise ValueError(f"one-off achievement {a.code!r} needs an evaluate function")
    _REGISTRY[a.code] = a
    return a


def load_all() -> None:
    package = importlib.import_module(_PACKAGE)
    for info in pkgutil.iter_modules(package.__path__):
        if info.name not in _SKIP_MODULES:
            importlib.import_module(f"{_PACKAGE}.{info.name}")


def all_achievements() -> list[Achievement]:
    """Every registered achievement, in category order, then registration order."""
    load_all()
    return sorted(_REGISTRY.values(), key=lambda a: _CATEGORY_ORDER[a.category])


def get(code: str) -> Achievement:
    load_all()
    try:
        return _REGISTRY[code]
    except KeyError:
        raise KeyError(f"unknown achievement {code!r}") from None


def trophies() -> list[Trophy]:
    out: list[Trophy] = []
    for a in all_achievements():
        if a.tiers:
            out.extend(Trophy(f"{a.code}:{tier.level}", a, tier) for tier in a.tiers)
        else:
            out.append(Trophy(a.code, a, None))
    return out


def trophy(code: str) -> Trophy | None:
    return next((t for t in trophies() if t.code == code), None)


def rarity_pct(holders: int, n_shooters: int) -> float:
    """Percent of shooters with >= 1 round who hold a trophy, 1 dp."""
    return round(100.0 * holders / n_shooters, 1) if n_shooters > 0 else 0.0


def _tier_awards(a: Achievement, ctx: AchContext) -> list[Award]:
    if a.value is None:
        raise ValueError(f"tiered achievement {a.code!r} has no value function")
    frame = a.value(ctx)
    if frame.empty:
        return []
    ordered = frame.assign(event_ts=pd.to_datetime(frame["event_date"])).sort_values(
        ["shooter_id", "event_ts"], kind="stable"
    )
    awards: list[Award] = []
    for tier in a.tiers:
        crossed = (
            ordered[ordered["value"] >= tier.threshold].groupby("shooter_id", sort=True).head(1)
        )
        for sid, ts, value in zip(
            crossed["shooter_id"], crossed["event_ts"], crossed["value"], strict=True
        ):
            awards.append(
                Award(
                    int(sid),
                    f"{a.code}:{tier.level}",
                    ts.date(),
                    None,
                    {"value": float(value), "threshold": tier.threshold},
                )
            )
    return awards


def _one_off_awards(a: Achievement, ctx: AchContext) -> list[Award]:
    if a.evaluate is None:
        raise ValueError(f"one-off achievement {a.code!r} has no evaluate function")
    raw = list(a.evaluate(ctx))
    for award in raw:
        if award.code != a.code:
            raise ValueError(f"{a.code!r} evaluate returned an award for {award.code!r}")
    seen_days: set[tuple[int, date]] = set()
    seen_shooters: set[int] = set()
    kept: list[Award] = []
    for award in sorted(raw, key=lambda w: (w.shooter_id, w.event_date)):
        if (award.shooter_id, award.event_date) in seen_days:
            continue
        if not a.repeatable and award.shooter_id in seen_shooters:
            continue
        seen_days.add((award.shooter_id, award.event_date))
        seen_shooters.add(award.shooter_id)
        kept.append(award)
    return kept


def evaluate_one(a: Achievement, ctx: AchContext) -> list[Award]:
    """Tiered: `code:level` at the first event whose value >= threshold (every crossed tier on
    that event). One-off: at most one award per shooter-day; non-repeatable keeps the first."""
    return _tier_awards(a, ctx) if a.tiers else _one_off_awards(a, ctx)


def evaluate_all(ctx: AchContext) -> list[Award]:
    awards = [award for a in all_achievements() for award in evaluate_one(a, ctx)]
    return sorted(awards, key=lambda w: (w.event_date, w.code, w.shooter_id))


def _progress_out(a: Achievement, current: float) -> ProgressOut:
    earned = [tier for tier in a.tiers if current >= tier.threshold]
    top = earned[-1] if earned else None
    nxt = next((tier for tier in a.tiers if current < tier.threshold), None)
    return ProgressOut(
        code=a.code,
        name=a.name,
        description=a.description,
        category=a.category,
        art_key=a.art_key,
        value=current,
        earned_level=top.level if top else 0,
        earned_metal=top.metal if top else None,
        earned_label=top.label if top else None,
        next_level=nxt.level if nxt else None,
        next_threshold=nxt.threshold if nxt else None,
        next_label=nxt.label if nxt else None,
        next_metal=nxt.metal if nxt else None,
        fraction=1.0 if nxt is None else min(1.0, max(0.0, current / nxt.threshold)),
    )


def _tiered() -> list[tuple[Achievement, Callable[[AchContext], pd.DataFrame]]]:
    return [(a, a.value) for a in all_achievements() if a.tiers and a.value is not None]


def progress(ctx: AchContext, shooter_id: int, as_of: date | None) -> list[ProgressOut]:
    """Per tiered family: current value (as of `as_of`), highest tier earned, next tier."""
    own = ctx.for_shooter(shooter_id).until(as_of)
    out: list[ProgressOut] = []
    for a, value in _tiered():
        frame = value(own)
        out.append(_progress_out(a, float(frame["value"].max()) if not frame.empty else 0.0))
    return out


def progress_many(
    ctx: AchContext, shooter_ids: Iterable[int], as_of: date | None
) -> dict[int, list[ProgressOut]]:
    """`progress` for many shooters, running each family's value function once over everyone
    (valid because tiered value functions are per-shooter separable)."""
    ids = list(shooter_ids)
    scoped = ctx.until(as_of)
    best_by_family: list[tuple[Achievement, dict[int, float]]] = []
    for a, value in _tiered():
        frame = value(scoped)
        top: dict[int, float] = {}
        if not frame.empty:
            for sid, v in frame.groupby("shooter_id")["value"].max().items():
                top[int(str(sid))] = float(v)
        best_by_family.append((a, top))
    return {
        sid: [_progress_out(a, best.get(sid, 0.0)) for a, best in best_by_family] for sid in ids
    }
