"""Client for the local OpenAI-compatible VLM server, with an on-disk response cache."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

DEFAULT_URL = "http://127.0.0.1:8888/v1/chat/completions"
DEFAULT_MODEL = "unsloth/gemma-4-26B-A4B-it-GGUF"
MAX_TOKENS = 800
TIMEOUT_SECONDS = 300.0


class VlmError(Exception):
    """One request failed (bad status, unreadable body); the block is flagged and the run goes on."""


class VlmUnreachable(VlmError):
    """The server cannot be reached at all; nothing else will work, so the run stops."""


def image_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def extract_json(text: str) -> dict[str, Any] | None:
    """The first JSON object in a model reply, tolerating ``` fences and <think> blocks."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"```(?:json)?", "", text)
    match = re.search(r"\{.*\}", text, re.S)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def cache_key(png: bytes, prompt: str, model: str, temperature: float, attempt: int) -> str:
    digest = hashlib.sha256()
    for part in (png, prompt.encode(), model.encode(), repr(temperature).encode(), str(attempt).encode()):
        digest.update(part)
        digest.update(b"|")
    return digest.hexdigest()


class VlmClient:
    def __init__(self, cache_dir: Path, *, http: httpx.Client | None = None, offline: bool = False) -> None:
        self.url = os.environ.get("VLM_URL") or DEFAULT_URL
        self.model = os.environ.get("VLM_MODEL") or DEFAULT_MODEL
        self.api_key = os.environ.get("VLM_API_KEY") or ""
        self.cache_dir = cache_dir
        self.offline = offline  # answer from the cache only: never open a connection to the server
        self.http = http or (None if offline else httpx.Client(timeout=TIMEOUT_SECONDS))

    def ask(self, image: Image.Image, prompt: str, temperature: float, attempt: int = 0) -> str:
        """The model's raw reply. A cached reply is returned without calling the server."""
        png = image_png(image)
        path = self.cache_dir / f"{cache_key(png, prompt, self.model, temperature, attempt)}.json"
        try:
            return str(json.loads(path.read_text())["content"])
        except (OSError, ValueError, KeyError, TypeError):
            pass  # no entry, or an unreadable one (a run stopped mid-write): ask the server again
        if self.offline:
            raise VlmError("no cached reply (offline: the server is not called)")
        content = self._post(png, prompt, temperature)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        partial.write_text(json.dumps({"content": content}))
        partial.replace(path)
        return content

    def _post(self, png: bytes, prompt: str, temperature: float) -> str:
        body = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": MAX_TOKENS,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        assert self.http is not None  # only an offline client has none, and it never gets here
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            response = self.http.post(self.url, json=body, headers=headers)
        except httpx.ConnectTimeout as exc:  # never got a connection: the server is not there
            raise VlmUnreachable(f"cannot reach the model server at {self.url}: {exc!r}") from exc
        except httpx.TimeoutException as exc:
            raise VlmError(f"the model took too long to reply: {exc!r}") from exc
        except httpx.TransportError as exc:
            raise VlmUnreachable(f"cannot reach the model server at {self.url}: {exc}") from exc
        if response.status_code != 200:
            raise VlmError(f"model server answered {response.status_code}")
        try:
            return str(response.json()["choices"][0]["message"].get("content") or "")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise VlmError("model server sent an unexpected reply") from exc

    def close(self) -> None:
        if self.http is not None:
            self.http.close()
