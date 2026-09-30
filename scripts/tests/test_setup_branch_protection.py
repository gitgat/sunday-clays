"""Runs setup-branch-protection.sh against a fake `gh` that records every call."""

import json
import os
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "setup-branch-protection.sh"

FAKE_GH = """#!/usr/bin/env bash
if [[ "$1" == "repo" ]]; then echo "gitgat/sunday-clays"; exit 0; fi
body="$(cat)"
printf '%s\\t%s\\t%s\\n' "$3" "$4" "$(printf '%s' "$body" | tr -d '\\n')" >> "$GH_LOG"
if [[ -n "${GH_FAIL_ON:-}" && "$4" == *"$GH_FAIL_ON"* ]]; then
  echo '{"message":"Branch protection needs GitHub Pro here."}' >&2
  exit 1
fi
echo '{}'
"""


def run_with_fake_gh(
    tmp_path: Path, fail_on: str = ""
) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "gh"
    fake.write_text(FAKE_GH)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "gh.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GH_LOG": str(log),
        "GH_FAIL_ON": fail_on,
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )
    calls = [line.split("\t") for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


def test_sets_merge_options_then_protects_main(tmp_path: Path) -> None:
    result, calls = run_with_fake_gh(tmp_path)

    assert result.returncode == 0, result.stderr
    assert [(method, path) for method, path, _ in calls] == [
        ("PATCH", "repos/gitgat/sunday-clays"),
        ("PUT", "repos/gitgat/sunday-clays/branches/main/protection"),
    ]
    assert json.loads(calls[0][2]) == {
        "allow_auto_merge": True,
        "delete_branch_on_merge": True,
        "allow_merge_commit": False,
        "allow_squash_merge": True,
    }
    assert json.loads(calls[1][2]) == {
        "required_status_checks": {"strict": True, "contexts": ["ci-ok"]},
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }


def test_api_error_is_printed_and_exits_1(tmp_path: Path) -> None:
    result, calls = run_with_fake_gh(tmp_path, fail_on="protection")

    assert result.returncode == 1
    assert "Branch protection needs GitHub Pro here." in result.stderr
    assert "branches/main/protection" in result.stderr
    assert len(calls) == 2
