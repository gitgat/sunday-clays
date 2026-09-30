"""Staging tables: immutable copies of every uploaded workbook and its parsed rows (C4)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class Import(Base):
    __tablename__ = "imports"
    __table_args__ = (
        CheckConstraint("kind IN ('scores', 'stations')", name=conv("ck_imports_kind")),
        CheckConstraint(
            "status IN ('pending', 'committed', 'discarded', 'rolled_back')",
            name=conv("ck_imports_status"),
        ),
        Index(conv("ix_imports_kind_status"), "kind", "status"),
        Index(conv("ix_imports_sha256"), "sha256"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    file_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    findings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )


class ImportScoreRow(Base):
    __tablename__ = "import_score_rows"
    __table_args__ = (Index(conv("ix_import_score_rows_import_id"), "import_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey(
            "imports.id", ondelete="CASCADE", name=conv("fk_import_score_rows_import_id_imports")
        ),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    gauge_class: Mapped[str | None] = mapped_column(Text, nullable=True)


class ImportAttendanceRow(Base):
    __tablename__ = "import_attendance_rows"
    __table_args__ = (Index(conv("ix_import_attendance_rows_import_id"), "import_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey(
            "imports.id",
            ondelete="CASCADE",
            name=conv("fk_import_attendance_rows_import_id_imports"),
        ),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    head_count: Mapped[int] = mapped_column(Integer, nullable=False)


class ImportStationSheet(Base):
    __tablename__ = "import_station_sheets"
    __table_args__ = (Index(conv("ix_import_station_sheets_import_id"), "import_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey(
            "imports.id",
            ondelete="CASCADE",
            name=conv("fk_import_station_sheets_import_id_imports"),
        ),
        nullable=False,
    )
    sheet_name: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)


class ImportStationLayout(Base):
    __tablename__ = "import_station_layout"
    __table_args__ = (Index(conv("ix_import_station_layout_sheet_id"), "sheet_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sheet_id: Mapped[int] = mapped_column(
        ForeignKey(
            "import_station_sheets.id",
            ondelete="CASCADE",
            name=conv("fk_import_station_layout_sheet_id_import_station_sheets"),
        ),
        nullable=False,
    )
    station_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    station_label: Mapped[str] = mapped_column(Text, nullable=False)
    target_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class ImportStationHit(Base):
    __tablename__ = "import_station_hits"
    __table_args__ = (Index(conv("ix_import_station_hits_sheet_id"), "sheet_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sheet_id: Mapped[int] = mapped_column(
        ForeignKey(
            "import_station_sheets.id",
            ondelete="CASCADE",
            name=conv("fk_import_station_hits_sheet_id_import_station_sheets"),
        ),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    station_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    station_label: Mapped[str] = mapped_column(Text, nullable=False)
    hits: Mapped[int] = mapped_column(SmallInteger, nullable=False)
