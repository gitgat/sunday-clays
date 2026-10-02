"""Value types shared by the workbook parsers (Architecture Contract C3).

Pure module: no database, no I/O.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import ClassVar


class FileKind(StrEnum):
    SCORES = "scores"
    STATIONS = "stations"
    SPECIAL = "special"  # Plan 17: one special Sunday with its own label and target total


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ParseError(Exception):
    """An upload that cannot be used at all; ``str(error)`` is shown to the admin."""


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    sheet: str | None = None
    row: int | None = None
    event_date: date | None = None
    name: str | None = None


@dataclass(frozen=True)
class ScoreRow:
    row_number: int
    raw_name: str
    score: int
    event_date: date
    status: str | None
    gauge_class: str | None


@dataclass(frozen=True)
class AttendanceRow:
    row_number: int
    event_date: date
    head_count: int


@dataclass(frozen=True)
class ScoresParse:
    score_rows: tuple[ScoreRow, ...]
    attendance_rows: tuple[AttendanceRow, ...]
    findings: tuple[Finding, ...]
    kind: ClassVar[FileKind] = FileKind.SCORES


@dataclass(frozen=True)
class StationLayoutEntry:
    """One station column: `station_no` is the sort integer, `label` the text ("7A")."""

    station_no: int
    target_count: int
    label: str = ""

    def __post_init__(self) -> None:
        if not self.label:  # a plain numbered station is labelled by its number
            object.__setattr__(self, "label", str(self.station_no))


@dataclass(frozen=True)
class StationHitsRow:
    row_number: int
    raw_name: str
    hits: tuple[tuple[str, int], ...]  # (station label, hits) in layout order


@dataclass(frozen=True)
class StationSheet:
    sheet_name: str
    event_date: date
    layout: tuple[StationLayoutEntry, ...]
    rows: tuple[StationHitsRow, ...]


@dataclass(frozen=True)
class StationsParse:
    sheets: tuple[StationSheet, ...]
    findings: tuple[Finding, ...]
    kind: ClassVar[FileKind] = FileKind.STATIONS


@dataclass(frozen=True)
class SpecialRow:
    """One shooter's row on a special-event sheet: (station label, hits) in layout order."""

    row_number: int
    raw_name: str
    hits: tuple[tuple[str, int], ...]

    @property
    def total(self) -> int:
        """The score: always recomputed from the stations, never read from a total cell."""
        return sum(hits for _, hits in self.hits)


@dataclass(frozen=True)
class SpecialParse:
    """A special event (Plan 17): one Sunday, its own name and target total, one round each."""

    event_date: date
    label: str
    layout: tuple[StationLayoutEntry, ...]
    rows: tuple[SpecialRow, ...]
    findings: tuple[Finding, ...]
    kind: ClassVar[FileKind] = FileKind.SPECIAL

    @property
    def target_total(self) -> int:
        return sum(entry.target_count for entry in self.layout)


ParsedUpload = ScoresParse | StationsParse | SpecialParse

# Codes of the findings parse_stations emits when it leaves a whole sheet out.
# Each such finding has `sheet` set and `row` None (Plan 03 T3 builds
# StationsDiff.sheets_skipped from them).
STATION_SHEET_EXCLUSION_CODES: frozenset[str] = frozenset(
    {
        "empty_station_sheet",
        "duplicate_sheet_date",
        "sheet_date_missing",
        "station_layout_missing",
    }
)
