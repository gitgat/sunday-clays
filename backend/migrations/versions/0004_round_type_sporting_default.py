"""round type is sporting or super sporting: fold 'unknown' into 'sporting'

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Data only: the next rebuild writes 'sporting' itself, this makes the stored rows and the
    # round_type_override rules valid straight away.
    op.execute("UPDATE events SET round_type = 'sporting' WHERE round_type = 'unknown'")
    op.execute(
        "UPDATE rules SET payload = jsonb_set(payload, '{round_type}', '\"sporting\"') "
        "WHERE rule_type = 'round_type_override' AND payload ->> 'round_type' = 'unknown'"
    )


def downgrade() -> None:
    # The old value cannot be told apart from a real 'sporting' Sunday; nothing to undo.
    pass
