"""Write the station workbook the app's parser accepts, plus the audit report and presentations sidecar."""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook

import checks

EXPORTABLE = ("ok", "accepted")
FIRST_ENTRY_ROW = 10

_VERIFY_SCRIPT = """
import sys, json
from collections import Counter
from sunday_clays.ingest import parse_upload
parsed = parse_upload(open(sys.argv[1], "rb").read())
counts = Counter(f.severity.value for f in parsed.findings)
errors = [f"{f.code}: {f.message}" for f in parsed.findings if f.severity.value == "error"]
print(json.dumps({"sheets": len(parsed.sheets), "rows": sum(len(s.rows) for s in parsed.sheets),
                  "findings": dict(counts), "errors": errors}))
"""


def load_metas(out: Path) -> list[dict[str, Any]]:
    """The scan data of every scanned Sunday, oldest first, whether or not it has been read."""
    return [json.loads(path.read_text()) for path in sorted((out / "sundays").glob("*/sunday.json"))]


def load_sundays(out: Path) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """(meta, readings) of every read Sunday, oldest first."""
    found = []
    for readings in sorted((out / "sundays").glob("*/readings.json")):
        found.append((json.loads((readings.parent / "sunday.json").read_text()), json.loads(readings.read_text())))
    return found


LEFT_OUT_REASONS = ("course_unreadable", "no_course")


def sunday_left_out(meta: dict[str, Any]) -> str | None:
    """Why a whole Sunday stays out of the workbook, or None."""
    if meta.get("course_unreadable"):
        return "course_unreadable"
    if not meta["layout"] and meta.get("course_page") is None:
        return "no_course"  # no typed course and no course picture to read one from
    return None


def sum_problem(total: int, official: int | str | None) -> str:
    """Why a shooter's station totals cannot be used: the spreadsheet score is authoritative and they must add
    up to it exactly. Empty when they do."""
    if official is not None and total == official:
        return ""
    return f"station totals add to {total}, spreadsheet score is {'missing' if official is None else official}"


def is_stale(meta: dict[str, Any], record: dict[str, Any]) -> bool:
    """A reading taken from another PDF than the one now scanned for that Sunday (scan ran again without read)."""
    sha = record.get("pdf_sha256")
    return sha is not None and meta.get("sha256") not in (None, sha)


def sheet_name(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day.month} {day.day} {day:%y}"


def export_all(out: Path, problems: list[str] | None = None) -> dict[str, int]:
    """Write stations_backfill.xlsx (only ok/accepted shooters), report.csv and presentations.json.

    The spreadsheet score is authoritative: a shooter whose station totals do not add up to it is left out of the
    workbook, reported as `sheet_vs_official` in report.csv, and described in `problems` when it is given."""
    sundays = load_sundays(out)
    metas = load_metas(out)
    left_out = {meta["date"]: reason for meta in metas if (reason := sunday_left_out(meta))}
    workbook = Workbook()
    workbook.remove(workbook.active)  # type: ignore[arg-type]
    sheets = rows = 0
    skipped = dict.fromkeys(LEFT_OUT_REASONS, 0)
    mismatched = 0
    presentations: dict[str, Any] = {
        meta["date"]: {"layout": meta["layout"], "presentations": meta["presentations"]} for meta in metas
    }
    with (out / "report.csv").open("w", newline="") as handle:
        report = csv.writer(handle)
        report.writerow(
            ["date", "block", "name_read", "matched_name", "official", "sheet_sum", "status", "reasons", "source"]
        )
        for meta, readings in sundays:
            keep: list[dict[str, Any]] = []
            for record in readings:
                status = "stale" if is_stale(meta, record) else record["status"]
                reasons = list(record["reasons"])
                if status in EXPORTABLE and record["matched"]:
                    problem = sum_problem(sum(tot or 0 for tot in record["tots"]), record["official"])
                    if problem:
                        status, mismatched = checks.SHEET_VS_OFFICIAL, mismatched + 1
                        reasons.append(problem)
                        if problems is not None:
                            problems.append(f"{meta['date']} {record['id']}: {problem}")
                    else:
                        keep.append(record)
                report.writerow(
                    [
                        meta["date"],
                        record["id"],
                        record["name_read"],
                        record["matched"] or "",
                        "" if record["official"] is None else record["official"],
                        record["sum"],
                        status,
                        ";".join(reasons),
                        record.get("source", "gemma"),
                    ]
                )
            if not keep or meta["date"] in left_out:
                continue
            sheet = workbook.create_sheet(sheet_name(meta["date"]))
            sheet.append(["Event Date"])
            sheet.append([date.fromisoformat(meta["date"])])
            sheet.append([])
            sheet.append(["STATION #", *(pair[0] for pair in meta["layout"])])
            sheet.append(["TARGET COUNT", *(pair[1] for pair in meta["layout"])])
            for _ in range(3):
                sheet.append([])
            sheet.append(["Name", "Station Hits"])
            for record in keep:
                sheet.append([record["matched"], *record["tots"]])
            sheets += 1
            rows += len(keep)
        for iso, reason in left_out.items():  # a whole Sunday skipped: say why
            report.writerow([iso, "", "", "", "", "", "sunday_skipped", reason])
            skipped[reason] += 1
    (out / "presentations.json").write_text(json.dumps(presentations, indent=1))
    target = out / "stations_backfill.xlsx"
    if sheets:
        workbook.save(target)
    else:
        target.unlink(missing_ok=True)  # never leave an older workbook for verify to check
    return {"sheets": sheets, "rows": rows, "skipped": sum(skipped.values()), "mismatched": mismatched, **skipped}


def verify_workbook(workbook: Path, backend: Path) -> tuple[bool, str]:
    """Run the backend's own station parser on the workbook; False if it reports any ERROR finding."""
    done = subprocess.run(
        ["uv", "run", "--project", str(backend), "python", "-c", _VERIFY_SCRIPT, str(workbook)],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return False, done.stderr.strip() or "the backend parser failed"
    summary = json.loads(done.stdout.strip().splitlines()[-1])
    text = f"{summary['sheets']} sheets, {summary['rows']} rows, findings {summary['findings']}"
    for error in summary["errors"]:
        text += f"\nERROR {error}"
    return not summary["errors"], text
