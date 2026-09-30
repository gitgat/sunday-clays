"""Engine, sessions and migration-state helpers (C2 ``db.py``)."""

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from fastapi import Depends
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from sunday_clays.config import get_settings

SOURCE_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
_BARE_SCHEMES = ("postgresql://", "postgres://")
CONNECT_TIMEOUT_SECONDS = 5  # per attempt; an unreachable host fails fast instead of hanging

SessionFactory: sessionmaker[Session] = sessionmaker(expire_on_commit=False)


def make_engine(url: str) -> Engine:
    """Engine for ``url``; bare ``postgresql://`` URLs use psycopg 3; sessions run in UTC."""
    for scheme in _BARE_SCHEMES:
        if url.startswith(scheme):
            url = "postgresql+psycopg://" + url.removeprefix(scheme)
            break
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": "-c timezone=UTC", "connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def get_session() -> Iterator[Session]:
    """One session per request; commit on success, rollback on any error. Use via SessionDep."""
    if SessionFactory.kw.get("bind") is None:
        SessionFactory.configure(bind=make_engine(get_settings().database_url.get_secret_value()))
    session = SessionFactory()
    try:
        yield session
    except BaseException:
        session.rollback()
        raise
    else:
        session.commit()
    finally:
        session.close()


# Never declare an unscoped ``Depends(get_session)``: use ``SessionDep`` or the inline
# ``Annotated[Session, Depends(get_session, scope="function")]``. FastAPI's default "request"
# scope would run the commit after the response is sent, so a failed commit would still reach
# the client as a success; "function" scope commits first, and a failure becomes a 500.
# A yield dependency that takes a session must also use scope="function".
SessionDep = Annotated[Session, Depends(get_session, scope="function")]


def alembic_config() -> Config:
    """``alembic.ini`` from the working directory (the image's /app), else the source tree."""
    ini = Path("alembic.ini")
    if not ini.is_file():
        ini = SOURCE_ALEMBIC_INI
    return Config(str(ini))


def schema_is_current(engine: Engine) -> bool:
    """At this image's head, or ahead of it after a rollback (``database_is_ahead``)."""
    script = ScriptDirectory.from_config(alembic_config())
    with engine.connect() as conn:
        current = set(MigrationContext.configure(conn).get_current_heads())
        ahead = database_is_ahead(conn, script)
    return ahead or current == set(script.get_heads())


def database_is_ahead(connection: Connection, script: ScriptDirectory) -> bool:
    """True when a revision the database is at is unknown to ``script`` (mixed known and unknown
    heads count as ahead too, since migrating would fail on the unknown one): this image is older
    than the schema, which happens only after a rollback. Expand/contract migrations keep the
    previous release's code working on the newer schema, so it must start without migrating
    (Plan 13)."""
    current = MigrationContext.configure(connection).get_current_heads()
    return bool(current) and not all(_knows(script, revision) for revision in current)


def _knows(script: ScriptDirectory, revision: str) -> bool:
    try:
        script.get_revision(revision)
    except CommandError:
        return False
    return True


def connect_with_retry(
    engine: Engine, *, timeout_s: float = 60.0, interval_s: float = 2.0
) -> Connection:
    """First connection for migrations: retry every ``interval_s`` until ``timeout_s`` elapses."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            return engine.connect()
        except OperationalError:
            if time.monotonic() + interval_s > deadline:
                raise
            time.sleep(interval_s)
