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
