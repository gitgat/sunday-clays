"""The Claude engine: read whole scoresheet pages with the local `claude` CLI in print mode (Opus, no tools).

Only the `claude` CLI is used (the owner's subscription): never the Anthropic API, never an API key. One call
per scoresheet page reads all six blocks. The page image goes in inline (base64, over stdin as one stream-json
user message) and every tool is switched off, so the model cannot touch the file system; replies are cached on
disk so a rerun is free. A cached Gemma reading
of a block (from an earlier Gemma run in the same out/ folder) is a second opinion; the server is never called.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from PIL import Image

import checks
import pipeline
from layout import BLOCKS_PER_PAGE
from vlm import VlmClient, VlmError, VlmUnreachable, extract_json, image_png

DEFAULT_MODEL = "opus"
DEFAULT_JOBS = 4
TIMEOUT_SECONDS = 300
PAGE_TRIES = 2  # the first reading and one retry
SOURCE = "claude"
SECOND_OPINION = "gemma_second_opinion"

SYSTEM_PROMPT = "You transcribe handwritten clay-shooting scoresheets into JSON exactly as written."
NO_TOOLS_FLAGS = ("--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--setting-sources", "")

PAGE_PROMPT = (
    "The image is a handwritten clay-shooting scoresheet with up to 6 shooter blocks, numbered as slots 1 to 6 "
    "from left to right, then top to bottom (two columns, three rows). For each block with a name, transcribe "
    "exactly what is written: the name, the station numbers in the Stn column (a number may carry a letter, "
    "like 7A: keep it), the handwritten number in the "
    "Tot column for each station (top to bottom), anything in the Malf. boxes, and the handwritten Event Total. "
    "Do not correct or reconcile numbers. Reply with ONLY JSON: "
    '{"blocks":[{"slot":1,"name":"...","stations":[{"stn":2,"tot":5},{"stn":"7A","tot":6}],"malf":"","event_total":27}]}'
)


class ClaudeError(VlmError):
    """One `claude` call failed (bad exit, bad envelope, too slow); the page is retried, then flagged."""


class ClaudeUnavailable(VlmUnreachable):
    """`claude` cannot run at all (not installed, or not logged in); nothing else will work, so the run stops."""


class ScanOutdated(VlmUnreachable):
    """The scan has no page images (it predates the Claude engine); scan again, then read."""


def run_claude(cmd: list[str], timeout: float, stdin: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """The one place the CLI is started; tests replace it. It runs in an empty folder (`cwd`) with `stdin` as input."""
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout, cwd=cwd)


def user_message(png: bytes, prompt: str) -> str:
    """The one-line stream-json user message: the image inline as base64, then the prompt."""
    image = {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()}
    content = [{"type": "image", "source": image}, {"type": "text", "text": prompt}]
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n"


def parse_stream(stdout: str) -> tuple[str, float]:
    """(model text, cost in USD) from the `"type":"result"` line of `claude -p --output-format stream-json`."""
    envelope: dict[str, Any] | None = None
    for line in stdout.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue  # not an event line; only the result line matters
        if isinstance(item, dict) and item.get("type") == "result":
            envelope = item
    if envelope is None:
        raise ClaudeError("claude printed no result line")
    result = envelope.get("result")
    if envelope.get("is_error"):
        message = str(result)[:200]
        if "login" in message.lower():
            raise ClaudeUnavailable(f"claude is not logged in: {message}")
        raise ClaudeError(f"claude reported an error: {message}")
    if not isinstance(result, str):
        raise ClaudeError("claude's result line has no result text")
    cost = envelope.get("total_cost_usd")
    return result, float(cost) if isinstance(cost, int | float) and not isinstance(cost, bool) else 0.0


def cache_key(png: bytes, prompt: str, model: str, attempt: int) -> str:
    digest = hashlib.sha256()
    for part in (png, prompt.encode(), model.encode(), str(attempt).encode()):
        digest.update(part)
        digest.update(b"|")
    return digest.hexdigest()


class ClaudeClient:
    """Same `ask` shape as VlmClient, so the course read works with either engine. Thread-safe."""

    def __init__(self, cache_dir: Path, *, model: str = DEFAULT_MODEL) -> None:
        self.cache_dir = cache_dir
        self.model = model
        self.binary = os.environ.get("CLAUDE_BIN") or "claude"
        self.cost = 0.0
        self.calls = 0
        self.cached = 0
        self._lock = threading.Lock()

    def ask(self, image: Image.Image, prompt: str, temperature: float, attempt: int = 0) -> str:
        """The model's text. A cached reply is returned without a call; the temperature is not used."""
        png = image_png(image)
        path = self.cache_dir / f"{cache_key(png, prompt, self.model, attempt)}.json"
        try:
            content = str(json.loads(path.read_text())["content"])
        except (OSError, ValueError, KeyError, TypeError):
            pass  # no entry, or a torn one: ask again
        else:
            with self._lock:
                self.cached += 1
            return content
        content, cost = self._call(png, prompt)
        with self._lock:
            self.calls += 1
            self.cost += cost
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        partial.write_text(json.dumps({"content": content, "cost": cost}))
        partial.replace(path)
        return content

    def _call(self, png: bytes, prompt: str) -> tuple[str, float]:
        cmd = [
            self.binary,
            "-p",
            "--model",
            self.model,
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            *NO_TOOLS_FLAGS,
            "--system-prompt",
            SYSTEM_PROMPT,
        ]
        try:
            with tempfile.TemporaryDirectory(prefix="scoresheets-claude-") as empty:
                done = run_claude(cmd, TIMEOUT_SECONDS, user_message(png, prompt), Path(empty))
        except FileNotFoundError as exc:
            raise ClaudeUnavailable(f"cannot run claude ({self.binary}); set CLAUDE_BIN or install it") from exc
        except subprocess.TimeoutExpired as exc:
            raise ClaudeError("claude took too long to reply") from exc
        try:
            return parse_stream(done.stdout)  # first: a "not logged in" result line comes with a non-zero exit
        except ClaudeUnavailable:
            raise
        except ClaudeError:
            if done.returncode != 0:
                raise ClaudeError(f"claude exited {done.returncode}: {done.stderr.strip()[:200]}") from None
            raise

    def discard(self, image: Image.Image, prompt: str, attempt: int) -> None:
        """Forget a cached reply that turned out to be unusable, so a rerun asks again."""
        path = self.cache_dir / f"{cache_key(image_png(image), prompt, self.model, attempt)}.json"
        path.unlink(missing_ok=True)

    def close(self) -> None:
        """Nothing to release; here so the CLI can close either engine's client."""


