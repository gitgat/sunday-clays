"""Insight value types (spec §3.1, §3.3, §3.6): enums, facts, chart links and proof checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Literal

from sunday_clays.analytics.insights.templates import Template
from sunday_clays.explorer.spec import QuerySpec


class Family(StrEnum):
    FORM = "form"
    STREAK = "streak"
    MILESTONE = "milestone"
    RACE = "race"
    RECORD = "record"
    WEATHER = "weather"
    TURNOUT = "turnout"
    NEWCOMER = "newcomer"
    STATION = "station"
    TROPHY = "trophy"
    RECAP = "recap"


class HomeSlot(StrEnum):
    FIELD = "field"
    PERSON = "person"
    MILESTONE = "milestone"
    RACE_RECORD = "race_record"


class SubjectType(StrEnum):
    SHOOTER = "shooter"
    SUNDAY = "sunday"
    CLUB = "club"
    SEASON = "season"
    STATION = "station"


class Page(StrEnum):
    PROFILE = "profile"
    SUNDAY = "sunday"
    HOME = "home"
    CLUB = "club"
    LEADERBOARDS = "leaderboards"
    RECORDS = "records"
    STATIONS = "stations"


class Polarity(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    FIELD_NEGATIVE = "field_negative"
    MIXED = "mixed"


P = Page  # short alias used by the kind modules' `pages=` sets
# Anchored rows leave a page after this many later held Sundays; the club, leaderboards, records
# and stations pages show only the latest Sunday's anchored rows (plus evergreen ones).
DEFAULT_EXPIRES: Mapping[Page, int] = {
    Page.HOME: 3,
    Page.PROFILE: 3,
    Page.CLUB: 1,
    Page.LEADERBOARDS: 1,
    Page.RECORDS: 1,
    Page.STATIONS: 1,
}
ROLLUP = "rollup"  # the variant of a Sunday/home roll-up card (spec §3.4 roll-ups)
PROFILE = "profile"  # the variant of an evergreen profile row (spec §3.1)


@dataclass(frozen=True, kw_only=True)
class Fact:
    """What a generator found. It never carries text (spec §3.3)."""

    subject_id: str
    anchor_date: date | None
    variant: str
    pages: frozenset[Page]
    params: Mapping[str, object] = field(hash=False)
    strength: float
    named_shooter_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Window:
    """The chart link's explicit evidence window, both ends inclusive (spec §3.6.1)."""

    start: date
    end: date

    def to_json(self) -> dict[str, str]:
        return {"from": self.start.isoformat(), "to": self.end.isoformat()}


@dataclass(frozen=True)
class Highlight:
    """What the target chart draws in the accent colour (`hl`, spec §3.6.2)."""

    dates: tuple[date, ...] = ()
    shooter_ids: tuple[int, ...] = ()
    keys: tuple[str, ...] = ()
    span: tuple[date, date] | None = None

    def to_json(self) -> dict[str, list[str | int]]:
        out: dict[str, list[str | int]] = {}
        if self.dates:
            out["dates"] = [d.isoformat() for d in self.dates]
        if self.shooter_ids:
            out["shooter_ids"] = list(self.shooter_ids)
        if self.keys:
            out["keys"] = list(self.keys)
        if self.span is not None:
            out["span"] = [self.span[0].isoformat(), self.span[1].isoformat()]
        return out


NO_HIGHLIGHT = Highlight()


@dataclass(frozen=True, kw_only=True, eq=False)
class ChartLink:
    """An Explorer link or a page chart anchor. `label` must be one of the kind's `labels`."""

    type: Literal["explorer", "page"]
    label: Template
    window: Window
    highlight: Highlight = NO_HIGHLIGHT
    spec: QuerySpec | None = None
    chart_type: Literal["bar", "line"] | None = None
    ref: float | None = None
    compare: QuerySpec | None = None
    route: str | None = None
    anchor: str | None = None
    params: Mapping[str, str] = field(default_factory=dict)
    also: tuple[ChartLink, ...] = ()


