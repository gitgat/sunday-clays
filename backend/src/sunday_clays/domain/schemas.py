"""Pydantic models shared by the domain layer and the admin API (C5)."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from sunday_clays.ingest.types import FileKind, Finding, Severity


class ImportStatus(StrEnum):
    PENDING = "pending"
    COMMITTED = "committed"
    DISCARDED = "discarded"
    ROLLED_BACK = "rolled_back"


class FindingOut(BaseModel):
    code: str
    severity: Severity
    message: str
    sheet: str | None = None
    row: int | None = None
    event_date: date | None = None
    name: str | None = None


def finding_out(finding: Finding) -> FindingOut:
    return FindingOut(
        code=finding.code,
        severity=finding.severity,
        message=finding.message,
        sheet=finding.sheet,
        row=finding.row,
        event_date=finding.event_date,
        name=finding.name,
    )


class ScoresDiff(BaseModel):
    events_added: list[date]
    events_removed: list[date]
    rows_added: int
    rows_removed: int
    rows_changed: int
    new_names: list[str]
    possible_duplicates: list[tuple[str, str]]
    attendance_changed: int


class StationsDiff(BaseModel):
    events_added: list[date]
    events_replaced: list[date]
    events_unchanged: list[date]
    sheets_skipped: list[str]


class ImportPreview(BaseModel):
    import_id: int
    kind: FileKind
    filename: str
    duplicate_of: int | None
    findings: list[FindingOut]
    diff: ScoresDiff | StationsDiff
    requires_removal_confirmation: bool


class ImportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: FileKind
    filename: str
    status: ImportStatus
    uploaded_at: datetime
    committed_at: datetime | None
    rolled_back_at: datetime | None
    sha256: str
