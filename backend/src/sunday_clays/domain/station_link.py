"""Pure station-entry -> round linking for one import or rebuild (C5)."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sunday_clays.ingest.names import clean_display_name
from sunday_clays.ingest.types import Finding, Severity


@dataclass(frozen=True)
class StationEntry:
    event_date: date
    entry_row: int
    raw_name: str
    name_key: str
    shooter_id: int | None
    total: int


@dataclass(frozen=True)
class LinkRound:
    round_id: int
    event_date: date
    shooter_id: int
    ordinal: int
    score: int


@dataclass(frozen=True)
class StationLink:
    event_date: date
    entry_row: int
    shooter_id: int | None
    round_id: int | None


def _quoted(entry: StationEntry) -> str:
    """The entry's name as shown in messages; the finding's ``name`` keeps the raw spelling."""
    return f'"{clean_display_name(entry.raw_name)}"'


def _finding(code: str, entry: StationEntry, message: str) -> Finding:
    return Finding(
        code=code,
        severity=Severity.WARNING,
        message=message,
        row=entry.entry_row,
        event_date=entry.event_date,
        name=entry.raw_name,
    )


def link_station_entries(
    entries: Sequence[StationEntry], rounds: Sequence[LinkRound]
) -> tuple[list[StationLink], list[Finding]]:
    """Link each station entry to at most one round of the same shooter on the same day."""
    links: list[StationLink] = []
    findings: list[Finding] = []
    rounds_by_shooter: dict[tuple[date, int], list[LinkRound]] = defaultdict(list)
    for rnd in sorted(rounds, key=lambda r: (r.ordinal, r.round_id)):
        rounds_by_shooter[(rnd.event_date, rnd.shooter_id)].append(rnd)
    entries_by_shooter: dict[tuple[date, int], list[StationEntry]] = defaultdict(list)
    for entry in entries:
        if entry.shooter_id is None:
            links.append(StationLink(entry.event_date, entry.entry_row, None, None))
            findings.append(
                _finding(
                    "station_name_unmatched",
                    entry,
                    f"Station sheet name {_quoted(entry)} matches no shooter",
                )
            )
        else:
            entries_by_shooter[(entry.event_date, entry.shooter_id)].append(entry)
    for key, group in sorted(entries_by_shooter.items()):
        candidates = rounds_by_shooter.get(key, [])
        unused = list(candidates)
        linked: dict[int, LinkRound] = {}
        ordered = sorted(group, key=lambda e: (-e.total, e.entry_row))
        for entry in ordered:  # pass 1: exact score match, lowest ordinal first
            match = next((r for r in unused if r.score == entry.total), None)
            if match is not None:
                unused.remove(match)
                linked[entry.entry_row] = match
        for entry in ordered:  # pass 2: pair leftovers in ordinal order
            if entry.entry_row in linked:
                continue
            if not unused:
                links.append(StationLink(entry.event_date, entry.entry_row, entry.shooter_id, None))
                findings.append(
                    _finding(
                        "station_score_missing",
                        entry,
                        f"No score row left for {_quoted(entry)} (station total {entry.total})",
                    )
                )
                continue
            match = unused.pop(0)
            linked[entry.entry_row] = match
            if len(candidates) >= 2:
                findings.append(
                    _finding(
                        "station_round_ambiguous",
                        entry,
                        f"{_quoted(entry)} shot {len(candidates)} rounds; station total "
                        f"{entry.total} was paired with the round scored {match.score}",
                    )
                )
        for entry in group:
            match = linked.get(entry.entry_row)
            if match is None:
                continue
            links.append(
                StationLink(entry.event_date, entry.entry_row, entry.shooter_id, match.round_id)
            )
            if match.score != entry.total:
                findings.append(
                    _finding(
                        "station_score_mismatch",
                        entry,
                        f"Station total {entry.total} != score {match.score} for {_quoted(entry)}",
                    )
                )
    return links, findings