class ProofHow(StrEnum):
    CELL = "cell"  # the value column of the single highlighted row
    SUM = "sum"  # sum over the highlighted rows (every row when nothing is highlighted)
    MEAN = "mean"  # mean over the highlighted rows
    COUNT = "count"  # number of highlighted rows with a value in the column
    RUN = "run"  # length of the run of consecutive highlighted rows
    RANK = "rank"  # 1-based position of the highlighted row, value descending
    ROWS = "rows"  # number of rows in the whole table
    MAX_BEFORE = "max_before"  # max of the column over rows before the first highlighted row
    SHARE = "share"  # percent of rows whose column >= threshold
    DIFF = "diff"  # the `key` row's value minus the `other` row's (a gap between two bars)
    LEAD = "lead"  # the largest value minus the next largest (the gap between the top two bars)
    DISTINCT = "distinct"  # number of different values of the column among the highlighted rows
    NA = "na"  # not readable off the chart (e.g. a sample size quoted in "how")


@dataclass(frozen=True)
class ProofCheck:
    """How one headline number is found in the chart's rows (spec §5 chart-proof test)."""

    param: str
    how: ProofHow
    column: str = "value"
    threshold: float | None = None
    reason: str = ""
    key: str | None = None  # CELL/RANK/DIFF: the row whose key is params[key] (else the hl rows)
    absolute: bool = False  # CELL/DIFF: compare the size (the text says "tougher"/"easier")
    other: str | None = None  # DIFF: the row subtracted, whose key equals params[other]


def cell(
    param: str, column: str = "value", *, key: str | None = None, absolute: bool = False
) -> ProofCheck:
    return ProofCheck(param, ProofHow.CELL, column, key=key, absolute=absolute)


def total(param: str, column: str = "value") -> ProofCheck:
    return ProofCheck(param, ProofHow.SUM, column)


def mean_of(param: str, column: str = "value") -> ProofCheck:
    return ProofCheck(param, ProofHow.MEAN, column)


def count_rows(param: str, column: str = "value") -> ProofCheck:
    return ProofCheck(param, ProofHow.COUNT, column)


def run_length(param: str) -> ProofCheck:
    return ProofCheck(param, ProofHow.RUN)


def rank_of(param: str, column: str = "value", *, key: str | None = None) -> ProofCheck:
    return ProofCheck(param, ProofHow.RANK, column, key=key)


def rows_total(param: str) -> ProofCheck:
    return ProofCheck(param, ProofHow.ROWS)


def max_before(param: str, column: str = "value") -> ProofCheck:
    return ProofCheck(param, ProofHow.MAX_BEFORE, column)


def share(param: str, threshold: float, column: str = "value") -> ProofCheck:
    return ProofCheck(param, ProofHow.SHARE, column, threshold)


def diff(
    param: str, key: str, other: str, column: str = "value", *, absolute: bool = False
) -> ProofCheck:
    return ProofCheck(param, ProofHow.DIFF, column, key=key, other=other, absolute=absolute)


def lead(param: str, column: str = "value") -> ProofCheck:
    return ProofCheck(param, ProofHow.LEAD, column)


def distinct(param: str, column: str) -> ProofCheck:
    return ProofCheck(param, ProofHow.DISTINCT, column)


def na(param: str, reason: str) -> ProofCheck:
    return ProofCheck(param, ProofHow.NA, reason=reason)


@dataclass(frozen=True)
class Requires:
    """Readiness a dormant kind waits for (spec §4.5)."""

    station_sundays: int = 0
    trophy_awards: int = 0

    def unmet(self, readiness: Readiness) -> str | None:
        if readiness.station_sundays < self.station_sundays:
            return (
                f"needs {self.station_sundays} Sundays with station sheets "
                f"(has {readiness.station_sundays})"
            )
        if readiness.trophy_awards < self.trophy_awards:
            return "needs at least one trophy award"
        return None


@dataclass(frozen=True)
class Readiness:
    station_sundays: int
    trophy_awards: int


@dataclass(frozen=True)
class Scope:
    """Anchored kinds emit Facts only for `sundays`; evergreen kinds are evaluated as of `as_of`."""

    sundays: frozenset[date]
    as_of: date


# --- typed access to Fact params (chart builders read them back) ---------------------------------


def p_int(params: Mapping[str, object], name: str) -> int:
    value = params[name]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"param {name!r} is not a number")
    return round(value)


def p_date(params: Mapping[str, object], name: str) -> date:
    value = params[name]
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"param {name!r} is not a date")


def p_ids(params: Mapping[str, object], name: str) -> tuple[int, ...]:
    value = params[name]
    if not isinstance(value, list | tuple):
        raise TypeError(f"param {name!r} is not a list")
    return tuple(int(v) for v in value)


def p_str(params: Mapping[str, object], name: str) -> str:
    return str(params[name])
