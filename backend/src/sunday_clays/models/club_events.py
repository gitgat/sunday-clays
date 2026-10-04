"""Club events (Plan 20): one-off club gatherings, their sign-ups, shooters' emails and the
sign-up rate-limit log. Durable: never in domain/rebuild.py LIVE_TABLES."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base

ACTIVE_SHOOTER = "status IN ('going', 'waitlist') AND shooter_id IS NOT NULL"
ACTIVE_TYPED_NAME = "status IN ('going', 'waitlist') AND shooter_id IS NULL"


class ClubEvent(Base):
    """One club event: times are instants (`timestamptz`), entered and shown in club time."""

    __tablename__ = "club_events"
    __table_args__ = (
        CheckConstraint(
            "char_length(title) BETWEEN 1 AND 80", name=conv("ck_club_events_title_length")
        ),
        CheckConstraint(
            "signup_deadline <= starts_at", name=conv("ck_club_events_deadline_before_start")
        ),
        CheckConstraint("char_length(notes) <= 2000", name=conv("ck_club_events_notes_length")),
        CheckConstraint(
            "capacity IS NULL OR capacity BETWEEN 1 AND 500",
            name=conv("ck_club_events_capacity_range"),
        ),
        CheckConstraint(
            "max_guests BETWEEN 0 AND 10", name=conv("ck_club_events_max_guests_range")
        ),
        CheckConstraint(
            "(allow_guests AND max_guests >= 1) OR (NOT allow_guests AND max_guests = 0)",
            name=conv("ck_club_events_guest_rule"),
        ),
        Index(conv("ix_club_events_starts_at"), "starts_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signup_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    capacity: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    allow_guests: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    max_guests: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    roster_purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    final_signups: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    final_spots: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ClubEventRegistration(Base):
    """One sign-up: a picked shooter or a typed name, plus `guests` unnamed guests. Queue order is
    `id` (assigned under the event lock, D9); `queue_at` is for display only."""

    __tablename__ = "club_event_registrations"
    __table_args__ = (
        CheckConstraint(
            "char_length(registrant_name) <= 60",
            name=conv("ck_club_event_registrations_name_length"),
        ),
        CheckConstraint(
            "char_length(registrant_email) <= 254",
            name=conv("ck_club_event_registrations_email_length"),
        ),
        CheckConstraint(
            "guests BETWEEN 0 AND 10", name=conv("ck_club_event_registrations_guests_range")
        ),
        CheckConstraint(
            "status IN ('going', 'waitlist', 'cancelled', 'removed')",
            name=conv("ck_club_event_registrations_status"),
        ),
        CheckConstraint(
            "cancelled_via IN ('device', 'email', 'organizer')",
            name=conv("ck_club_event_registrations_cancelled_via"),
        ),
        CheckConstraint(
            "shooter_id IS NOT NULL OR (registrant_name IS NOT NULL AND name_key IS NOT NULL)",
            name=conv("ck_club_event_registrations_who"),
        ),
        CheckConstraint(
            "registrant_email IS NULL OR shooter_id IS NULL",
            name=conv("ck_club_event_registrations_email_owner"),
        ),
        CheckConstraint(
            "status IN ('going', 'waitlist') OR (registrant_email IS NULL AND token_hash IS NULL)",
            name=conv("ck_club_event_registrations_inactive_scrubbed"),
        ),
        Index(conv("ix_club_event_registrations_queue"), "event_id", "status", "id"),
        Index(
            conv("uq_club_event_registrations_shooter"),
            "event_id",
            "shooter_id",
            unique=True,
            postgresql_where=text(ACTIVE_SHOOTER),
        ),
        Index(
            conv("uq_club_event_registrations_name"),
            "event_id",
            "name_key",
            unique=True,
            postgresql_where=text(ACTIVE_TYPED_NAME),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey(
            "club_events.id",
            name=conv("fk_club_event_registrations_event_id_club_events"),
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    shooter_id: Mapped[int | None] = mapped_column(
        ForeignKey("shooters.id", name=conv("fk_club_event_registrations_shooter_id_shooters")),
        nullable=True,
    )
    registrant_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    registrant_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    guests: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    queue_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_via: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ShooterContact(Base):
    """One email per shooter, used for quicker sign-ups; only organizers ever see it."""

    __tablename__ = "shooter_contacts"
    __table_args__ = (
        CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254", name=conv("ck_shooter_contacts_email_length")
        ),
        CheckConstraint(
            "source IN ('signup', 'organizer', 'link')", name=conv("ck_shooter_contacts_source")
        ),
    )

    shooter_id: Mapped[int] = mapped_column(
        ForeignKey("shooters.id", name=conv("fk_shooter_contacts_shooter_id_shooters")),
        primary_key=True,
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClubEventAttempt(Base):
    """One sign-up, check or failed cancel per row, keyed by the client fingerprint (never an
    address). `registration_id` has no FK, so a purge never cascades into the limiter."""

    __tablename__ = "club_event_attempts"
    __table_args__ = (
        CheckConstraint(
            "action IN ('signup', 'check', 'cancel_fail')",
            name=conv("ck_club_event_attempts_action"),
        ),
        Index(conv("ix_club_event_attempts_ip_action_at"), "ip", "action", "at"),
        Index(conv("ix_club_event_attempts_registration_id_at"), "registration_id", "at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    registration_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
