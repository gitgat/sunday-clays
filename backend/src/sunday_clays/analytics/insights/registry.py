"""Insight kind registry (spec §3.3): the same pattern as analytics/achievements/registry.py.

Kind modules (every non-infrastructure sibling module) call `register(Kind(...))` at import;
`load_all()` imports them via pkgutil. `register` validates the kind and raises `KindError`, so a
bad template, a missing proof or a person-vs-person sentence fails the import and therefore CI;
the recompute step never validates anything at run time (spec §3.2).
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from sunday_clays.analytics.insights.context import InsightFrames
from sunday_clays.analytics.insights.lints import d9_problems, has_second_person, lint_clauses
from sunday_clays.analytics.insights.templates import Template, slots, template_slots
from sunday_clays.analytics.insights.types import (
    DEFAULT_EXPIRES,
    ROLLUP,
    ChartLink,
    Fact,
    Family,
    HomeSlot,
    Page,
    Polarity,
    ProofCheck,
    Requires,
    Scope,
    SubjectType,
)

_PACKAGE = "sunday_clays.analytics.insights"
# Infrastructure modules; every other sibling module defines kinds.
_SKIP_MODULES = frozenset(
    {
        "anchors",
        "charts",
        "context",
        "engine",
        "lints",
        "picks",
        "proof",
        "rank",
        "registry",
        "select",
        "store",
        "templates",
        "types",
    }
)
_ID = re.compile(r"^(pf|ev|cl|lb|rec|st|home)\.[a-z0-9]+(-[a-z0-9]+)*$")
_ROLLUP_PAGES = frozenset({Page.SUNDAY, Page.HOME})


class KindError(ValueError):
    """A kind breaks a registry rule; raised at import time so CI fails (spec §3.3)."""


@dataclass(frozen=True, kw_only=True, eq=False)
class Kind:
    id: str
    family: Family
    home_slot: HomeSlot | None
    subject: SubjectType
    pages: frozenset[Page]
    polarity: Polarity
    care: int
    anchored: bool
    guard: Mapping[str, float]
    params: frozenset[str]
    templates: Mapping[str, tuple[Template, ...]]  # variant -> 1-3 phrasings
    how: Mapping[str, tuple[Template, ...]]  # variant -> 1-3 "How we worked it out" bullets
    labels: tuple[Template, ...]  # every chart label the chart builder may use
    chart: Callable[[Fact], ChartLink]
    proof: tuple[ProofCheck, ...]
    evaluate: Callable[[InsightFrames, Scope], Iterable[Fact]]
    kudos: bool = False
    expires: Mapping[Page, int] = field(default_factory=lambda: dict(DEFAULT_EXPIRES))
    requires: Requires = field(default_factory=Requires)
    supersedes: frozenset[str] = frozenset()
    variant_care: Mapping[str, int] = field(default_factory=dict)  # overrides `care` per variant

    def care_for(self, variant: str) -> int:
        return self.variant_care.get(variant, self.care)


_REGISTRY: dict[str, Kind] = {}


def _variant_problems(kind: Kind, variant: str, templates: tuple[Template, ...]) -> list[str]:
    problems: list[str] = []
    if not 1 <= len(templates) <= 3:
        problems.append(f"variant {variant!r} needs 1-3 templates")
    you_expected = kind.subject is SubjectType.SHOOTER and variant != ROLLUP
    for t in templates:
        problems.extend(lint_clauses(t.third))
        for clause in t.third:
            problems.extend(d9_problems(clause))
        if has_second_person(t.third):
            problems.append(f"{variant!r}: third-person form says 'you'")
        if you_expected:
            if t.you is None:
                problems.append(f"{variant!r}: a shooter kind needs a 'you' form")
            else:
                problems.extend(lint_clauses(t.you))
                for clause in t.you:
                    problems.extend(d9_problems(clause))
                if not has_second_person(t.you):
                    problems.append(f"{variant!r}: the 'you' form never says you/your")
        elif t.you is not None:
            problems.append(f"{variant!r}: only shooter kinds have a 'you' form")
    return problems


def _how_problems(kind: Kind) -> list[str]:
    problems: list[str] = []
    for variant in kind.templates:
        bullets = kind.how.get(variant) or kind.how.get("")
        if not bullets:
            problems.append(f"variant {variant!r} has no 'how' bullet")
            continue
        you_expected = kind.subject is SubjectType.SHOOTER and variant != ROLLUP
        for t in bullets:
            problems.extend(lint_clauses(t.third, force_named=True))
            if you_expected and t.you is None:
                problems.append(f"{variant!r}: 'how' bullet needs a 'you' form")
            if t.you is not None:
                problems.extend(lint_clauses(t.you, force_named=True))
    return problems


def _label_problems(kind: Kind) -> list[str]:
    """Labels are linted like named clauses; a label that names the shooter needs a 'you' twin."""
    problems: list[str] = []
    if not kind.labels:
        problems.append("no chart label")
    for t in kind.labels:
        problems.extend(lint_clauses(t.third, force_named=True))
        names_someone = any(s.names_shooters for s in slots(t.third))
        if names_someone and kind.subject is SubjectType.SHOOTER:
            if t.you is None or not has_second_person(t.you):
                problems.append("a chart label that names the shooter needs a 'you' form")
            else:
                problems.extend(lint_clauses(t.you, force_named=True))
    return problems


def _slot_problems(kind: Kind) -> list[str]:
    problems: list[str] = []
    numeric: set[str] = set()
    every = [t for ts in kind.templates.values() for t in ts]
    every += [t for ts in kind.how.values() for t in ts] + list(kind.labels)
    for t in every:
        for slot in template_slots(t):
            if slot.param not in kind.params:
                problems.append(f"slot {slot.param!r} is not a declared param")
    for ts in kind.templates.values():
        for t in ts:
            numeric |= {s.param for s in template_slots(t) if s.numeric}
    missing = numeric - {check.param for check in kind.proof}
    if missing:
        problems.append(f"no proof check for {sorted(missing)}")
    return problems


def validate(kind: Kind) -> list[str]:
    """Every registry rule of spec §3.3 and §4.1-§4.2 this kind breaks (empty = valid)."""
    problems: list[str] = []
    if not _ID.match(kind.id):
        problems.append(f"bad id {kind.id!r}")
    if not all(1 <= c <= 5 for c in (kind.care, *kind.variant_care.values())):
        problems.append("care must be 1-5")
    if not kind.templates:
        problems.append("no templates")
    if Page.HOME in kind.pages and kind.home_slot is None and kind.family is not Family.RECAP:
        problems.append("a home kind needs a home_slot")
    if kind.subject is SubjectType.SHOOTER and kind.polarity not in (
        Polarity.POSITIVE,
        Polarity.NEUTRAL,
    ):
        problems.append("a shooter kind must be positive or neutral (D1)")
    every_clause = [c for ts in kind.templates.values() for t in ts for c in t.third]
    has_named_name = any(
        c.role == "named" and any(s.names_shooters for s in slots([c])) for c in every_clause
    )
    if kind.polarity is Polarity.FIELD_NEGATIVE and (
        has_named_name or kind.subject is SubjectType.SHOOTER
    ):
        problems.append("a field_negative kind names no shooter (D1)")
    if (
        kind.anchored
        and kind.subject is SubjectType.SHOOTER
        and kind.pages & _ROLLUP_PAGES
        and ROLLUP not in kind.templates
    ):
        problems.append("an anchored shooter kind on the Sunday or home page needs a 'rollup'")
    for variant, templates in kind.templates.items():
        problems.extend(_variant_problems(kind, variant, templates))
    problems.extend(_how_problems(kind))
    problems.extend(_label_problems(kind))
    problems.extend(_slot_problems(kind))
    return problems


def register(kind: Kind) -> Kind:
    if kind.id in _REGISTRY:
        raise KindError(f"duplicate insight kind {kind.id!r}")
    problems = validate(kind)
    if problems:
        raise KindError(f"{kind.id}: " + "; ".join(problems))
    _REGISTRY[kind.id] = kind
    return kind


def load_all() -> None:
    package = importlib.import_module(_PACKAGE)
    for info in pkgutil.iter_modules(package.__path__):
        if info.name not in _SKIP_MODULES and not info.name.startswith("_"):
            importlib.import_module(f"{_PACKAGE}.{info.name}")


def all_kinds() -> list[Kind]:
    """Every registered kind, sorted by id (deterministic evaluation order, spec §3.2)."""
    load_all()
    return sorted(_REGISTRY.values(), key=lambda k: k.id)


def get(kind_id: str) -> Kind:
    load_all()
    try:
        return _REGISTRY[kind_id]
    except KeyError:
        raise KeyError(f"unknown insight kind {kind_id!r}") from None
