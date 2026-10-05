"""Pure helpers for the ClaySmasher scores export (skipped by router discovery).

The export is one CSV per discipline in ClaySmasher's Scores CSV import format (the app's
ScoreCsvFormat, sporting family): '#' comment lines, a header row of Date, Name, Tournament?,
Location, Course, Gun, Gauge, Ammo, Weather, Total Hits, Total Targets, Notes, then a
'Station n Hits' / 'Station n Targets' pair per station. ClaySmasher locates columns by header
name, drops rows whose first cell starts with '#' and skips any row whose Name contains "example".
"""

import csv
import io
import re
import unicodedata
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from sunday_clays.domain.round_type import RoundType
from sunday_clays.station_label import label_sort_key

# A round without station data: the club's 50-target round (ingest.validate.LAYOUT_TOTAL).
TARGETS_PER_ROUND = 50
# ClaySmasher's template has 15 station pairs; its parser takes any number.
STATION_COLUMNS = 15
CLUB_LOCATION = "Tri-County Gun Club"
EVENT_NAME = "Sunday Clays"
SOURCE_NOTE = "Imported from Sunday Clays"

# Discipline -> (file name in the zip, the discipline's name in ClaySmasher's import picker).
DISCIPLINES: dict[RoundType, tuple[str, str]] = {
    RoundType.SPORTING: ("claysmasher-sporting.csv", "Sporting Clays"),
    RoundType.SUPER_SPORTING: ("claysmasher-super-sporting.csv", "Super Sport"),
}
_FIXED_COLUMNS = (
    "Date",
    "Name",
    "Tournament?",
    "Location",
    "Course",
    "Gun",
    "Gauge",
    "Ammo",
    "Weather",
    "Total Hits",
    "Total Targets",
    "Notes",
)

RoundNaturalKey = tuple[date, str, int]


@dataclass(frozen=True)
class ExportStation:
    label: str
    targets: int
    hits: int


@dataclass(frozen=True)
class ExportRound:
    """One live regular-Sunday round; `stations` are in shot (station) order."""

    event_date: date
    number: int  # the shooter's 1-based round number that day (day_ordinals)
    round_type: RoundType
    score: int
    gauge_class: str | None
    stations: tuple[ExportStation, ...]

    @property
    def target_count(self) -> int:
        """The stations' targets, or the club's 50 when the round has no station data."""
        if self.stations:
            return sum(station.targets for station in self.stations)
        return TARGETS_PER_ROUND


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


def header(stations: int) -> list[str]:
    """The header row with max(stations, 15) Hits/Targets pairs."""
    pairs = [
        column
        for n in range(1, max(stations, STATION_COLUMNS) + 1)
        for column in (f"Station {n} Hits", f"Station {n} Targets")
    ]
    return [*_FIXED_COLUMNS, *pairs]


def round_name(number: int) -> str:
    """The round's title in ClaySmasher. Never contains "example" (ClaySmasher skips those)."""
    return EVENT_NAME if number == 1 else f"{EVENT_NAME} (round {number})"


def _notes(round_out: ExportRound) -> str:
    # The gauge class ("20 Gauge", "Sub-gauge") goes here: ClaySmasher's Gauge column only
    # accepts 12/16/20/28/410 and rejects the whole row otherwise.
    if round_out.gauge_class:
        return f"{SOURCE_NOTE}; class: {round_out.gauge_class}"
    return SOURCE_NOTE


def _row(round_out: ExportRound, stations: int) -> list[str]:
    cells = [
        round_out.event_date.strftime("%m/%d/%Y"),
        round_name(round_out.number),
        "",  # Tournament?: blank = practice; a club Sunday is not a registered shoot
        CLUB_LOCATION,
        "",  # Course
        "",  # Gun
        "",  # Gauge
        "",  # Ammo
        "",  # Weather
        str(round_out.score),
        str(round_out.target_count),
        _notes(round_out),
    ]
    for station in round_out.stations:
        cells += [str(station.hits), str(station.targets)]
    width = len(_FIXED_COLUMNS) + 2 * max(stations, STATION_COLUMNS)
    return cells + [""] * (width - len(cells))


def render_csv(rounds: Iterable[ExportRound], discipline: RoundType, shooter_name: str) -> str:
    """One discipline's ClaySmasher import file: comments, header, a row per round by date."""
    ordered = sorted(rounds, key=lambda r: (r.event_date, r.number))
    for round_out in ordered:
        if round_out.round_type != discipline:
            raise ValueError(f"a {round_out.round_type} round in the {discipline} file")
    stations = max((len(r.stations) for r in ordered), default=0)
    picker = DISCIPLINES[discipline][1]
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n")
    # Each comment is a single cell, so a comma or quote in a name cannot split it.
    for comment in (
        f"# ClaySmasher score import - {picker} - from {EVENT_NAME} at {CLUB_LOCATION}",
        f"# Shooter: {shooter_name}",
        "# In ClaySmasher: Settings > Import & export scores > Import from CSV"
        f" (discipline {picker}).",
        "# Lines starting with # are ignored on import.",
    ):
        writer.writerow([comment])
    writer.writerow(header(stations))
    writer.writerows(_row(round_out, stations) for round_out in ordered)
    return out.getvalue()


def export_files(rounds: Sequence[ExportRound], shooter_name: str) -> dict[str, str]:
    """File name -> CSV text, one file per discipline the shooter has rounds in."""
    files: dict[str, str] = {}
    for discipline, (filename, _) in DISCIPLINES.items():
        mine = [r for r in rounds if r.round_type == discipline]
        if mine:
            files[filename] = render_csv(mine, discipline, shooter_name)
    return files


def zip_files(files: Mapping[str, str]) -> bytes:
    """A deflated zip holding each text file as UTF-8 (no BOM)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode("utf-8"))
    return buffer.getvalue()


def shooter_slug(display_name: str, shooter_id: int) -> str:
    """An ASCII slug of the name for the download's file name; `shooter-<id>` if none is left."""
    folded = unicodedata.normalize("NFKD", display_name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.casefold()).strip("-")
    return slug or f"shooter-{shooter_id}"
