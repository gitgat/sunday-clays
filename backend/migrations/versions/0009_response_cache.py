"""response cache: finished JSON bodies of allowlisted viewer GET routes (Plan 19 §3.7)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-02

Expand-only: one new table the previous release never reads. UNLOGGED: no write-ahead log, so
stores are cheap; Postgres empties it after a crash, which is harmless for a cache. It is
disposable (never in domain/rebuild.py LIVE_TABLES), and a restore needs no step for it.
If Plan 20 merges first and takes 0009, renumber this file to the next free number and set
down_revision to the head on main at that moment (spec D5).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNLOGGED TABLE response_cache (
            key text NOT NULL,
            data_version integer NOT NULL,
            local_date date NOT NULL,
            app_version text NOT NULL,
            role text NOT NULL,
            route text NOT NULL,
            body bytea NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT pk_response_cache PRIMARY KEY (key),
            CONSTRAINT ck_response_cache_role CHECK (role IN ('viewer', 'admin')),
            CONSTRAINT ck_response_cache_body_size CHECK (octet_length(body) <= 2097152)
        )
        """
    )


def downgrade() -> None:
    op.drop_table("response_cache")
