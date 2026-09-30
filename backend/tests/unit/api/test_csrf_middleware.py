from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sunday_clays.api.csrf import CsrfGuardMiddleware

SITE = "sundayclays.claysmasher.com"


@pytest.fixture
def guarded() -> Iterator[TestClient]:
    app = FastAPI()

    @app.post("/api/echo")
    def echo_post() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/echo")
    def echo_get() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(CsrfGuardMiddleware)
    with TestClient(app) as test_client:  # lifespan scope also passes through the middleware
        yield test_client


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": SITE, "Origin": "https://shop.claysmasher.com"},
        {"Host": "localhost:8080", "Origin": "http://localhost:3000"},
        {"Host": SITE, "Origin": "null"},
        {"Host": SITE, "Origin": "not a url"},
        {"Host": SITE, "Origin": "http://[::1"},
        {"Host": SITE, "Sec-Fetch-Site": "same-site"},
        {"Host": SITE, "Sec-Fetch-Site": "cross-site"},
        {"Host": SITE, "Origin": f"https://{SITE}", "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_site_post_is_blocked(guarded: TestClient, headers: dict[str, str]) -> None:
    response = guarded.post("/api/echo", headers=headers)
    assert response.status_code == 403
    assert response.json() == {"error": {"code": "csrf", "message": "Cross-site request blocked"}}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Host": "localhost:8080", "Origin": "http://localhost:8080"},
        {"Host": SITE, "Origin": "https://SundayClays.ClaySmasher.com"},
        {"Host": SITE, "Origin": f"https://{SITE}", "Sec-Fetch-Site": "same-origin"},
        {"Host": SITE, "Sec-Fetch-Site": "none"},
    ],
)
def test_same_origin_or_headerless_post_passes(
    guarded: TestClient, headers: dict[str, str]
) -> None:
    assert guarded.post("/api/echo", headers=headers).status_code == 200


def test_get_with_foreign_origin_passes(guarded: TestClient) -> None:
    headers = {"Host": SITE, "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}
    assert guarded.get("/api/echo", headers=headers).status_code == 200


def test_delete_with_foreign_origin_is_blocked_before_routing(guarded: TestClient) -> None:
    headers = {"Host": SITE, "Origin": "https://evil.example"}
    assert guarded.delete("/api/echo", headers=headers).status_code == 403
