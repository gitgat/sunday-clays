"""thrown-out stations: station and Sunday flags (Plan thrown-out stations T1a)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-25

Expand-only: three new columns with server defaults, no change to an existing column. The
previous release never writes the flags, and the defaults (false / NULL) keep its rebuild
correct while a rollout is in flight.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("stats_excluded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "station_layouts",
        sa.Column("dropped", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("station_layouts", sa.Column("dropped_source", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_station_layouts_dropped_source"),
        "station_layouts",
        "dropped_source IN ('auto', 'override')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_station_layouts_dropped_source"), "station_layouts", type_="check")
    op.drop_column("station_layouts", "dropped_source")
    op.drop_column("station_layouts", "dropped")
    op.drop_column("events", "stats_excluded")
