"""page views: anonymous page-view counts, their rate-limit log, and day/week rollups

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01

Expand-only: four new tables that the previous release never reads, so it runs unchanged on this
schema. All are durable: rebuild_live only clears the live tables (domain/rebuild.py LIVE_TABLES).
page_kind has no CHECK on purpose (Plan 16 Decision 3): the API validates it, so a new kind needs
no migration. page_view_attempts holds an IP only for the rate limit: rows older than 10 minutes are
pruned on the next beacon (as bump_attempts is) and by the daily page_view_rollup job.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page_views",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("page_kind", sa.Text(), nullable=False),
        sa.Column("me_state", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "me_state IN ('picked', 'skipped', 'none')", name=op.f("ck_page_views_me_state")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_views")),
    )
    op.create_index(
        op.f("ix_page_views_device_id_page_kind_at"),
        "page_views",
        ["device_id", "page_kind", "at"],
    )
    op.create_index(op.f("ix_page_views_at"), "page_views", ["at"])
    op.create_table(
        "page_view_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_view_attempts")),
    )
    op.create_index(op.f("ix_page_view_attempts_ip_at"), "page_view_attempts", ["ip", "at"])
    op.create_table(
        "page_view_rollups",
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("start_day", sa.Date(), nullable=False),
        sa.Column("devices", sa.Integer(), nullable=False),
        sa.Column("me_picked", sa.Integer(), nullable=False),
        sa.Column("me_skipped", sa.Integer(), nullable=False),
        sa.Column("me_none", sa.Integer(), nullable=False),
        sa.CheckConstraint("period IN ('day', 'week')", name=op.f("ck_page_view_rollups_period")),
        sa.PrimaryKeyConstraint("period", "start_day", name=op.f("pk_page_view_rollups")),
    )
    op.create_table(
        "page_kind_rollups",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("page_kind", sa.Text(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("day", "page_kind", name=op.f("pk_page_kind_rollups")),
    )


def downgrade() -> None:
    op.drop_table("page_kind_rollups")
    op.drop_table("page_view_rollups")
    op.drop_index(op.f("ix_page_view_attempts_ip_at"), table_name="page_view_attempts")
    op.drop_table("page_view_attempts")
    op.drop_index(op.f("ix_page_views_at"), table_name="page_views")
    op.drop_index(op.f("ix_page_views_device_id_page_kind_at"), table_name="page_views")
    op.drop_table("page_views")
