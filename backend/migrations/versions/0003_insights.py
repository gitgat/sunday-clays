"""insights and insight_picks (Plan 12 Phase 1a T1)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Expand-only: new tables that the previous release never reads.
    op.create_table(
        "insights",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value_hash", sa.Text(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("first_generation", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("home_slot", sa.Text(), nullable=True),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("anchor_date", sa.Date(), nullable=True),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("pages", ARRAY(sa.Text()), nullable=False),
        sa.Column("expires", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "named_shooter_ids",
            ARRAY(sa.Integer()),
            server_default=sa.text("'{}'::integer[]"),
            nullable=False,
        ),
        sa.Column("polarity", sa.Text(), nullable=False),
        sa.Column("kudos", sa.Boolean(), nullable=False),
        sa.Column("template_id", sa.Text(), nullable=False),
        sa.Column("params", JSONB, nullable=False),
        sa.Column("strength", sa.REAL(), nullable=False),
        sa.Column("base_score", sa.REAL(), nullable=False),
        sa.Column("rank_score", sa.REAL(), nullable=False),
        sa.Column("headline", JSONB, nullable=False),
        sa.Column("headline_you", JSONB, nullable=True),
        sa.Column("how", JSONB, nullable=False),
        sa.Column("how_you", JSONB, nullable=True),
        sa.Column("chart", JSONB, nullable=False),
        sa.CheckConstraint(
            "polarity IN ('positive', 'neutral', 'field_negative', 'mixed')",
            name=op.f("ck_insights_polarity"),
        ),
        sa.CheckConstraint(
            "polarity <> 'field_negative' OR cardinality(named_shooter_ids) = 0",
            name=op.f("ck_insights_field_negative_unnamed"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name=op.f("uq_insights_key")),
    )
    op.create_index(
        op.f("ix_insights_subject_type_subject_id"), "insights", ["subject_type", "subject_id"]
    )
    op.create_index(op.f("ix_insights_pages"), "insights", ["pages"], postgresql_using="gin")
    op.create_index(op.f("ix_insights_anchor_date"), "insights", ["anchor_date"])
    op.create_index(
        op.f("ix_insights_named_shooter_ids"),
        "insights",
        ["named_shooter_ids"],
        postgresql_using="gin",
    )
    op.create_table(
        "insight_picks",
        sa.Column("sunday", sa.Date(), nullable=False),
        sa.Column("slot", sa.Text(), nullable=False),
        sa.Column("insight_key", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("sunday", "slot"),
    )


def downgrade() -> None:
    op.drop_table("insight_picks")
    op.drop_index(op.f("ix_insights_named_shooter_ids"), table_name="insights")
    op.drop_index(op.f("ix_insights_anchor_date"), table_name="insights")
    op.drop_index(op.f("ix_insights_pages"), table_name="insights")
    op.drop_index(op.f("ix_insights_subject_type_subject_id"), table_name="insights")
    op.drop_table("insights")