def _reading(item: dict[str, Any]) -> dict[str, Any] | None:
    stations = item.get("stations")
    tots = (
        [pipeline._int(s.get("tot")) if isinstance(s, dict) else None for s in stations]
        if isinstance(stations, list)
        else []
    )
    record = {
        "name_read": str(item.get("name") or "").strip(),
        "tots": tots,
        "stns": [checks.station_label(s.get("stn")) if isinstance(s, dict) else None for s in stations]
        if isinstance(stations, list)
        else [],
        "event_total": pipeline._int(item.get("event_total")),
        "malf": str(item.get("malf") or ""),
    }
    written = record["name_read"] or record["event_total"] is not None or any(tot is not None for tot in tots)
    return record if written else None


def parse_page(text: str) -> dict[int, dict[str, Any] | None] | None:
    """{slot: reading, or None when the slot is blank} from a page reply; None when the reply is unusable."""
    reply = extract_json(text)
    blocks = None if reply is None else reply.get("blocks")
    if not isinstance(blocks, list):
        return None
    found: dict[int, dict[str, Any] | None] = {}
    for item in blocks:
        slot = pipeline._int(item.get("slot")) if isinstance(item, dict) else None
        if slot is None or not 1 <= slot <= BLOCKS_PER_PAGE or slot in found:
            return None
        found[slot] = _reading(item)
    return found


def read_page(client: ClaudeClient, image: Image.Image) -> tuple[dict[int, dict[str, Any] | None] | None, int, str]:
    """(slots, tries, error): the page's readings, or None and why after two tries."""
    error = ""
    for attempt in range(PAGE_TRIES):
        try:
            text = client.ask(image, PAGE_PROMPT, 0.0, attempt)
        except VlmUnreachable:
            raise
        except VlmError as exc:
            error = str(exc)
            continue
        parsed = parse_page(text)
        if parsed is not None:
            return parsed, attempt + 1, ""
        client.discard(image, PAGE_PROMPT, attempt)  # never replay a reply that could not be used
        error = "claude's reply was not the expected JSON"
    return None, PAGE_TRIES, error


