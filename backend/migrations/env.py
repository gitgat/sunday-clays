"""Alembic environment: one connection, one advisory lock, then the migrations (Plan 01 T1)."""

import logging
from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text

from sunday_clays.config import database_url_from_env
from sunday_clays.db import connect_with_retry, database_is_ahead, make_engine
from sunday_clays.models import Base

MIGRATION_LOCK_KEY = 7263001  # pg_advisory_xact_lock key; serialises concurrent `api` starts

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or database_url_from_env()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        script = ScriptDirectory.from_config(config)
        if database_is_ahead(connection, script):
            logging.getLogger("alembic.env").warning(
                "database schema is newer than this image's migrations (a rollback);"
                " starting without migrating (database at %s, image head %s)",
                ", ".join(context.get_context().get_current_heads()),
                ", ".join(script.get_heads()),
            )
            return
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    shared = config.attributes.get("connection")
    if shared is not None:
        _run(shared)
        return
    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    x_args = context.get_x_argument(as_dictionary=True)
    retry_seconds = float(x_args.get("connect_retry_seconds", "60"))
    engine = make_engine(_database_url())
    try:
        with connect_with_retry(engine, timeout_s=retry_seconds) as connection:
            _run(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
