"""insight bumps: anonymous per-device fist bumps on insights, and their rate-limit log

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01

Expand-only: two new tables that the previous release never reads, so it runs unchanged on this
schema. Both are durable: rebuild_live only clears the live tables (domain/rebuild.py LIVE_TABLES).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fist_bumps",
        sa.Column("insight_key", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("insight_key", "device_id", name=op.f("pk_fist_bumps")),
    )
    op.create_table(
        "bump_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bump_attempts")),
    )
    op.create_index(op.f("ix_bump_attempts_ip_at"), "bump_attempts", ["ip", "at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_bump_attempts_ip_at"), table_name="bump_attempts")
    op.drop_table("bump_attempts")
    op.drop_table("fist_bumps")
