"""Minimal imagen client (dev-only; the app and CI never call imagen).

Fields follow ../imagen/src/imagen/api/schemas.py: POST /api/generations takes
GenerationCreateIn{request: RequestIn, title} with an Idempotency-Key header, and seeds travel as
strings (imagen hazard H15). GET /api/generations/{id} is polled until a terminal state, then the
first output's bytes_url is downloaded. Login is optional: an imagen with no login-capable account
serves anonymous callers, and POST /api/auth/login's session cookie rides on every later call.

Retries: the idempotency key is deterministic, so rerunning `generate` replays a failed or canceled
generation instead of rendering again. `attempt` > 0 (CLI: `generate --retry N`) appends `|retryN` to the
key, which makes imagen create a fresh generation; attempt 0 is exactly C12's key."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

TERMINAL_STATES = frozenset({"completed", "failed", "canceled"})


class ImagenError(RuntimeError):
    """A login, create, poll or download that did not succeed."""


class ImagenUnreachable(ImagenError):
    """A transport failure (connection refused, timeout, ...): retrying other seeds would fail the same way."""


@dataclass(frozen=True)
class Sampling:
    """The four sampler fields imagen requires on every txt2img create."""

    steps: int
    cfg: float
    sampler: str
    scheduler: str


def idempotency_key(
    art_key: str,
    metal: str | None,
    prompt: str,
    model: str,
    seed: int,
    attempt: int = 0,
    sampling: Sampling | None = None,
) -> str:
    """sha256 of the joined fields; the sampling fields are folded in so a changed request never replays an old key."""
    tail = "" if sampling is None else f"|{sampling.steps}|{sampling.cfg}|{sampling.sampler}|{sampling.scheduler}"
    suffix = f"|retry{attempt}" if attempt else ""
    return hashlib.sha256(f"{art_key}|{metal or ''}|{prompt}|{model}|{seed}{tail}{suffix}".encode()).hexdigest()


@dataclass(frozen=True)
class GenerationSpec:
    art_key: str
    metal: str | None
    prompt: str
    negative: str
    model: str
    seed: int
    size: int
    attempt: int = 0
    steps: int | None = None
    cfg: float | None = None
    sampler: str | None = None
    scheduler: str | None = None


class ImagenClient:
    def __init__(
        self,
        base_url: str,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        poll_seconds: float = 3.0,
        timeout_seconds: float = 900.0,
    ) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=60.0)
        self._sleep = sleep
        self._clock = clock
        self._poll_seconds = poll_seconds
        self._model_defaults: dict[str, dict[str, Any]] | None = None
        self._timeout_seconds = timeout_seconds

    def close(self) -> None:
        self._http.close()

    def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise ImagenUnreachable(f"cannot reach imagen ({method} {url}): {exc!r}") from exc

    def login(self, username: str, password: str) -> None:
        response = self._send("POST", "/api/auth/login", json={"username": username, "password": password})
        if response.status_code != 200:
            raise ImagenError(f"login failed: HTTP {response.status_code}")

    def _models(self) -> dict[str, dict[str, Any]]:
        if self._model_defaults is None:
            response = self._send("GET", "/api/models")
            if response.status_code != 200:
                raise ImagenError(f"model list failed: HTTP {response.status_code}")
            self._model_defaults = {
                str(m["key"]): dict(m.get("defaults") or {}) for m in response.json().get("models", [])
            }
        return self._model_defaults

    def sampling_for(self, spec: GenerationSpec) -> Sampling:
        """Manifest overrides win over the model's own defaults from GET /api/models (fetched once)."""
        models = self._models()
        if spec.model not in models:
            raise ImagenError(f"imagen has no model {spec.model!r} (known: {', '.join(sorted(models)) or 'none'})")
        d = models[spec.model]
        try:
            return Sampling(
                steps=int(spec.steps if spec.steps is not None else d["steps"]),
                cfg=float(spec.cfg if spec.cfg is not None else d["cfg"]),
                sampler=str(spec.sampler if spec.sampler is not None else d["sampler"]),
                scheduler=str(spec.scheduler if spec.scheduler is not None else d["scheduler"]),
            )
        except KeyError as exc:
            raise ImagenError(f"model {spec.model!r} has no default {exc.args[0]} and the manifest sets none") from exc

    @staticmethod
    def _rejection(response: httpx.Response) -> str:
        detail = ""
        try:
            errors = response.json().get("detail")
        except (ValueError, AttributeError):
            errors = None
        if errors:
            detail = f": {str(errors)[:300]}"
        return f"create failed: HTTP {response.status_code}{detail}"

    def create(self, spec: GenerationSpec) -> str:
        sampling = self.sampling_for(spec)
        body = {
            "request": {
                "capability": "txt2img",
                "model_key": spec.model,
                "prompt": spec.prompt,
                "negative_prompt": spec.negative,
                "seed": str(spec.seed),
                "width": spec.size,
                "height": spec.size,
                "batch": 1,
                "steps": sampling.steps,
                "cfg": sampling.cfg,
                "sampler": sampling.sampler,
                "scheduler": sampling.scheduler,
            },
            "title": f"trophy {spec.art_key} {spec.metal or 'one-off'} seed {spec.seed}",
        }
        key = idempotency_key(spec.art_key, spec.metal, spec.prompt, spec.model, spec.seed, spec.attempt, sampling)
        response = self._send("POST", "/api/generations", json=body, headers={"Idempotency-Key": key})
        if response.status_code == 409:
            raise ImagenError(
                "create failed: HTTP 409, this seed was already submitted with a different request "
                "(negative prompt or size changed?); change the prompt or seed, or pass --retry N"
            )
        if response.status_code not in (200, 201):
            raise ImagenError(self._rejection(response))
        return str(response.json()["id"])

    def wait(self, generation_id: str) -> dict[str, Any]:
        deadline = self._clock() + self._timeout_seconds
        while True:
            response = self._send("GET", f"/api/generations/{generation_id}")
            if response.status_code != 200:
                raise ImagenError(f"poll failed: HTTP {response.status_code}")
            doc: dict[str, Any] = response.json()
            if doc["state"] in TERMINAL_STATES:
                return doc
            if self._clock() > deadline:
                raise ImagenError(f"generation {generation_id} timed out after {self._timeout_seconds:.0f} s")
            self._sleep(self._poll_seconds)

    def download_first_output(self, doc: dict[str, Any]) -> bytes:
        outputs: list[dict[str, Any]] = list(doc.get("outputs") or [])
        if doc["state"] != "completed" or not outputs:
            raise ImagenError(f"generation {doc['id']} ended {doc['state']} with {len(outputs)} outputs")
        response = self._send("GET", str(outputs[0]["bytes_url"]))
        if response.status_code != 200:
            raise ImagenError(f"download failed: HTTP {response.status_code}")
        return response.content

    def generate(self, spec: GenerationSpec) -> bytes:
        return self.download_first_output(self.wait(self.create(spec)))
