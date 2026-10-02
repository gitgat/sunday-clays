"""Workbook ingest: pure parsers for the Sunday Clays workbooks (Contract C3, Plan 17).

``parse_upload`` is the only entry point the domain layer uses.
"""

from dataclasses import replace

from sunday_clays.ingest.scores import parse_scores
from sunday_clays.ingest.special import parse_special
from sunday_clays.ingest.stations import parse_stations
from sunday_clays.ingest.types import FileKind, ParsedUpload, ParseError
from sunday_clays.ingest.validate import validate_scores, validate_special, validate_stations
from sunday_clays.ingest.workbook import detect_kind, load_workbook_bytes

__all__ = ["parse_upload"]

PROCESSING_FAILED_MESSAGE = "This workbook could not be processed"


def parse_upload(data: bytes) -> ParsedUpload:
    """load -> detect kind -> parse -> append the validate_* findings.

    Raises ParseError (user-facing message only) for any unusable upload,
    including unexpected failures inside the parsers.
    """
    try:
        return _parse(data)
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(PROCESSING_FAILED_MESSAGE) from exc


def _parse(data: bytes) -> ParsedUpload:
    lw = load_workbook_bytes(data)
    kind = detect_kind(lw)
    if kind is FileKind.SCORES:
        scores = parse_scores(lw)
        return replace(scores, findings=scores.findings + validate_scores(scores))
    if kind is FileKind.SPECIAL:
        special = parse_special(lw)
        return replace(special, findings=special.findings + validate_special(special))
    stations = parse_stations(lw)
    return replace(stations, findings=stations.findings + validate_stations(stations))
