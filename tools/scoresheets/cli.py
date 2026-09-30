"""scoresheets CLI (run from tools/scoresheets): scan -> read -> review / apply-review -> export -> verify.

`run <pdf...>` does scan, read, export and the review page in one go. Dev-only: the app and CI never call
the model. Everything it writes goes under the gitignored out/ folder because it contains member names.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import claude_engine
import export
import pipeline
import review
import scores
from vlm import VlmClient, VlmUnreachable

HERE = Path(__file__).resolve().parent
DEFAULT_SCORES = HERE.parent.parent / "backend" / "tests" / "fixtures" / "scores_2026-09-27.xlsx"


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _officials(args: argparse.Namespace) -> dict[str, list[dict[str, Any]]] | None:
    """Official rows by Sunday from the scores workbook: --scores, else the backend fixture when it exists."""
    path = args.scores or (DEFAULT_SCORES if DEFAULT_SCORES.exists() else None)
    return None if path is None else scores.load_officials(path)


def _scan(args: argparse.Namespace) -> int:
    results = pipeline.scan_pdfs(args.pdfs, args.out, args.skip_date, _officials(args))
    for result in results:
        print(f"{result.pdf}: {result.note}")
    print(f"scanned {sum(1 for r in results if r.note[0].isdigit())} Sundays")
    return 0


def _dates(args: argparse.Namespace) -> list[str]:
    found = sorted(p.parent.name for p in (args.out / "sundays").glob("*/sunday.json"))
    return [d for d in found if not args.date or d in args.date]


def _jobs(args: argparse.Namespace) -> int:
    """--jobs, else 4 for the Claude engine (pages in parallel) and 1 for the single local model server."""
    return args.jobs or (claude_engine.DEFAULT_JOBS if args.engine == "claude" else 1)


def _read_dates(args: argparse.Namespace, dates: Sequence[str]) -> int:
    client: pipeline.Asker
    extra: dict[str, Any] = {}
    if args.engine == "claude":
        client = claude_engine.ClaudeClient(args.out / "claude-cache", model=args.claude_model)
        cached = VlmClient(args.out / "cache", offline=True) if (args.out / "cache").is_dir() else None
        extra["reader"] = claude_engine.page_reader(client)
    else:
        client = VlmClient(args.out / "cache")
        cached = None
    try:
        for iso in dates:
            root = pipeline.sunday_dir(args.out, iso)
            if pipeline.course_needed(root):
                if not pipeline.read_course(root, client):
                    print(f"{iso}: course_unreadable (the course picture did not read as 50 targets); not read")
                    continue
                print(f"{iso}: course read from the picture")
            if pipeline.typed_data_missing(root):
                print(f"{iso}: no typed results or course in the PDF (pasted as pictures?); not read")
                continue
            if args.engine == "claude":
                extra["refine"] = claude_engine.second_opinion(cached, root)
            counts = pipeline.read_sunday(root, client, jobs=_jobs(args), log=_log, **extra)
            print(f"{iso}: {counts['ok']} ok, {counts['review']} review, {counts['skipped']} blank")
            if counts["kept"]:
                print(f"{iso}: {counts['kept']} review decisions kept")
            if counts["stale"]:
                print(f"{iso}: {counts['stale']} stale review decisions dropped (the PDF changed)")
    except VlmUnreachable as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        client.close()
        if cached is not None:
            cached.close()
        if isinstance(client, claude_engine.ClaudeClient):
            print(f"claude: {client.calls} calls, {client.cached} cached, cost ${client.cost:.4f}")
    return 0


def _read(args: argparse.Namespace) -> int:
    return _read_dates(args, _dates(args))


def _review(args: argparse.Namespace) -> int:
    path, count = review.build_review(args.out)
    print(f"wrote {path} ({count} blocks to review)")
    return 0


def _apply_review(args: argparse.Namespace) -> int:
    applied, problems = review.apply_review(args.out, args.decisions)
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"applied {applied} decisions")
    return 1 if problems else 0


def _export(args: argparse.Namespace) -> int:
    problems: list[str] = []
    counts = export.export_all(args.out, problems)
    _report_export(counts, problems)
    return 0


def _print_problems(problems: Sequence[str]) -> None:
    for problem in problems:
        print(f"left out: {problem}", file=sys.stderr)


def _report_export(counts: dict[str, int], problems: list[str]) -> None:
    print(f"wrote {counts['sheets']} sheets, {counts['rows']} shooter rows, report.csv and presentations.json")
    _print_problems(problems)
    if counts["skipped"]:
        why = ", ".join(f"{reason} {counts[reason]}" for reason in export.LEFT_OUT_REASONS if counts[reason])
        print(f"{counts['skipped']} Sundays left out of the workbook ({why}); report.csv has each one")


def _verify(args: argparse.Namespace) -> int:
    workbook = args.out / "stations_backfill.xlsx"
    if not workbook.exists():
        print(f"no {workbook}: run export first", file=sys.stderr)
        return 1
    ok, text = export.verify_workbook(workbook, args.backend)
    print(text)
    return 0 if ok else 1


def _summary(out: Path, dates: Sequence[str]) -> None:
    counts = {"ok": 0, "review": 0, "accepted": 0, "skipped": 0}
    mismatches: list[str] = []
    for meta, readings in export.load_sundays(out):
        if meta["date"] not in dates:
            continue
        blanks = len(meta["blocks"]) - len(readings)
        counts["skipped"] += blanks
        for record in readings:
            counts[record["status"]] += 1
            if "sheet_vs_official" in record["reasons"]:
                mismatches.append(
                    f"{meta['date']} {record['id']}: sheet {record['sum']} vs official {record['official']}"
                )
    print(f"Sundays {len(dates)}: shooters {counts['ok']} ok, {counts['review']} review, {counts['skipped']} blank")
    for line in mismatches:
        print(f"sheet_vs_official {line}")


def _run(args: argparse.Namespace) -> int:
    results = pipeline.scan_pdfs(args.pdfs, args.out, args.skip_date, _officials(args))
    dates = sorted({r.sunday for r in results if r.sunday and r.note[0].isdigit()})
    code = _read_dates(args, dates)
    if code:
        return code
    problems: list[str] = []
    counts = export.export_all(args.out, problems)
    _print_problems(problems)
    path, _ = review.build_review(args.out)
    _summary(args.out, dates)
    print(f"exported {counts['sheets']} sheets; review page {path}")
    return 0


COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "scan": _scan,
    "read": _read,
    "review": _review,
    "apply-review": _apply_review,
    "export": _export,
    "verify": _verify,
    "run": _run,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scoresheets", description="Sunday Clays scoresheet backfill (dev-only).")
    parser.add_argument("--out", type=Path, default=HERE / "out")
    parser.add_argument(
        "--scores",
        type=Path,
        default=None,
        help="scores workbook with the official results (default: the backend test fixture, if present)",
    )
    parser.add_argument("--backend", type=Path, default=HERE.parent.parent / "backend")
    parser.add_argument(
        "--engine",
        choices=("gemma", "claude"),
        default="gemma",
        help="gemma: the local model server (default); claude: the local `claude` CLI, one call per page",
    )
    parser.add_argument("--claude-model", default=claude_engine.DEFAULT_MODEL, help="model for --engine claude")
    parser.add_argument(
        "--jobs", type=int, default=None, help="blocks (gemma) or pages (claude) read at once; default 1 / 4"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, helptext in (
        ("scan", "parse PDFs and cut scoresheet blocks"),
        ("run", "scan, read, export and review page"),
    ):
        cmd = sub.add_parser(name, help=helptext)
        cmd.add_argument("pdfs", nargs="+", type=Path)
        cmd.add_argument("--skip-date", action="append", default=[], metavar="YYYY-MM-DD")
        if name == "run":
            cmd.add_argument("--jobs", type=int, default=argparse.SUPPRESS)
    read = sub.add_parser("read", help="read every scanned block with the local model (cached, resumable)")
    read.add_argument("--jobs", type=int, default=argparse.SUPPRESS)
    read.add_argument("--date", action="append", default=[], metavar="YYYY-MM-DD")
    sub.add_parser("review", help="write out/review.html")
    apply = sub.add_parser("apply-review", help="merge review-decisions.json into the readings")
    apply.add_argument("decisions", type=Path)
    sub.add_parser("export", help="write stations_backfill.xlsx, report.csv, presentations.json")
    sub.add_parser("verify", help="run the backend station parser on the workbook")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except scores.ScoresError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
