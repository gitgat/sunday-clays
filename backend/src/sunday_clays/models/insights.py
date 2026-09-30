"""Insight tables written by recompute step 60 (Plan 12, spec §3.1)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        CheckConstraint(
            "polarity IN ('positive', 'neutral', 'field_negative', 'mixed')",
            name=conv("ck_insights_polarity"),
        ),
        CheckConstraint(
            "polarity <> 'field_negative' OR cardinality(named_shooter_ids) = 0",
            name=conv("ck_insights_field_negative_unnamed"),
        ),
        UniqueConstraint("key", name=conv("uq_insights_key")),
        Index(conv("ix_insights_subject_type_subject_id"), "subject_type", "subject_id"),
        Index(conv("ix_insights_pages"), "pages", postgresql_using="gin"),
        Index(conv("ix_insights_anchor_date"), "anchor_date"),
        Index(conv("ix_insights_named_shooter_ids"), "named_shooter_ids", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value_hash: Mapped[str] = mapped_column(Text, nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    first_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[str] = mapped_column(Text, nullable=False)
    home_slot: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    variant: Mapped[str] = mapped_column(Text, nullable=False)
    pages: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    expires: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    named_shooter_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, server_default=text("'{}'::integer[]")
    )
    polarity: Mapped[str] = mapped_column(Text, nullable=False)
    kudos: Mapped[bool] = mapped_column(Boolean, nullable=False)
    template_id: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    strength: Mapped[float] = mapped_column(REAL, nullable=False)
    base_score: Mapped[float] = mapped_column(REAL, nullable=False)
    rank_score: Mapped[float] = mapped_column(REAL, nullable=False)
    headline: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    headline_you: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    how: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    how_you: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    chart: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class InsightPick(Base):
    __tablename__ = "insight_picks"

    sunday: Mapped[date] = mapped_column(Date, primary_key=True)
    slot: Mapped[str] = mapped_column(Text, primary_key=True)
    insight_key: Mapped[str] = mapped_column(Text, nullable=False)
