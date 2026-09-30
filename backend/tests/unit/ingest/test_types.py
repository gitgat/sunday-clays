from dataclasses import FrozenInstanceError, fields
from datetime import date

import pytest

from sunday_clays.ingest.types import (
    FileKind,
    Finding,
    ScoresParse,
    Severity,
    StationsParse,
)


def test_parse_results_carry_their_file_kind_without_a_constructor_field() -> None:
    scores = ScoresParse(score_rows=(), attendance_rows=(), findings=())
    stations = StationsParse(sheets=(), findings=())

    assert scores.kind is FileKind.SCORES
    assert stations.kind is FileKind.STATIONS
    assert "kind" not in {field.name for field in fields(ScoresParse)}
    assert "kind" not in {field.name for field in fields(StationsParse)}


def test_finding_location_fields_default_to_none() -> None:
    finding = Finding("score_missing", Severity.ERROR, "Score Shot is blank")

    assert (finding.sheet, finding.row, finding.event_date, finding.name) == (
        None,
        None,
        None,
        None,
    )


def test_findings_are_immutable_values() -> None:
    first = Finding("x", Severity.INFO, "m", sheet="S", row=3, event_date=date(2026, 9, 13))
    same = Finding("x", Severity.INFO, "m", sheet="S", row=3, event_date=date(2026, 9, 13))

    assert first == same
    assert len({first, same}) == 1
    with pytest.raises(FrozenInstanceError):
        first.row = 4  # type: ignore[misc]
