"""Request-body cap for the MCP app: the largest legitimate call is a 200-shooter week."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 1024 * 1024
_TOO_LARGE_BODY = b'{"error":"too_large"}'


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
            if name == b"content-length" and value.isdigit() and int(value) > self._max:
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
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_TOO_LARGE_BODY)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _TOO_LARGE_BODY})
