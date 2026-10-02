"""Anonymous page views (Plan 16): raw visits, their rate-limit log, and the day/week rollups
kept after the raw rows go. Durable: never rebuilt."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, Index, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class PageView(Base):
    """One counted visit: a random device id, a coarse page kind and the "Which one are you?"
    state. Never a name, a URL or an IP."""

    __tablename__ = "page_views"
    __table_args__ = (
        CheckConstraint(
            "me_state IN ('picked', 'skipped', 'none')", name=conv("ck_page_views_me_state")
        ),
        Index(conv("ix_page_views_device_id_page_kind_at"), "device_id", "page_kind", "at"),
        Index(conv("ix_page_views_at"), "at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    page_kind: Mapped[str] = mapped_column(Text, nullable=False)
    me_state: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PageViewAttempt(Base):
    """One beacon per row, for the per-IP rate limit. Rows older than the window are pruned on
    the next beacon and by the daily page_view_rollup job."""

    __tablename__ = "page_view_attempts"
    __table_args__ = (Index(conv("ix_page_view_attempts_ip_at"), "ip", "at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PageViewRollup(Base):
    """Unique devices in one local day or ISO week, split by each device's last answer there."""

    __tablename__ = "page_view_rollups"
    __table_args__ = (
        CheckConstraint("period IN ('day', 'week')", name=conv("ck_page_view_rollups_period")),
    )

    period: Mapped[str] = mapped_column(Text, primary_key=True)
    start_day: Mapped[date] = mapped_column(Date, primary_key=True)
    devices: Mapped[int] = mapped_column(Integer, nullable=False)
    me_picked: Mapped[int] = mapped_column(Integer, nullable=False)
    me_skipped: Mapped[int] = mapped_column(Integer, nullable=False)
    me_none: Mapped[int] = mapped_column(Integer, nullable=False)


class PageKindRollup(Base):
    """Counted views of one page kind on one local day."""

    __tablename__ = "page_kind_rollups"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    page_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False)
