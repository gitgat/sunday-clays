"""ClaySmasher export (spec 2026-10-01 §4.1): one shooter's whole history in one viewer call.

`round_key` ("{event_date}:{name_key}:{ordinal}") stands in for the spec's `round_id`: rebuild_live
renumbers every live id on each import commit, rollback and rule change, while the natural key is
DB-unique (uq_rounds_event_date_name_key_ordinal) and is what overlay rules already target.
"""

from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.errors import error_body
from sunday_clays.api.routes._claysmasher import (
    TARGETS_PER_ROUND,
    day_ordinals,
    latest,
    round_key,
    rule_stamps,
    station_orders,
)
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.identity import merge_map
from sunday_clays.domain.round_type import RoundType

router = APIRouter()

# C8 path template `{id}`, bound to a descriptive argument (as shooters.py does).
ShooterId = Annotated[int, Path(alias="id")]


class ClubOut(BaseModel):
    name: str
    event_name: str
    city: str
    region: str


CLUB = ClubOut(name="Tri-County Gun Club", event_name="Sunday Clays", city="Sherwood", region="OR")


class ExportShooterOut(BaseModel):
    id: int
    display_name: str


class ExportStationOut(BaseModel):
    order: int
    station_label: str
    target_count: int
    hits: int


class ExportRoundOut(BaseModel):
    round_key: str
    event_date: date
    ordinal: int
    round_type: RoundType
    score: int
    target_count: int
    gauge_class: str | None
    status: str | None
    updated_at: datetime
    stations: list[ExportStationOut]


class ShooterExportOut(BaseModel):
    schema_version: Literal[1] = 1
    club: ClubOut
    shooter: ExportShooterOut
    generated_at: datetime
    rounds: list[ExportRoundOut]


_PROFILE_SQL = text("SELECT display_name FROM shooter_profiles WHERE shooter_id = :s")
# Regular Sundays only (Plan 17): a special Sunday such as the 3-Bird Shoot counts only as an
# appearance, and its score (out of its own target total) is not a Sporting round to import.
# COLLATE "C": byte order equals Python's codepoint order, which day_ordinals ranks by. The DB's
# default collation (en_US.utf8 in postgres:17) ignores spaces, hyphens and apostrophes at the first
# level, so it could list a day's ordinal 2 before its ordinal 1 after a merge.
_ROUNDS_SQL = text(
    """
SELECT r.id, r.event_date, r.name_key, r.ordinal, r.score, r.gauge_class, r.status,
       e.round_type
FROM rounds r
JOIN events e ON e.event_date = r.event_date
WHERE r.shooter_id = :s AND e.kind = 'regular'
ORDER BY r.event_date, r.ordinal, r.name_key COLLATE "C"
"""
)
# Linked entries only: station_hits.round_id is NULL for an entry that matched no round.
_STATIONS_SQL = text(
    """
SELECT h.round_id, h.station_label, h.hits, l.target_count
FROM station_hits h
JOIN rounds r ON r.id = h.round_id
JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
JOIN events e ON e.event_date = r.event_date
WHERE r.shooter_id = :s AND e.kind = 'regular'
"""
)
_LAYOUTS_SQL = text(
    """
SELECT l.event_date, l.station_label
FROM station_layouts l
JOIN events e ON e.event_date = l.event_date
WHERE e.kind = 'regular'
  AND l.event_date IN (SELECT event_date FROM rounds WHERE shooter_id = :s)
"""
)
# Commits and rollbacks both change what is live; counting rollbacks keeps updated_at monotonic.
_SCORES_CHANGED_SQL = text(
    """
SELECT max(GREATEST(committed_at, rolled_back_at))
FROM imports
WHERE kind = 'scores' AND status IN ('committed', 'rolled_back')
"""
)
_STATIONS_CHANGED_SQL = text(
    """
SELECT s.event_date, max(GREATEST(i.committed_at, i.rolled_back_at))
FROM import_station_sheets s
JOIN imports i ON i.id = s.import_id
WHERE i.kind = 'stations' AND i.status IN ('committed', 'rolled_back')
  AND s.event_date IN (SELECT event_date FROM rounds WHERE shooter_id = :s)
GROUP BY s.event_date
"""
)
_RULES_SQL = text(
    """
SELECT rule_type, payload, GREATEST(created_at, deactivated_at)
FROM rules
WHERE rule_type IN ('score_override', 'hide_round', 'round_type_override')
"""
)


