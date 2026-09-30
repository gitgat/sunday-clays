import json

import httpx
import pytest
import respx
from PIL import Image

import vlm

URL = "http://vlm.test/v1/chat/completions"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("VLM_URL", URL)
    monkeypatch.setenv("VLM_API_KEY", "k")
    monkeypatch.delenv("VLM_MODEL", raising=False)


def reply(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def image(color="white"):
    return Image.new("RGB", (8, 8), color)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('<think>{"a": 2}</think>sure: {"a": 1} done', {"a": 1}),
        ("no json", None),
        ("{broken", None),
        ("{not: json}", None),
        ("[1, 2]", None),
    ],
)
def test_extract_json(text, expected):
    assert vlm.extract_json(text) == expected


def test_cache_key_depends_on_every_part():
    base = vlm.cache_key(b"img", "p", "m", 0.2, 0)
    assert base == vlm.cache_key(b"img", "p", "m", 0.2, 0)
    for other in (
        vlm.cache_key(b"img2", "p", "m", 0.2, 0),
        vlm.cache_key(b"img", "p2", "m", 0.2, 0),
        vlm.cache_key(b"img", "p", "m2", 0.2, 0),
        vlm.cache_key(b"img", "p", "m", 0.8, 0),
        vlm.cache_key(b"img", "p", "m", 0.2, 1),
    ):
        assert other != base


@respx.mock
def test_request_shape_and_cache_hit_and_miss(tmp_path):
    route = respx.post(URL).mock(return_value=reply('{"x": 1}'))
    client = vlm.VlmClient(tmp_path)
    assert client.ask(image(), "prompt", 0.2) == '{"x": 1}'
    body = json.loads(route.calls.last.request.content)
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["temperature"] == 0.2
    assert body["model"] == vlm.DEFAULT_MODEL
    assert body["max_tokens"] <= 800
    assert route.calls.last.request.headers["authorization"] == "Bearer k"
    assert body["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")
    # Same inputs: served from disk. A different attempt or image: a new request.
    assert client.ask(image(), "prompt", 0.2) == '{"x": 1}'
    assert route.call_count == 1
    client.ask(image(), "prompt", 0.2, attempt=1)
    client.ask(image("black"), "prompt", 0.2)
    assert route.call_count == 3
    # A fresh client over the same folder is resumed for free.
    vlm.VlmClient(tmp_path).ask(image(), "prompt", 0.2)
    assert route.call_count == 3
    client.close()


@respx.mock
def test_defaults_without_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VLM_URL")
    monkeypatch.delenv("VLM_API_KEY")
    monkeypatch.setenv("VLM_MODEL", "other-model")
    route = respx.post(vlm.DEFAULT_URL).mock(return_value=reply(""))
    client = vlm.VlmClient(tmp_path)
    assert client.ask(image(), "p", 0.1) == ""
    assert "authorization" not in route.calls.last.request.headers
    assert json.loads(route.calls.last.request.content)["model"] == "other-model"


@respx.mock
def test_unreachable_server(tmp_path):
    respx.post(URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(vlm.VlmUnreachable, match="cannot reach"):
        vlm.VlmClient(tmp_path).ask(image(), "p", 0.2)


@respx.mock
def test_bad_status_and_bad_body_are_not_cached(tmp_path):
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, json={"oops": 1}),
            httpx.Response(200, text="x"),
            reply("ok"),
        ]
    )
    client = vlm.VlmClient(tmp_path)
    with pytest.raises(vlm.VlmError, match="500"):
        client.ask(image(), "p", 0.2)
    with pytest.raises(vlm.VlmError, match="unexpected"):
        client.ask(image(), "p", 0.2)
    with pytest.raises(vlm.VlmError, match="unexpected"):
        client.ask(image(), "p", 0.2)
    assert client.ask(image(), "p", 0.2) == "ok"
    assert route.call_count == 4


@respx.mock
def test_a_slow_reply_flags_the_block_but_does_not_stop_the_run(tmp_path):
    respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(vlm.VlmError, match="too long") as caught:
        vlm.VlmClient(tmp_path).ask(image(), "p", 0.2)
    assert not isinstance(caught.value, vlm.VlmUnreachable)


@respx.mock
def test_a_truncated_cache_entry_is_a_miss_and_is_rewritten(tmp_path):
    route = respx.post(URL).mock(return_value=reply("fresh"))
    client = vlm.VlmClient(tmp_path)
    client.ask(image(), "p", 0.2)
    (entry,) = tmp_path.glob("*.json")
    entry.write_text('{"content": "tru')
    assert client.ask(image(), "p", 0.2) == "fresh"
    assert route.call_count == 2
    assert json.loads(entry.read_text()) == {"content": "fresh"}
    assert not list(tmp_path.glob("*.tmp"))


@respx.mock
def test_a_connect_timeout_means_the_server_is_unreachable(tmp_path):
    respx.post(URL).mock(side_effect=httpx.ConnectTimeout("no route"))
    with pytest.raises(vlm.VlmUnreachable, match="cannot reach"):
        vlm.VlmClient(tmp_path).ask(image(), "p", 0.2)
