"""Audit trail of the scores MCP's write tools: one row per preview, commit, refusal."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class McpOperation(Base):
    __tablename__ = "mcp_operations"
    __table_args__ = (
        CheckConstraint("kind IN ('week', 'correction')", name=conv("ck_mcp_operations_kind")),
        CheckConstraint(
            "status IN ('previewed', 'committed', 'rolled_back', 'expired', 'refused')",
            name=conv("ck_mcp_operations_status"),
        ),
        CheckConstraint(
            "commit_path IN ('mcp-auto', 'cli-approve', 'web-ui-approve')",
            name=conv("ck_mcp_operations_commit_path"),
        ),
        Index(conv("ix_mcp_operations_status_created_at"), "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    caller: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    scores_import_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("imports.id", name=conv("fk_mcp_operations_scores_import_id")),
        nullable=True,
    )
    stations_import_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("imports.id", name=conv("fk_mcp_operations_stations_import_id")),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    commit_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    backup_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
