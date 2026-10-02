"""Fist bumps on insights and their rate-limit log (Plan 15); durable, never rebuilt."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class FistBump(Base):
    """One anonymous bump: an insight key and the random id of the device that bumped it."""

    __tablename__ = "fist_bumps"

    insight_key: Mapped[str] = mapped_column(Text, primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BumpAttempt(Base):
    """One bump action (add or take back) per row, for the per-IP rate limit."""

    __tablename__ = "bump_attempts"
    __table_args__ = (Index(conv("ix_bump_attempts_ip_at"), "ip", "at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
