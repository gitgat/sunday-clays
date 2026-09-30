"""Shooter-name normalisation and possible-duplicate hints (Contract C3).

Pure module: no database, no I/O.
"""

import difflib
import re
import unicodedata
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date

_PUNCTUATION = str.maketrans(
    {chr(code): "'" for code in (0x2018, 0x2019, 0x02BC, 0x0060, 0x00B4)}
    | {chr(code): "-" for code in range(0x2010, 0x2016)}
)
_WHITESPACE = re.compile(r"\s+")
_NOT_KEY_CHAR = re.compile(r"[^\w\s'-]")
_FULL_RATIO = 0.88
_SURNAME_RATIO = 0.80
_GIVEN_RATIO = 0.70
_GIVEN_PREFIX = 3


def clean_display_name(raw: str) -> str:
    """NFKC (which turns NBSP into a space), collapse whitespace, strip.

    Punctuation is kept: this is the name shown to people.
    """
    text = unicodedata.normalize("NFKC", raw)
    return _WHITESPACE.sub(" ", text).strip()


def name_key(raw: str) -> str:
    """Matching key: ``"Linwood Luther"`` and ``"Linwood, Luther"`` share one key."""
    text = unicodedata.normalize("NFKC", raw.translate(_PUNCTUATION))
    # NFKC can produce a mapped character (U+0149 becomes U+02BC + "n"), so
    # the map runs again after casefold; without it name_key is not idempotent.
    text = text.casefold().translate(_PUNCTUATION)
    text = _NOT_KEY_CHAR.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def identity_key(key: str, event_date: date) -> str:
    """First-name-only keys are scoped to their event date."""
    if len(key.split()) >= 2:
        return key
    return f"{key}@{event_date.isoformat()}"


def base_key(identity: str) -> str:
    """Strip the ``@<date>`` suffix that identity_key adds to one-token keys."""
    return identity.partition("@")[0]


def similar_name_keys(
    key: str,
    key_dates: AbstractSet[date],
    candidates: Mapping[str, AbstractSet[date]],
) -> list[str]:
    """Identity keys in ``candidates`` that may be the same person as ``key``.

    ``key`` itself is never returned, nor is any candidate that shot on one of
    ``key_dates`` (two people at one event are two people). Sorted ascending.
    """
    base = base_key(key)
    matches = [
        candidate
        for candidate, candidate_dates in candidates.items()
        if candidate != key
        and key_dates.isdisjoint(candidate_dates)
        and _is_similar(base, base_key(candidate))
    ]
    return sorted(matches)


def _is_similar(base: str, other: str) -> bool:
    surname, _, given = base.partition(" ")
    other_surname, _, other_given = other.partition(" ")
    if not given:
        # One-token key T: the same T on another day, or a full name whose
        # given part is T.
        return base in (other, other_given)
    if _ratio(base, other) >= _FULL_RATIO:
        return True
    if not other_given or _ratio(surname, other_surname) < _SURNAME_RATIO:
        return False
    return (
        _ratio(given, other_given) >= _GIVEN_RATIO
        or given[:_GIVEN_PREFIX] == other_given[:_GIVEN_PREFIX]
    )


def _ratio(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, left, right).ratio()
