"""Analytics tables written by recompute steps (C4, C6)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import REAL, Boolean, Date, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class RoundMetric(Base):
    __tablename__ = "round_metrics"

    round_id: Mapped[int] = mapped_column(
        ForeignKey("rounds.id", name=conv("fk_round_metrics_round_id_rounds")), primary_key=True
    )
    field_median: Mapped[float | None] = mapped_column(REAL, nullable=True)
    adjusted: Mapped[float | None] = mapped_column(REAL, nullable=True)
    event_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_best_round: Mapped[bool] = mapped_column(Boolean, nullable=False)
    percentile: Mapped[float | None] = mapped_column(REAL, nullable=True)
    expected: Mapped[float | None] = mapped_column(REAL, nullable=True)
    residual: Mapped[float | None] = mapped_column(REAL, nullable=True)
    mu_before: Mapped[float | None] = mapped_column(REAL, nullable=True)
    var_before: Mapped[float | None] = mapped_column(REAL, nullable=True)
    mu_after: Mapped[float | None] = mapped_column(REAL, nullable=True)
    var_after: Mapped[float | None] = mapped_column(REAL, nullable=True)


class EventMetric(Base):
    __tablename__ = "event_metrics"

    event_date: Mapped[date] = mapped_column(Date, primary_key=True)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    median: Mapped[float] = mapped_column(REAL, nullable=False)
    mean: Mapped[float] = mapped_column(REAL, nullable=False)
    stdev: Mapped[float | None] = mapped_column(REAL, nullable=True)
    top_score: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty: Mapped[float | None] = mapped_column(REAL, nullable=True)


class RatingHistory(Base):
    __tablename__ = "rating_history"

    shooter_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_date: Mapped[date] = mapped_column(Date, primary_key=True)
    mu: Mapped[float] = mapped_column(REAL, nullable=False)
    var: Mapped[float] = mapped_column(REAL, nullable=False)


class AchievementAwarded(Base):
    __tablename__ = "achievements_awarded"
    __table_args__ = (
        UniqueConstraint(
            "shooter_id",
            "code",
            "event_date",
            name=conv("uq_achievements_awarded_shooter_id_code_event_date"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shooter_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    round_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
