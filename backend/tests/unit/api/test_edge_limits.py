"""Oversized bodies get the API's `payload_too_large` JSON whether the API or Caddy answers.

Caddy reads `max_size` with SI or IEC units (256KB = 256,000 bytes, 256KiB = 262,144). Its limits
sit just above the API's, so a body the API accepts is never cut off at the edge, and a limit far
above the API's would stop protecting it. A body that declares a `Content-Length` over the edge
limit is refused by Caddy before it proxies anything: forwarded, the API's early 413 would race
Caddy's own cutoff, and Caddy could drop the connection mid-reply with no response at all.
`request_body` stays as the backstop for a chunked body, which declares no length. Caddy's own
413 carries the API's envelope and Cache-Control.
"""

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.types import Receive, Scope, Send

from sunday_clays.api.bodylimit import (
    DEFAULT_LIMIT_BYTES,
    IMPORTS_PATH,
    UPLOAD_OVERHEAD_BYTES,
    BodySizeLimitMiddleware,
)
from sunday_clays.api.etag import cache_control_for
from sunday_clays.config import Settings

CADDYFILE = Path(__file__).resolve().parents[4] / "deploy" / "caddy" / "Caddyfile"
UNITS = {"B": 1, "KB": 1000, "KiB": 1024, "MB": 1000**2, "MiB": 1024**2}
# A top-level `handle <path> { ... }` of the site block (tab-indented, as `caddy fmt` writes it).
HANDLE_BLOCK = re.compile(r"^\thandle (\S+) \{\n(.*?)^\t\}$", re.MULTILINE | re.DOTALL)
BODY_LIMIT = re.compile(r"request_body \{\s+max_size (\d+)([A-Za-z]+)\s+\}")
LENGTH_GUARD = re.compile(
    r"@(\w+) expression `\{http\.request\.header\.Content-Length\} != \"\" "
    r"&& int\(\{http\.request\.header\.Content-Length\}\) > (\d+)`\s+error @\1 413\s"
)
CADDY_413 = re.compile(
    r"handle_errors 413 \{\s+import security_headers\s+"
    r"header Content-Type application/json\s+"
    r"(?:header Cache-Control (?P<cache_control>\S+)\s+)?"
    r"respond `(?P<body>\{.*?\})` 413\s+\}"
)


def handle_blocks() -> dict[str, str]:
    """The body of each `handle <path>` block in the Caddyfile, by path."""
    return dict(HANDLE_BLOCK.findall(CADDYFILE.read_text()))


def caddy_limits() -> dict[str, int]:
    """Bytes allowed by the `request_body` of each `handle <path>` block in the Caddyfile."""
    return {
        path: int(limit.group(1)) * UNITS[limit.group(2)]
        for path, block in handle_blocks().items()
        if (limit := BODY_LIMIT.search(block))
    }


def test_caddy_limits_sit_just_above_the_api_limits() -> None:
    upload_limit = Settings.model_fields["max_upload_bytes"].default + UPLOAD_OVERHEAD_BYTES
    limits = caddy_limits()

    assert set(limits) == {IMPORTS_PATH, "/api/*"}
    assert DEFAULT_LIMIT_BYTES < limits["/api/*"] <= DEFAULT_LIMIT_BYTES * 1.1
    assert upload_limit < limits[IMPORTS_PATH] <= upload_limit * 1.1


def test_a_declared_length_over_the_edge_limit_is_refused_before_proxying() -> None:
    guards = {
        path: int(guard.group(2))
        for path, block in handle_blocks().items()
        if (guard := LENGTH_GUARD.search(block))
    }

    assert guards == caddy_limits(), (
        "every `handle` with a `request_body` limit must refuse a larger Content-Length itself"
    )


async def never_runs(scope: Scope, receive: Receive, send: Send) -> None:
    raise AssertionError("the body limit answers before the app runs")


def test_caddys_own_413_answers_exactly_what_the_api_answers() -> None:
    api = TestClient(BodySizeLimitMiddleware(never_runs)).post(
        "/api/auth/login", content=b"x" * (DEFAULT_LIMIT_BYTES + 1)
    )
    caddy = CADDY_413.search(CADDYFILE.read_text())

    assert api.status_code == 413
    assert caddy is not None, "no `handle_errors 413` answering JSON in the Caddyfile"
    assert json.loads(caddy.group("body")) == api.json()
    # Every route that takes a body is under /api/auth/ or /api/admin/: the API sends no-store.
    assert caddy.group("cache_control") == cache_control_for("/api/auth/login")
    assert caddy.group("cache_control") == cache_control_for(IMPORTS_PATH)
