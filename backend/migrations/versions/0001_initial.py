"""initial schema: every C4 table

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
TSTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    # --- staging -------------------------------------------------------------------------
    op.create_table(
        "imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("file_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("uploaded_at", TSTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("committed_at", TSTZ, nullable=True),
        sa.Column("rolled_back_at", TSTZ, nullable=True),
        sa.Column("summary", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("findings", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.CheckConstraint("kind IN ('scores', 'stations')", name=op.f("ck_imports_kind")),
        sa.CheckConstraint(
            "status IN ('pending', 'committed', 'discarded', 'rolled_back')",
            name=op.f("ck_imports_status"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_imports_kind_status"), "imports", ["kind", "status"])
    op.create_index(op.f("ix_imports_sha256"), "imports", ["sha256"])

    op.create_table(
        "import_score_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("gauge_class", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["imports.id"],
            name=op.f("fk_import_score_rows_import_id_imports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_import_score_rows_import_id"), "import_score_rows", ["import_id"])

    op.create_table(
        "import_attendance_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("head_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["imports.id"],
            name=op.f("fk_import_attendance_rows_import_id_imports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_import_attendance_rows_import_id"), "import_attendance_rows", ["import_id"]
    )

    op.create_table(
        "import_station_sheets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("sheet_name", sa.Text(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["imports.id"],
            name=op.f("fk_import_station_sheets_import_id_imports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_import_station_sheets_import_id"), "import_station_sheets", ["import_id"]
    )

    op.create_table(
        "import_station_layout",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sheet_id", sa.Integer(), nullable=False),
        sa.Column("station_no", sa.SmallInteger(), nullable=False),
        sa.Column("target_count", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sheet_id"],
            ["import_station_sheets.id"],
            name=op.f("fk_import_station_layout_sheet_id_import_station_sheets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_import_station_layout_sheet_id"), "import_station_layout", ["sheet_id"]
    )

    op.create_table(
        "import_station_hits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sheet_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("station_no", sa.SmallInteger(), nullable=False),
        sa.Column("hits", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sheet_id"],
            ["import_station_sheets.id"],
            name=op.f("fk_import_station_hits_sheet_id_import_station_sheets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_import_station_hits_sheet_id"), "import_station_hits", ["sheet_id"])

    # --- identity & rules ---------------------------------------------------------------
    op.create_table(
        "shooters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("created_at", TSTZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "shooter_aliases",
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("shooter_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["shooter_id"], ["shooters.id"], name=op.f("fk_shooter_aliases_shooter_id_shooters")
        ),
        sa.PrimaryKeyConstraint("name_key"),
    )
    op.create_index(op.f("ix_shooter_aliases_shooter_id"), "shooter_aliases", ["shooter_id"])
    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", TSTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("deactivated_at", TSTZ, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("at", TSTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=False),
        sa.Column("at", TSTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_login_attempts_ip_at"), "login_attempts", ["ip", "at"])

    # --- live (rebuilt) -----------------------------------------------------------------
    op.create_table(
        "events",
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("round_type", sa.Text(), nullable=False),
        sa.Column("round_type_source", sa.Text(), nullable=False),
        sa.Column("head_count", sa.Integer(), nullable=True),
        sa.Column("n_rounds", sa.Integer(), nullable=False),
        sa.Column("n_shooters", sa.Integer(), nullable=False),
        sa.Column("has_scores", sa.Boolean(), nullable=False),
        sa.Column("has_stations", sa.Boolean(), nullable=False),
        sa.Column("results_complete", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "round_type_source IN ('stations', 'override', 'none')",
            name=op.f("ck_events_round_type_source"),
        ),
        sa.PrimaryKeyConstraint("event_date"),
    )
    op.create_table(
        "rounds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("shooter_id", sa.Integer(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("gauge_class", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_date"], ["events.event_date"], name=op.f("fk_rounds_event_date_events")
        ),
        sa.ForeignKeyConstraint(
            ["shooter_id"], ["shooters.id"], name=op.f("fk_rounds_shooter_id_shooters")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_date", "name_key", "ordinal", name=op.f("uq_rounds_event_date_name_key_ordinal")
        ),
    )
    op.create_index(op.f("ix_rounds_shooter_id"), "rounds", ["shooter_id"])
    op.create_table(
        "shooter_profiles",
        sa.Column("shooter_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("first_event", sa.Date(), nullable=False),
        sa.Column("last_event", sa.Date(), nullable=False),
        sa.Column("n_rounds", sa.Integer(), nullable=False),
        sa.Column("n_events", sa.Integer(), nullable=False),
        sa.Column("left_censored", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["shooter_id"], ["shooters.id"], name=op.f("fk_shooter_profiles_shooter_id_shooters")
        ),
        sa.PrimaryKeyConstraint("shooter_id"),
    )
    op.create_table(
        "station_layouts",
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("station_no", sa.SmallInteger(), nullable=False),
        sa.Column("target_count", sa.SmallInteger(), nullable=False),
        sa.Column("source_import_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("event_date", "station_no"),
    )
    op.create_table(
        "station_hits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("station_no", sa.SmallInteger(), nullable=False),
        sa.Column("sheet_id", sa.Integer(), nullable=False),
        sa.Column("entry_row", sa.Integer(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("shooter_id", sa.Integer(), nullable=True),
        sa.Column("round_id", sa.Integer(), nullable=True),
        sa.Column("hits", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["shooter_id"], ["shooters.id"], name=op.f("fk_station_hits_shooter_id_shooters")
        ),
        sa.ForeignKeyConstraint(
            ["round_id"], ["rounds.id"], name=op.f("fk_station_hits_round_id_rounds")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_date",
            "entry_row",
            "station_no",
            name=op.f("uq_station_hits_event_date_entry_row_station_no"),
        ),
    )
    op.create_table(
        "data_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("shooter_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- weather -----------------------------------------------------------------------
    op.create_table(
        "weather_hourly",
        sa.Column("ts_local", sa.DateTime(timezone=False), nullable=False),
        sa.Column("temp_f", sa.REAL(), nullable=True),
        sa.Column("apparent_f", sa.REAL(), nullable=True),
        sa.Column("precip_in", sa.REAL(), nullable=True),
        sa.Column("rain_in", sa.REAL(), nullable=True),
        sa.Column("wind_mph", sa.REAL(), nullable=True),
        sa.Column("gust_mph", sa.REAL(), nullable=True),
        sa.Column("wind_dir_deg", sa.REAL(), nullable=True),
        sa.Column("cloud_pct", sa.REAL(), nullable=True),
        sa.Column("humidity_pct", sa.REAL(), nullable=True),
        sa.Column("pressure_hpa", sa.REAL(), nullable=True),
        sa.Column("weather_code", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("fetched_at", TSTZ, nullable=False),
        sa.CheckConstraint(
            "source IN ('archive', 'forecast')", name=op.f("ck_weather_hourly_source")
        ),
        sa.PrimaryKeyConstraint("ts_local"),
    )
    op.create_table(
        "event_weather",
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("temp_f", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("apparent_f", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("precip_in", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("wind_mph", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("gust_mph", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("wind_dir_deg", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("cloud_pct", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("humidity_pct", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("pressure_hpa", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("event_date"),
    )
    op.create_table(
        "forecast_cache",
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("fetched_at", TSTZ, nullable=False),
        sa.PrimaryKeyConstraint("target_date"),
    )

    # --- analytics (recomputed) ---------------------------------------------------------
    op.create_table(
        "round_metrics",
        sa.Column("round_id", sa.Integer(), nullable=False),
        sa.Column("field_median", sa.REAL(), nullable=True),
        sa.Column("adjusted", sa.REAL(), nullable=True),
        sa.Column("event_rank", sa.Integer(), nullable=True),
        sa.Column("is_best_round", sa.Boolean(), nullable=False),
        sa.Column("percentile", sa.REAL(), nullable=True),
        sa.Column("expected", sa.REAL(), nullable=True),
        sa.Column("residual", sa.REAL(), nullable=True),
        sa.Column("mu_before", sa.REAL(), nullable=True),
        sa.Column("var_before", sa.REAL(), nullable=True),
        sa.Column("mu_after", sa.REAL(), nullable=True),
        sa.Column("var_after", sa.REAL(), nullable=True),
        sa.ForeignKeyConstraint(
            ["round_id"], ["rounds.id"], name=op.f("fk_round_metrics_round_id_rounds")
        ),
        sa.PrimaryKeyConstraint("round_id"),
    )
    op.create_table(
        "event_metrics",
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column("median", sa.REAL(), nullable=False),
        sa.Column("mean", sa.REAL(), nullable=False),
        sa.Column("stdev", sa.REAL(), nullable=True),
        sa.Column("top_score", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.REAL(), nullable=True),
        sa.PrimaryKeyConstraint("event_date"),
    )
    op.create_table(
        "rating_history",
        sa.Column("shooter_id", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("mu", sa.REAL(), nullable=False),
        sa.Column("var", sa.REAL(), nullable=False),
        sa.PrimaryKeyConstraint("shooter_id", "event_date"),
    )
    op.create_table(
        "achievements_awarded",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shooter_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("round_id", sa.Integer(), nullable=True),
        sa.Column("details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "shooter_id",
            "code",
            "event_date",
            name=op.f("uq_achievements_awarded_shooter_id_code_event_date"),
        ),
    )

    # --- ops ---------------------------------------------------------------------------
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("run_after", TSTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", TSTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", TSTZ, nullable=True),
        sa.Column("finished_at", TSTZ, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')", name=op.f("ck_jobs_status")
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("uq_jobs_dedupe_key_queued"),
        "jobs",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(op.f("ix_jobs_status_run_after"), "jobs", ["status", "run_after"])
    op.create_table(
        "app_state",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", JSONB, nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    for table in (
        "app_state",
        "jobs",
        "achievements_awarded",
        "rating_history",
        "event_metrics",
        "round_metrics",
        "forecast_cache",
        "event_weather",
        "weather_hourly",
        "data_issues",
        "station_hits",
        "station_layouts",
        "shooter_profiles",
        "rounds",
        "events",
        "login_attempts",
        "audit_log",
        "rules",
        "shooter_aliases",
        "shooters",
        "import_station_hits",
        "import_station_layout",
        "import_station_sheets",
        "import_attendance_rows",
        "import_score_rows",
        "imports",
    ):
        op.drop_table(table)
