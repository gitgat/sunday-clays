"""Pure checks on one read shooter block. A check only ever raises a reason: official scores are never changed."""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

MATCH_THRESHOLD = 0.7

STATION_COUNT = "station_count"
TOT_MISSING = "tot_missing"
TOT_OUT_OF_RANGE = "tot_out_of_range"
SUM_VS_EVENT_TOTAL = "sum_vs_event_total"
EVENT_TOTAL_MISSING = "event_total_missing"
NO_OFFICIAL_MATCH = "no_official_match"
SHEET_VS_OFFICIAL = "sheet_vs_official"
MODEL_ERROR = "model_error"
ENGINE_ERROR = "engine_error"  # the Claude engine could not read a page (two tries)
STATION_MISMATCH = "station_mismatch"  # the station numbers Claude read do not match the course
ENGINES_DISAGREE = "engines_disagree"  # Claude and a cached Gemma reading both pass the checks but differ


_STATION_LABEL = re.compile(r"(\d{1,2})([A-Z]?)")


def station_label(value: object) -> int | str | None:
    """A station as the course names it: an int for "7", a string for a lettered station like "7A".

    Accepts ints and text (trimmed, any case); None for anything else, a bool, station 0 or a longer label.
    """
    if isinstance(value, bool) or not isinstance(value, int | str):
        return None
    match = _STATION_LABEL.fullmatch(str(value).strip().upper())
    if match is None or int(match[1]) < 1:
        return None
    number = int(match[1])
    return f"{number}{match[2]}" if match[2] else number


def normalise_name(name: str) -> str:
    """Case-insensitive, punctuation-free, token-sorted, so "Last, First" equals "First Last"."""
    return " ".join(sorted(re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()))


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalise_name(a), normalise_name(b)).ratio()


def best_match(name: str, officials: Sequence[str], threshold: float = MATCH_THRESHOLD) -> int | None:
    """Index of the most similar official name, or None below the threshold (ignores one-to-one)."""
    best: int | None = None
    best_score = threshold
    for index, official in enumerate(officials):
        score = similarity(name, official)
        if score >= best_score and (best is None or score > best_score):
            best, best_score = index, score
    return best


def match_names(
    names: Sequence[str],
    officials: Sequence[str],
    threshold: float = MATCH_THRESHOLD,
    *,
    sums: Sequence[int | None] | None = None,
    hits: Sequence[int] | None = None,
) -> list[int | None]:
    """One-to-one: every read name gets at most one official row and every row at most one name.

    The closest pairs are assigned first, so a near-duplicate name cannot steal another shooter's row. When a
    shooter has two rows (two rounds) and `sums`/`hits` are given, a sheet prefers the row it agrees with.
    """

    def disagrees(i: int, j: int) -> int:
        return 0 if sums is None or hits is None or sums[i] == hits[j] else 1

    pairs = sorted(
        (
            (score, i, j)
            for i, name in enumerate(names)
            if name.strip()
            for j, official in enumerate(officials)
            if (score := similarity(name, official)) >= threshold
        ),
        key=lambda pair: (-pair[0], disagrees(pair[1], pair[2]), pair[1], pair[2]),
    )
    result: list[int | None] = [None] * len(names)
    taken: set[int] = set()
    for _, i, j in pairs:
        if result[i] is None and j not in taken:
            result[i] = j
            taken.add(j)
    return result


def check_reading(
    tots: Sequence[int | None],
    event_total: int | None,
    targets: Sequence[int],
    official: int | None,
    *,
    matched: bool,
) -> list[str]:
    """Reasons a reading needs a human; empty means it is consistent with everything typed and written."""
    reasons: list[str] = []
    if len(tots) != len(targets):
        reasons.append(STATION_COUNT)
    if any(tot is None for tot in tots):
        reasons.append(TOT_MISSING)
    if any(tot is not None and not 0 <= tot <= target for tot, target in zip(tots, targets, strict=False)):
        reasons.append(TOT_OUT_OF_RANGE)
    total = sum(tot or 0 for tot in tots)
    if event_total is None:
        reasons.append(EVENT_TOTAL_MISSING)
    elif event_total != total:
        reasons.append(SUM_VS_EVENT_TOTAL)
    if not matched:
        reasons.append(NO_OFFICIAL_MATCH)
    elif official is not None and official != total:
        reasons.append(SHEET_VS_OFFICIAL)
    return reasons
