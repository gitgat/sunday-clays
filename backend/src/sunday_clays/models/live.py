"""Live tables: cleared (DELETE) and rebuilt in one transaction by ``rebuild_live`` (C4).

``domain.rebuild`` holds ``rebuild_live``, the delete order and why DELETE, not TRUNCATE.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "round_type_source IN ('stations', 'override', 'none')",
            name=conv("ck_events_round_type_source"),
        ),
    )

    event_date: Mapped[date] = mapped_column(Date, primary_key=True)
    round_type: Mapped[str] = mapped_column(Text, nullable=False)
    round_type_source: Mapped[str] = mapped_column(Text, nullable=False)
    head_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    n_shooters: Mapped[int] = mapped_column(Integer, nullable=False)
    has_scores: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_stations: Mapped[bool] = mapped_column(Boolean, nullable=False)
    results_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Round(Base):
    __tablename__ = "rounds"
    __table_args__ = (
        UniqueConstraint(
            "event_date", "name_key", "ordinal", name=conv("uq_rounds_event_date_name_key_ordinal")
        ),
        Index(conv("ix_rounds_shooter_id"), "shooter_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_date: Mapped[date] = mapped_column(
        ForeignKey("events.event_date", name=conv("fk_rounds_event_date_events")), nullable=False
    )
    shooter_id: Mapped[int] = mapped_column(
        ForeignKey("shooters.id", name=conv("fk_rounds_shooter_id_shooters")), nullable=False
    )
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    gauge_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)


class ShooterProfile(Base):
    __tablename__ = "shooter_profiles"

    shooter_id: Mapped[int] = mapped_column(
        ForeignKey("shooters.id", name=conv("fk_shooter_profiles_shooter_id_shooters")),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    first_event: Mapped[date] = mapped_column(Date, nullable=False)
    last_event: Mapped[date] = mapped_column(Date, nullable=False)
    n_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    n_events: Mapped[int] = mapped_column(Integer, nullable=False)
    left_censored: Mapped[bool] = mapped_column(Boolean, nullable=False)


class StationLayout(Base):
    __tablename__ = "station_layouts"

    event_date: Mapped[date] = mapped_column(Date, primary_key=True)
    station_label: Mapped[str] = mapped_column(Text, primary_key=True)
    # the sort integer of the label (7 for "7A"); migration 0005 keeps it for the previous release
    station_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    target_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source_import_id: Mapped[int] = mapped_column(Integer, nullable=False)


class StationHit(Base):
    __tablename__ = "station_hits"
    __table_args__ = (
        UniqueConstraint(
            "event_date",
            "entry_row",
            "station_label",
            name=conv("uq_station_hits_event_date_entry_row_station_label"),
        ),
        # migration 0002: keeps the per-round FK check of rebuild's DELETE FROM rounds indexed
        Index(conv("ix_station_hits_round_id"), "round_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    station_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    station_label: Mapped[str] = mapped_column(Text, nullable=False)
    sheet_id: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_row: Mapped[int] = mapped_column(Integer, nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    shooter_id: Mapped[int | None] = mapped_column(
        ForeignKey("shooters.id", name=conv("fk_station_hits_shooter_id_shooters")), nullable=True
    )
    round_id: Mapped[int | None] = mapped_column(
        ForeignKey("rounds.id", name=conv("fk_station_hits_round_id_rounds")), nullable=True
    )
    hits: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class DataIssue(Base):
    __tablename__ = "data_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    shooter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
