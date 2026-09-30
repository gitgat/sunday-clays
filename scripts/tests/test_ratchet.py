import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "ratchet.py"
BASELINE_90 = {
    "backend_lines": 90.0,
    "backend_branches": 90.0,
    "frontend_lines": 90.0,
    "frontend_branches": 90.0,
}


def write_inputs(
    root: Path,
    *,
    backend: tuple[float, float] = (0.95, 0.93),
    frontend: tuple[float, float] = (94.5, 91.25),
    bundle: tuple[float, float] = (120.0, 900.0),
    baseline: dict[str, float] | None = None,
) -> list[str]:
    """Writes baseline, budgets and the three CI artifacts; returns the CLI path flags."""
    (root / "baseline.json").write_text(json.dumps(baseline or BASELINE_90))
    (root / "budgets.json").write_text(json.dumps({"entry_js_gz_kb": 250, "total_js_gz_kb": 1600}))
    (root / "coverage.xml").write_text(
        f'<?xml version="1.0" ?><coverage line-rate="{backend[0]}" branch-rate="{backend[1]}"/>'
    )
    (root / "coverage-summary.json").write_text(
        json.dumps({"total": {"lines": {"pct": frontend[0]}, "branches": {"pct": frontend[1]}}})
    )
    (root / "bundle-stats.json").write_text(
        json.dumps({"entry_js_gz_kb": bundle[0], "total_js_gz_kb": bundle[1], "chunks": {}})
    )
    return [
        f"--baseline={root / 'baseline.json'}",
        f"--budgets={root / 'budgets.json'}",
        f"--backend-coverage={root / 'coverage.xml'}",
        f"--frontend-coverage={root / 'coverage-summary.json'}",
        f"--bundle-stats={root / 'bundle-stats.json'}",
    ]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_check_passes_when_coverage_meets_baseline_and_bundles_fit(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAIL" not in result.stdout


def test_check_fails_when_backend_branch_coverage_drops(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path, backend=(0.95, 0.899)))

    assert result.returncode == 1
    assert "FAIL backend_branches: 89.90" in result.stdout


def test_check_fails_when_frontend_line_coverage_drops(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path, frontend=(89.99, 95.0)))

    assert result.returncode == 1
    assert "FAIL frontend_lines" in result.stdout


def test_check_fails_when_entry_bundle_exceeds_budget(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path, bundle=(250.01, 900.0)))

    assert result.returncode == 1
    assert "FAIL entry_js_gz_kb" in result.stdout


def test_check_fails_when_total_bundle_exceeds_budget(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path, bundle=(100.0, 1600.5)))

    assert result.returncode == 1
    assert "FAIL total_js_gz_kb" in result.stdout


def test_check_compares_against_a_raised_baseline(tmp_path: Path) -> None:
    raised = BASELINE_90 | {"frontend_branches": 92.0}

    result = run("check", *write_inputs(tmp_path, frontend=(95.0, 91.5), baseline=raised))

    assert result.returncode == 1
    assert "FAIL frontend_branches: 91.50 (baseline 92.00)" in result.stdout


@pytest.mark.parametrize(
    "bad_baseline",
    [
        BASELINE_90 | {"ruff_violations": 0},
        {k: v for k, v in BASELINE_90.items() if k != "backend_lines"},
    ],
)
def test_baseline_must_have_exactly_the_four_coverage_keys(
    tmp_path: Path, bad_baseline: dict[str, float]
) -> None:
    result = run("check", *write_inputs(tmp_path, baseline=bad_baseline))

    assert result.returncode == 2
    assert "baseline.json" in result.stderr


def test_missing_artifact_is_reported_not_crashed(tmp_path: Path) -> None:
    flags = write_inputs(tmp_path)
    (tmp_path / "coverage.xml").unlink()

    result = run("check", *flags)

    assert result.returncode == 2
    assert "coverage.xml" in result.stderr


def test_update_raises_to_floor_minus_one_and_never_lowers(tmp_path: Path) -> None:
    old = {
        "backend_lines": 90.0,
        "backend_branches": 93.0,
        "frontend_lines": 90.0,
        "frontend_branches": 90.0,
    }
    flags = write_inputs(tmp_path, backend=(0.976, 0.912), frontend=(88.0, 90.9), baseline=old)

    result = run("update", *flags)

    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "baseline.json").read_text()) == {
        "backend_branches": 93.0,
        "backend_lines": 96.0,
        "frontend_branches": 90.0,
        "frontend_lines": 90.0,
    }


def test_update_writes_sorted_indented_json(tmp_path: Path) -> None:
    flags = write_inputs(tmp_path, backend=(0.99, 0.99), frontend=(99.0, 99.0))

    run("update", *flags)

    text = (tmp_path / "baseline.json").read_text()
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_update_ignores_bundle_budgets(tmp_path: Path) -> None:
    flags = write_inputs(tmp_path, bundle=(999.0, 9999.0))

    assert run("update", *flags).returncode == 0


def test_committed_ratchet_files_are_well_formed(tmp_path: Path) -> None:
    """The committed files parse and have exactly the expected keys, whatever their values.

    Perfect coverage and empty bundles pass any legal baseline (update never writes above 99)
    and any non-negative budget, so a chore/ratchet-* PR that raises the floors keeps this
    green, while a malformed or mis-keyed committed file still exits 2.
    """
    repo_ratchets = SCRIPT.parents[1] / "ratchets"
    flags = write_inputs(tmp_path, backend=(1.0, 1.0), frontend=(100.0, 100.0), bundle=(0.0, 0.0))
    flags[0] = f"--baseline={repo_ratchets / 'baseline.json'}"
    flags[1] = f"--budgets={repo_ratchets / 'budgets.json'}"

    result = run("check", *flags)

    assert result.returncode == 0, result.stdout + result.stderr
