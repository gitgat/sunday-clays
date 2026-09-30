"""Suite-wide network guard: no test may open a socket. respx intercepts httpx before it reaches one, so
any request a test forgot to mock fails here as a ConnectError instead of reaching imagen."""

import socket
from typing import Any, NoReturn

import pytest


def _blocked(*_args: Any, **_kwargs: Any) -> NoReturn:
    raise OSError("network blocked by tools/trophy_art tests/conftest.py")


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
