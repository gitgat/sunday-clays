"""Pure ASGI request-body size limit that runs before routing and auth (C2 Body size limit)."""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from sunday_clays.api.errors import error_body
from sunday_clays.config import get_settings

IMPORTS_PATH = "/api/admin/imports"
DEFAULT_LIMIT_BYTES = 262_144
UPLOAD_OVERHEAD_BYTES = 65_536
_BODY_413 = json.dumps(error_body("payload_too_large", "Request body is too large")).encode()


class _BodyTooLarge(Exception):
    """Raised inside the wrapped ``receive`` once the running byte count passes the limit."""


async def _send_413(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_BODY_413)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": _BODY_413})


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _limit_for(scope: Scope) -> int:
    if scope["method"] == "POST" and scope["path"].rstrip("/") == IMPORTS_PATH:
        return get_settings().max_upload_bytes + UPLOAD_OVERHEAD_BYTES  # read on first upload
    return DEFAULT_LIMIT_BYTES


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            await self.app(scope, receive, send)
            return
        limit = _limit_for(scope)
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            await _send_413(send)
            return

        received = 0
        exceeded = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if exceeded:
                return  # the app's own error response is replaced by the 413 below
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not response_started:
            await _send_413(send)
