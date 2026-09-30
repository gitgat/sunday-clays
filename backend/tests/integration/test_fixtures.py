from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.types import Message, Receive, Scope, Send

from sunday_clays.config import get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import DomainError


def test_client_keeps_good_writes_and_rolls_back_write_then_raise(
    client: TestClient, session: Session
) -> None:
    session.execute(text("CREATE TABLE fixture_probe (v int NOT NULL)"))
    app = client.app
    assert isinstance(app, FastAPI)

    @app.post("/api/_probe/ok")
    def ok(db: SessionDep) -> None:
        db.execute(text("INSERT INTO fixture_probe VALUES (1)"))

    @app.post("/api/_probe/fail")
    def fail(db: SessionDep) -> None:
        db.execute(text("INSERT INTO fixture_probe VALUES (2)"))
        raise DomainError("rejected", "write then raise")

    assert client.post("/api/_probe/ok").status_code == 200
    assert client.post("/api/_probe/fail").status_code == 400

    assert list(session.execute(text("SELECT v FROM fixture_probe")).scalars()) == [1]


def test_client_runs_with_insecure_cookies(client: TestClient) -> None:
    assert get_settings().cookie_secure is False


def test_client_keeps_a_write_committed_before_raising(
    client: TestClient, session: Session
) -> None:
    session.execute(text("CREATE TABLE fixture_probe (v int NOT NULL)"))
    app = client.app
    assert isinstance(app, FastAPI)

    @app.post("/api/_probe/commit-then-fail")
    def commit_then_fail(db: SessionDep) -> None:
        db.execute(text("INSERT INTO fixture_probe VALUES (3)"))
        db.commit()
        raise DomainError("rejected", "persisted first")

    assert client.post("/api/_probe/commit-then-fail").status_code == 400

    assert list(session.execute(text("SELECT v FROM fixture_probe")).scalars()) == [3]


def test_client_override_commits_before_the_response_starts(
    client: TestClient, session: Session
) -> None:
    """The override inherits SessionDep's function scope, like the real get_session."""
    session.execute(text("CREATE TABLE fixture_probe (v int NOT NULL)"))
    app = client.app
    assert isinstance(app, FastAPI)
    savepoint_open_at_response_start: list[bool] = []

    @app.post("/api/_probe/write")
    def write(db: SessionDep) -> None:
        db.execute(text("INSERT INTO fixture_probe VALUES (4)"))

    async def recording_app(scope: Scope, receive: Receive, send: Send) -> None:
        async def recording_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                savepoint_open_at_response_start.append(session.in_nested_transaction())
            await send(message)

        await app(scope, receive, recording_send)

    assert TestClient(recording_app).post("/api/_probe/write").status_code == 200

    assert savepoint_open_at_response_start == [False]
    assert list(session.execute(text("SELECT v FROM fixture_probe")).scalars()) == [4]