def _with_station_check(reading: dict[str, Any], meta: dict[str, Any], tries: int) -> dict[str, Any]:
    """The block's record; flagged `station_mismatch` when a station number Claude read is not the course's."""
    stns = reading["stns"]
    record = {key: value for key, value in reading.items() if key != "stns"}
    record.update(tries=tries, source=SOURCE)
    course = [pair[0] for pair in meta["layout"]]
    if any(read is not None and read != want for read, want in zip(stns, course, strict=False)):
        record.update(error="station numbers read do not match the course", error_reason=checks.STATION_MISMATCH)
    return record


def page_reader(client: ClaudeClient) -> pipeline.Reader:
    """A reader for `pipeline.read_sunday`: one call per page, slot n of page p is block id p<p>-b<n>."""

    def reader(
        root: Path, meta: dict[str, Any], pending: Sequence[str], jobs: int, log: Callable[[str], None]
    ) -> dict[str, dict[str, Any] | None]:
        pages = sorted({int(block_id[1:].split("-b")[0]) for block_id in pending})

        def one(page: int) -> tuple[dict[int, dict[str, Any] | None] | None, int, str]:
            path = root / "pages" / f"p{page}.png"
            if not path.exists():
                raise ScanOutdated(f"{meta['date']}: no page images in the scan; run scan again, then read")
            with Image.open(path) as opened:
                image = opened.convert("RGB")
            result = read_page(client, image)
            log(f"{meta['date']} page {page}: {'read' if result[0] is not None else 'engine_error'}")
            return result

        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            results = dict(zip(pages, pool.map(one, pages), strict=True))
        out: dict[str, dict[str, Any] | None] = {}
        for block_id in pending:
            page, slot = (int(part) for part in block_id[1:].split("-b"))
            slots, tries, error = results[page]
            if slots is None:
                out[block_id] = {
                    "name_read": "",
                    "tots": [],
                    "event_total": None,
                    "malf": "",
                    "tries": tries,
                    "source": SOURCE,
                    "error": error,
                    "error_reason": checks.ENGINE_ERROR,
                }
            else:
                reading = slots.get(slot)
                out[block_id] = None if reading is None else _with_station_check(reading, meta, tries)
        return out

    return reader


def second_opinion(gemma: VlmClient | None, root: Path) -> pipeline.Refiner | None:
    """A refiner using cached Gemma readings (never the server): adopt one that rescues a failed Claude reading
    only when its Event Total is the same one Claude read; flag `engines_disagree` when both pass but differ."""
    if gemma is None:
        return None

    def refine(free: dict[str, Any], fresh: list[dict[str, Any]]) -> None:
        targets = [pair[1] for pair in free["layout"]]
        for record in fresh:
            if record["reasons"] == [checks.ENGINE_ERROR]:
                continue
            with (
                Image.open(root / "blocks" / f"{record['id']}.png") as block,
                Image.open(root / "blocks" / f"{record['id']}-tot.png") as tot,
            ):
                other = pipeline.read_block(gemma, block, tot, targets, free["officials"])
            if other is None or "error" in other:
                continue
            matched = record["matched"] is not None
            other_reasons = checks.check_reading(
                other["tots"], other["event_total"], targets, record["official"], matched=matched
            )
            same = {"tots": other["tots"], "event_total": other["event_total"]}
            if record["status"] == "review":
                if not other_reasons and other["event_total"] == record["event_total"]:
                    record["claude"] = {"tots": record["tots"], "event_total": record["event_total"]}
                    record.update(
                        tots=other["tots"], sum=sum(other["tots"]), reasons=[], status="ok", source=SECOND_OPINION
                    )
                else:
                    record["gemma"] = same
            elif not other_reasons and other["tots"] != record["tots"]:
                record.update(reasons=[checks.ENGINES_DISAGREE], status="review", gemma=same)

    return refine
