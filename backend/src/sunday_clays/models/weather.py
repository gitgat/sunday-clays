"""Weather cache tables (C4); durable, never truncated by rebuild."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import DOUBLE_PRECISION, REAL, CheckConstraint, Date, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class WeatherHourly(Base):
    __tablename__ = "weather_hourly"
    __table_args__ = (
        CheckConstraint("source IN ('archive', 'forecast')", name=conv("ck_weather_hourly_source")),
    )

    ts_local: Mapped[datetime] = mapped_column(DateTime(timezone=False), primary_key=True)
    temp_f: Mapped[float | None] = mapped_column(REAL, nullable=True)
    apparent_f: Mapped[float | None] = mapped_column(REAL, nullable=True)
    precip_in: Mapped[float | None] = mapped_column(REAL, nullable=True)
    rain_in: Mapped[float | None] = mapped_column(REAL, nullable=True)
    wind_mph: Mapped[float | None] = mapped_column(REAL, nullable=True)
    gust_mph: Mapped[float | None] = mapped_column(REAL, nullable=True)
    wind_dir_deg: Mapped[float | None] = mapped_column(REAL, nullable=True)
    cloud_pct: Mapped[float | None] = mapped_column(REAL, nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(REAL, nullable=True)
    pressure_hpa: Mapped[float | None] = mapped_column(REAL, nullable=True)
    weather_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EventWeather(Base):
    __tablename__ = "event_weather"

    event_date: Mapped[date] = mapped_column(Date, primary_key=True)
    temp_f: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    apparent_f: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    precip_in: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    wind_mph: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    gust_mph: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    wind_dir_deg: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    cloud_pct: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    pressure_hpa: Mapped[float | None] = mapped_column(DOUBLE_PRECISION, nullable=True)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)


class ForecastCache(Base):
    __tablename__ = "forecast_cache"

    target_date: Mapped[date] = mapped_column(Date, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
