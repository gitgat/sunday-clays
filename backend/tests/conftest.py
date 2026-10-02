"""Shared pytest fixtures (C2 Tests). Plan 01 T1 owns every fixture in this file.

Later plans add their own fixtures here (Plan 03 T6/T7, Plan 04 T1, Plan 06 T1) and never
change these.
"""

import os
import socket
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer

from sunday_clays.analytics.cache import clear_cache
from sunday_clays.api.app import create_app
from sunday_clays.auth.sessions import Role
from sunday_clays.config import SECRET_FIELDS, Settings, get_settings
from sunday_clays.db import alembic_config, get_session, make_engine

FIXTURES_DIR = Path(__file__).parent / "fixtures"
VIEWER_TEST_PASSWORD = "viewer-test-password"
ADMIN_TEST_PASSWORD = "admin-test-password"
TEST_SESSION_SECRET = "test-session-secret-0123456789abcdef-0123456789abcdef"


@pytest.fixture(autouse=True)
def _fresh_settings_cache() -> Iterator[None]:
    """Every test starts and ends with an empty ``get_settings`` cache."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def closed_port() -> int:
    """A localhost TCP port with nothing listening (connections are refused at once)."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def password_hashes() -> dict[str, str]:
    """argon2id hashes (m=19456 KiB, t=2, p=1) of the viewer and admin test passwords."""
    hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
    return {"viewer": hasher.hash(VIEWER_TEST_PASSWORD), "admin": hasher.hash(ADMIN_TEST_PASSWORD)}


