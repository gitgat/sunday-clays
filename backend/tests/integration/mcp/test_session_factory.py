"""default_session_factory against a real database: read-only, time-limited, rolls back."""

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from sunday_clays import db
from sunday_clays.mcp import server


@pytest.fixture(autouse=True)
def _fresh_factory(
    monkeypatch: pytest.MonkeyPatch, database_url: str, engine: object
) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", database_url)
    factory = sessionmaker()
    monkeypatch.setattr(db, "SessionFactory", factory)
    yield
    bind = factory.kw.get("bind")
    if bind is not None:
        bind.dispose()


def test_statement_timeout_is_ten_seconds() -> None:
    with server.default_session_factory() as session:
        assert session.scalar(text("SHOW statement_timeout")) == "10s"


def test_sessions_are_read_only() -> None:
    with (
        pytest.raises(DBAPIError, match="read-only"),
        server.default_session_factory() as session,
    ):
        session.execute(text("CREATE TEMP TABLE should_fail (x int)"))


def _fail_inside_a_session() -> None:
    with server.default_session_factory() as session:
        session.execute(text("SELECT 1"))
        raise RuntimeError("boom")


def test_an_error_rolls_the_session_back_and_reraises() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        _fail_inside_a_session()
    # The pool still hands out a working connection afterwards.
    with server.default_session_factory() as session:
        assert session.scalar(text("SELECT 1")) == 1


def test_write_sessions_are_writable_with_a_sixty_second_timeout_and_commit() -> None:
    server._write_sessionmakers.clear()
    try:
        with server.write_session_factory() as session:
            assert session.scalar(text("SHOW statement_timeout")) == "1min"
            session.execute(text("CREATE TABLE write_probe (x int)"))
            session.execute(text("INSERT INTO write_probe VALUES (1)"))
        with server.write_session_factory() as session:
            assert session.scalar(text("SELECT x FROM write_probe")) == 1
            session.execute(text("DROP TABLE write_probe"))
    finally:
        for maker in server._write_sessionmakers.values():
            maker.kw["bind"].dispose()
        server._write_sessionmakers.clear()


def test_a_refusal_commits_its_record_through_the_real_write_factory() -> None:
    import datetime as dt

    from sunday_clays.mcp import writes
    from sunday_clays.mcp.build import WeekInput
    from sunday_clays.models import McpOperation

    server._write_sessionmakers.clear()
    week = WeekInput.model_validate(
        {
            "date": "2026-10-04",
            "stations": ["1", "2", "3", "4", "5"],
            "counts": [10, 10, 10, 10, 10],
            "shooters": [{"name": "Testshooter, Beta", "score": 3, "status": "Guest"}],
        }
    )
    now = dt.datetime(2026, 10, 6, tzinfo=dt.UTC)
    try:
        with pytest.raises(writes.Refusal) as exc:  # an empty database has no base import
            writes.run_write(
                server.write_session_factory, lambda s: writes.preview_week(s, week, now=now)
            )
        assert exc.value.code == "no_base"
        with server.write_session_factory() as session:
            op = session.query(McpOperation).filter_by(status="refused").one()
            assert op.result["code"] == "no_base"
            session.query(McpOperation).delete()
            session.execute(text("DELETE FROM audit_log WHERE action = 'mcp.refuse'"))
    finally:
        for maker in server._write_sessionmakers.values():
            maker.kw["bind"].dispose()
        server._write_sessionmakers.clear()
