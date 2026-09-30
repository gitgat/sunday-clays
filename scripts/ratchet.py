#!/usr/bin/env python3
"""Coverage ratchet and bundle budgets (C11). Standard library only.

check:  fail if any measured coverage is below ratchets/baseline.json or any bundle metric
        exceeds ratchets/budgets.json.
update: raise ratchets/baseline.json to max(old, max(90.0, floor(measured) - 1.0)); never lowers.
"""

import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

COVERAGE_KEYS = ("backend_lines", "backend_branches", "frontend_lines", "frontend_branches")
BUDGET_KEYS = ("entry_js_gz_kb", "total_js_gz_kb")
FLOOR = 90.0


class RatchetError(Exception):
    """Unusable input file; reported with exit code 2."""


def _load_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RatchetError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RatchetError(f"{path} must hold a JSON object")
    return data


def _exact_keys(data: dict[str, object], keys: Sequence[str], path: Path) -> dict[str, float]:
    if sorted(data) != sorted(keys):
        raise RatchetError(
            f"{path} must have exactly the keys {sorted(keys)}, found {sorted(data)}"
        )
    values: dict[str, float] = {}
    for key in keys:
        value = data[key]
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise RatchetError(f"{path}: {key} must be a number")
        values[key] = float(value)
    return values


def read_backend_coverage(path: Path) -> dict[str, float]:
    """Cobertura XML from pytest-cov: root line-rate / branch-rate (0..1) as percentages."""
    try:
        root = ET.parse(path).getroot()
        return {
            "backend_lines": float(root.attrib["line-rate"]) * 100,
            "backend_branches": float(root.attrib["branch-rate"]) * 100,
        }
    except (OSError, ET.ParseError, KeyError, ValueError) as exc:
        raise RatchetError(f"cannot read backend coverage {path}: {exc}") from exc


def read_frontend_coverage(path: Path) -> dict[str, float]:
    """Vitest json-summary: total.lines.pct / total.branches.pct."""
    data = _load_json(path)
    try:
        total = data["total"]
        return {
            "frontend_lines": float(total["lines"]["pct"]),
            "frontend_branches": float(total["branches"]["pct"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise RatchetError(f"cannot read frontend coverage {path}: {exc}") from exc


def read_bundle_stats(path: Path) -> dict[str, float]:
    """bundle-stats.json from scripts/bundle_stats.py (extra keys such as "chunks" ignored)."""
    data = _load_json(path)
    return _exact_keys({key: data.get(key) for key in BUDGET_KEYS}, BUDGET_KEYS, path)


def check(
    baseline: dict[str, float],
    budgets: dict[str, float],
    coverage: dict[str, float],
    bundle: dict[str, float],
) -> list[str]:
    """Report lines; entries starting with FAIL mean the check failed."""
    report: list[str] = []
    for key in COVERAGE_KEYS:
        ok = coverage[key] >= baseline[key]
        verdict = "ok" if ok else "FAIL"
        report.append(f"{verdict} {key}: {coverage[key]:.2f} (baseline {baseline[key]:.2f})")
    for key in BUDGET_KEYS:
        ok = bundle[key] <= budgets[key]
        verdict = "ok" if ok else "FAIL"
        report.append(f"{verdict} {key}: {bundle[key]:.2f} (budget {budgets[key]:.2f})")
    return report


def updated_baseline(baseline: dict[str, float], coverage: dict[str, float]) -> dict[str, float]:
    return {
        key: max(baseline[key], max(FLOOR, math.floor(coverage[key]) - 1.0))
        for key in COVERAGE_KEYS
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("command", choices=("check", "update"))
    parser.add_argument("--baseline", type=Path, default=Path("ratchets/baseline.json"))
    parser.add_argument("--budgets", type=Path, default=Path("ratchets/budgets.json"))
    parser.add_argument(
        "--backend-coverage", type=Path, default=Path("artifacts/backend-coverage/coverage.xml")
    )
    parser.add_argument(
        "--frontend-coverage",
        type=Path,
        default=Path("artifacts/frontend-coverage/coverage-summary.json"),
    )
    parser.add_argument(
        "--bundle-stats", type=Path, default=Path("artifacts/bundle-stats/bundle-stats.json")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        baseline = _exact_keys(_load_json(args.baseline), COVERAGE_KEYS, args.baseline)
        coverage = read_backend_coverage(args.backend_coverage) | read_frontend_coverage(
            args.frontend_coverage
        )
        if args.command == "update":
            new = updated_baseline(baseline, coverage)
            args.baseline.write_text(
                json.dumps(new, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            for key in COVERAGE_KEYS:
                print(f"{key}: {baseline[key]:.2f} -> {new[key]:.2f}")
            return 0
        budgets = _exact_keys(_load_json(args.budgets), BUDGET_KEYS, args.budgets)
        bundle = read_bundle_stats(args.bundle_stats)
    except RatchetError as exc:
        print(f"ratchet: {exc}", file=sys.stderr)
        return 2
    report = check(baseline, budgets, coverage, bundle)
    print("\n".join(report))
    return 1 if any(line.startswith("FAIL") for line in report) else 0


if __name__ == "__main__":
    sys.exit(main())
