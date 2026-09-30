"""Suite-wide network guard: no test may open a socket, so nothing can reach the real model server."""

import socket
from typing import Any, NoReturn

import pytest


def _blocked(*_args: Any, **_kwargs: Any) -> NoReturn:
    raise OSError("network blocked by tools/scoresheets tests/conftest.py")


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
