"""station labels: a lettered station such as 7A is its own station

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-29

Rollback limit: station_no is only the sort integer, so "7" and "7A" both have station_no 7. Once
a Sunday with a lettered station has been imported, the previous release cannot rebuild it (its
station_layouts primary key on station_no collides), double-counts the 7A hits in its station_no
joins, and raises a KeyError on a station_reset stored as {"station": "7A"}. Roll back to the
pre-label release only before a lettered Sunday is imported, or delete the staged lettered imports
and lettered station_reset rules first.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("import_station_layout", "import_station_hits", "station_layouts", "station_hits")


def upgrade() -> None:
    # Expand: station_no stays (it is the sort integer, 7 for "7A") and nothing is dropped, so the
    # previous release still runs against this schema. It never writes a label, so a trigger
    # fills the label of its rows from station_no.
    # TODO(contract): drop station_label_default() and these triggers in the contract migration that
    # follows the first release that no longer needs to roll back to the pre-label version.
    op.execute(
        "CREATE FUNCTION station_label_default() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN "
        "IF NEW.station_label IS NULL THEN NEW.station_label := NEW.station_no::text; END IF; "
        "RETURN NEW; END $$"
    )
    for table in TABLES:
        op.add_column(table, sa.Column("station_label", sa.Text(), nullable=True))
        op.execute(f"UPDATE {table} SET station_label = station_no::text")  # noqa: S608 - fixed names
        op.alter_column(table, "station_label", nullable=False)
        op.execute(
            f"CREATE TRIGGER {table}_station_label_default BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION station_label_default()"
        )
    op.drop_constraint(op.f("pk_station_layouts"), "station_layouts", type_="primary")
    op.create_primary_key(
        op.f("pk_station_layouts"), "station_layouts", ["event_date", "station_label"]
    )
    op.drop_constraint(
        op.f("uq_station_hits_event_date_entry_row_station_no"), "station_hits", type_="unique"
    )
    op.create_unique_constraint(
        op.f("uq_station_hits_event_date_entry_row_station_label"),
        "station_hits",
        ["event_date", "entry_row", "station_label"],
    )


def downgrade() -> None:
    # A lettered station cannot exist without its label, so its rows go (the next rebuild from
    # the staged imports would put them back under the labelled schema).
    for table in (
        "station_hits",
        "station_layouts",
        "import_station_hits",
        "import_station_layout",
    ):
        op.execute(f"DELETE FROM {table} WHERE station_label <> station_no::text")  # noqa: S608
    op.drop_constraint(
        op.f("uq_station_hits_event_date_entry_row_station_label"), "station_hits", type_="unique"
    )
    op.create_unique_constraint(
        op.f("uq_station_hits_event_date_entry_row_station_no"),
        "station_hits",
        ["event_date", "entry_row", "station_no"],
    )
    op.drop_constraint(op.f("pk_station_layouts"), "station_layouts", type_="primary")
    op.create_primary_key(
        op.f("pk_station_layouts"), "station_layouts", ["event_date", "station_no"]
    )
    for table in TABLES:
        op.execute(f"DROP TRIGGER {table}_station_label_default ON {table}")
        op.drop_column(table, "station_label")
    op.execute("DROP FUNCTION station_label_default()")
