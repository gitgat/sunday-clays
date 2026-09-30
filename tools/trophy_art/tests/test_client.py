import hashlib
import json

import httpx
import pytest

from client import GenerationSpec, ImagenClient, ImagenError, ImagenUnreachable, Sampling, idempotency_key

BASE = "https://imagen.test"
SPEC = GenerationSpec(
    art_key="clays_broken", metal="gold", prompt="p", negative="n", model="z-image", seed=11, size=1024
)
OUTPUT = {
    "ordinal": 0,
    "asset_id": "a1",
    "thumb_url": "/api/assets/a1/thumb?w=320",
    "bytes_url": "/api/assets/a1/bytes",
}


MODELS = {
    "models": [
        {
            "key": "z-image",
            "capabilities": ["txt2img"],
            "defaults": {"sampler": "euler", "scheduler": "normal", "steps": 30, "cfg": 4.0, "width": 1024},
        },
        {"key": "bare", "defaults": {"steps": 20}},
    ]
}
DEFAULTS = Sampling(steps=30, cfg=4.0, sampler="euler", scheduler="normal")


@pytest.fixture(autouse=True)
def models_route(respx_mock):
    return respx_mock.get(f"{BASE}/api/models").mock(return_value=httpx.Response(200, json=MODELS))


def generation(state, outputs=()):
    return {"id": "gen-1", "state": state, "outputs": list(outputs)}


def test_idempotency_key_is_sha256_of_the_joined_fields():
    assert (
        idempotency_key("clays_broken", "gold", "p", "z-image", 11)
        == hashlib.sha256(b"clays_broken|gold|p|z-image|11").hexdigest()
    )
    assert (
        idempotency_key("doubleheader", None, "p", "z-image", 11, sampling=DEFAULTS)
        == hashlib.sha256(b"doubleheader||p|z-image|11|30|4.0|euler|normal").hexdigest()
    )


