"""Input validation edges and the websocket refusal."""

import asyncio

import pytest
from pydantic import ValidationError

from sunday_clays.mcp.auth import BearerMiddleware
from sunday_clays.mcp.schemas import FindShootersInput, GetJobInput


@pytest.mark.parametrize("query", [" ", ",", " , "])
def test_blank_queries_are_rejected(query: str) -> None:
    with pytest.raises(ValidationError, match="non-blank"):
        FindShootersInput(query=query)


def test_job_id_is_bounded_to_a_postgres_integer() -> None:
    assert GetJobInput(id=2**31 - 1).id == 2**31 - 1
    with pytest.raises(ValidationError):
        GetJobInput(id=2**31)


def test_unauthorized_websocket_is_closed_with_policy_violation() -> None:
    sent: list[dict[str, object]] = []

    async def app(scope: object, receive: object, send: object) -> None:
        raise AssertionError("must not reach the app")

    async def receive() -> dict[str, object]:
        return {}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    gate = BearerMiddleware(app, "secret")  # type: ignore[arg-type]
    scope = {"type": "websocket", "path": "/mcp", "headers": []}
    asyncio.run(gate(scope, receive, send))  # type: ignore[arg-type]

    assert sent == [{"type": "websocket.close", "code": 1008}]
