import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from sunday_clays.api import app as app_module
from sunday_clays.config import Settings
from sunday_clays.db import (
    SessionDep,
    SessionFactory,
    alembic_config,
    connect_with_retry,
    database_is_ahead,
    schema_is_current,
)

INTERNAL_ERROR = {"error": {"code": "internal", "message": "Internal server error"}}

PENDING_REVISION = """
revision = "9999_pending"
down_revision = "{head}"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
"""


def _script() -> ScriptDirectory:
    return ScriptDirectory.from_config(alembic_config())


def _copy_migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """This image's migrations under ``tmp_path`` (the new working directory); returns the
    versions directory and the current head revision."""
    script = _script()
    head = script.get_current_head()
    assert head is not None
    shutil.copytree(
        Path(script.dir), tmp_path / "migrations", ignore=shutil.ignore_patterns("__pycache__")
    )
    (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = %(here)s/migrations\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path / "migrations" / "versions", head


def test_schema_is_current_on_the_migrated_test_database(engine: Engine) -> None:
    assert schema_is_current(engine) is True


def test_schema_is_not_current_while_a_revision_is_pending(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions, head = _copy_migrations(tmp_path, monkeypatch)
    (versions / "9999_pending.py").write_text(PENDING_REVISION.format(head=head))

    assert schema_is_current(engine) is False


def test_schema_newer_than_the_image_counts_as_current_after_a_rollback(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plan 13: a rolled-back worker must start against the newer (expand/contract) schema."""
    versions, head = _copy_migrations(tmp_path, monkeypatch)
    newest = _script().get_revision(head)
    (versions / Path(newest.path).name).unlink()

    assert schema_is_current(engine) is True
    with engine.connect() as conn:
        assert database_is_ahead(conn, _script()) is True


def test_a_database_at_this_images_head_is_not_ahead(engine: Engine) -> None:
    with engine.connect() as conn:
        assert database_is_ahead(conn, _script()) is False


def test_an_unmigrated_database_is_not_ahead(engine: Engine) -> None:
    with engine.connect() as conn, conn.begin() as tx:
        conn.execute(text("DELETE FROM alembic_version"))
        assert database_is_ahead(conn, _script()) is False
        tx.rollback()


def test_connections_run_in_utc(engine: Engine) -> None:
    with engine.connect() as conn:
        assert conn.execute(text("SHOW timezone")).scalar_one() == "UTC"


def test_connect_with_retry_returns_a_live_connection(engine: Engine) -> None:
    with connect_with_retry(engine, timeout_s=1.0, interval_s=0.1) as conn:
        assert conn.execute(text("SELECT 1")).scalar_one() == 1


@pytest.fixture
def probe_table(engine: Engine) -> Iterator[None]:
    """A committed scratch table so real commits can be observed; dropped afterwards.

    Its UNIQUE check is deferred to COMMIT, so a duplicate insert makes the commit itself fail.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE plan01_session_probe (v int NOT NULL,"
                " UNIQUE (v) DEFERRABLE INITIALLY DEFERRED)"
            )
        )
    yield
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE plan01_session_probe"))


@pytest.fixture
def factory_bound_to_test_engine(engine: Engine) -> Iterator[None]:
    SessionFactory.configure(bind=engine)
    yield
    SessionFactory.configure(bind=None)


def probe_app() -> FastAPI:
    app = FastAPI()

    @app.post("/ok")
    def ok(session: SessionDep) -> None:
        session.execute(text("INSERT INTO plan01_session_probe VALUES (1)"))

    @app.post("/fail")
    def fail(session: SessionDep) -> None:
        session.execute(text("INSERT INTO plan01_session_probe VALUES (2)"))
        raise HTTPException(status_code=401)

    return app


def committed_values(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return list(conn.execute(text("SELECT v FROM plan01_session_probe ORDER BY v")).scalars())


def test_get_session_commits_on_success_and_rolls_back_on_http_exception(
    engine: Engine, probe_table: None, factory_bound_to_test_engine: None
) -> None:
    client = TestClient(probe_app())

    assert client.post("/ok").status_code == 200
    assert client.post("/fail").status_code == 401

    assert committed_values(engine) == [1]


def test_get_session_binds_the_factory_from_settings_on_first_use(
    test_settings: Settings, engine: Engine, probe_table: None
) -> None:
    SessionFactory.configure(bind=None)
    try:
        assert TestClient(probe_app()).post("/ok").status_code == 200
        bound = SessionFactory.kw["bind"]
        assert bound is not engine
        assert bound.url.database == engine.url.database
        assert bound.url.port == engine.url.port
    finally:
        bound_engine = SessionFactory.kw.get("bind")
        SessionFactory.configure(bind=None)
        if bound_engine is not None:
            bound_engine.dispose()
    assert committed_values(engine) == [1]


class CommittedAtResponseStart:
    """Outermost ASGI wrapper: at ``http.response.start``, reads the committed probe rows
    through a separate connection, i.e. exactly what a client acting on the response sees."""

    def __init__(self, app: ASGIApp, engine: Engine, seen: list[list[int]]) -> None:
        self.app = app
        self.engine = engine
        self.seen = seen

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def recording_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                self.seen.append(committed_values(self.engine))
            await send(message)

        await self.app(scope, receive, recording_send)


@pytest.fixture
def session_dep_app(
    settings_env: None,
    monkeypatch: pytest.MonkeyPatch,
    probe_table: None,
    factory_bound_to_test_engine: None,
) -> FastAPI:
    """create_app() with router discovery emptied (Decision 28) plus two SessionDep POST probes."""
    monkeypatch.setattr(app_module, "discover_routers", lambda: [])
    app = app_module.create_app(page_cache_allowlist=())

    @app.post("/api/_probe/insert")
    def insert(session: SessionDep) -> dict[str, bool]:
        session.execute(text("INSERT INTO plan01_session_probe VALUES (1)"))
        return {"ok": True}

    @app.post("/api/_probe/commit-fails")
    def commit_fails(session: SessionDep) -> dict[str, bool]:
        session.execute(text("INSERT INTO plan01_session_probe VALUES (5), (5)"))
        return {"ok": True}  # the deferred UNIQUE check fails only in get_session's commit

    return app


def test_session_dep_commits_before_the_response_starts(
    session_dep_app: FastAPI, engine: Engine
) -> None:
    seen: list[list[int]] = []
    session_dep_app.add_middleware(CommittedAtResponseStart, engine=engine, seen=seen)

    with TestClient(session_dep_app) as client:
        response = client.post("/api/_probe/insert")

    assert response.status_code == 200
    assert seen == [[1]]


def test_session_dep_commit_failure_is_a_500_not_a_success(
    session_dep_app: FastAPI, engine: Engine
) -> None:
    with TestClient(session_dep_app, raise_server_exceptions=False) as client:
        response = client.post("/api/_probe/commit-fails")

    assert response.status_code == 500
    assert response.json() == INTERNAL_ERROR
    assert committed_values(engine) == []


def test_a_database_with_a_known_and_an_unknown_revision_counts_as_ahead(engine: Engine) -> None:
    """Mixed heads: the unknown one would make `run_migrations()` fail, so do not migrate."""
    with engine.connect() as conn, conn.begin() as tx:
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('9999_unknown')"))
        assert database_is_ahead(conn, _script()) is True
        tx.rollback()
