"""scan (PDF -> typed data + block images under out/) and read (block images -> checked readings)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

import checks
from layout import crop_blocks, tot_crop
from parse import parse_course, parse_date, parse_results
from vlm import VlmError, VlmUnreachable, extract_json

RENDER_DPI = 200
FIRST_TEMPERATURE = 0.2
RETRY_TEMPERATURE = 0.8
RETRIES = 5
COURSE_TRIES = 3
COURSE_TARGETS = 50
LITTLE_TEXT = 150  # a page with less typed text than this is a picture page (its footer may still be text)
DEFAULT_SKIPS = {"2025-11-16": "no scores for that Sunday in the workbook (a PDF, but probably no shoot)"}
_RESULTS_HEADING = re.compile(r"Note\s+Place\s+Name|Average Score")


class Asker(Protocol):
    """What the pipeline needs from an engine's client: the Gemma `VlmClient` and the Claude client both fit."""

    def ask(self, image: Image.Image, prompt: str, temperature: float, attempt: int = 0) -> str: ...

    def close(self) -> None: ...


WHOLE_PROMPT = (
    "This is one shooter's block from a handwritten clay-shooting scoresheet. "
    "Transcribe only what is written; do not check or reconcile numbers. Reply with ONLY this JSON: "
    '{"name": "<handwritten name>", "malf": "<anything written in the Malf. boxes, or empty>", '
    '"event_total": <the handwritten Event Total as an int, or null>}'
)


def tot_prompt(rows: int) -> str:
    return (
        f"This is the right-hand Tot column of a handwritten scoresheet: {rows} boxed handwritten digits, "
        "top to bottom, then the boxed Event Total at the bottom. Reply with ONLY this JSON, no other text: "
        '{"tots": [<one int per row, top to bottom>], "event_total": <int>}'
    )


COURSE_PROMPT = (
    "This is the course sheet of a clay-target shoot: a table with one row per station. Read only the station "
    "number and the number of targets a shooter shoots there (the Tgts column, not the traps or presentations), "
    "in the order listed. A station number may carry a letter (for example 7A, a separate station next to 7): "
    "keep the letter. Reply with ONLY this JSON, no other text: "
    '{"stations": [{"stn": <number, or number and letter like "7A">, "targets": <int>}]}'
)


@dataclass(frozen=True)
class ScanResult:
    pdf: str
    sunday: str | None
    note: str


