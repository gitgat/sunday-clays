"""Synthetic scores workbooks (test utility for Plan 02 Task 3 onward)."""

import io
import re
import zipfile
from collections.abc import Iterable
from datetime import date

from sunday_clays.ingest.workbook import LoadedWorkbook, load_workbook_bytes

from .builders import SheetRows, loaded_workbook, workbook_bytes

SCORE_HEADER: list[object] = ["Name", "Score Shot", "Event", "Status", "Class"]
ATTENDANCE_HEADER: list[object] = ["Date", "Count", "Median"]
SUNDAY = date(2026, 9, 13)
NEXT_SUNDAY = date(2026, 9, 20)


def scores_sheets(
    score_rows: SheetRows = (), attendance_rows: SheetRows = ()
) -> dict[str, list[list[object]]]:
    """Both scores-workbook sheets with their header on row 1 (data from row 2)."""
    return {
        "ALL SCORE DETAIL": [SCORE_HEADER, *(list(row) for row in score_rows)],
        "Attendance History": [
            ATTENDANCE_HEADER,
            *(list(row) for row in attendance_rows),
        ],
    }


def scores_workbook(score_rows: SheetRows = (), attendance_rows: SheetRows = ()) -> LoadedWorkbook:
    return loaded_workbook(scores_sheets(score_rows, attendance_rows))


def with_empty_text_results(data: bytes, sheet_number: int, refs: Iterable[str]) -> bytes:
    """Mark formula cells as returning "" the way Excel and LibreOffice save them.

    openpyxl writes a formula as ``<c r="B3"><f>…</f><v /></c>`` with no cached
    value. Excel saves a formula whose result is "" as ``t="str"`` with an empty
    ``<v></v>``, which openpyxl also reads back as the value None.
    """
    path = f"xl/worksheets/sheet{sheet_number}.xml"
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        members = {info.filename: source.read(info) for info in source.infolist()}
    xml = members[path].decode()
    for ref in refs:
        xml, count = re.subn(
            rf'<c r="{ref}"><f>(.*?)</f><v />',
            rf'<c r="{ref}" t="str"><f>\1</f><v></v>',
            xml,
        )
        assert count == 1, f"{ref} is not a formula cell in {path}"
    members[path] = xml.encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for name, content in members.items():
            target.writestr(name, content)
    return buffer.getvalue()


def scores_workbook_with_empty_text_results(
    score_rows: SheetRows = (),
    attendance_rows: SheetRows = (),
    *,
    score_refs: Iterable[str] = (),
    attendance_refs: Iterable[str] = (),
) -> LoadedWorkbook:
    """``scores_workbook`` whose listed formula cells hold a cached "" result."""
    data = workbook_bytes(scores_sheets(score_rows, attendance_rows))
    data = with_empty_text_results(data, 1, score_refs)
    data = with_empty_text_results(data, 2, attendance_refs)
    return load_workbook_bytes(data)
