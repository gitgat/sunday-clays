"""Reads and writes of the `insights` and `insight_picks` tables (spec §3.1), by C4 table name."""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement, Table, delete, func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.templates import Segment
from sunday_clays.analytics.insights.types import Readiness
from sunday_clays.models import AppState, Base

COLUMNS: tuple[str, ...] = (
    "key",
    "value_hash",
    "generation",
    "first_generation",
    "kind",
    "family",
    "home_slot",
    "subject_type",
    "subject_id",
    "anchor_date",
    "variant",
    "pages",
    "expires",
    "named_shooter_ids",
    "polarity",
    "kudos",
    "template_id",
    "params",
    "strength",
    "base_score",
    "rank_score",
    "headline",
    "headline_you",
    "how",
    "how_you",
    "chart",
)
_JSONB = frozenset({"expires", "params", "headline", "headline_you", "how", "how_you", "chart"})


@dataclass(frozen=True)
class InsightRow:
    key: str
    value_hash: str
    generation: int
    first_generation: int
    kind: str
    family: str
    home_slot: str | None
    subject_type: str
    subject_id: str
    anchor_date: date | None
    variant: str
    pages: tuple[str, ...]
    expires: Mapping[str, int]
    named_shooter_ids: tuple[int, ...]
    polarity: str
    kudos: bool
    template_id: str
    params: Mapping[str, Any]
    strength: float
    base_score: float
    rank_score: float
    headline: list[Segment]
    headline_you: list[Segment] | None
    how: list[list[Segment]]
    how_you: list[list[Segment]] | None
    chart: Mapping[str, Any]

    def is_new_since(self, new_since: int | None) -> bool:
        """New = first seen at or after the last upload's generation (none recorded: this run)."""
        return self.first_generation >= (self.generation if new_since is None else new_since)

    @property
    def kudos_sunday(self) -> date | None:
        """The Sunday whose kudos strip shows this row (spec §3.4 Kudos)."""
        value = self.params.get("kudos_sunday")
        return date.fromisoformat(value) if isinstance(value, str) else self.anchor_date


@dataclass(frozen=True)
class Pick:
    sunday: date
    slot: str  # 'hero' | 'spotlight'
    insight_key: str


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def to_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=_json_default)


def _tables() -> tuple[Table, Table]:
    tables = Base.metadata.tables
    return tables["insights"], tables["insight_picks"]


def _bind(row: InsightRow) -> dict[str, object]:
    """Column values; JSON columns go through JSON once so dates become ISO strings."""
    out: dict[str, object] = {}
    for c in COLUMNS:
        value = getattr(row, c)
        if c in _JSONB:
            out[c] = None if value is None else json.loads(to_json(value))
        elif c in ("pages", "named_shooter_ids"):
            out[c] = list(value)
        else:
            out[c] = value
    return out


def previous_versions(session: Session) -> dict[str, tuple[str, int]]:
    """key -> (value_hash, first_generation) of the rows about to be replaced."""
    insights, _ = _tables()
    result = session.execute(
        select(insights.c.key, insights.c.value_hash, insights.c.first_generation)
    )
    return {str(k): (str(h), int(g)) for k, h, g in result}


NEW_SINCE_KEY = "insights_new_since"


def get_new_since(session: Session) -> int | None:
    """The generation of the last upload's recompute, or None if no upload has been recorded."""
    value = session.scalar(select(AppState.value).where(AppState.key == NEW_SINCE_KEY))
    return None if value is None else int(value)


def set_new_since(session: Session, generation: int) -> None:
    """Record the generation the upload's own recompute will write ("New" means since then).

    Weather and admin recomputes run later with higher generations but leave this alone, so a
    row first seen by the upload stays New until the next upload (spec §3.1, final review I-1).
    """
    session.execute(
        pg_insert(AppState)
        .values(key=NEW_SINCE_KEY, value=generation)
        .on_conflict_do_update(index_elements=[AppState.key], set_={"value": generation})
    )


def replace_all(session: Session, rows: Sequence[InsightRow], picks: Sequence[Pick]) -> None:
    """Full replace inside the caller's (pipeline) transaction (spec §3.2 step 6)."""
    insights, picks_table = _tables()
    session.execute(delete(insights))
    session.execute(delete(picks_table))
    if rows:
        session.execute(insert(insights), [_bind(r) for r in rows])
    if picks:
        session.execute(
            insert(picks_table),
            [{"sunday": p.sunday, "slot": p.slot, "insight_key": p.insight_key} for p in picks],
        )


def _row(record: Mapping[str, Any]) -> InsightRow:
    values = {c: record[c] for c in COLUMNS}
    values["pages"] = tuple(values["pages"])
    values["named_shooter_ids"] = tuple(values["named_shooter_ids"])
    return InsightRow(**values)


def load_rows(session: Session, *where: ColumnElement[bool]) -> list[InsightRow]:
    """Rows matching every `where` clause, best first."""
    insights, _ = _tables()
    query = (
        select(*(insights.c[c] for c in COLUMNS))
        .where(*where)
        .order_by(insights.c.rank_score.desc(), insights.c.key)
    )
    return [_row(dict(r)) for r in session.execute(query).mappings()]


def insights_table() -> Table:
    return _tables()[0]


def existing_keys(session: Session, keys: Collection[str]) -> set[str]:
    """The asked keys that are stored insights now, in one query (Plan 15 bumps)."""
    wanted = sorted(set(keys))
    if not wanted:
        return set()
    insights = insights_table()
    found: list[str] = list(
        session.scalars(select(insights.c.key).where(insights.c.key.in_(wanted)))
    )
    return set(found)


def load_picks(session: Session, sunday: date | None = None) -> list[Pick]:
    """The stored picks, optionally only those of one Sunday."""
    _, picks_table = _tables()
    query = select(picks_table.c.sunday, picks_table.c.slot, picks_table.c.insight_key)
    if sunday is not None:
        query = query.where(picks_table.c.sunday == sunday)
    result = session.execute(query)
    return [Pick(day, str(slot), str(k)) for day, slot, k in result]


_STATION_SUNDAYS_SQL = text(
    "SELECT count(DISTINCT h.event_date) FROM station_hits h "
    "JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label "
    "JOIN events e ON e.event_date = h.event_date WHERE e.kind = 'regular'"
)


def readiness_from_db(session: Session) -> Readiness:
    """The same inputs as engine.readiness_of, counted in SQL (the admin kinds page).

    Station Sundays use the joins of `frames.load_station_hits` (layout and event), so a hit row
    without a layout counts on neither side.
    """
    awards = Base.metadata.tables["achievements_awarded"]
    return Readiness(
        station_sundays=int(session.scalar(_STATION_SUNDAYS_SQL) or 0),
        trophy_awards=int(session.scalar(select(func.count()).select_from(awards)) or 0),
    )