@pytest.fixture
def settings_env(
    monkeypatch: pytest.MonkeyPatch, closed_port: int, password_hashes: dict[str, str]
) -> None:
    """Valid env for ``Settings`` with no database (DATABASE_URL points at a closed port)."""
    for name in SECRET_FIELDS:
        monkeypatch.delenv(f"{name.upper()}_FILE", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x")
    monkeypatch.setenv("SESSION_SECRET", TEST_SESSION_SECRET)
    monkeypatch.setenv("VIEWER_PASSWORD_HASH", password_hashes["viewer"])
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", password_hashes["admin"])
    monkeypatch.setenv("COOKIE_SECURE", "false")
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """``TEST_DATABASE_URL`` if set, else a ``postgres:17`` testcontainer for this pytest run."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return
    with pytest.MonkeyPatch.context() as mp:
        if sys.platform == "darwin" and "TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE" not in os.environ:
            # Docker Desktop/Colima/OrbStack: Ryuk must mount the VM-side socket path.
            mp.setenv("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", "/var/run/docker.sock")
        with PostgresContainer("postgres:17", driver="psycopg") as postgres:
            yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    """Session-scoped engine on the test DB, upgraded once to the Alembic head."""
    test_engine = make_engine(database_url)
    config = alembic_config()
    with test_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session inside an outer transaction that is rolled back after the test."""
    connection = engine.connect()
    outer = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db_session
    finally:
        db_session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def test_settings(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> Settings:
    """``settings_env`` pointed at the real test database; ``cookie_secure`` is False."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def client(session: Session, test_settings: Settings) -> Iterator[TestClient]:
    """TestClient whose ``get_session`` override mirrors production commit/rollback per request.

    The override inherits ``SessionDep``'s function scope, so it too commits before the response.
    """
    app = create_app()

    def session_override() -> Iterator[Session]:
        nested = session.begin_nested()
        try:
            yield session
        except BaseException:
            if nested.is_active:
                nested.rollback()
            raise
        else:
            if nested.is_active:
                nested.commit()

    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def scores_bytes() -> bytes:
    return (FIXTURES_DIR / "scores_2026-09-27.xlsx").read_bytes()


@pytest.fixture(scope="session")
def stations_bytes() -> bytes:
    return (FIXTURES_DIR / "stations_2026-09-27.xlsx").read_bytes()


# --- Plan 03 T7: real commits for multi-connection tests (C2) ----------------------------------
@pytest.fixture
def committed_engine(engine: Engine) -> Iterator[Engine]:
    """The empty test DB with real commits; SessionFactory is bound to it for the test."""
    from sunday_clays.db import SessionFactory  # local: keeps this appended block self-contained

    previous_bind = SessionFactory.kw.get("bind")
    SessionFactory.configure(bind=engine)
    try:
        yield engine
    finally:
        SessionFactory.configure(bind=previous_bind)
        with engine.begin() as conn:
            tables = (
                conn.exec_driver_sql(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
                .scalars()
                .all()
            )
            quoted = ", ".join(f'"{table}"' for table in tables)
            # A connection still holding locks (e.g. a leaked rollback-fixture session) must fail
            # the teardown, not hang the run.
            conn.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
            conn.exec_driver_sql(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")


# --- Plan 04 T1: auth fixtures (C2; plan Decisions D5, D6) ------------------------------------

_TEST_PASSWORDS: dict[Role, str] = {
    "viewer": VIEWER_TEST_PASSWORD,
    "admin": ADMIN_TEST_PASSWORD,
}
# Cheap argon2id parameters keep logins fast; verify reads the parameters from the hash.
_FAST_HASHER = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
_TEST_HASHES: dict[Role, str] = {
    role: _FAST_HASHER.hash(pw) for role, pw in _TEST_PASSWORDS.items()
}
_SECRET_ENV = tuple(name.upper() for name in SECRET_FIELDS)


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch, closed_port: int) -> Iterator[Settings]:
    """Settings with the known test passwords, via env vars, for every get_settings() caller.

    Keeps a DATABASE_URL already set (e.g. by ``client``); otherwise points at Plan 01's closed
    port, like ``settings_env``, so a stray connection from a unit test is refused at once.
    """
    for name in _SECRET_ENV:
        monkeypatch.delenv(f"{name}_FILE", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get("DATABASE_URL")
        or f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x",
    )
    monkeypatch.setenv("SESSION_SECRET", TEST_SESSION_SECRET)
    monkeypatch.setenv("VIEWER_PASSWORD_HASH", _TEST_HASHES["viewer"])
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", _TEST_HASHES["admin"])
    monkeypatch.setenv("COOKIE_SECURE", "false")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def login_passwords() -> dict[Role, str]:
    return dict(_TEST_PASSWORDS)


def _use_env_settings(test_client: TestClient) -> FastAPI:
    app = cast(FastAPI, test_client.app)
    app.dependency_overrides.pop(get_settings, None)
    return app


def _logged_in(app: FastAPI, role: Role) -> TestClient:
    logged_in = TestClient(app)
    response = logged_in.post("/api/auth/login", json={"password": _TEST_PASSWORDS[role]})
    assert response.status_code == 200, response.text
    return logged_in


@pytest.fixture
def anon_client(client: TestClient, auth_env: Settings) -> TestClient:
    """The C2 ``client`` (no cookie) wired to the ``auth_env`` settings."""
    _use_env_settings(client)
    return client


@pytest.fixture
def viewer_client(anon_client: TestClient) -> Iterator[TestClient]:
    logged_in = _logged_in(cast(FastAPI, anon_client.app), "viewer")
    yield logged_in
    logged_in.close()


@pytest.fixture
def admin_client(anon_client: TestClient) -> Iterator[TestClient]:
    logged_in = _logged_in(cast(FastAPI, anon_client.app), "admin")
    yield logged_in
    logged_in.close()


@pytest.fixture
def fx_viewer_client(fx_client: TestClient, auth_env: Settings) -> Iterator[TestClient]:
    """Viewer over the committed-fixtures world; usable once Plan 03 T6's ``fx_client`` exists."""
    logged_in = _logged_in(_use_env_settings(fx_client), "viewer")
    yield logged_in
    logged_in.close()


@pytest.fixture
def fx_admin_client(fx_client: TestClient, auth_env: Settings) -> Iterator[TestClient]:
    """Admin over the committed-fixtures world; usable once Plan 03 T6's ``fx_client`` exists."""
    logged_in = _logged_in(_use_env_settings(fx_client), "admin")
    yield logged_in
    logged_in.close()


# --- Plan 12 Phase 1a T1: weather for the committed-fixtures world -----------------------------
WEATHER_FIXTURE = FIXTURES_DIR / "weather_hourly_2026-09-27.json"
WEATHER_FETCHED_AT = "2026-09-28T00:00:00+00:00"


def load_weather_fixture(session: Session) -> None:
    """Insert the committed `weather_hourly` window rows (10:00-12:00 of every fixture date).

    s20 rebuilds `event_weather` from these on the next `run_pipeline`, so the fx world has the
    same weather bands as the dev stack the file was exported from.
    """
    import json
    from datetime import datetime

    from sqlalchemy import insert

    from sunday_clays.models import WeatherHourly

    rows = json.loads(WEATHER_FIXTURE.read_text())
    fetched = datetime.fromisoformat(WEATHER_FETCHED_AT)
    session.execute(
        insert(WeatherHourly),
        [
            {**row, "ts_local": datetime.fromisoformat(row["ts_local"]), "fetched_at": fetched}
            for row in rows
        ],
    )


# --- Plan 03 T6: the committed-fixtures world (C2) ---------------------------------------------
@contextmanager
def _build_world(
    engine: Engine, suffix: str, uploads: Sequence[tuple[str, bytes]]
) -> Iterator[Engine]:
    """Database ``<test db>_<suffix>`` with ``uploads`` committed and rebuilt, then the pipeline.

    Built with real commits: stage + commit + ``rebuild_live`` each upload in order, then the
    weather fixture and ``run_pipeline``. The database is dropped on exit, also when setup fails.
    Shared by ``fx_engine`` and ``fx_special_engine`` so the worlds are built the same way.
    """
    # local imports keep this appended block self-contained
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    from sunday_clays.analytics.pipeline import run_pipeline
    from sunday_clays.domain.imports import commit_import, stage_import
    from sunday_clays.domain.rebuild import rebuild_live

    url = engine.url.set(database=f"{engine.url.database}_{suffix}")
    drop = f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'
    # NullPool: no idle connection to the maintenance database is held for the whole run.
    admin = create_engine(
        engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    with admin.connect() as conn:
        conn.exec_driver_sql(drop)
        conn.exec_driver_sql(f'CREATE DATABASE "{url.database}"')
    world = make_engine(url.render_as_string(hide_password=False))
    try:
        config = alembic_config()
        with world.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(world) as setup:
            # Scores go live before the stations file is staged, as in the real admin flow, so
            # the stored stations preview links against live rounds (Hadley's 9/13 mismatch).
            for filename, data in uploads:
                preview = stage_import(setup, data, filename)
                commit_import(setup, preview.import_id)
                rebuild_live(setup)
            load_weather_fixture(setup)  # Plan 12: weather kinds need event_weather (s20)
            run_pipeline(setup)
            setup.commit()
        yield world
    finally:
        world.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(drop)
        admin.dispose()


def _fixture_uploads() -> list[tuple[str, bytes]]:
    return [
        (name, (FIXTURES_DIR / name).read_bytes())
        for name in ("scores_2026-09-27.xlsx", "stations_2026-09-27.xlsx")
    ]


def _rolled_back_session(world: Engine) -> Iterator[Session]:
    """A session on ``world`` whose work is rolled back after the test."""
    connection = world.connect()
    outer = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db_session
    finally:
        db_session.close()
        outer.rollback()
        connection.close()


def _client_for(db_session: Session) -> Iterator[TestClient]:
    """Like ``client`` (same get_session override), bound to ``db_session``."""
    app = create_app()

    def session_override() -> Iterator[Session]:
        nested = db_session.begin_nested()
        try:
            yield db_session
        except BaseException:
            if nested.is_active:
                nested.rollback()
            raise
        else:
            if nested.is_active:
                nested.commit()

    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def fx_engine(engine: Engine) -> Iterator[Engine]:
    """Database ``<test db>_fx`` holding both real fixtures committed and rebuilt, once per run.

    Tests reach it only through ``fx_session``/``fx_client`` (rolled back after each test); they
    never run the worker or open their own ``SessionFactory`` session on it.
    """
    with _build_world(engine, "fx", _fixture_uploads()) as world:
        yield world


@pytest.fixture
def fx_session(fx_engine: Engine) -> Iterator[Session]:
    """Like ``session``, but on the committed-fixtures database."""
    yield from _rolled_back_session(fx_engine)


@pytest.fixture
def fx_client(fx_session: Session, test_settings: Settings) -> Iterator[TestClient]:
    """Like ``client`` (same settings fixture and get_session override), bound to fx_session."""
    yield from _client_for(fx_session)


# --- Plan 06 T1: the analytics memo (C2) --------------------------------------------------------
@pytest.fixture(autouse=True)
def _clear_analytics_cache() -> None:
    """C2: every test starts with an empty analytics memo (Plan 06 T1)."""
    clear_cache()


# --- Plan 17 T1: special-event workbooks ------------------------------------------------------
SPECIAL_SUNDAY = date(2026, 9, 20)  # the fixture has no Sunday on this date
SPECIAL_LABEL = "3-Bird Shoot"
SPECIAL_ENTRIES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("Hadley, Ike", (6, 5, 6, 4, 6, 5, 6, 6, 5, 6)),  # 55
    ("Kaplan, Noel", (6, 5, 5, 5, 6, 5, 5, 5, 4, 5)),  # 51
    ("Devlin, Sid", (5, 5, 4, 5, 5, 4, 5, 5, 5, 5)),  # 48
    ("Abernathy, Preston", (4, 5, 4, 5, 4, 4, 5, 4, 5, 4)),  # 44
    ("Kim, Pat", (4, 4, 3, 4, 4, 4, 4, 4, 4, 4)),  # 39, not in the fixture: a new shooter
)


def _special_workbook(
    entries: Sequence[tuple[str, Sequence[int]]] = SPECIAL_ENTRIES,
    *,
    event_date: date = SPECIAL_SUNDAY,
    label: str = SPECIAL_LABEL,
    stations: Sequence[object] = tuple(range(1, 11)),
    targets: Sequence[int] = (6,) * 10,
    total: bool = True,
) -> bytes:
    """A special-event workbook (Plan 17 format) with correct totals."""
    import io

    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Special Event"
    sheet.append(["Special event", label])
    sheet.append(["Event date", event_date])
    sheet.append(["Station", *stations, *(["Total"] if total else [])])
    sheet.append(["Targets", *targets])
    for name, hits in entries:
        sheet.append([name, *hits, *([sum(hits)] if total else [])])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


@pytest.fixture
def special_workbook() -> Callable[..., bytes]:
    return _special_workbook


# --- Plan 17 T2: the committed-fixtures world plus one special Sunday --------------------------
@pytest.fixture(scope="session")
def fx_special_engine(engine: Engine) -> Iterator[Engine]:
    """`fx_engine`'s world built the same way, plus the special Sunday 2026-09-20 (Plan 17).

    SPECIAL_ENTRIES: four fixture shooters who shot 2026-09-13 and 2026-09-27, and Kim, Pat, who
    is new. Its own database, so the analytics memo (keyed by database name) never mixes it with
    fx_engine; tests that read both worlds still call clear_cache() between them.
    """
    uploads = [*_fixture_uploads(), ("special_2026-09-20.xlsx", _special_workbook())]
    with _build_world(engine, "fx_special", uploads) as world:
        yield world


@pytest.fixture
def fx_special_session(fx_special_engine: Engine) -> Iterator[Session]:
    """Like ``fx_session``, on the special-Sunday world."""
    yield from _rolled_back_session(fx_special_engine)


@pytest.fixture
def fx_special_client(fx_special_session: Session, test_settings: Settings) -> Iterator[TestClient]:
    """Like ``fx_client``, bound to ``fx_special_session``."""
    yield from _client_for(fx_special_session)


@pytest.fixture
def fx_special_viewer_client(
    fx_special_client: TestClient, auth_env: Settings
) -> Iterator[TestClient]:
    logged_in = _logged_in(_use_env_settings(fx_special_client), "viewer")
    yield logged_in
    logged_in.close()
