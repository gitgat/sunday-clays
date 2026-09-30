"""Synthetic station-sheet rows (test utility for Plan 02 Task 4 onward)."""

from collections.abc import Sequence
from datetime import date

from .builders import SheetRows

STATIONS = (4, 5, 6, 7, 8, 9, 10)
TARGETS = (7, 7, 7, 7, 7, 7, 8)
FIRST_ENTRY_ROW = 10
SUNDAY = date(2026, 9, 13)
NEXT_SUNDAY = date(2026, 9, 20)
HADLEY = ["Hadley, Ike", 3, 4, 6, 5, 7, 4, 7]  # total 36, as on the 9/13 fixture tab
DEVLIN = ["Devlin, Sid", 2, 4, 6, 5, 2, 0, 6]  # total 25


def station_sheet(
    event_date: object,
    entries: SheetRows = (),
    *,
    stations: Sequence[object] = STATIONS,
    targets: Sequence[object] = TARGETS,
) -> list[list[object]]:
    """Rows of one station tab laid out like the fixture.

    A1 "Event Date", A2 the date, row 4 station numbers, row 5 target counts,
    row 9 the "Name" header, entries from row 10 (FIRST_ENTRY_ROW).
    """
    return [
        ["Event Date"],
        [event_date],
        [],
        ["STATION #", *stations, "Total"],
        ["TARGET COUNT", *targets, "=SUM(B5:H5)"],
        [],
        ["Median Hits"],
        [],
        ["Name", "Station Hits"],
        *(list(entry) for entry in entries),
    ]
