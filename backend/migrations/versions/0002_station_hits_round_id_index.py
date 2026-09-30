"""index station_hits.round_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # rebuild_live clears rounds with DELETE after station_hits; each deleted round's FK check
    # looks up station_hits by round_id, a sequential scan per round without this index.
    # Expand-only: the previous release runs unchanged against it.
    op.create_index(op.f("ix_station_hits_round_id"), "station_hits", ["round_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_station_hits_round_id"), table_name="station_hits")