def run_pdftotext(pdf: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout


def render_page(pdf: Path, page: int) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "page"
        subprocess.run(
            [
                "pdftoppm",
                "-r",
                str(RENDER_DPI),
                "-f",
                str(page),
                "-l",
                str(page),
                "-png",
                "-singlefile",
                str(pdf),
                str(base),
            ],
            check=True,
        )
        with Image.open(base.with_suffix(".png")) as opened:
            return opened.convert("RGB")


def sunday_dir(out: Path, iso: str) -> Path:
    return out / "sundays" / iso


def _date_from_name(name: str) -> date | None:
    """A downloaded file is named "YYYY-MM-DD Sunday Clays Update.pdf"; used when the typed header has no date."""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    try:
        return date.fromisoformat(match[1]) if match else None
    except ValueError:
        return None


def scan_pdfs(
    pdfs: Sequence[Path],
    out: Path,
    skip_dates: Sequence[str] = (),
    officials: Mapping[str, list[dict[str, Any]]] | None = None,
) -> list[ScanResult]:
    """Scan each PDF once per Sunday: a repeat of a date (a re-download or "(1)" copy) is skipped.

    `officials` (from the scores workbook) gives the official rows of a Sunday; a Sunday it has no rows for
    falls back to the typed results table.
    """
    seen: dict[str, str] = {}
    results: list[ScanResult] = []
    for pdf in pdfs:
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        text = run_pdftotext(pdf)
        found = parse_date(text) or _date_from_name(pdf.name)
        iso = None if found is None else found.isoformat()
        if iso is None:
            results.append(ScanResult(pdf.name, None, "no Sunday date in the typed header; skipped"))
        elif iso in DEFAULT_SKIPS:
            results.append(ScanResult(pdf.name, iso, f"skipped: {DEFAULT_SKIPS[iso]}"))
        elif iso in skip_dates:
            results.append(ScanResult(pdf.name, iso, "skipped by request"))
        elif iso in seen:
            same = "identical copy" if seen[iso] == sha else "a different file for the same Sunday"
            results.append(ScanResult(pdf.name, iso, f"duplicate of {iso} ({same}); skipped"))
        else:
            seen[iso] = sha
            results.append(ScanResult(pdf.name, iso, _scan_one(pdf, text, sha, iso, out, (officials or {}).get(iso))))
    return results


def _picture_pages(pages: Sequence[str]) -> tuple[int | None, int | None]:
    """(course page, results page), 1-based, for a PDF whose course sheet is a picture.

    The course is the picture page after the typed results. When the results are pictures too, the first
    picture page is the results and the second is the course. Pages before the results are commentary.
    """
    heading = max((n for n, page in enumerate(pages, 1) if _RESULTS_HEADING.search(page)), default=None)
    little = [  # a picture page still carries a text footer; a page with no text at all is a blank scoresheet
        n for n, page in enumerate(pages, 1) if 0 < len(page.strip()) < LITTLE_TEXT and (heading is None or n > heading)
    ]
    if heading is not None:
        return (little[0] if little else None), None
    return (little[1] if len(little) > 1 else None), (little[0] if little else None)


def _scan_one(
    pdf: Path, text: str, sha: str, iso: str, out: Path, workbook_rows: list[dict[str, Any]] | None = None
) -> str:
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    course = parse_course(text)
    course_page, results_page = (None, None) if course.stations else _picture_pages(pages)
    scan_pages = [
        number for number, page in enumerate(pages, 1) if not page.strip() and number not in (course_page, results_page)
    ]
    if workbook_rows:
        results = workbook_rows
        source = "workbook"
    else:
        results = [asdict(row) for row in parse_results(text)]
        source = "typed"
    root = sunday_dir(out, iso)
    (root / "blocks").mkdir(parents=True, exist_ok=True)
    if course_page is None:
        (root / "course.png").unlink(missing_ok=True)
    else:
        render_page(pdf, course_page).save(root / "course.png")
    blocks: list[str] = []
    shutil.rmtree(root / "pages", ignore_errors=True)  # whole pages, for the Claude engine; never from another PDF
    (root / "pages").mkdir()
    for number in scan_pages:
        page_image = render_page(pdf, number)
        page_image.save(root / "pages" / f"p{number}.png")
        for index, block in enumerate(crop_blocks(page_image), 1):
            block_id = f"p{number}-b{index}"
            block.save(root / "blocks" / f"{block_id}.png")
            tot_crop(block).save(root / "blocks" / f"{block_id}-tot.png")
            blocks.append(block_id)
    meta = {
        "date": iso,
        "sha256": sha,
        "pdf": pdf.name,
        "layout": [list(pair) for pair in course.stations],
        "course_page": course_page,
        "results_page": results_page,
        "presentations": {stn: [asdict(p) for p in items] for stn, items in course.presentations.items()},
        "officials": results,
        "officials_source": source,
        "blocks": blocks,
    }
    (root / "sunday.json").write_text(json.dumps(meta, indent=1))
    found = f"{len(results)} results" + (" (from the scores workbook)" if source == "workbook" else "")
    if course.stations:
        targets = sum(count for _, count in course.stations)
        shape = f"{len(course.stations)} stations ({targets} targets)"
    elif course_page is None:
        shape = "no typed course and no course page found"
    else:
        shape = f"no typed course (course page {course_page})"
    return f"{found}, {shape}, {len(blocks)} blocks, scoresheet pages: {len(scan_pages)}"


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _ints(value: object) -> list[int | None]:
    return [_int(item) for item in value] if isinstance(value, list) else []


def _ask(client: Asker, image: Image.Image, prompt: str, temperature: float, attempt: int) -> dict[str, Any]:
    return extract_json(client.ask(image, prompt, temperature, attempt)) or {}


def _worth_retrying(reasons: Sequence[str]) -> bool:
    """Whether another look at the Tot column could help.

    A name with no official row cannot be fixed by it. A sheet that is consistent with itself (every check
    passes and the numbers add up to the written Event Total) but differs from the official score is what
    the person wrote, so it goes to review without a retry.
    """
    fixable = [reason for reason in reasons if reason != checks.NO_OFFICIAL_MATCH]
    return bool(fixable) and fixable != [checks.SHEET_VS_OFFICIAL]


def _settles(reasons: Sequence[str], total: int | None, agreed: set[int]) -> bool:
    """Whether a retry ends the search. One that only disagrees with the official score must also carry an Event
    Total the first reading or the whole-block read already gave: a misread total plus matching misread Tots
    would otherwise pass for a person's sheet."""
    if _worth_retrying(reasons):
        return False
    return checks.SHEET_VS_OFFICIAL not in reasons or total in agreed


def _official_for(name: str, officials: Sequence[dict[str, Any]], total: int) -> tuple[bool, int | None]:
    """(matched, official score) for a read name; a shooter with two rounds gets the row that agrees with the sheet."""
    names = [str(row["name"]) for row in officials]
    hit = checks.best_match(name, names)
    if hit is None:
        return False, None
    top = checks.similarity(name, names[hit])
    same = [j for j, other in enumerate(names) if checks.similarity(name, other) == top]
    chosen = next((j for j in same if int(officials[j]["hits"]) == total), hit)
    return True, int(officials[chosen]["hits"])


def course_needed(root: Path) -> bool:
    """True when the PDF gave no typed course but a course picture was found for the model to read."""
    return not json.loads((root / "sunday.json").read_text())["layout"] and (root / "course.png").exists()


def _course_layout(reply: dict[str, Any]) -> list[list[int | str]] | None:
    """The stations of a course reply, or None unless they are distinct labels (7, 7A) whose targets sum to 50."""
    stations = reply.get("stations")
    if not isinstance(stations, list):
        return None
    layout: list[list[int | str]] = []
    total = 0
    for item in stations:
        if not isinstance(item, dict):
            return None
        stn, targets = checks.station_label(item.get("stn")), _int(item.get("targets"))
        if stn is None or targets is None or targets < 1:
            return None
        layout.append([stn, targets])
        total += targets
    distinct = len({stn for stn, _ in layout}) == len(layout)
    return layout if distinct and total == COURSE_TARGETS else None


def read_course(root: Path, client: Asker) -> bool:
    """Read the course picture into sunday.json's layout; False, marked course_unreadable, after 3 bad replies."""
    path = root / "sunday.json"
    meta = json.loads(path.read_text())
    with Image.open(root / "course.png") as image:
        for attempt in range(COURSE_TRIES):
            try:
                reply = _ask(
                    client, image, COURSE_PROMPT, FIRST_TEMPERATURE if attempt == 0 else RETRY_TEMPERATURE, attempt
                )
            except VlmUnreachable:
                raise
            except VlmError:
                continue
            layout = _course_layout(reply)
            if layout is not None:
                meta.pop("course_unreadable", None)
                path.write_text(json.dumps({**meta, "layout": layout, "course_source": "image"}, indent=1))
                return True
    path.write_text(json.dumps({**meta, "course_unreadable": True}, indent=1))
    return False


def typed_data_missing(root: Path) -> bool:
    """True when the PDF's typed layer gave no results rows or no course (some weeks paste them as pictures)."""
    meta = json.loads((root / "sunday.json").read_text())
    return not meta["layout"] or not meta["officials"]


def read_block(
    client: Asker,
    block: Image.Image,
    tot: Image.Image,
    targets: Sequence[int],
    officials: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    """Read one block; None when it is blank. Retries the Tot read until a reading passes the checks."""
    prompt = tot_prompt(len(targets))
    try:
        whole = _ask(client, block, WHOLE_PROMPT, FIRST_TEMPERATURE, 0)
        name = str(whole.get("name") or "").strip()
        first = _ask(client, tot, prompt, FIRST_TEMPERATURE, 0)
    except VlmUnreachable:
        raise
    except VlmError as exc:
        return {"name_read": "", "tots": [], "event_total": None, "malf": "", "tries": 1, "error": str(exc)}
    whole_total = _int(whole.get("event_total"))

    def assess(reading: dict[str, Any]) -> tuple[list[int | None], int | None, list[str]]:
        tots = _ints(reading.get("tots"))
        event_total = _int(reading.get("event_total"))
        if event_total is None:
            event_total = whole_total
        matched, official = _official_for(name, officials, sum(tot or 0 for tot in tots))
        return tots, event_total, checks.check_reading(tots, event_total, targets, official, matched=matched)

    tots, event_total, reasons = assess(first)
    agreed = {total for total in (event_total, whole_total) if total is not None}
    if not name and not any(tot is not None for tot in tots) and event_total is None:
        return None
    tries = 1
    while _worth_retrying(reasons) and tries <= RETRIES:
        try:
            again = _ask(client, tot, prompt, RETRY_TEMPERATURE, tries)
        except VlmUnreachable:
            raise
        except VlmError:
            break
        tries += 1
        new_tots, new_total, new_reasons = assess(again)
        if _settles(new_reasons, new_total, agreed):
            tots, event_total, reasons = new_tots, new_total, new_reasons
    return {
        "name_read": name,
        "tots": tots,
        "event_total": event_total,
        "malf": str(whole.get("malf") or ""),
        "tries": tries,
    }


def resolve(meta: dict[str, Any], readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match names one-to-one to the Sunday's results rows and set each reading's final status and reasons."""
    officials = meta["officials"]
    targets = [pair[1] for pair in meta["layout"]]
    matches = checks.match_names(
        [str(r["name_read"]) for r in readings],
        [str(o["name"]) for o in officials],
        sums=[sum(tot or 0 for tot in r["tots"]) for r in readings],
        hits=[int(o["hits"]) for o in officials],
    )
    for record, hit in zip(readings, matches, strict=True):
        official = None if hit is None else officials[hit]
        record["matched"] = None if official is None else official["name"]
        record["official"] = None if official is None else official["hits"]
        record["sum"] = sum(tot or 0 for tot in record["tots"])
        if "error" in record:
            record["reasons"] = [record.pop("error_reason", checks.MODEL_ERROR)]
        else:
            record["reasons"] = checks.check_reading(
                record["tots"], record["event_total"], targets, record["official"], matched=official is not None
            )
        record["status"] = "ok" if not record["reasons"] else "review"
        record.pop("error", None)
    return readings


def _decisions(path: Path, sha: str | None) -> tuple[dict[str, dict[str, Any]], int]:
    """(readings a person accepted or skipped and that still stand, how many went stale).

    A decision made on a different PDF (the Sunday was re-scanned from another file) no longer describes the
    blocks on disk, so it is dropped and its block is read again. A decision saved before shas were stored
    carries no sha; nothing says it is stale, so it is kept.
    """
    if not path.exists():
        return {}, 0
    decided = [r for r in json.loads(path.read_text()) if r["status"] in ("accepted", "skipped")]
    stale = [r for r in decided if r.get("pdf_sha256") not in (None, sha)]
    return {r["id"]: r for r in decided if r not in stale}, len(stale)


def _without_used_rows(officials: Sequence[dict[str, Any]], kept: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The official rows no accepted decision has used: one row per decision, so a second round stays free."""
    free = list(officials)
    for record in kept:
        if record["status"] == "accepted":
            used = next(
                (i for i, o in enumerate(free) if (o["name"], o["hits"]) == (record["matched"], record["official"])),
                None,
            )
            if used is not None:
                free.pop(used)
    return free


# A page reader answers for every pending block id at once: {block id: record, or None when the block is blank}.
Reader = Callable[[Path, dict[str, Any], Sequence[str], int, Callable[[str], None]], dict[str, dict[str, Any] | None]]
# A refiner may change fresh readings (already resolved against the results) in place.
Refiner = Callable[[dict[str, Any], list[dict[str, Any]]], None]


def read_sunday(
    root: Path,
    client: Asker,
    *,
    jobs: int = 1,
    log: Callable[[str], None] = lambda _message: None,
    reader: Reader | None = None,
    refine: Refiner | None = None,
) -> dict[str, int]:
    """Read every block of one scanned Sunday into readings.json; returns counts by status.

    By default each block is read by the model client; `reader` (the Claude engine) reads whole pages instead.
    """
    meta = json.loads((root / "sunday.json").read_text())
    sha = meta.get("sha256")
    targets = [pair[1] for pair in meta["layout"]]
    kept, stale = _decisions(root / "readings.json", sha)

    def one(block_id: str) -> dict[str, Any] | None:
        if block_id in kept:
            return kept[block_id]
        with (
            Image.open(root / "blocks" / f"{block_id}.png") as block,
            Image.open(root / "blocks" / f"{block_id}-tot.png") as tot,
        ):
            record = read_block(client, block, tot, targets, meta["officials"])
        return _tag(record, block_id, sha, meta["date"], log)

    if reader is None:
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            found = list(pool.map(one, meta["blocks"]))
    else:
        pending = [block_id for block_id in meta["blocks"] if block_id not in kept]
        read = reader(root, meta, pending, jobs, log) if pending else {}
        found = [kept[i] if i in kept else _tag(read[i], i, sha, meta["date"], lambda _m: None) for i in meta["blocks"]]
    free = {**meta, "officials": _without_used_rows(meta["officials"], list(kept.values()))}
    fresh = resolve(free, [r for r in found if r is not None and r["id"] not in kept])
    if refine is not None:
        refine(free, fresh)
    fresh_by_id = {r["id"]: r for r in fresh}
    readings = [kept.get(r["id"]) or fresh_by_id[r["id"]] for r in found if r is not None]
    for record in kept.values():
        if sha is not None and "pdf_sha256" not in record:
            record["pdf_sha256"] = sha  # decided before shas were stored: pin it to this PDF so a re-scan can drop it
    (root / "readings.json").write_text(json.dumps(readings, indent=1))
    counts = {"ok": 0, "review": 0, "skipped": len(found) - len(readings), "kept": len(kept), "stale": stale}
    for record in readings:
        if record["id"] not in kept:
            counts[record["status"]] += 1
    return counts


def _tag(
    record: dict[str, Any] | None, block_id: str, sha: str | None, iso: str, log: Callable[[str], None]
) -> dict[str, Any] | None:
    if record is not None:
        page, index = block_id[1:].split("-b")
        record.update({"id": block_id, "page": int(page), "block": int(index), "pdf_sha256": sha})
    log(f"{iso} {block_id}: {'blank' if record is None else 'read'}")
    return record
