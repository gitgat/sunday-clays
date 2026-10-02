"""Pure helpers for the ClaySmasher export (spec 2026-10-01 §4.1; skipped by discovery).

Rounds are keyed by their natural key, (event_date, identity name_key, ordinal): rebuild_live
renumbers every live id, while this key is DB-unique and is what overlay rules target.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from sunday_clays.station_label import label_sort_key

# A round without station data: the club's 50-target round (ingest.validate.LAYOUT_TOTAL).
TARGETS_PER_ROUND = 50

RoundNaturalKey = tuple[date, str, int]


def round_key(event_date: date, name_key: str, ordinal: int) -> str:
    """The export's stable round id. Keys hold only [\\w\\s'-] and '@', so ':' is unambiguous."""
    return f"{event_date.isoformat()}:{name_key}:{ordinal}"


def station_orders(labels: Iterable[str]) -> dict[str, int]:
    """label -> 1-based position in station order (4, 5, 6, 7, 7A, 8) within one event."""
    ordered = sorted(set(labels), key=label_sort_key)
    return {label: position for position, label in enumerate(ordered, start=1)}


def day_ordinals(keys: Iterable[RoundNaturalKey]) -> dict[RoundNaturalKey, int]:
    """Natural key -> the shooter's 1-based round number that day, by (ordinal, name_key).

    Equal to the native ordinal unless a merge left one shooter with rounds under two name keys
    on the same day (both ordinal 1), which this numbers 1 and 2.
    """
    by_day: dict[date, list[tuple[str, int]]] = defaultdict(list)
    for event_date, name_key, ordinal in keys:
        by_day[event_date].append((name_key, ordinal))
    numbers: dict[RoundNaturalKey, int] = {}
    for event_date, rounds in by_day.items():
        ranked = sorted(rounds, key=lambda pair: (pair[1], pair[0]))
        for number, (name_key, ordinal) in enumerate(ranked, start=1):
            numbers[(event_date, name_key, ordinal)] = number
    return numbers


def latest(*stamps: datetime | None) -> datetime | None:
    """The newest of the given aware datetimes, in UTC; None when none is given."""
    present = [stamp for stamp in stamps if stamp is not None]
    return max(present).astimezone(UTC) if present else None


def rule_stamps(
    rules: Iterable[tuple[str, Mapping[str, Any], datetime]],
) -> tuple[dict[RoundNaturalKey, datetime], dict[date, datetime]]:
    """Newest change per targeted round and per event date from (rule_type, payload, changed_at).

    `round_type_override` targets a date; `score_override` and `hide_round` target a round key.
    """
    by_round: dict[RoundNaturalKey, datetime] = {}
    by_day: dict[date, datetime] = {}
    for rule_type, payload, changed_at in rules:
        day = date.fromisoformat(str(payload["event_date"]))
        if rule_type == "round_type_override":
            by_day[day] = max(by_day.get(day, changed_at), changed_at)
        else:
            key = (day, str(payload["name_key"]), int(payload["ordinal"]))
            by_round[key] = max(by_round.get(key, changed_at), changed_at)
    return by_round, by_day
