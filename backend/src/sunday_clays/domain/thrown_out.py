"""Thrown-out stations: pure detection and the shared copy (stdlib only)."""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

MIN_DROP_ENTRIES: Final = 8
"""Fewest sheet entries a station needs before "everyone shot perfect" counts as thrown out.

This is the one documented place for the threshold. Real turnouts run 13 to 40 shooters, so
eight entries is far below a normal Sunday and a perfect station that small is never a
coincidence. The rule fires twice in production: 2026-10-25 Station 11 and 2026-01-11 Station 10.
"""

SUNDAY_THROWN_OUT: Final = "A station was thrown out this Sunday"


@dataclass(frozen=True)
class ThrownOut:
    station_label: str | None  # None = Sunday-level override
    target_count: int | None  # None when station_label is None
    credited: bool  # entries exist and every entry has hits == target_count
    source: Literal["auto", "override"]


def _credited(entries: Sequence[int], target: int) -> bool:
    return bool(entries) and all(h == target for h in entries)


def detect_thrown_out(
    hits: Mapping[tuple[date, str], Sequence[int]],
    target_counts: Mapping[tuple[date, str], int],
    overrides: Mapping[tuple[date, str | None], tuple[int, bool]],
    special_dates: Collection[date],
) -> dict[date, tuple[ThrownOut, ...]]:
    """Per regular Sunday, the stations thrown out (layout order), Sunday-level item last."""
    skip = set(special_dates)
    found: dict[date, list[ThrownOut]] = {}
    for (d, label), target in target_counts.items():
        if d in skip:
            continue
        entries = hits.get((d, label), ())
        credited = _credited(entries, target)
        override = overrides.get((d, label))
        if override is not None:
            if not override[1]:
                continue
            item = ThrownOut(label, target, credited, "override")
        elif len(entries) >= MIN_DROP_ENTRIES and credited:
            item = ThrownOut(label, target, credited, "auto")
        else:
            continue
        found.setdefault(d, []).append(item)
    for (d, key), (_, forced) in overrides.items():
        if key is None and forced and d not in skip:
            found.setdefault(d, []).append(ThrownOut(None, None, False, "override"))
    return {d: tuple(found[d]) for d in sorted(found)}


def thrown_out_phrase(items: Sequence[ThrownOut]) -> str:
    stations = [i for i in items if i.station_label is not None]
    if not stations:
        return SUNDAY_THROWN_OUT
    if len(stations) == 1:
        s = stations[0]
        base = f"Station {s.station_label} was thrown out"
        if s.credited:
            return f"{base}; everyone was credited {s.target_count}/{s.target_count}"
        return base
    labels = [str(s.station_label) for s in stations]
    phrase = f"Stations {', '.join(labels[:-1])} and {labels[-1]} were thrown out"
    if all(s.credited for s in stations):
        phrase += "; everyone was credited in full"
    return phrase
