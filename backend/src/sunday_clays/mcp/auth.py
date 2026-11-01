"""Bearer-token gate for the MCP app. The gateway sends one shared upstream token."""

import hmac
import os

from starlette.types import ASGIApp, Receive, Scope, Send

from sunday_clays.config import ConfigError, read_secret_env

OPEN_PATHS = frozenset({"/healthz"})
_UNAUTHORIZED_BODY = b'{"error":"unauthorized"}'


def load_auth_token() -> str | None:
    """The shared bearer token, or None only when ``MCP_AUTH_DISABLED=1`` (tests and dev)."""
    if os.environ.get("MCP_AUTH_DISABLED") == "1":
        return None
    token = read_secret_env("MCP_AUTH_TOKEN")
    if not token or not token.strip():
        raise ConfigError(
            "Set MCP_AUTH_TOKEN or MCP_AUTH_TOKEN_FILE (or MCP_AUTH_DISABLED=1 for dev)"
        )
    return token.strip()


class BearerMiddleware:
    """Pure ASGI: 401 unless ``Authorization: Bearer <token>`` matches (constant time)."""

    def __init__(self, app: ASGIApp, token: str | None) -> None:
        self.app = app
        self._token = None if token is None else token.encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._token is None or scope["path"] in OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        if self._authorized(scope, self._token):
            await self.app(scope, receive, send)
            return
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_UNAUTHORIZED_BODY)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _UNAUTHORIZED_BODY})

    @staticmethod
    def _authorized(scope: Scope, token: bytes) -> bool:
        for name, value in scope["headers"]:
            if name == b"authorization":
                scheme, _, supplied = value.partition(b" ")
                if scheme.lower() != b"bearer":
                    return False
                return hmac.compare_digest(supplied.strip(), token)
        return False
