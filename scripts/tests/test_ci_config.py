"""Durable guard on the shape of the CI workflows (C11); PyYAML reads the `on:` key as True.

Rules that return a list of problems are tested twice: the real workflows must be clean, and a
deliberately weakened ci.yml must be rejected (test_each_rule_rejects_a_weakened_ci_yml).
"""

import copy
import os
import re
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
PIPE = re.compile(r"(?<!\|)\|(?!\|)")  # a pipe, not `||`
# How GitHub-hosted Linux runners run a step's `run:` script file, keyed by the step's `shell:`.
RUNNER_SHELLS: dict[str | None, list[str]] = {
    None: ["bash", "-e"],  # no `shell:` → `bash -e {0}`, so no pipefail
    "bash": ["bash", "--noprofile", "--norc", "-eo", "pipefail"],
}
CI_OK_GATE = {f"contains(needs.*.result, '{r}')" for r in ("failure", "cancelled", "skipped")}
PUBLISH_GATE = (
    "github.ref == 'refs/heads/main' && (github.event_name == 'workflow_dispatch'"
    " || (github.event_name == 'push' && vars.PUBLISH_ON_PUSH == 'true'))"
)
PUBLISH_PERMISSIONS = {"contents": "read", "packages": "write"}
MAIN_ONLY = "github.ref == 'refs/heads/main'"
GIT_ENV = {
    "PATH": os.environ["PATH"],
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "ci-config test",
    "GIT_AUTHOR_EMAIL": "ci-config@example.invalid",
    "GIT_COMMITTER_NAME": "ci-config test",
    "GIT_COMMITTER_EMAIL": "ci-config@example.invalid",
}


def load(name: str) -> dict[Any, Any]:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


CI = load("ci.yml")
PUBLISH = load("publish.yml")
JOBS: dict[str, dict[str, Any]] = CI["jobs"]


