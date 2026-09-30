"""Pure helpers shared by the import preview and the rebuild: row identity, ordinals and diffs."""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date

from sunday_clays.ingest.names import similar_name_keys

RowKey = tuple[date, str, int]  # (event_date, identity name_key, ordinal)
SheetContent = tuple[tuple[tuple[str, int], ...], tuple[tuple[str, str, int], ...]]


@dataclass(frozen=True)
class StagedScore:
    row_id: int
    row_number: int
    raw_name: str
    name_key: str
    event_date: date
    score: int
    status: str | None
    gauge_class: str | None


@dataclass(frozen=True)
class RowChanges:
    events_added: list[date]
    events_removed: list[date]
    rows_added: int
    rows_removed: int
    rows_changed: int


def assign_ordinals(rows: Iterable[StagedScore]) -> dict[int, int]:
    """row_id -> ordinal 1..n per (event_date, name_key), by raw score desc then row_number."""
    groups: dict[tuple[date, str], list[StagedScore]] = defaultdict(list)
    for row in rows:
        groups[(row.event_date, row.name_key)].append(row)
    ordinals: dict[int, int] = {}
    for group in groups.values():
        ranked = sorted(group, key=lambda r: (-r.score, r.row_number))
        for ordinal, row in enumerate(ranked, start=1):
            ordinals[row.row_id] = ordinal
    return ordinals


def keyed_rows(rows: Sequence[StagedScore]) -> dict[RowKey, StagedScore]:
    ordinals = assign_ordinals(rows)
    return {(r.event_date, r.name_key, ordinals[r.row_id]): r for r in rows}


def representative_names(rows: Iterable[StagedScore]) -> dict[str, str]:
    """name_key -> raw name of its most recent row (latest event_date, then lowest row_number)."""
    best: dict[str, StagedScore] = {}
    for row in rows:
        current = best.get(row.name_key)
        if current is None or (row.event_date, -row.row_number) > (
            current.event_date,
            -current.row_number,
        ):
            best[row.name_key] = row
    return {key: row.raw_name for key, row in best.items()}


def score_row_changes(new: Sequence[StagedScore], old: Sequence[StagedScore]) -> RowChanges:
    new_keyed, old_keyed = keyed_rows(new), keyed_rows(old)
    new_dates = {r.event_date for r in new}
    old_dates = {r.event_date for r in old}
    common = new_keyed.keys() & old_keyed.keys()
    changed = sum(
        1
        for k in common
        if (new_keyed[k].score, new_keyed[k].status, new_keyed[k].gauge_class)
        != (old_keyed[k].score, old_keyed[k].status, old_keyed[k].gauge_class)
    )
    return RowChanges(
        events_added=sorted(new_dates - old_dates),
        events_removed=sorted(old_dates - new_dates),
        rows_added=len(new_keyed.keys() - old_keyed.keys()),
        rows_removed=len(old_keyed.keys() - new_keyed.keys()),
        rows_changed=changed,
    )


def attendance_by_date(rows: Iterable[tuple[int, date, int]]) -> dict[date, int]:
    """(row_number, event_date, head_count) rows -> head count per date; the later row wins."""
    return {d: count for _, d, count in sorted(rows)}


def attendance_changes(new: Mapping[date, int], old: Mapping[date, int]) -> int:
    return sum(1 for d in new.keys() | old.keys() if new.get(d) != old.get(d))


def station_changes(
    new: Mapping[date, SheetContent], active: Mapping[date, SheetContent]
) -> tuple[list[date], list[date], list[date]]:
    """(added, replaced, unchanged) event dates of a staged stations import vs the live sources."""
    added = sorted(d for d in new if d not in active)
    replaced = sorted(d for d in new if d in active and new[d] != active[d])
    unchanged = sorted(d for d in new if d in active and new[d] == active[d])
    return added, replaced, unchanged


def possible_duplicate_pairs(
    new_keys: Iterable[str],
    key_dates: Mapping[str, Set[date]],
    display: Mapping[str, str],
) -> list[tuple[str, str]]:
    """Unordered (display, display) pairs of a new identity key and a similar known key."""
    pairs: set[tuple[str, str]] = set()
    for key in new_keys:
        for other in similar_name_keys(key, key_dates[key], key_dates):
            first, second = sorted((key, other))
            pairs.add((first, second))
    return sorted((display[a], display[b]) for a, b in pairs)