@pytest.mark.parametrize(
    "changed",
    [
        Sampling(31, 4.0, "euler", "normal"),
        Sampling(30, 4.5, "euler", "normal"),
        Sampling(30, 4.0, "dpmpp_2m", "normal"),
        Sampling(30, 4.0, "euler", "karras"),
    ],
)
def test_idempotency_key_changes_with_any_sampling_field(changed):
    args = ("clays_broken", "gold", "p", "z-image", 11)
    assert idempotency_key(*args, sampling=changed) != idempotency_key(*args, sampling=DEFAULTS)
    assert idempotency_key(*args, 1, DEFAULTS) != idempotency_key(*args, 0, DEFAULTS)


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_login_posts_credentials(respx_mock):
    route = respx_mock.post("/api/auth/login").mock(
        return_value=httpx.Response(200, json={"id": "u1", "username": "bryan", "is_admin": False})
    )
    ImagenClient(BASE).login("bryan", "secret")
    assert json.loads(route.calls.last.request.content) == {"username": "bryan", "password": "secret"}


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_login_session_cookie_rides_on_later_requests(respx_mock):
    respx_mock.post("/api/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={"id": "u1", "username": "bryan", "is_admin": False},
            headers={"Set-Cookie": "imagen_session=tok; Path=/; HttpOnly; SameSite=lax; Secure"},
        )
    )
    route = respx_mock.post("/api/generations").mock(return_value=httpx.Response(201, json=generation("queued")))
    client = ImagenClient(BASE)
    client.login("bryan", "secret")
    client.create(SPEC)
    assert route.calls.last.request.headers["Cookie"] == "imagen_session=tok"


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_create_needs_no_login(respx_mock):
    route = respx_mock.post("/api/generations").mock(return_value=httpx.Response(201, json=generation("queued")))
    assert ImagenClient(BASE).create(SPEC) == "gen-1"
    assert "Cookie" not in route.calls.last.request.headers


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_login_failure_raises(respx_mock):
    respx_mock.post("/api/auth/login").mock(return_value=httpx.Response(401))
    with pytest.raises(ImagenError, match="login failed: HTTP 401"):
        ImagenClient(BASE).login("bryan", "wrong")


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_create_sends_request_fields_and_idempotency_key(respx_mock):
    route = respx_mock.post("/api/generations").mock(return_value=httpx.Response(201, json=generation("queued")))
    assert ImagenClient(BASE).create(SPEC) == "gen-1"
    sent = route.calls.last.request
    assert (
        sent.headers["Idempotency-Key"]
        == hashlib.sha256(b"clays_broken|gold|p|z-image|11|30|4.0|euler|normal").hexdigest()
    )
    assert json.loads(sent.content) == {
        "request": {
            "capability": "txt2img",
            "model_key": "z-image",
            "prompt": "p",
            "negative_prompt": "n",
            "seed": "11",
            "width": 1024,
            "height": 1024,
            "batch": 1,
            "steps": 30,
            "cfg": 4.0,
            "sampler": "euler",
            "scheduler": "normal",
        },
        "title": "trophy clays_broken gold seed 11",
    }


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_replayed_create_returns_the_existing_generation(respx_mock):
    respx_mock.post("/api/generations").mock(return_value=httpx.Response(200, json=generation("completed")))
    assert ImagenClient(BASE).create(SPEC) == "gen-1"


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_create_rejection_raises(respx_mock):
    respx_mock.post("/api/generations").mock(return_value=httpx.Response(500))
    with pytest.raises(ImagenError, match=r"create failed: HTTP 500$"):
        ImagenClient(BASE).create(SPEC)


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_422_surfaces_the_validation_detail(respx_mock):
    detail = [{"type": "value_error", "msg": "txt2img requires steps, cfg, sampler, scheduler"}]
    respx_mock.post("/api/generations").mock(return_value=httpx.Response(422, json={"detail": detail}))
    with pytest.raises(ImagenError, match=r"HTTP 422: .*txt2img requires steps, cfg, sampler, scheduler"):
        ImagenClient(BASE).create(SPEC)


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_422_detail_is_truncated_and_non_json_bodies_are_tolerated(respx_mock):
    route = respx_mock.post("/api/generations")
    route.mock(return_value=httpx.Response(422, json={"detail": "x" * 1000}))
    with pytest.raises(ImagenError) as long:
        ImagenClient(BASE).create(SPEC)
    assert len(str(long.value)) < 350
    route.mock(return_value=httpx.Response(422, text="<html>nope</html>"))
    with pytest.raises(ImagenError, match=r"HTTP 422$"):
        ImagenClient(BASE).create(SPEC)
    route.mock(return_value=httpx.Response(422, json=["not", "a", "dict"]))
    with pytest.raises(ImagenError, match=r"HTTP 422$"):
        ImagenClient(BASE).create(SPEC)


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_manifest_overrides_win_over_model_defaults(respx_mock):
    route = respx_mock.post("/api/generations").mock(return_value=httpx.Response(201, json=generation("queued")))
    spec = GenerationSpec(
        "clays_broken", "gold", "p", "n", "z-image", 11, 512, steps=12, cfg=2.5, sampler="dpmpp_2m", scheduler="karras"
    )
    ImagenClient(BASE).create(spec)
    request = json.loads(route.calls.last.request.content)["request"]
    assert (request["steps"], request["cfg"], request["sampler"], request["scheduler"]) == (
        12,
        2.5,
        "dpmpp_2m",
        "karras",
    )
    assert request["width"] == request["height"] == 512
    key = route.calls.last.request.headers["Idempotency-Key"]
    assert key == idempotency_key(
        "clays_broken", "gold", "p", "z-image", 11, sampling=Sampling(12, 2.5, "dpmpp_2m", "karras")
    )


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_models_are_fetched_once_per_client(respx_mock, models_route):
    respx_mock.post("/api/generations").mock(return_value=httpx.Response(201, json=generation("queued")))
    client = ImagenClient(BASE)
    client.create(SPEC)
    client.create(SPEC)
    assert models_route.call_count == 1


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_unknown_model_is_a_clean_error(respx_mock):
    spec = GenerationSpec("a", None, "p", "n", "nope", 1, 64)
    with pytest.raises(ImagenError, match=r"no model 'nope' .*z-image"):
        ImagenClient(BASE).create(spec)


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_model_missing_a_default_is_a_clean_error(respx_mock):
    spec = GenerationSpec("a", None, "p", "n", "bare", 1, 64)
    with pytest.raises(ImagenError, match="'bare' has no default cfg"):
        ImagenClient(BASE).create(spec)


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_model_list_failure_is_a_clean_error(models_route):
    models_route.mock(return_value=httpx.Response(503))
    with pytest.raises(ImagenError, match="model list failed: HTTP 503"):
        ImagenClient(BASE).create(SPEC)


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_wait_polls_until_terminal(respx_mock):
    respx_mock.get("/api/generations/gen-1").mock(
        side_effect=[
            httpx.Response(200, json=generation("queued")),
            httpx.Response(200, json=generation("running")),
            httpx.Response(200, json=generation("completed", [OUTPUT])),
        ]
    )
    sleeps: list[float] = []
    assert ImagenClient(BASE, sleep=sleeps.append).wait("gen-1")["state"] == "completed"
    assert sleeps == [3.0, 3.0]


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_wait_times_out(respx_mock):
    respx_mock.get("/api/generations/gen-1").mock(return_value=httpx.Response(200, json=generation("running")))
    ticks = iter([0.0, 100.0, 1000.0])
    client = ImagenClient(BASE, sleep=lambda _: None, clock=lambda: next(ticks), timeout_seconds=900.0)
    with pytest.raises(ImagenError, match="timed out"):
        client.wait("gen-1")


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_poll_error_raises(respx_mock):
    respx_mock.get("/api/generations/gen-1").mock(return_value=httpx.Response(500))
    with pytest.raises(ImagenError, match="poll failed: HTTP 500"):
        ImagenClient(BASE).wait("gen-1")


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_downloads_the_first_output(respx_mock):
    respx_mock.post("/api/generations").mock(return_value=httpx.Response(201, json=generation("queued")))
    respx_mock.get("/api/generations/gen-1").mock(
        return_value=httpx.Response(200, json=generation("completed", [OUTPUT]))
    )
    respx_mock.get("/api/assets/a1/bytes").mock(return_value=httpx.Response(200, content=b"PNGDATA"))
    client = ImagenClient(BASE)
    assert client.generate(SPEC) == b"PNGDATA"
    client.close()


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_failed_generation_raises(respx_mock):
    respx_mock.get("/api/generations/gen-1").mock(return_value=httpx.Response(200, json=generation("failed")))
    client = ImagenClient(BASE)
    with pytest.raises(ImagenError, match="ended failed with 0 outputs"):
        client.download_first_output(client.wait("gen-1"))


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_download_error_raises(respx_mock):
    respx_mock.get("/api/assets/a1/bytes").mock(return_value=httpx.Response(404))
    with pytest.raises(ImagenError, match="download failed: HTTP 404"):
        ImagenClient(BASE).download_first_output(generation("completed", [OUTPUT]))


def test_idempotency_key_retry_suffix_changes_only_retries():
    base = idempotency_key("clays_broken", "gold", "p", "z-image", 11)
    assert idempotency_key("clays_broken", "gold", "p", "z-image", 11, 0) == base
    retry = idempotency_key("clays_broken", "gold", "p", "z-image", 11, 1)
    assert retry == hashlib.sha256(b"clays_broken|gold|p|z-image|11|retry1").hexdigest()
    with_sampling = idempotency_key("clays_broken", "gold", "p", "z-image", 11, 1, DEFAULTS)
    assert with_sampling == hashlib.sha256(b"clays_broken|gold|p|z-image|11|30|4.0|euler|normal|retry1").hexdigest()
    assert retry != base


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_create_conflict_has_a_clear_message(respx_mock):
    respx_mock.post("/api/generations").mock(return_value=httpx.Response(409))
    with pytest.raises(ImagenError, match="already submitted with a different request"):
        ImagenClient(BASE).create(SPEC)


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_transport_errors_become_imagen_unreachable(respx_mock):
    respx_mock.get("/api/generations/gen-1").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ImagenUnreachable, match="cannot reach imagen"):
        ImagenClient(BASE).wait("gen-1")
