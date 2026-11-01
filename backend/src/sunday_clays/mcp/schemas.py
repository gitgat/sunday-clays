"""Typed inputs and outputs of the MCP tools."""

import datetime as dt
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FindShootersInput(_Input):
    query: str = Field(min_length=1, max_length=60)
    limit: int = Field(default=10, ge=1, le=25)

    @field_validator("query")
    @classmethod
    def _has_a_token(cls, value: str) -> str:
        if not value.replace(",", " ").split():
            raise ValueError("query must contain at least one non-blank character")
        return value


class GetEventInput(_Input):
    date: dt.date
    include_rows: bool = False


class GetJobInput(_Input):
    id: int = Field(ge=1)


class ShooterHit(BaseModel):
    display_name: str
    rounds: int
    last_shot: dt.date | None
    usual_status: str | None


class FindShootersResult(BaseModel):
    shooters: list[ShooterHit]


class StationInfo(BaseModel):
    label: str
    targets: int
    dropped: bool


class IssueInfo(BaseModel):
    severity: str
    code: str
    message: str


class RowInfo(BaseModel):
    name: str
    score: int
    status: str | None
    gauge_class: str | None


class EventSummary(BaseModel):
    date: dt.date
    head_count: int | None
    round_type: str
    stats_excluded: bool
    target_total: int
    n_rounds: int
    score_sum: int
    average: float | None
    stations: list[StationInfo]
    data_issues: list[IssueInfo]
    rows: list[RowInfo] | None = None


class NoEvent(BaseModel):
    date: dt.date
    found: Literal[False] = False
    last_event_date: dt.date | None


class JobStatus(BaseModel):
    id: int
    kind: str
    status: str
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None


class NotFound(BaseModel):
    id: int
    found: Literal[False] = False
