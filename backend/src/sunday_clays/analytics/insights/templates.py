"""Insight text templates (spec §3.5): literal text and typed slots, rendered to segments.

Templates are code, not data. A clause is `named` (may hold shooter names; must be positive or
neutral) or `field_` (no names; may be negative about the club or the field). Rendering never
builds HTML: the output is a list of segments the frontend turns into React text nodes.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal, NotRequired, TypedDict

from sunday_clays.station_label import parse_label

MINUS = chr(0x2212)  # true minus sign, as lib/format.ts formatSigned writes it
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

Role = Literal["field", "named"]
SegmentKind = Literal["text", "shooter", "num", "date", "trophy", "station"]


class Segment(TypedDict):
    t: SegmentKind
    v: str
    id: NotRequired[int]


class TemplateError(ValueError):
    """A template asked for a param the Fact does not carry, or of the wrong type."""


def natural_name(display_name: str) -> str:
    """'Hadley, Ike' -> 'Ike Hadley'; a name without a comma is kept as written."""
    last, sep, first = display_name.partition(",")
    if not sep or not first.strip():
        return display_name.strip()
    return f"{first.strip()} {last.strip()}"


def _text(v: str) -> Segment:
    return {"t": "text", "v": v}


def _num(v: str) -> Segment:
    return {"t": "num", "v": v}


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_dec1(value: float) -> str:
    return f"{value:,.1f}"


def fmt_signed(value: float, digits: int = 1) -> str:
    magnitude = f"{abs(value):,.{digits}f}"
    if float(magnitude.replace(",", "")) == 0:
        return magnitude
    return f"+{magnitude}" if value > 0 else f"{MINUS}{magnitude}"


def fmt_ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def fmt_short_date(d: date) -> str:
    return f"{_MONTHS[d.month - 1]} {d.day}"


def fmt_full_date(d: date) -> str:
    return f"{_MONTHS[d.month - 1]} {d.day}, {d.year}"


def fmt_month_year(d: date) -> str:
    return f"{_MONTHS[d.month - 1]} {d.year}"


def fmt_sunday(d: date) -> str:
    return f"Sunday {d.month}/{d.day}"


def _param(params: Mapping[str, object], name: str) -> object:
    if name not in params:
        raise TemplateError(f"missing param {name!r}")
    return params[name]


def _as_int(params: Mapping[str, object], name: str) -> int:
    value = _param(params, name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TemplateError(f"param {name!r} must be a number")
    return round(value)


def _as_float(params: Mapping[str, object], name: str) -> float:
    value = _param(params, name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TemplateError(f"param {name!r} must be a number")
    return float(value)


def _as_date(params: Mapping[str, object], name: str) -> date:
    value = _param(params, name)
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TemplateError(f"param {name!r} must be a date")


def _as_ids(params: Mapping[str, object], name: str) -> list[int]:
    value = _param(params, name)
    if not isinstance(value, list | tuple) or not all(isinstance(v, int) for v in value):
        raise TemplateError(f"param {name!r} must be a list of shooter ids")
    return [int(v) for v in value]


@dataclass(frozen=True)
class Slot:
    """A typed hole in a template, filled from `params[param]`."""

    param: str

    #: numeric slots need a proof check (spec §3.3)
    numeric = False
    #: shooter-name slots (D9 and per-clause polarity rules)
    names_shooters = False

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        raise NotImplementedError


@dataclass(frozen=True)
class Shooter(Slot):
    names_shooters = True

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        sid = _as_int(params, self.param)
        return [{"t": "shooter", "id": sid, "v": names.get(sid, f"Shooter {sid}")}]


@dataclass(frozen=True)
class NameList(Slot):
    """Up to five shooters: 'A', 'A and B', 'A, B and C'."""

    names_shooters = True

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        ids = _as_ids(params, self.param)[:5]
        out: list[Segment] = []
        for i, sid in enumerate(ids):
            if i > 0:
                out.append(_text(" and " if i == len(ids) - 1 else ", "))
            out.append({"t": "shooter", "id": sid, "v": names.get(sid, f"Shooter {sid}")})
        return out


@dataclass(frozen=True)
class Int(Slot):
    numeric = True

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [_num(fmt_int(_as_int(params, self.param)))]


@dataclass(frozen=True)
class Dec1(Slot):
    numeric = True

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [_num(fmt_dec1(_as_float(params, self.param)))]


@dataclass(frozen=True)
class Signed(Slot):
    digits: int = 1
    numeric = True

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [_num(fmt_signed(_as_float(params, self.param), self.digits))]


@dataclass(frozen=True)
class Pct(Slot):
    """A percentage already on 0-100, written whole: '61%'."""

    numeric = True

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [_num(f"{_as_int(params, self.param)}%")]


@dataclass(frozen=True)
class Ordinal(Slot):
    numeric = True

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [_num(fmt_ordinal(_as_int(params, self.param)))]


@dataclass(frozen=True)
class Count(Slot):
    """'1 Sunday' / '3 Sundays': the number is a num segment, the noun plain text."""

    noun: str = ""
    plural: str = ""
    numeric = True

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        n = _as_int(params, self.param)
        noun = self.noun if n == 1 else (self.plural or f"{self.noun}s")
        return [_num(fmt_int(n)), _text(f" {noun}")]


@dataclass(frozen=True)
class Year(Slot):
    """A calendar year, written without a thousands separator."""

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [{"t": "date", "v": str(_as_int(params, self.param))}]


@dataclass(frozen=True)
class ShortDate(Slot):
    """'Aug 3'."""

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [{"t": "date", "v": fmt_short_date(_as_date(params, self.param))}]


@dataclass(frozen=True)
class FullDate(Slot):
    """'Jun 1, 2025'."""

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [{"t": "date", "v": fmt_full_date(_as_date(params, self.param))}]


@dataclass(frozen=True)
class MonthYear(Slot):
    """'Aug 2024'."""

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [{"t": "date", "v": fmt_month_year(_as_date(params, self.param))}]


@dataclass(frozen=True)
class SundayDate(Slot):
    """'Sunday 9/27'."""

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [{"t": "date", "v": fmt_sunday(_as_date(params, self.param))}]


@dataclass(frozen=True)
class Word(Slot):
    """One of a fixed set of literal phrases, chosen by `params[param]` (linted at import)."""

    choices: tuple[tuple[str, str], ...] = ()

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        key = str(_param(params, self.param))
        table = dict(self.choices)
        if key not in table:
            raise TemplateError(f"param {self.param!r}={key!r} is not a known choice")
        return [_text(table[key])]


@dataclass(frozen=True)
class TrophyName(Slot):
    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        return [{"t": "trophy", "v": str(_param(params, self.param))}]


@dataclass(frozen=True)
class Station(Slot):
    """'Station 7' or 'Station 7A': the param is a station number or a label."""

    numeric = True

    def segments(self, params: Mapping[str, object], names: Mapping[int, str]) -> list[Segment]:
        value = _param(params, self.param)
        label = parse_label(value)
        if label is None:
            raise TemplateError(f"param {self.param!r} must be a station number or label")
        return [{"t": "station", "v": f"Station {label}"}]


Part = str | Slot


@dataclass(frozen=True)
class Clause:
    role: Role
    parts: tuple[Part, ...]


def named(*parts: Part) -> Clause:
    """A clause that may name shooters; it must be positive or neutral (D1)."""
    return Clause("named", parts)


def field_(*parts: Part) -> Clause:
    """A name-free clause about the club or the field; it may be negative."""
    return Clause("field", parts)


@dataclass(frozen=True)
class Template:
    """Third-person clauses plus, for shooter subjects, the second-person ("you") twin."""

    third: tuple[Clause, ...]
    you: tuple[Clause, ...] | None = None


def T(*third: Clause, you: Clause | tuple[Clause, ...] | None = None) -> Template:
    if isinstance(you, Clause):
        you = (you,)
    return Template(third=third, you=you)


def slots(clauses: Sequence[Clause]) -> Iterator[Slot]:
    for clause in clauses:
        for part in clause.parts:
            if isinstance(part, Slot):
                yield part


def template_slots(t: Template) -> Iterator[Slot]:
    yield from slots(t.third)
    if t.you is not None:
        yield from slots(t.you)


def literal_texts(clause: Clause) -> list[str]:
    """The clause's own words: literal parts plus every Word choice (for the lints)."""
    out: list[str] = []
    for part in clause.parts:
        if isinstance(part, str):
            out.append(part)
        elif isinstance(part, Word):
            out.extend(text for _key, text in part.choices)
    return out


def render(
    t: Template,
    params: Mapping[str, object],
    names: Mapping[int, str],
    *,
    you: bool = False,
) -> list[Segment]:
    """Segments for the chosen person form; adjacent text segments are merged."""
    clauses = t.you if you and t.you is not None else t.third
    out: list[Segment] = []
    for i, clause in enumerate(clauses):
        if i > 0:
            out.append(_text(" "))
        for part in clause.parts:
            out.extend([_text(part)] if isinstance(part, str) else part.segments(params, names))
    merged: list[Segment] = []
    for seg in out:
        if seg["v"] == "":
            continue
        if merged and seg["t"] == "text" and merged[-1]["t"] == "text":
            merged[-1] = _text(merged[-1]["v"] + seg["v"])
        else:
            merged.append(seg)
    return merged


def plain(segments: Sequence[Segment]) -> str:
    return "".join(seg["v"] for seg in segments)
