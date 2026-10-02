"""special events: an event kind with its own label and target total, and special imports

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-01

Expand-only. `events` gains kind (default 'regular'), label and target_total (default 50); the
previous release never writes them, so its rebuild stores regular Sundays exactly as before.
`imports.kind` also allows 'special', and `import_special_events` holds each special import's
date, label and target total (its rows and stations use the existing staging tables).

Rollback limit: the previous release lists imports through a FileKind without 'special', so its
admin import list fails once a special import exists, and its rebuild drops special Sundays from
the live tables. Roll back to it only before a special shoot is uploaded, or after
`DELETE FROM imports WHERE kind = 'special'` and a rebuild.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPECIAL_DATES = "SELECT event_date FROM events WHERE kind = 'special'"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_imports_kind"), "imports", type_="check")
    op.create_check_constraint(
        op.f("ck_imports_kind"), "imports", "kind IN ('scores', 'stations', 'special')"
    )
    op.add_column(
        "events",
        sa.Column("kind", sa.Text(), server_default=sa.text("'regular'"), nullable=False),
    )
    op.add_column("events", sa.Column("label", sa.Text(), nullable=True))
    op.add_column(
        "events",
        sa.Column("target_total", sa.SmallInteger(), server_default=sa.text("50"), nullable=False),
    )
    op.create_check_constraint(op.f("ck_events_kind"), "events", "kind IN ('regular', 'special')")
    op.create_table(
        "import_special_events",
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("target_total", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["imports.id"],
            name=op.f("fk_import_special_events_import_id_imports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("import_id", name=op.f("pk_import_special_events")),
    )


def downgrade() -> None:
    # Special Sundays cannot exist without the kind: their live rows go now (rebuildable; the
    # analytics tables are rewritten by the next pipeline run), their imports cascade away.
    op.execute(f"DELETE FROM station_hits WHERE event_date IN ({SPECIAL_DATES})")  # noqa: S608
    op.execute(f"DELETE FROM station_layouts WHERE event_date IN ({SPECIAL_DATES})")  # noqa: S608
    op.execute(
        "DELETE FROM round_metrics WHERE round_id IN (SELECT id FROM rounds"  # noqa: S608
        f" WHERE event_date IN ({SPECIAL_DATES}))"
    )
    op.execute(f"DELETE FROM rounds WHERE event_date IN ({SPECIAL_DATES})")  # noqa: S608
    op.execute("DELETE FROM events WHERE kind = 'special'")
    op.execute("DELETE FROM imports WHERE kind = 'special'")
    op.drop_table("import_special_events")
    op.drop_constraint(op.f("ck_events_kind"), "events", type_="check")
    op.drop_column("events", "target_total")
    op.drop_column("events", "label")
    op.drop_column("events", "kind")
    op.drop_constraint(op.f("ck_imports_kind"), "imports", type_="check")
    op.create_check_constraint(op.f("ck_imports_kind"), "imports", "kind IN ('scores', 'stations')")
