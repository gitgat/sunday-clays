"""Parse the typed text layer of a weekly "Sunday Clays Update" PDF (`pdftotext -layout` output)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

_DATE_RE = re.compile(r"Sunday,\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})")
_RESULT_RE = re.compile(
    r"^\s*(?:(?P<note>[A-Z]{1,2})\s+)?(?:(?P<place>\d{1,3})\s+)?"
    r"(?P<name>[A-Za-z][^,\n]*?, \S.*?)\s{2,}(?P<hits>\d{1,2})"
    r"(?:\s{2,}(?P<gauge>\d+\s+Gauge|\.410))?(?:\s+(?P<rank>\d{1,3}))?\s*$"
)
_TAIL = r"(?P<traps>[A-Z](?:-[A-Z])*)(?:\s+[A-Za-z]+-[A-Za-z]+)?(?:\s+(?P<count>\d+))?(?:\s{2,}.*)?$"
_STATION_RE = re.compile(
    r"^\s+(?P<stn>\d{1,2}[A-Z]?)\s+(?P<tgts>\d{1,2})\s+(?P<reps>\d+)\s+(?P<pres>[A-Za-z][A-Za-z ]*?)\s+" + _TAIL
)
_PRESENTATION_RE = re.compile(r"^\s+(?:(?P<reps>\d+)\s+)?(?P<pres>[A-Za-z][A-Za-z ]*?)\s+" + _TAIL)
_COURSE_HEADING_RE = re.compile(r"COURSE (?:ARRANGEMENT|DESIGN) SHEET")


@dataclass(frozen=True)
class ResultRow:
    name: str  # "Last, First"
    hits: int
    note: str | None = None  # G, N, PB, NG
    gauge: str | None = None


@dataclass(frozen=True)
class Presentation:
    reps: int | None  # blank on a continuation line of some weeks
    presentation: str
    traps: str
    targets: int | None  # the Count column; absent in some weeks


@dataclass(frozen=True)
class Course:
    stations: tuple[tuple[int | str, int], ...]  # (station, target count) in course order; a label may be like 7A
    presentations: dict[str, tuple[Presentation, ...]] = field(default_factory=dict)


def parse_date(text: str) -> date | None:
    """The Sunday named in the typed header ("Sunday, May 31, 2026")."""
    match = _DATE_RE.search(text)
    if match is None:
        return None
    try:
        return datetime.strptime(" ".join(match.groups()), "%B %d %Y").date()
    except ValueError:
        return None


def parse_results(text: str) -> tuple[ResultRow, ...]:
    """Rows of the "Note Place Name Hits Class" table; the table ends at "Average Score"."""
    lines = text.splitlines()
    start = next((i + 1 for i, line in enumerate(lines) if re.search(r"Note\s+Place\s+Name", line)), 0)
    rows: list[ResultRow] = []
    for line in lines[start:]:
        if "Average Score" in line:
            break
        match = _RESULT_RE.match(line)
        if match is None:
            continue
        rows.append(
            ResultRow(
                name=match["name"].strip(),
                hits=int(match["hits"]),
                note=match["note"],
                gauge=match["gauge"],
            )
        )
    return tuple(rows)


def parse_course(text: str) -> Course:
    """Station -> target count and its presentation lines from the COURSE ARRANGEMENT SHEET."""
    parts = _COURSE_HEADING_RE.split(text, maxsplit=1)
    if len(parts) < 2:
        return Course(stations=())
    block = parts[1]
    stations: dict[str, int] = {}
    presentations: dict[str, list[Presentation]] = {}
    current: str | None = None
    for line in block.splitlines():
        header = _STATION_RE.match(line)
        if header is not None:
            stn = header["stn"]
            if stn in stations:
                current = None
                continue
            current = stn
            stations[stn] = int(header["tgts"])
            presentations[stn] = [_presentation(header)]
            continue
        more = _PRESENTATION_RE.match(line)
        if more is not None and current is not None:
            presentations[current].append(_presentation(more))
    return Course(
        stations=tuple((int(stn) if stn.isdigit() else stn, tgts) for stn, tgts in stations.items()),
        presentations={stn: tuple(items) for stn, items in presentations.items()},
    )


def _presentation(match: re.Match[str]) -> Presentation:
    reps, count = match["reps"], match["count"]
    return Presentation(
        None if reps is None else int(reps),
        match["pres"].upper(),
        match["traps"],
        None if count is None else int(count),
    )
