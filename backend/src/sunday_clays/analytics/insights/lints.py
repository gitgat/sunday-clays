"""Language lints for insight text (spec §4.1 b, §4.2).

Every check runs on literal template text (and on the text segments of rendered headlines),
never on display names, so a shooter surnamed "He" never trips the pronoun lint.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from itertools import pairwise

from sunday_clays.analytics.insights.templates import Clause, Segment, Slot, literal_texts

NEGATIVE = re.compile(
    r"\b(worst|worse|slump\w*|drop|dropped|fell|lost|below|behind|struggl\w*|bad|poor|"
    r"off form|declin\w*|last place)\b",
    re.IGNORECASE,
)
PERSON_VS_PERSON = re.compile(
    r"\b(upsets?|giant[- ]?killers?|odds|favou?rites?|rivals?|rivalry|head[- ]to[- ]head)\b",
    re.IGNORECASE,
)
PRONOUNS = re.compile(r"\b(he|she|his|her|hers|him|himself|herself)\b", re.IGNORECASE)
CLASS_WORD = re.compile(r"\bclass(es)?\b", re.IGNORECASE)
EVENT_WORD = re.compile(r"\bevents?\b", re.IGNORECASE)
JARGON = re.compile(
    r"\b(residuals?|percentiles?|median|stdev|standard deviation|z-scores?|significant|"
    r"correlation|regression|mu|sigma|expected)\b",
    re.IGNORECASE,
)
SECOND_PERSON = re.compile(r"\b(you|your|yours|yourself)\b", re.IGNORECASE)
# D9: the only literal text allowed between two name slots of one named clause, so no
# "ahead", "behind", "lead", "beat", "over" or "than" can ever sit between two names.
LIST_JOINERS = frozenset({", ", " and "})

_ALWAYS = (
    ("person-vs-person", PERSON_VS_PERSON),
    ("pronoun", PRONOUNS),
    ("class", CLASS_WORD),
    ("event", EVENT_WORD),
    ("jargon", JARGON),
)


def lint_text(text: str, *, named: bool) -> list[str]:
    """Lint codes a piece of literal text trips; `named` adds the negative-word lint (D1)."""
    problems = [f"{code}: {m.group(0)!r}" for code, rx in _ALWAYS if (m := rx.search(text))]
    if named and (m := NEGATIVE.search(text)):
        problems.append(f"negative: {m.group(0)!r}")
    return problems


def lint_clauses(clauses: Sequence[Clause], *, force_named: bool = False) -> list[str]:
    """Lints every clause; `field` clauses skip the negative-word lint unless `force_named`."""
    problems: list[str] = []
    for clause in clauses:
        named = force_named or clause.role == "named"
        for text in [*literal_texts(clause), *_joined_runs(clause)]:
            problems.extend(p for p in lint_text(text, named=named) if p not in problems)
    return problems


def _joined_runs(clause: Clause) -> list[str]:
    """Runs of adjacent literal parts joined, so a banned phrase split across parts is caught."""
    runs: list[list[str]] = [[]]
    for part in clause.parts:
        if isinstance(part, str):
            runs[-1].append(part)
        else:
            runs.append([])
    return ["".join(run) for run in runs if len(run) > 1]


def has_second_person(clauses: Sequence[Clause]) -> bool:
    return any(SECOND_PERSON.search(t) for c in clauses for t in literal_texts(c))


def d9_problems(clause: Clause) -> list[str]:
    """In a named clause, two name slots may only form a list ("A, B and C", "A and B both").

    A field clause may not hold a name at all (per-clause polarity, spec §3.3).
    """
    name_positions = [
        i for i, p in enumerate(clause.parts) if isinstance(p, Slot) and p.names_shooters
    ]
    if clause.role == "field":
        return ["field clause names a shooter"] if name_positions else []
    problems: list[str] = []
    for a, b in pairwise(name_positions):
        between = clause.parts[a + 1 : b]
        text = "".join(p for p in between if isinstance(p, str))
        if any(isinstance(p, Slot) for p in between) or text not in LIST_JOINERS:
            problems.append(f"two names joined by {text!r}: only a list is allowed (D9)")
    return problems


def lint_segments(segments: Iterable[Segment], *, named: bool = True) -> list[str]:
    """Lints the text segments of a rendered headline (names and numbers are skipped)."""
    text = "".join(s["v"] for s in segments if s["t"] == "text")
    return lint_text(text, named=named)
