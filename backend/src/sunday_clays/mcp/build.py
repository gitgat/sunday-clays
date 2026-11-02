"""Pure workbook builders: a validated week (or correction) becomes import workbooks.

Port of the weekly-import skill's build script. The scores workbook is the latest committed
scores import with the new rows appended (the parser treats an upload as the full history);
the stations workbook is a fresh one-sheet file. No DB access.
"""

import datetime as dt
import io
import re
import unicodedata
from typing import Annotated, Self

import openpyxl
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from sunday_clays.ingest.names import name_key
from sunday_clays.ingest.scores import _GAUGES
from sunday_clays.station_label import parse_label

SCORES_SHEET = "ALL SCORE DETAIL"
ATTENDANCE_SHEET = "Attendance History"
TOTAL_TARGETS = 50
KNOWN_CLASSES = frozenset(_GAUGES.values()) | {"Pump"}

StationLabel = Annotated[str, Field(min_length=1, max_length=4)]


class BuildError(Exception):
    """A refusal with a stable code (the message)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_NAME_PART = re.compile(r"[^\W\d_]+(?:[ '\u2019.-]+[^\W\d_]+)*\.?")


def _check_name(value: str) -> str:
    """'Last, First' of letters, spaces, apostrophes, hyphens and periods; never a formula."""
    if any(unicodedata.category(ch).startswith("C") for ch in value):
        raise ValueError("name must not hold control characters or newlines")
    if value.count(",") != 1:
        raise ValueError("name must be 'Last, First' with exactly one comma")
    last, first = (part.strip() for part in value.split(","))
    if not last or not first:
        raise ValueError("name must be 'Last, First'")
    for part in (last, first):
        if not _NAME_PART.fullmatch(part):
            raise ValueError("name may only hold letters, spaces, apostrophes, hyphens and periods")
    clean = f"{last}, {first}"
    if not 3 <= len(clean) <= 60:
        raise ValueError("name must be 3-60 characters")
    return clean


def _dup_keys(names: list[str]) -> bool:
    keys = [name_key(n) for n in names]
    return len(set(keys)) != len(keys)


def _check_hits(name: str, hits: list[int], counts: list[int], score: int) -> None:
    if len(hits) != len(counts):
        raise ValueError(f"{name}: hits must have one value per station")
    if any(not 0 <= h <= c for h, c in zip(hits, counts, strict=True)):
        raise ValueError(f"{name}: a station has hits outside 0..target count")
    if sum(hits) != score:
        raise ValueError(f"{name}: hits sum to {sum(hits)}, not the score {score}")


def _check_layout(stations: list[str], counts: list[int]) -> None:
    if len(stations) != len(counts):
        raise ValueError("stations and counts must be the same length")
    labels = [parse_label(s) for s in stations]
    if any(label is None or label != s for label, s in zip(labels, stations, strict=True)):
        raise ValueError("each station must be a label such as '7' or '7A'")
    if len(set(stations)) != len(stations):
        raise ValueError("duplicate station label")
    if sum(counts) != TOTAL_TARGETS:
        raise ValueError(f"target counts must sum to {TOTAL_TARGETS}")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ShooterRow(_Model):
    name: str
    score: StrictInt = Field(ge=0, le=50)
    status: str = Field(pattern=r"^(Member|Guest)$")
    class_: str | None = Field(default=None, alias="class")
    hits: list[StrictInt] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _check_name(value)

    @field_validator("class_")
    @classmethod
    def _class(cls, value: str | None) -> str | None:
        if value is not None and value not in KNOWN_CLASSES:
            raise ValueError(f"class must be one of {sorted(KNOWN_CLASSES)}")
        return value


class WeekInput(_Model):
    date: dt.date
    stations: list[StationLabel] = Field(min_length=1, max_length=12)
    counts: list[StrictInt] = Field(min_length=1, max_length=12)
    expected_total: StrictInt | None = None
    shooters: list[ShooterRow] = Field(min_length=1, max_length=200)

    @field_validator("counts")
    @classmethod
    def _each_count(cls, value: list[int]) -> list[int]:
        if any(not 1 <= c <= 10 for c in value):
            raise ValueError("each target count must be 1-10")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _check_layout(self.stations, self.counts)
        if _dup_keys([s.name for s in self.shooters]):
            raise ValueError("duplicate shooter name")
        for s in self.shooters:
            if s.hits is not None:
                _check_hits(s.name, s.hits, self.counts, s.score)
        total = sum(s.score for s in self.shooters)
        if self.expected_total is not None and self.expected_total != total:
            raise ValueError(f"scores sum to {total}, not expected_total {self.expected_total}")
        return self


class CorrectionRow(_Model):
    """Score-only: a stations import replaces the whole day, so corrections carry no hits."""

    name: str
    score: StrictInt = Field(ge=0, le=50)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _check_name(value)


class CorrectionInput(_Model):
    date: dt.date
    rows: list[CorrectionRow] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if _dup_keys([r.name for r in self.rows]):
            raise ValueError("duplicate shooter name")
        return self


def _midnight(day: dt.date) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day)  # noqa: DTZ001 - workbook dates are naive


def _as_date(value: object) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return None


def _load(base: bytes) -> openpyxl.Workbook:
    return openpyxl.load_workbook(io.BytesIO(base))


def _save(wb: openpyxl.Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_scores(base: bytes, week: WeekInput) -> bytes:
    day = _midnight(week.date)
    wb = _load(base)
    ws = wb[SCORES_SHEET]
    if any(_as_date(r[2]) == week.date for r in ws.iter_rows(min_row=2, values_only=True)):
        raise BuildError("date_present")
    for s in sorted(week.shooters, key=lambda s: -s.score):
        ws.append([s.name, s.score, day, s.status, s.class_])
    att = wb[ATTENDANCE_SHEET]
    found = False
    for row in att.iter_rows(min_row=2):
        if _as_date(row[0].value) == week.date:
            row[1].value = len(week.shooters)
            found = True
    if not found:
        att.append([day, len(week.shooters), None])
    return _save(wb)


def _stations_workbook(
    day: dt.date, stations: list[str], counts: list[int], rows: list[tuple[str, list[int]]]
) -> bytes | None:
    if not rows:
        return None
    out = openpyxl.Workbook()
    w = out.active
    if w is None:  # a new workbook always has an active sheet
        raise BuildError("workbook_error")
    w.title = day.strftime("%m %d %y")
    w.append(["Event Date"])
    w.append([_midnight(day)])
    w.append([])
    w.append(["STATION #", *stations, "Total"])
    w.append(["TARGET COUNT", *counts, sum(counts)])
    w.append([])
    w.append(["Name", "Station Hits"])
    for name, hits in rows:
        w.append([name, *hits, sum(hits)])
    return _save(out)


def build_stations(week: WeekInput) -> bytes | None:
    rows = [(s.name, s.hits) for s in week.shooters if s.hits]
    return _stations_workbook(week.date, week.stations, week.counts, rows)


def build_correction(base: bytes, c: CorrectionInput) -> bytes:
    wb = _load(base)
    ws = wb[SCORES_SHEET]
    on_date: dict[str, list[int]] = {}
    for row in ws.iter_rows(min_row=2):
        if _as_date(row[2].value) == c.date and isinstance(row[0].value, str):
            on_date.setdefault(name_key(row[0].value), []).append(row[0].row)
    for r in c.rows:
        matches = on_date.get(name_key(r.name), [])
        if not matches:
            raise BuildError("name_not_on_date")
        if len(matches) > 1:
            raise BuildError("name_ambiguous")
        ws.cell(matches[0], 2).value = r.score
    return _save(wb)
