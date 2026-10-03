"""The page cache (Plan 19 D28): one row per stored response body. Disposable and UNLOGGED."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, LargeBinary, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class ResponseCache(Base):
    __tablename__ = "response_cache"
    __table_args__ = (
        CheckConstraint("role IN ('viewer', 'admin')", name=conv("ck_response_cache_role")),
        CheckConstraint("octet_length(body) <= 2097152", name=conv("ck_response_cache_body_size")),
        {"prefixes": ["UNLOGGED"]},
    )

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    data_version: Mapped[int] = mapped_column(Integer, nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    app_version: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