def steps(workflow: dict[Any, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            yield name, step


def all_steps(workflow: dict[Any, Any]) -> list[dict[str, Any]]:
    return [step for _, step in steps(workflow)]


def uses(step_or_job: dict[str, Any]) -> str:
    return str(step_or_job.get("uses", ""))


def label(step: dict[str, Any]) -> str:
    return str(step.get("name") or step.get("uses") or str(step.get("run", "")).splitlines()[0])


def needs_of(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


# Rules: each returns the problems it finds in a parsed workflow.


def unpinned_actions(workflow: dict[Any, Any]) -> list[str]:
    """Every action or reusable workflow, `actions/*` included (D1), that is neither local nor
    pinned to a full commit SHA."""
    refs = [uses(step) for step in all_steps(workflow)]
    refs += [uses(job) for job in workflow["jobs"].values()]
    return [ref for ref in refs if ref and not ref.startswith("./") and not SHA_PIN.match(ref)]


def ci_ok_step_problems(workflow: dict[Any, Any]) -> list[str]:
    """ci-ok has one step, `exit 1`, run exactly when some need failed, was cancelled or skipped."""
    ci_ok_steps = workflow["jobs"]["ci-ok"].get("steps", [])
    if len(ci_ok_steps) != 1:
        return ["ci-ok must have exactly one step"]
    step = ci_ok_steps[0]
    problems = []
    if str(step.get("run", "")).strip() != "exit 1":
        problems.append("ci-ok's step must run `exit 1`")
    if {c.strip() for c in str(step.get("if", "")).split("||")} != CI_OK_GATE:
        problems.append(f"ci-ok's step must OR exactly {sorted(CI_OK_GATE)}")
    return problems


def publish_job_problems(workflow: dict[Any, Any]) -> list[str]:
    job = workflow["jobs"]["publish"]
    problems = []
    if needs_of(job) != ["ci-ok"]:
        problems.append("publish must need ci-ok")
    if uses(job) != "./.github/workflows/publish.yml":
        problems.append("publish must call ./.github/workflows/publish.yml")
    if " ".join(str(job.get("if", "")).split()) != PUBLISH_GATE:
        problems.append(f"publish must be gated by {PUBLISH_GATE}")
    if job.get("permissions") != PUBLISH_PERMISSIONS:
        problems.append(f"publish permissions must be {PUBLISH_PERMISSIONS}")
    return problems


def continue_on_error(workflow: dict[Any, Any]) -> list[str]:
    """Jobs and steps that set continue-on-error: their failure would reach ci-ok as success."""
    found = [f"job {name}" for name, job in workflow["jobs"].items() if "continue-on-error" in job]
    found += [f"{name}: {label(s)}" for name, s in steps(workflow) if "continue-on-error" in s]
    return found


def unguarded_pipes(workflow: dict[Any, Any]) -> list[str]:
    """`run:` steps with a pipe but no pipefail, where a failing producer would go unnoticed."""
    default = workflow.get("defaults", {}).get("run", {}).get("shell")
    found = []
    for name, job in workflow["jobs"].items():
        job_default = job.get("defaults", {}).get("run", {}).get("shell", default)
        for step in job.get("steps", []):
            if PIPE.search(str(step.get("run", ""))) and step.get("shell", job_default) != "bash":
                found.append(f"{name}: {label(step)}")
    return found


def racing_uv_caches(workflow: dict[Any, Any]) -> list[str]:
    """Jobs that save the same setup-uv cache key. They race ("Failed to save: … another job may
    be creating this cache"). `enable-cache` defaults to `auto`, which caches on hosted runners."""
    savers: dict[tuple[str, str, str], list[str]] = {}
    for name, step in steps(workflow):
        options = step.get("with") or {}
        if not uses(step).startswith("astral-sh/setup-uv@"):
            continue
        if options.get("enable-cache", "auto") is False or options.get("save-cache") is False:
            continue
        key = (
            str(options.get("cache-dependency-glob", "<default>")).strip(),
            str(options.get("python-version", "")),
            str(options.get("cache-suffix", "")),
        )
        savers.setdefault(key, []).append(name)
    return [f"{' and '.join(jobs)} save one uv cache" for jobs in savers.values() if len(jobs) > 1]


# The real workflows.


def test_ci_ok_always_runs_and_needs_every_other_job() -> None:
    assert "always()" in JOBS["ci-ok"]["if"]
    assert set(JOBS["ci-ok"]["needs"]) == set(JOBS) - {"ci-ok", "publish"}


def test_ci_ok_fails_on_failure_cancellation_or_skip() -> None:
    assert ci_ok_step_problems(CI) == []


def test_publish_runs_only_from_main_after_ci_ok() -> None:
    assert publish_job_problems(CI) == []


def test_publish_workflow_can_only_be_called_and_only_writes_packages() -> None:
    assert set(PUBLISH[True]) == {"workflow_call"}
    assert PUBLISH["permissions"] == PUBLISH_PERMISSIONS


def test_no_other_job_can_be_skipped_by_a_job_level_if() -> None:
    conditional = {name for name, job in JOBS.items() if "if" in job}
    assert conditional <= {"ci-ok", "publish"}


@pytest.mark.parametrize("workflow", ["ci.yml", "publish.yml"])
def test_no_job_or_step_can_continue_on_error(workflow: str) -> None:
    assert continue_on_error(load(workflow)) == []


def test_triggers_run_every_pull_request_and_no_merge_queue() -> None:
    on = CI[True]
    assert "merge_group" not in on
    pull_request = on["pull_request"] or {}
    for key in ("branches", "branches-ignore", "paths", "paths-ignore"):
        assert key not in pull_request
    assert on["push"] == {"branches": ["main"]}
    assert "workflow_dispatch" in on


def test_top_level_permissions_are_read_only() -> None:
    assert CI["permissions"] == {"contents": "read"}


@pytest.mark.parametrize("workflow", ["ci.yml", "publish.yml"])
def test_checkouts_do_not_persist_credentials(workflow: str) -> None:
    checkouts = [s for s in all_steps(load(workflow)) if uses(s).startswith("actions/checkout@")]
    assert checkouts
    for step in checkouts:
        assert step["with"]["persist-credentials"] is False


@pytest.mark.parametrize("workflow", ["ci.yml", "publish.yml"])
def test_every_action_is_pinned_to_a_full_sha(workflow: str) -> None:
    assert unpinned_actions(load(workflow)) == []


@pytest.mark.parametrize("workflow", ["ci.yml", "publish.yml"])
def test_piped_run_steps_use_pipefail(workflow: str) -> None:
    assert unguarded_pipes(load(workflow)) == []


def test_jobs_never_race_to_save_one_uv_cache() -> None:
    assert racing_uv_caches(CI) == []


def build_steps(workflow: dict[Any, Any], job: str) -> list[dict[str, Any]]:
    job_steps = workflow["jobs"][job]["steps"]
    return [s for s in job_steps if uses(s).startswith("docker/build-push-action@")]


# Multi-arch images (Plan 13): each architecture builds natively in its own job, in CI and in
# publish, with its own cache scopes; publish pushes by digest and tags only once both exist.
IMAGES = ("deployer", "backend", "frontend")
RUNNERS = {"amd64": "ubuntu-24.04", "arm64": "ubuntu-24.04-arm"}
CI_IMAGE_JOBS = {"amd64": "docker", "arm64": "docker-arm64"}
# The repo's Actions cache is capped at 10 GB: arm64 keeps only final layers (Plan 13 Decision 21).
CACHE_MODE = {"amd64": "max", "arm64": "min"}


def cache_scope(arch: str, image: str) -> str:
    return image if arch == "amd64" else f"{image}-{arch}"


@pytest.mark.parametrize("arch", list(RUNNERS))
def test_only_main_writes_the_image_build_cache_that_prs_and_publish_read(arch: str) -> None:
    """A PR's cache is visible only to that PR; main's is visible to every PR and to publish."""
    ci_builds, publish_builds = build_steps(CI, CI_IMAGE_JOBS[arch]), build_steps(PUBLISH, arch)
    mode = f"type=gha,mode={CACHE_MODE[arch]},"
    assert [b["with"]["cache-from"] for b in ci_builds] == [
        f"type=gha,scope={cache_scope(arch, image)}" for image in IMAGES
    ]
    assert [b["with"]["cache-from"] for b in publish_builds] == [
        b["with"]["cache-from"] for b in ci_builds
    ]
    for build in ci_builds:
        scope = build["with"]["cache-from"].removeprefix("type=gha,scope=")
        assert build["with"]["cache-to"] == (
            "${{ " + MAIN_ONLY + " && '" + mode + "scope=" + scope + "' || '' }}"
        )
    for build in publish_builds:
        assert build["with"]["cache-to"] == build["with"]["cache-from"].replace("type=gha,", mode)


@pytest.mark.parametrize(
    ("workflow", "job", "arch"),
    [
        ("ci.yml", "docker", "amd64"),
        ("ci.yml", "docker-arm64", "arm64"),
        ("publish.yml", "amd64", "amd64"),
        ("publish.yml", "arm64", "arm64"),
    ],
)
def test_each_image_job_builds_natively_for_its_one_architecture(
    workflow: str, job: str, arch: str
) -> None:
    """Native runners, not QEMU: an emulated arm64 build is slower and bills more minutes."""
    parsed = load(workflow)
    builds = build_steps(parsed, job)

    assert parsed["jobs"][job]["runs-on"] == RUNNERS[arch]
    assert builds
    assert {b["with"]["platforms"] for b in builds} == {f"linux/{arch}"}
    assert not [s for s in all_steps(parsed) if uses(s).startswith("docker/setup-qemu-action@")]


def test_every_arm64_smoke_line_asserts_the_architecture_of_its_image() -> None:
    """The arm64 job builds natively, so each image's smoke line proves it is really aarch64."""
    smoke = next(
        s
        for s in load("ci.yml")["jobs"]["docker-arm64"]["steps"]
        if "Smoke-test" in s.get("name", "")
    )
    lines = [ln for ln in smoke["run"].splitlines() if "docker run" in ln]
    deployer = next(ln for ln in lines if "sunday-clays-deployer" in ln)

    assert 'test "$(uname -m)" = aarch64' in deployer


def test_publish_pushes_each_architecture_by_digest_without_attestations() -> None:
    """Attestation entries would add an unknown/unknown platform to every release list."""
    for arch in RUNNERS:
        job = PUBLISH["jobs"][arch]
        builds = build_steps(PUBLISH, arch)

        assert job["outputs"] == {i: "${{ steps." + i + ".outputs.digest }}" for i in IMAGES}
        assert [b["id"] for b in builds] == list(IMAGES)
        for image, build in zip(IMAGES, builds, strict=True):
            options = build["with"]
            assert options["tags"] == f"ghcr.io/gitgat/sunday-clays-{image}", arch
            assert options["outputs"] == (
                "type=image,push-by-digest=true,name-canonical=true,push=true"
            )
            assert options["provenance"] is False
            assert "push" not in options


def test_publish_tags_a_release_only_once_both_architectures_are_pushed() -> None:
    manifest = PUBLISH["jobs"]["manifest"]
    merges = [s for s in manifest["steps"] if "imagetools create" in str(s.get("run", ""))]

    assert needs_of(manifest) == list(RUNNERS)
    assert len(merges) == 1
    assert merges[0]["env"] == {
        f"{image.upper()}_{arch.upper()}": "${{ needs." + arch + ".outputs." + image + " }}"
        for image in IMAGES
        for arch in RUNNERS
    }
    calls = [line.split() for line in merges[0]["run"].splitlines() if line.startswith("merge ")]
    assert calls == [
        ["merge", image, *(f'"${image.upper()}_{arch.upper()}"' for arch in RUNNERS)]
        for image in IMAGES
    ]


def test_e2e_keeps_diagnostics_on_failure_or_timeout_and_always_stops_the_stack() -> None:
    e2e = JOBS["e2e"]["steps"]
    logs = next(s for s in e2e if s.get("name") == "Compose logs")
    report = next(s for s in e2e if (s.get("with") or {}).get("name") == "playwright-report")
    stop = next(s for s in e2e if "down -v" in str(s.get("run", "")))

    assert logs["if"] == report["if"] == "failure() || cancelled()"
    assert stop["if"] == "always()"
    assert e2e.index(logs) < e2e.index(stop) == len(e2e) - 1


def test_dependabot_updates_actions_uv_and_npm_monthly() -> None:
    config = yaml.safe_load((WORKFLOWS.parent / "dependabot.yml").read_text(encoding="utf-8"))
    updates = {(u["package-ecosystem"], u["directory"]): u for u in config["updates"]}

    assert set(updates) == {("github-actions", "/"), ("uv", "/backend"), ("npm", "/frontend")}
    assert {u["schedule"]["interval"] for u in updates.values()} == {"monthly"}


def test_dependabot_never_proposes_the_pinned_or_held_back_versions() -> None:
    """D1 pins uv/uv_build together; D4 holds these frontend majors on purpose."""
    config = yaml.safe_load((WORKFLOWS.parent / "dependabot.yml").read_text(encoding="utf-8"))
    updates = {u["package-ecosystem"]: u for u in config["updates"]}

    def ignored(ecosystem: str) -> dict[str, list[str]]:
        rules = updates[ecosystem].get("ignore", [])
        return {r["dependency-name"]: r.get("update-types", ["all"]) for r in rules}

    assert ignored("uv") == {"uv-build": ["all"]}
    npm = ignored("npm")
    for held in ("react-router", "typescript", "jsdom", "@types/node"):
        assert npm.get(held) == ["version-update:semver-major"], held


# Weakened copies of ci.yml that the rules above must reject.

Jobs = dict[str, dict[str, Any]]


def step_in(jobs: Jobs, job: str, match: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    return next(step for step in jobs[job]["steps"] if match(step))


def setup_uv(jobs: Jobs, job: str) -> dict[str, Any]:
    step = step_in(jobs, job, lambda s: uses(s).startswith("astral-sh/setup-uv@"))
    options: dict[str, Any] = step["with"]
    return options


def unpin_a_github_action(jobs: Jobs) -> None:
    step_in(jobs, "backend", lambda s: uses(s).startswith("actions/checkout@"))["uses"] = (
        "actions/checkout@v7.0.1"
    )


def ci_ok_exits_0(jobs: Jobs) -> None:
    jobs["ci-ok"]["steps"][0]["run"] = "exit 0"


def ci_ok_ands_its_checks(jobs: Jobs) -> None:
    step = jobs["ci-ok"]["steps"][0]
    step["if"] = step["if"].replace("||", "&&")


def ci_ok_ignores_skipped(jobs: Jobs) -> None:
    jobs["ci-ok"]["steps"][0]["if"] = (
        "contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')"
    )


def ci_ok_gets_a_second_step(jobs: Jobs) -> None:
    jobs["ci-ok"]["steps"].append({"run": "exit 0"})


def publish_off_main(jobs: Jobs) -> None:
    jobs["publish"]["if"] = "github.event_name == 'workflow_dispatch'"


def publish_on_every_push(jobs: Jobs) -> None:
    jobs["publish"]["if"] = PUBLISH_GATE.replace(" && vars.PUBLISH_ON_PUSH == 'true'", "")


def publish_writes_contents(jobs: Jobs) -> None:
    jobs["publish"]["permissions"] = {"contents": "write", "packages": "write"}


def backend_job_may_fail(jobs: Jobs) -> None:
    jobs["backend"]["continue-on-error"] = True


def pytest_step_may_fail(jobs: Jobs) -> None:
    pytest_step = step_in(jobs, "backend", lambda s: "pytest" in str(s.get("run", "")))
    pytest_step["continue-on-error"] = True


def pipe_without_pipefail(jobs: Jobs) -> None:
    step_in(jobs, "stack-config", lambda s: "|" in str(s.get("run", ""))).pop("shell", None)


def frontend_reuses_the_backend_uv_cache_key(jobs: Jobs) -> None:
    setup_uv(jobs, "frontend").update(setup_uv(jobs, "backend"))


def small_jobs_cache_uv_by_default(jobs: Jobs) -> None:
    for job in ("ratchet", "stack-config"):
        setup_uv(jobs, job).pop("enable-cache", None)


Rule = Callable[[dict[Any, Any]], list[str]]


@pytest.mark.parametrize(
    ("rule", "weaken", "message"),
    [
        (unpinned_actions, unpin_a_github_action, "actions/checkout@v7.0.1"),
        (ci_ok_step_problems, ci_ok_exits_0, "`exit 1`"),
        (ci_ok_step_problems, ci_ok_ands_its_checks, "must OR exactly"),
        (ci_ok_step_problems, ci_ok_ignores_skipped, "must OR exactly"),
        (ci_ok_step_problems, ci_ok_gets_a_second_step, "exactly one step"),
        (publish_job_problems, publish_off_main, "must be gated by"),
        (publish_job_problems, publish_on_every_push, "must be gated by"),
        (publish_job_problems, publish_writes_contents, "permissions must be"),
        (continue_on_error, backend_job_may_fail, "job backend"),
        (continue_on_error, pytest_step_may_fail, "backend: "),
        (unguarded_pipes, pipe_without_pipefail, "stack-config: "),
        (racing_uv_caches, frontend_reuses_the_backend_uv_cache_key, "backend and frontend"),
        (racing_uv_caches, small_jobs_cache_uv_by_default, "ratchet and stack-config"),
    ],
    ids=lambda value: getattr(value, "__name__", None),
)
def test_each_rule_rejects_a_weakened_ci_yml(
    rule: Rule, weaken: Callable[[Jobs], None], message: str
) -> None:
    workflow = copy.deepcopy(CI)
    weaken(workflow["jobs"])

    problems = rule(workflow)

    assert any(message in problem for problem in problems), problems


# The ratchets/ guard, run as the runner runs it.


def ratchet_guard() -> dict[str, Any]:
    guards = [s for s in JOBS["ratchet"]["steps"] if "-- ratchets/" in str(s.get("run", ""))]
    assert len(guards) == 1
    return guards[0]


def test_ratchet_guard_runs_on_pull_requests_after_a_full_history_checkout() -> None:
    ratchet_steps = JOBS["ratchet"]["steps"]
    guard = ratchet_guard()
    checkout = next(s for s in ratchet_steps if uses(s).startswith("actions/checkout@"))

    assert guard["if"] == "github.event_name == 'pull_request'"
    assert checkout["with"]["fetch-depth"] == 0
    assert ratchet_steps.index(checkout) < ratchet_steps.index(guard)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True, capture_output=True)


def pull_request_checkout(root: Path, changed: str, base: str, lower: str | None) -> Path:
    """A full-history PR checkout whose base is ``origin/<base>``; HEAD also changes ``changed``.

    ``origin/main`` is the first commit. A stacked base (another stack branch) is a lower layer on
    top of it that changes ``lower``.
    """
    repo = root / "repo"
    (repo / "ratchets").mkdir(parents=True)
    (repo / "ratchets" / "baseline.json").write_text('{"backend_lines": 90.0}\n')
    (repo / "README.md").write_text("base\n")
    git(repo, "init", "--quiet")
    git(repo, "add", ".")
    git(repo, "commit", "--quiet", "-m", "base")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    if base != "main":
        assert lower is not None
        (repo / lower).write_text("lower stack layer\n")
        git(repo, "commit", "--quiet", "-am", "lower stack layer")
        git(repo, "update-ref", f"refs/remotes/origin/{base}", "HEAD")
    (repo / changed).write_text("changed\n")
    git(repo, "commit", "--quiet", "-am", "pull request")
    return repo


@pytest.mark.parametrize(
    ("head_ref", "base_ref", "lower", "changed", "returncode"),
    [
        ("task/01-5-ci", "main", None, "ratchets/baseline.json", 1),
        ("chore/deps-openpyxl", "main", None, "ratchets/baseline.json", 1),
        ("chore/ratchet-wave-1", "main", None, "ratchets/baseline.json", 0),
        ("task/01-5-ci", "main", None, "README.md", 0),
        # Stacked PRs: the base is another stack branch, and only this layer's changes count.
        ("task/03-2-x", "task/03-1-x", "README.md", "ratchets/baseline.json", 1),
        ("task/03-2-x", "task/03-1-x", "ratchets/baseline.json", "README.md", 0),
    ],
)
def test_ratchet_guard_blocks_ratchets_changes_outside_chore_branches(
    tmp_path: Path, head_ref: str, base_ref: str, lower: str | None, changed: str, returncode: int
) -> None:
    repo = pull_request_checkout(tmp_path, changed, base_ref, lower)
    guard = ratchet_guard()
    script = tmp_path / "guard.sh"
    script.write_text(guard["run"])

    result = subprocess.run(
        [*RUNNER_SHELLS[guard.get("shell")], str(script)],
        cwd=repo,
        env={**GIT_ENV, "BASE_REF": base_ref, "HEAD_REF": head_ref},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == returncode, result.stdout + result.stderr
