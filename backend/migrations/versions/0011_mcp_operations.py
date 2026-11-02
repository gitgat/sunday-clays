"""scores MCP audit table: mcp_operations (scores MCP phase 2 T4)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-01

Expand-only: one new table, no change to an existing one. The previous release never touches it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("caller", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("scores_import_id", sa.Integer(), nullable=True),
        sa.Column("stations_import_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("commit_path", sa.Text(), nullable=True),
        sa.Column("backup_file", sa.Text(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('week', 'correction')", name=op.f("ck_mcp_operations_kind")),
        sa.CheckConstraint(
            "status IN ('previewed', 'committed', 'rolled_back', 'expired', 'refused')",
            name=op.f("ck_mcp_operations_status"),
        ),
        sa.CheckConstraint(
            "commit_path IN ('mcp-auto', 'cli-approve', 'web-ui-approve')",
            name=op.f("ck_mcp_operations_commit_path"),
        ),
        sa.ForeignKeyConstraint(
            ["scores_import_id"], ["imports.id"], name=op.f("fk_mcp_operations_scores_import_id")
        ),
        sa.ForeignKeyConstraint(
            ["stations_import_id"],
            ["imports.id"],
            name=op.f("fk_mcp_operations_stations_import_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_operations")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_mcp_operations_idempotency_key")),
    )
    op.create_index(
        op.f("ix_mcp_operations_status_created_at"),
        "mcp_operations",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mcp_operations_status_created_at"), table_name="mcp_operations")
    op.drop_table("mcp_operations")
