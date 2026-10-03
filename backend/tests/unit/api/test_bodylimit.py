import asyncio
import json
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest
import starlette.formparsers
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from sunday_clays.api import app as app_module
from sunday_clays.api.bodylimit import BodySizeLimitMiddleware

DEFAULT_LIMIT = 262_144
PAYLOAD_TOO_LARGE = {"error": {"code": "payload_too_large", "message": "Request body is too large"}}


class RecordingApp:
    """Inner ASGI app: reads the whole body, then answers 200 with the byte count."""

    def __init__(self) -> None:
        self.called = False
        self.bytes_seen = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.called = True
        if scope["type"] == "http":
            more = True
            while more:
                message = await receive()
                self.bytes_seen += len(message.get("body", b""))
                more = message.get("more_body", False)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": str(self.bytes_seen).encode()})


class SwallowingApp:
    """Inner app that turns any body-read error into its own 400, as FastAPI's parser does."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            while (await receive()).get("more_body", False):
                pass
        except Exception:
            await send({"type": "http.response.start", "status": 400, "headers": []})
            await send({"type": "http.response.body", "body": b"parse error"})


class FailingApp:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise RuntimeError("unrelated failure")


def http_scope(path: str, *, method: str = "POST", content_length: str | None = None) -> Scope:
    headers = [] if content_length is None else [(b"content-length", content_length.encode())]
    return {"type": "http", "method": method, "path": path, "headers": headers}


def drive(app: Any, scope: Scope, chunks: list[bytes]) -> list[Message]:
    pending = list(chunks)
    sent: list[Message] = []

    async def receive() -> Message:
        body = pending.pop(0) if pending else b""
        return {"type": "http.request", "body": body, "more_body": bool(pending)}

    async def send(message: Message) -> None:
        sent.append(message)

    asyncio.run(BodySizeLimitMiddleware(app)(scope, receive, send))
    return sent


def status_of(sent: list[Message]) -> int:
    return int(next(m["status"] for m in sent if m["type"] == "http.response.start"))


def body_of(sent: list[Message]) -> Any:
    return json.loads(
        b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    )


def test_declared_length_over_limit_is_rejected_before_the_app_runs() -> None:
    inner = RecordingApp()

    sent = drive(inner, http_scope("/api/auth/login", content_length=str(DEFAULT_LIMIT + 1)), [])

    assert status_of(sent) == 413
    assert body_of(sent) == PAYLOAD_TOO_LARGE
    assert inner.called is False


def test_body_exactly_at_the_limit_is_accepted() -> None:
    inner = RecordingApp()

    sent = drive(
        inner,
        http_scope("/api/auth/login", content_length=str(DEFAULT_LIMIT)),
        [b"x" * DEFAULT_LIMIT],
    )

    assert status_of(sent) == 200
    assert inner.bytes_seen == DEFAULT_LIMIT


def test_chunked_body_is_cut_off_as_soon_as_it_passes_the_limit() -> None:
    inner = RecordingApp()

    sent = drive(inner, http_scope("/api/auth/login"), [b"x" * 100_000] * 4)

    assert status_of(sent) == 413
    assert body_of(sent) == PAYLOAD_TOO_LARGE
    assert inner.bytes_seen <= DEFAULT_LIMIT


def test_malformed_content_length_falls_back_to_counting() -> None:
    inner = RecordingApp()

    sent = drive(inner, http_scope("/api/x", content_length="lots"), [b"x" * 200_000] * 2)

    assert status_of(sent) == 413


def test_app_error_response_after_the_cutoff_is_replaced_by_413() -> None:
    sent = drive(SwallowingApp(), http_scope("/api/x"), [b"x" * 200_000] * 2)

    assert [m["status"] for m in sent if m["type"] == "http.response.start"] == [413]


def test_disconnect_messages_pass_through_to_the_app() -> None:
    inner = RecordingApp()
    messages: list[Message] = [
        {"type": "http.request", "body": b"part", "more_body": True},
        {"type": "http.disconnect"},
    ]
    sent: list[Message] = []

    async def receive() -> Message:
        return messages.pop(0)

    async def send(message: Message) -> None:
        sent.append(message)

    asyncio.run(BodySizeLimitMiddleware(inner)(http_scope("/api/x"), receive, send))

    assert status_of(sent) == 200
    assert inner.bytes_seen == 4


def test_errors_unrelated_to_the_limit_propagate() -> None:
    with pytest.raises(RuntimeError, match="unrelated failure"):
        drive(FailingApp(), http_scope("/api/x"), [b"small"])


def test_non_api_paths_are_not_limited() -> None:
    inner = RecordingApp()

    sent = drive(inner, http_scope("/assets/app.js", content_length="999999999"), [b"ok"])

    assert status_of(sent) == 200


def test_non_http_scopes_pass_through() -> None:
    inner = RecordingApp()

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None:
        return None

    asyncio.run(BodySizeLimitMiddleware(inner)({"type": "lifespan"}, receive, send))

    assert inner.called is True


def test_imports_upload_limit_is_max_upload_bytes_plus_overhead(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1000")
    limit = 1000 + 65_536

    over = drive(
        RecordingApp(), http_scope("/api/admin/imports", content_length=str(limit + 1)), []
    )
    at_limit = drive(
        RecordingApp(),
        http_scope("/api/admin/imports/", content_length=str(limit)),
        [b"x" * limit],
    )
    listing = drive(
        RecordingApp(),
        http_scope("/api/admin/imports", method="GET", content_length=str(DEFAULT_LIMIT + 1)),
        [],
    )

    assert status_of(over) == 413
    assert status_of(at_limit) == 200
    assert status_of(listing) == 413


class RecordingSpool(tempfile.SpooledTemporaryFile[bytes]):
    """Counts multipart spool files created by Starlette and any rollover to disk."""

    created: ClassVar[int] = 0
    rolled_to_disk: ClassVar[int] = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        type(self).created += 1
        super().__init__(*args, **kwargs)

    def rollover(self) -> None:
        type(self).rolled_to_disk += 1
        super().rollover()


@dataclass
class UploadProbe:
    client: TestClient
    route_calls: list[str]


@pytest.fixture
def upload_probe(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[UploadProbe]:
    """create_app() plus a probe upload route at the imports path; MAX_UPLOAD_BYTES=1000.

    Router discovery is emptied, so once Plan 04 T2 adds the real (admin-only)
    POST /api/admin/imports route it cannot shadow the probe. The middleware stack that
    create_app() installs stays under test.
    """
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1000")
    RecordingSpool.created = 0
    RecordingSpool.rolled_to_disk = 0
    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", RecordingSpool)
    monkeypatch.setattr(app_module, "discover_routers", lambda: [])
    route_calls: list[str] = []
    app = app_module.create_app(page_cache_allowlist=())

    @app.post("/api/admin/imports")
    async def upload(file: UploadFile) -> dict[str, int]:
        route_calls.append(file.filename or "")
        return {"size": len(await file.read())}

    with TestClient(app) as client:
        yield UploadProbe(client=client, route_calls=route_calls)


def multipart_body(boundary: str, size: int) -> bytes:
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="big.xlsx"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    return head + b"x" * size + f"\r\n--{boundary}--\r\n".encode()


def test_oversized_upload_with_content_length_never_reaches_the_parser(
    upload_probe: UploadProbe,
) -> None:
    response = upload_probe.client.post(
        "/api/admin/imports", files={"file": ("big.xlsx", b"x" * 70_000, "application/xlsx")}
    )

    assert response.status_code == 413
    assert response.json() == PAYLOAD_TOO_LARGE
    assert upload_probe.route_calls == []
    assert RecordingSpool.created == 0


def test_oversized_chunked_upload_is_rejected_without_touching_disk(
    upload_probe: UploadProbe,
) -> None:
    body = multipart_body("sc-boundary", 200_000)

    def chunks() -> Iterator[bytes]:
        for start in range(0, len(body), 16_384):
            yield body[start : start + 16_384]

    response = upload_probe.client.post(
        "/api/admin/imports",
        content=chunks(),
        headers={"content-type": "multipart/form-data; boundary=sc-boundary"},
    )

    assert response.status_code == 413
    assert response.json() == PAYLOAD_TOO_LARGE
    assert upload_probe.route_calls == []
    assert RecordingSpool.rolled_to_disk == 0


def test_upload_within_the_limit_reaches_the_route(upload_probe: UploadProbe) -> None:
    response = upload_probe.client.post(
        "/api/admin/imports", files={"file": ("ok.xlsx", b"x" * 500, "application/xlsx")}
    )

    assert response.json() == {"size": 500}
    assert upload_probe.route_calls == ["ok.xlsx"]
