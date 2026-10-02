"""Synthetic special-event sheets (test utility for Plan 17 Task 1)."""

from collections.abc import Sequence
from datetime import date

from .builders import SheetRows

SPECIAL_SUNDAY = date(2026, 9, 20)
LABEL = "Three Clay Shoot"
STATIONS = tuple(range(1, 11))
TARGETS = (6,) * 10
HADLEY = ["Hadley, Ike", 6, 5, 6, 4, 6, 5, 6, 6, 5, 6]  # 55
DEVLIN = ["Devlin, Sid", 5, 5, 4, 5, 5, 4, 5, 5, 5, 5]  # 48


def special_sheet(
    entries: SheetRows = (HADLEY, DEVLIN),
    *,
    label: object = LABEL,
    event_date: object = SPECIAL_SUNDAY,
    stations: Sequence[object] = STATIONS,
    targets: Sequence[object] = TARGETS,
    total: bool = True,
) -> list[list[object]]:
    """Rows of a "Special Event" sheet. With `total`, a row of exactly name + one int per station
    gets its correct total appended; a longer row keeps the total it was given."""
    rows: list[list[object]] = [
        ["Special event", label],
        ["Event date", event_date],
        ["Station", *stations, *(["Total"] if total else [])],
        ["Targets", *targets],
    ]
    for entry in entries:
        cells = list(entry)
        hits = cells[1:]
        if total and len(hits) == len(stations) and all(type(v) is int for v in hits):
            cells.append(sum(hits))  # type: ignore[arg-type]
        rows.append(cells)
    return rows
