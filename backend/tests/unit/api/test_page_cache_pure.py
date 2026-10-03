"""Page-cache key, storability and bypass rules (Plan 19 D29, D32; §5.1)."""

import pytest

from sunday_clays.api import page_cache as pc

BASE = (
    "1.4.0",
    412,
    "2026-10-02",
    "viewer",
    "/api/shooters/3",
    "as_of=2026-09-27&since=2026-08-03",
)


def test_the_same_request_gives_the_same_key_and_the_key_shape() -> None:
    assert pc.cache_key(*BASE) == pc.cache_key(*BASE)
    assert pc.cache_key(*BASE) == (
        "v1|1.4.0|412|2026-10-02|viewer|GET /api/shooters/3?as_of=2026-09-27&since=2026-08-03"
    )


@pytest.mark.parametrize("index", range(6))
def test_every_input_changes_the_key(index: int) -> None:
    changed = list(BASE)
    changed[index] = f"{changed[index]}x" if isinstance(changed[index], str) else 413
    assert pc.cache_key(*changed) != pc.cache_key(*BASE)  # type: ignore[arg-type]


def test_query_order_does_not_change_the_key() -> None:
    from starlette.requests import Request

    def query(raw: str) -> str:
        scope = {"type": "http", "query_string": raw.encode(), "headers": []}
        return pc.sorted_query(Request(scope))

    assert query("since=1&as_of=2") == query("as_of=2&since=1")


@pytest.mark.parametrize(
    ("status", "content_type", "cookie", "size", "ok"),
    [
        (200, "application/json", False, 10, True),
        (200, "application/json", False, pc.MAX_BODY_BYTES, True),
        (200, "application/json", False, pc.MAX_BODY_BYTES + 1, False),
        (200, "text/html; charset=utf-8", False, 10, False),
        (200, "application/json", True, 10, False),
        *[
            (s, "application/json", False, 10, False)
            for s in (201, 204, 304, 400, 401, 403, 404, 409, 422, 500)
        ],
    ],
)
def test_storable(status: int, content_type: str, cookie: bool, size: int, ok: bool) -> None:
    assert pc.storable(status, content_type, cookie, size) is ok


def test_undeclared_parameters_and_long_urls_bypass() -> None:
    route = pc.CachedRoute("/api/events", pc.compile_template("/api/events"), frozenset({"year"}))
    assert pc.bypass_reason(route, "/api/events", [("year", "2026")]) is None
    assert pc.bypass_reason(route, "/api/events", [("_", "1")]) == "undeclared"
    long_value = "x" * pc.MAX_KEY_URL
    assert pc.bypass_reason(route, "/api/events", [("year", long_value)]) == "too_long"


def test_a_route_an_allowlisted_template_would_swallow_fails_startup() -> None:
    """A fixed GET route that an allowlisted regex matches would be served and stored under the
    wrong template (match_route is first-match). At the plan's base no route does (checked over
    all 60 GET routes)."""
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/api/shooters/compare")
    def compare() -> dict[str, str]:
        return {}

    @app.get("/api/shooters/{id}")
    def shooter(id: int) -> dict[str, int]:
        return {"id": id}

    with pytest.raises(ValueError, match="GET /api/shooters/compare also matches /api/shooters/"):
        pc.resolve_allowlist(app, ("/api/shooters/{id}",))
    assert [r.template for r in pc.resolve_allowlist(app, ())] == []
