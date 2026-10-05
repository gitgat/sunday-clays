"""ClaySmasher scores export: one shooter's regular-Sunday rounds as a zip of CSV files.

The zip holds one file per discipline the shooter has rounds in (claysmasher-sporting.csv,
claysmasher-super-sporting.csv), each in ClaySmasher's Scores CSV import format (see
_claysmasher.py), ready for the app's Settings > Import & export scores > Import from CSV.
"""

from collections import defaultdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.errors import error_body
from sunday_clays.api.routes._claysmasher import (
    ExportRound,
    ExportStation,
    day_ordinals,
    export_files,
    shooter_slug,
    station_orders,
    zip_files,
)
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.identity import merge_map
from sunday_clays.domain.round_type import RoundType

router = APIRouter()

# C8 path template `{id}`, bound to a descriptive argument (as shooters.py does).
ShooterId = Annotated[int, Path(alias="id")]

_PROFILE_SQL = text("SELECT display_name FROM shooter_profiles WHERE shooter_id = :s")
# Regular Sundays only (Plan 17): a special Sunday such as the 3-Bird Shoot counts only as an
# appearance, and its score (out of its own target total) is not a Sporting round to import.
# COLLATE "C": byte order equals Python's codepoint order, which day_ordinals ranks by. The DB's
# default collation (en_US.utf8 in postgres:17) ignores spaces, hyphens and apostrophes at the first
# level, so it could list a day's ordinal 2 before its ordinal 1 after a merge.
_ROUNDS_SQL = text(
    """
SELECT r.id, r.event_date, r.name_key, r.ordinal, r.score, r.gauge_class, e.round_type
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


def _rounds(session: Session, shooter_id: int) -> list[ExportRound]:
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
    numbers = day_ordinals((r.event_date, r.name_key, r.ordinal) for r in rounds)

    out: list[ExportRound] = []
    for r in rounds:
        order = orders.get(r.event_date, {})
        stations = sorted(hits[r.id], key=lambda station: order[station[0]])
        out.append(
            ExportRound(
                event_date=r.event_date,
                number=numbers[(r.event_date, r.name_key, r.ordinal)],
                round_type=RoundType(str(r.round_type)),
                score=int(r.score),
                gauge_class=r.gauge_class,
                stations=tuple(
                    ExportStation(label, targets, value) for label, value, targets in stations
                ),
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


@router.get(
    "/api/shooters/{id}/claysmasher-export",
    response_class=Response,
    responses={
        200: {
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
            "description": "A zip of ClaySmasher Scores CSV import files, one per discipline.",
        },
        404: {
            "description": "shooter_not_found, shooter_merged (with merged_into) or"
            " no_exportable_rounds (the shooter has no regular-Sunday rounds)."
        },
    },
)
def get_claysmasher_export(shooter_id: ShooterId, session: SessionDep) -> Response:
    """One shooter's scores as ClaySmasher import CSVs (one per discipline) in a zip."""
    name = session.execute(_PROFILE_SQL, {"s": shooter_id}).scalar_one_or_none()
    if name is None:
        return _not_found(session, shooter_id)
    files = export_files(_rounds(session, shooter_id), str(name))
    if not files:
        raise NotFoundError("no_exportable_rounds", "There are no Sunday rounds to export yet.")
    filename = f"claysmasher-{shooter_slug(str(name), shooter_id)}-scores.zip"
    return Response(
        content=zip_files(files),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