def _rounds(session: Session, shooter_id: int, generated_at: datetime) -> list[ExportRoundOut]:
    """Every live regular-Sunday round of the shooter with its linked station hits.

    A fixed number of queries. Special Sundays (Plan 17) are left out: see _ROUNDS_SQL.
    """
    params = {"s": shooter_id}
    rounds = session.execute(_ROUNDS_SQL, params).all()
    hits: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
    for round_id, label, value, targets in session.execute(_STATIONS_SQL, params):
        hits[int(round_id)].append((str(label), int(value), int(targets)))
    labels: dict[date, list[str]] = defaultdict(list)
    for event_date, label in session.execute(_LAYOUTS_SQL, params):
        labels[event_date].append(str(label))
    orders = {day: station_orders(day_labels) for day, day_labels in labels.items()}
    scores_changed: datetime | None = session.execute(_SCORES_CHANGED_SQL).scalar()
    stations_changed: dict[date, datetime] = {
        row[0]: row[1] for row in session.execute(_STATIONS_CHANGED_SQL, params)
    }
    by_round, by_day = rule_stamps((str(r[0]), r[1], r[2]) for r in session.execute(_RULES_SQL))
    numbers = day_ordinals((r.event_date, r.name_key, r.ordinal) for r in rounds)

    out: list[ExportRoundOut] = []
    for r in rounds:
        natural = (r.event_date, r.name_key, r.ordinal)
        stations = sorted(
            (
                ExportStationOut(
                    order=orders[r.event_date][label],
                    station_label=label,
                    target_count=targets,
                    hits=value,
                )
                for label, value, targets in hits[r.id]
            ),
            key=lambda station: station.order,
        )
        changed = latest(
            scores_changed,
            stations_changed.get(r.event_date),
            by_round.get(natural),
            by_day.get(r.event_date),
        )
        out.append(
            ExportRoundOut(
                round_key=round_key(*natural),
                event_date=r.event_date,
                ordinal=numbers[natural],
                round_type=RoundType(str(r.round_type)),
                score=int(r.score),
                target_count=(
                    sum(station.target_count for station in stations)
                    if stations
                    else TARGETS_PER_ROUND
                ),
                gauge_class=r.gauge_class,
                status=r.status,
                updated_at=changed or generated_at,
                stations=stations,
            )
        )
    return out


def _not_found(session: Session, shooter_id: int) -> JSONResponse:
    """404: `shooter_merged` plus `merged_into` for a merged-away shooter, else shooter_not_found.

    A merged-away shooter keeps its `shooters` row but has no profile, as no live round names it.
    The standard handler only renders {"error": ...}, so the merged case is built here.
    """
    target = merge_map(session).get(shooter_id)
    if target is None:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    content: dict[str, object] = {
        **error_body("shooter_merged", f"Shooter {shooter_id} was merged into {target}"),
        "merged_into": target,
    }
    return JSONResponse(status_code=404, content=content)


@router.get("/api/shooters/{id}/export", response_model=ShooterExportOut)
def get_shooter_export(
    shooter_id: ShooterId, session: SessionDep
) -> ShooterExportOut | JSONResponse:
    """One shooter's rounds with their per-station hits, for the ClaySmasher app."""
    name = session.execute(_PROFILE_SQL, {"s": shooter_id}).scalar_one_or_none()
    if name is None:
        return _not_found(session, shooter_id)
    generated_at = datetime.now(UTC)
    return ShooterExportOut(
        club=CLUB,
        shooter=ExportShooterOut(id=shooter_id, display_name=str(name)),
        generated_at=generated_at,
        rounds=_rounds(session, shooter_id, generated_at),
    )
