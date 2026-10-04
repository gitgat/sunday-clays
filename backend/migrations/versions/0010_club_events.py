"""club events: one-off club gatherings, their sign-ups, shooters' emails and a rate-limit log

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-02

Expand-only (Plan 20 D19): four new durable tables that the previous release never reads, so it
runs unchanged on this schema. None of them is in domain/rebuild.py LIVE_TABLES, so a rebuild
keeps them. club_event_attempts stores ip_fingerprint(request), never an address, and its rows are
pruned after a day. No index includes registrant_email, so a unique-violation DETAIL never quotes
one (D22 covers CHECK violations).

Rollback limit: rolling the app back is safe at any time, because the previous release never reads
these tables. `alembic downgrade 0009` deletes every club event, every sign-up and every stored
email.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_SHOOTER = "status IN ('going', 'waitlist') AND shooter_id IS NOT NULL"
ACTIVE_TYPED_NAME = "status IN ('going', 'waitlist') AND shooter_id IS NULL"


def upgrade() -> None:
    op.create_table(
        "club_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signup_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("capacity", sa.SmallInteger(), nullable=True),
        sa.Column("allow_guests", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("max_guests", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("roster_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_signups", sa.SmallInteger(), nullable=True),
        sa.Column("final_spots", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 80", name=op.f("ck_club_events_title_length")
        ),
        sa.CheckConstraint(
            "signup_deadline <= starts_at", name=op.f("ck_club_events_deadline_before_start")
        ),
        sa.CheckConstraint("char_length(notes) <= 2000", name=op.f("ck_club_events_notes_length")),
        sa.CheckConstraint(
            "capacity IS NULL OR capacity BETWEEN 1 AND 500",
            name=op.f("ck_club_events_capacity_range"),
        ),
        sa.CheckConstraint(
            "max_guests BETWEEN 0 AND 10", name=op.f("ck_club_events_max_guests_range")
        ),
        sa.CheckConstraint(
            "(allow_guests AND max_guests >= 1) OR (NOT allow_guests AND max_guests = 0)",
            name=op.f("ck_club_events_guest_rule"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_events")),
    )
    op.create_index(op.f("ix_club_events_starts_at"), "club_events", ["starts_at"])
    op.create_table(
        "club_event_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("shooter_id", sa.Integer(), nullable=True),
        sa.Column("registrant_name", sa.Text(), nullable=True),
        sa.Column("name_key", sa.Text(), nullable=True),
        sa.Column("registrant_email", sa.Text(), nullable=True),
        sa.Column("guests", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "queue_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_via", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "char_length(registrant_name) <= 60",
            name=op.f("ck_club_event_registrations_name_length"),
        ),
        sa.CheckConstraint(
            "char_length(registrant_email) <= 254",
            name=op.f("ck_club_event_registrations_email_length"),
        ),
        sa.CheckConstraint(
            "guests BETWEEN 0 AND 10", name=op.f("ck_club_event_registrations_guests_range")
        ),
        sa.CheckConstraint(
            "status IN ('going', 'waitlist', 'cancelled', 'removed')",
            name=op.f("ck_club_event_registrations_status"),
        ),
        sa.CheckConstraint(
            "cancelled_via IN ('device', 'email', 'organizer')",
            name=op.f("ck_club_event_registrations_cancelled_via"),
        ),
        sa.CheckConstraint(
            "shooter_id IS NOT NULL OR (registrant_name IS NOT NULL AND name_key IS NOT NULL)",
            name=op.f("ck_club_event_registrations_who"),
        ),
        sa.CheckConstraint(
            "registrant_email IS NULL OR shooter_id IS NULL",
            name=op.f("ck_club_event_registrations_email_owner"),
        ),
        sa.CheckConstraint(
            "status IN ('going', 'waitlist') OR (registrant_email IS NULL AND token_hash IS NULL)",
            name=op.f("ck_club_event_registrations_inactive_scrubbed"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["club_events.id"],
            name=op.f("fk_club_event_registrations_event_id_club_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shooter_id"],
            ["shooters.id"],
            name=op.f("fk_club_event_registrations_shooter_id_shooters"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_event_registrations")),
    )
    op.create_index(
        op.f("ix_club_event_registrations_queue"),
        "club_event_registrations",
        ["event_id", "status", "id"],
    )
    op.create_index(
        op.f("uq_club_event_registrations_shooter"),
        "club_event_registrations",
        ["event_id", "shooter_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_SHOOTER),
    )
    op.create_index(
        op.f("uq_club_event_registrations_name"),
        "club_event_registrations",
        ["event_id", "name_key"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_TYPED_NAME),
    )
    op.create_table(
        "shooter_contacts",
        sa.Column("shooter_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254", name=op.f("ck_shooter_contacts_email_length")
        ),
        sa.CheckConstraint(
            "source IN ('signup', 'organizer', 'link')", name=op.f("ck_shooter_contacts_source")
        ),
        sa.ForeignKeyConstraint(
            ["shooter_id"], ["shooters.id"], name=op.f("fk_shooter_contacts_shooter_id_shooters")
        ),
        sa.PrimaryKeyConstraint("shooter_id", name=op.f("pk_shooter_contacts")),
    )
    op.create_table(
        "club_event_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("registration_id", sa.Integer(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('signup', 'check', 'cancel_fail')",
            name=op.f("ck_club_event_attempts_action"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_event_attempts")),
    )
    op.create_index(
        op.f("ix_club_event_attempts_ip_action_at"), "club_event_attempts", ["ip", "action", "at"]
    )
    op.create_index(
        op.f("ix_club_event_attempts_registration_id_at"),
        "club_event_attempts",
        ["registration_id", "at"],
    )


def downgrade() -> None:
    op.drop_table("club_event_attempts")
    op.drop_table("shooter_contacts")
    op.drop_table("club_event_registrations")
    op.drop_table("club_events")
