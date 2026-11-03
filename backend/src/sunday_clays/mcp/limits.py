"""Request-body cap for the MCP app: the largest legitimate call is a 200-shooter week."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 1024 * 1024
_TOO_LARGE_BODY = b'{"error":"too_large"}'
_BAD_REQUEST_BODY = b'{"error":"bad_request"}'
_MAX_DIGITS = 15


class BodyLimitMiddleware:
    """Pure ASGI: 413 when Content-Length, or the bytes actually streamed, exceed the cap."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self._max = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope["headers"]:
            if name != b"content-length":
                continue
            text = value.strip()
            if not text.isdigit() or not text.isascii():
                await self._reject(send, 400, _BAD_REQUEST_BODY)
                return
            # A very long digit string is over the cap by definition (and int() would raise).
            if len(text) > _MAX_DIGITS or int(text) > self._max:
                await self._reject(send)
                return
        seen = 0
        rejected = False

        async def counting_receive() -> Message:
            nonlocal seen, rejected
            message = await receive()
            if message["type"] == "http.request" and not rejected:
                seen += len(message.get("body", b""))
                if seen > self._max:
                    rejected = True
                    await self._reject(send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not rejected:  # once we have answered 413 the app's own reply is dropped
                await send(message)

        await self.app(scope, counting_receive, guarded_send)

    @staticmethod
    async def _reject(send: Send, status: int = 413, body: bytes = _TOO_LARGE_BODY) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
