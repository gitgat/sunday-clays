"""deploy/deployer/deployer.py against fake git, docker and api health endpoints (Plan 13)."""

import fcntl
import importlib.util
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "deployer" / "deployer.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("deployer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["deployer"] = module
    spec.loader.exec_module(module)
    return module


d = _load()

MAIN = "a" * 40
NEXT = "b" * 40
OLD_TAG = "sha-0000000"
GITHUB_TOKEN = "ghp_github_secret_value"
GHCR_TOKEN = "ghp_ghcr_secret_value"
REG = "registry.thehalf.io"  # what the services run
SRC = "ghcr.io/gitgat"  # what CI publishes
BOTH = ["linux/amd64", "linux/arm64"]


def published(*tags: str) -> set[str]:
    """The refs CI has put in GHCR."""
    return {
        f"{SRC}/sunday-clays-{kind}:{tag}"
        for tag in tags
        for kind in ("backend", "frontend", "deployer")
    }


def ref(service: str, tag: str) -> str:
    return f"{REG}/sunday-clays-{d.IMAGE_OF[service]}:{tag}"


def index(name: str, platforms: Sequence[str] = BOTH) -> str:
    """A raw OCI index, as `imagetools inspect --raw` prints it."""
    return json.dumps(
        {
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                {
                    "digest": f"sha256:{name}-{p}",
                    "platform": dict(zip(("os", "architecture"), p.split("/"))),
                }
                for p in platforms
            ],
        }
    )


class Fake:
    """git + docker + the api's /api/health, as the deployer sees them.

    `docker service update` models Swarm: a service in `fail_update` fails and stays put, one in
    `roll_back` is rolled back by Swarm although the CLI exits 0, and an update to the image a
    service already runs while its status is a stale `rollback_completed` exits 1 (the CLI's
    progress watcher reads the old status). `docker service rollback` swaps back to the
    previous spec."""

    def __init__(self) -> None:
        self.main = MAIN
        self.published: set[str] = published(d.tag_for(MAIN), d.tag_for(NEXT), OLD_TAG)
        self.platforms: dict[str, list[str]] = {}  # source ref -> platforms (default BOTH)
        self.local: dict[str, str] = {}  # fleet-registry ref -> raw index
        self.fail_create: set[str] = set()  # source refs whose `imagetools create` fails
        self.images = {f"sundayclays_{s}": ref(s, OLD_TAG) for s in d.ORDER}
        self.previous = dict(self.images)
        self.status = {name: "completed" for name in self.images}
        self.fail_update: set[str] = set()
        self.roll_back: set[str] = set()
        self.fail_rollback: set[str] = set()
        self.manifest_stderr = "no such manifest: {ref}"
        self.api_reports_version = True
        self.calls: list[list[str]] = []
        self.envs: list[Mapping[str, str] | None] = []
        self.inputs: list[str | None] = []
        self.git_rc = 0
        self.git_stderr = ""
        self.now = 1000.0

    def run(
        self,
        argv: Sequence[str],
        *,
        input: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = 60.0,
    ) -> subprocess.CompletedProcess[str]:
        argv = list(argv)
        self.calls.append(argv)
        self.envs.append(env)
        self.inputs.append(input)

        def done(rc: int, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, rc, out, err)

        if argv[:2] == ["git", "ls-remote"]:
            return done(
                self.git_rc,
                f"{self.main}\t{argv[3]}\n" if self.git_rc == 0 else "",
                self.git_stderr,
            )
        if argv[:2] == ["docker", "login"]:
            return done(0, "Login Succeeded\n")
        if argv[:3] == ["docker", "manifest", "inspect"]:
            if argv[3] in self.published:
                return done(0)
            return done(1, err=self.manifest_stderr.format(ref=argv[3]))
        if argv[:4] == ["docker", "buildx", "imagetools", "inspect"]:
            target = argv[-1]
            if target in self.local:
                return done(0, self.local[target])
            if target in self.published:
                return done(0, index(target, self.platforms.get(target, BOTH)))
            return done(1, err=f"{target}: not found")
        if argv[:4] == ["docker", "buildx", "imagetools", "create"]:
            dst, src = argv[argv.index("--tag") + 1], argv[-1]
            if src in self.fail_create:
                return done(1, err="ERROR: failed to push: denied")
            self.local[dst] = index(src, self.platforms.get(src, BOTH))
            return done(0)
        if argv[:3] == ["docker", "service", "update"]:
            name, image = argv[-1], argv[argv.index("--image") + 1]
            if name in self.fail_update:
                self.status[name] = "rollback_completed"
                return done(1, err="service rolled back: failure")
            if self.images[name] == image and self.status[name] == "rollback_completed":
                return done(1, err="service rolled back: rollback completed")
            if name in self.roll_back:
                self.status[name] = "rollback_completed"
                return done(0)
            self.previous[name], self.images[name] = self.images[name], image
            self.status[name] = "completed"
            return done(0)
        if argv[:3] == ["docker", "service", "rollback"]:
            name = argv[-1]
            if name in self.fail_rollback:
                return done(1, err="rollback failed")
            self.images[name], self.previous[name] = self.previous[name], self.images[name]
            self.status[name] = "rollback_completed"
            return done(0)
        if argv[:3] == ["docker", "service", "inspect"]:
            body = [
                {
                    "Spec": {
                        "Name": name,
                        "TaskTemplate": {
                            "ContainerSpec": {"Image": self.images[name] + "@sha256:" + "f" * 64}
                        },
                    },
                    "UpdateStatus": {"State": self.status[name]},
                }
                for name in argv[3:]
            ]
            return done(0, json.dumps(body))
        raise AssertionError(f"unexpected command {argv}")

    def fetch(self, url: str, timeout: float) -> str:
        assert url == "http://api:8000/api/health"
        version = self.images["sundayclays_api"].rsplit(":", 1)[1]
        if not self.api_reports_version:
            version = OLD_TAG
        return json.dumps({"status": "ok", "version": version})

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def updates(self) -> list[str]:
        return [c[-1] for c in self.calls if c[:3] == ["docker", "service", "update"]]

    def creates(self) -> list[str]:
        return [
            c[c.index("--tag") + 1]
            for c in self.calls
            if c[:4] == ["docker", "buildx", "imagetools", "create"]
        ]

    def rollbacks(self) -> list[str]:
        return [c[-1] for c in self.calls if c[:3] == ["docker", "service", "rollback"]]

    def tags(self) -> set[str]:
        return {image.rsplit(":", 1)[1] for image in self.images.values()}


@pytest.fixture
def fake() -> Fake:
    return Fake()


@pytest.fixture
def logs() -> list[str]:
    return []


@pytest.fixture
def deps(fake: Fake, logs: list[str]) -> Any:
    return d.Deps(
        run=fake.run,
        fetch=fake.fetch,
        sleep=fake.sleep,
        clock=fake.clock,
        now=lambda: datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
        log=logs.append,
    )


@pytest.fixture
def cfg(tmp_path: Path) -> Any:
    (tmp_path / "github_token").write_text(GITHUB_TOKEN + "\n")
    (tmp_path / "ghcr_token").write_text(GHCR_TOKEN + "\n")
    return d.Config.from_env(
        {
            "GHCR_USER": "gitgat-bot",
            "GITHUB_TOKEN_FILE": str(tmp_path / "github_token"),
            "GHCR_TOKEN_FILE": str(tmp_path / "ghcr_token"),
            "STATE_DIR": str(tmp_path / "state"),
            "HEARTBEAT_FILE": str(tmp_path / "heartbeat"),
        }
    )


APP = [f"sundayclays_{s}" for s in ("api", "worker", "caddy", "backup")]


def seed_history(cfg: Any, tag: str) -> None:
    """Rollback accepts only tags the deployer itself deployed (Decision 23)."""
    d.record(cfg.state_dir, sha="", tag=tag, when=datetime.now(UTC), how="auto")


def test_new_main_sha_updates_api_worker_caddy_backup_in_order_and_records_it(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    assert d.tick(cfg, deps, set()) == "deployed"

    assert fake.updates() == APP
    assert all(
        "--image" in c and "--with-registry-auth" not in c
        for c in fake.calls
        if c[:3] == ["docker", "service", "update"]
    )
    assert fake.images["sundayclays_caddy"] == f"{REG}/sunday-clays-frontend:sha-aaaaaaa"
    assert fake.images["sundayclays_worker"] == f"{REG}/sunday-clays-backend:sha-aaaaaaa"
    state = d.load_state(cfg.state_dir)
    assert (state["sha"], state["tag"]) == (MAIN, "sha-aaaaaaa")
    assert state["history"][0]["how"] == "auto"


def test_db_and_the_deployer_itself_are_never_updated(cfg: Any, deps: Any, fake: Fake) -> None:
    d.tick(cfg, deps, set())
    d.tick(cfg, deps, set())

    touched = " ".join(" ".join(c) for c in fake.calls)
    assert "sundayclays_db" not in touched
    assert "sundayclays_deployer" not in touched


def test_worker_is_updated_only_after_api_reports_the_new_version(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    seen: list[str] = []
    real_fetch = fake.fetch

    def fetch(url: str, timeout: float) -> str:
        seen.append(",".join(fake.updates()))
        return real_fetch(url, timeout)

    deps.fetch = fetch
    d.tick(cfg, deps, set())

    assert seen == ["sundayclays_api"]


def test_unchanged_sha_only_reads_the_running_images(cfg: Any, deps: Any, fake: Fake) -> None:
    d.tick(cfg, deps, set())
    fake.calls.clear()

    assert d.tick(cfg, deps, set()) == "unchanged"
    assert [c[:2] for c in fake.calls] == [["git", "ls-remote"], ["docker", "service"]]
    assert fake.calls[1] == ["docker", "service", "inspect", *APP]  # one call, no login


def test_drift_from_a_hand_stack_deploy_is_redeployed(
    cfg: Any, deps: Any, fake: Fake, logs: list[str]
) -> None:
    """A hand `docker stack deploy` with a stale IMAGE_TAG while main is unchanged."""
    d.tick(cfg, deps, set())
    fake.images = {f"sundayclays_{s}": ref(s, OLD_TAG) for s in d.ORDER}
    fake.calls.clear()

    assert d.tick(cfg, deps, set()) == "deployed"
    assert fake.updates() == APP
    assert fake.tags() == {"sha-aaaaaaa"}
    assert any(line.startswith("drift: sundayclays_api runs") for line in logs)
    assert d.load_state(cfg.state_dir)["history"][0]["how"] == "drift"


def test_a_service_still_updating_is_not_drift(cfg: Any, deps: Any, fake: Fake) -> None:
    d.tick(cfg, deps, set())
    fake.images["sundayclays_caddy"] = ref("caddy", OLD_TAG)
    fake.status["sundayclays_caddy"] = "updating"
    fake.calls.clear()

    assert d.tick(cfg, deps, set()) == "unchanged"
    assert fake.updates() == []


@pytest.mark.parametrize("kind", ["backend", "frontend", "deployer"])
def test_waits_while_any_image_is_unpublished(
    cfg: Any, deps: Any, fake: Fake, logs: list[str], kind: str
) -> None:
    fake.published.discard(f"{SRC}/sunday-clays-{kind}:sha-aaaaaaa")

    assert d.tick(cfg, deps, set()) == "waiting"
    assert fake.updates() == []
    assert d.load_state(cfg.state_dir) == {}
    assert f"sunday-clays-{kind}:sha-aaaaaaa" in logs[-1]

    fake.published |= published("sha-aaaaaaa")
    assert d.tick(cfg, deps, set()) == "deployed"


def test_waiting_is_logged_once_per_sha(cfg: Any, deps: Any, fake: Fake, logs: list[str]) -> None:
    """A main commit that failed CI never publishes: that must not log every poll forever."""
    fake.published = published(OLD_TAG)
    waiting: set[str] = set()

    for _ in range(3):
        assert d.tick(cfg, deps, set(), waiting) == "waiting"

    assert sum("waiting for" in line for line in logs) == 1


def test_a_registry_error_is_not_mistaken_for_waiting(cfg: Any, deps: Any, fake: Fake) -> None:
    fake.published = set()
    fake.manifest_stderr = "unauthorized: authentication required"

    with pytest.raises(d.DeployError, match="manifest inspect .* failed: unauthorized"):
        d.tick(cfg, deps, set())


def test_api_that_never_reports_the_new_version_stops_the_deploy_and_records_nothing(
    cfg: Any, deps: Any, fake: Fake, logs: list[str]
) -> None:
    fake.api_reports_version = False
    failed: set[str] = set()

    assert d.tick(cfg, deps, failed) == "failed"
    assert fake.updates() == ["sundayclays_api"]
    assert fake.rollbacks() == ["sundayclays_api"]
    assert fake.tags() == {OLD_TAG}
    state = d.load_state(cfg.state_dir)
    assert "sha" not in state and "tag" not in state
    assert state["last_failure"]["tag"] == "sha-aaaaaaa"
    assert failed == {MAIN}
    assert "FAILED" in logs[-1] and "sha-aaaaaaa" in logs[-1]
    assert "rolled back sundayclays_api" in logs[-1]
    assert fake.now >= 1000.0 + cfg.health_timeout


def test_failed_worker_update_rolls_api_back_and_leaves_caddy_and_backup_alone(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    fake.fail_update.add("sundayclays_worker")

    assert d.tick(cfg, deps, set()) == "failed"
    assert fake.updates() == ["sundayclays_api", "sundayclays_worker"]
    assert fake.rollbacks() == ["sundayclays_api"]
    assert fake.tags() == {OLD_TAG}
    assert "sha" not in d.load_state(cfg.state_dir)


def test_failure_after_api_rolls_the_earlier_services_back(
    cfg: Any, deps: Any, fake: Fake, logs: list[str]
) -> None:
    """Swarm rolled caddy back (the CLI exited 0): api and worker must not stay on the new
    release beside the old frontend."""
    fake.roll_back.add("sundayclays_caddy")

    assert d.tick(cfg, deps, set()) == "failed"
    assert fake.updates() == APP[:3]
    assert fake.rollbacks() == ["sundayclays_worker", "sundayclays_api"]
    assert fake.tags() == {OLD_TAG}
    assert "sha" not in d.load_state(cfg.state_dir)
    assert "rolled back sundayclays_worker, sundayclays_api" in logs[-1]


def test_a_failed_rollback_is_logged_and_the_others_still_roll_back(
    cfg: Any, deps: Any, fake: Fake, logs: list[str]
) -> None:
    fake.roll_back.add("sundayclays_caddy")
    fake.fail_rollback.add("sundayclays_worker")

    assert d.tick(cfg, deps, set()) == "failed"
    assert fake.rollbacks() == ["sundayclays_worker", "sundayclays_api"]
    assert any("sundayclays_worker: docker service rollback failed" in line for line in logs)
    assert "rolled back sundayclays_api" in logs[-1]


def test_a_failed_sha_is_not_retried_every_poll(cfg: Any, deps: Any, fake: Fake) -> None:
    fake.fail_update.add("sundayclays_api")
    failed: set[str] = set()
    d.tick(cfg, deps, failed)
    fake.calls.clear()

    assert d.tick(cfg, deps, failed) == "failed-before"
    assert [c[0] for c in fake.calls] == ["git"]


def test_a_newer_sha_after_a_failure_is_deployed(cfg: Any, deps: Any, fake: Fake) -> None:
    fake.fail_update.add("sundayclays_api")
    failed: set[str] = set()
    d.tick(cfg, deps, failed)
    fake.fail_update.clear()
    fake.main = NEXT

    assert d.tick(cfg, deps, failed) == "deployed"
    assert d.load_state(cfg.state_dir)["tag"] == "sha-bbbbbbb"


def test_restart_after_success_is_a_no_op(cfg: Any, deps: Any, fake: Fake) -> None:
    d.tick(cfg, deps, set())
    fake.calls.clear()

    assert d.tick(cfg, deps, set()) == "unchanged"  # fresh `failed`, as after a restart
    assert fake.updates() == []


def test_restart_after_failure_tries_that_sha_once_more(cfg: Any, deps: Any, fake: Fake) -> None:
    fake.fail_update.add("sundayclays_api")
    d.tick(cfg, deps, set())
    fake.fail_update.clear()

    assert d.tick(cfg, deps, set()) == "deployed"


def test_services_already_on_the_target_are_not_updated(
    cfg: Any, deps: Any, fake: Fake, logs: list[str]
) -> None:
    """A deployer restarted with an empty state (killed before recording, or moved to another
    manager) records the live release without a single `docker service update`."""
    d.tick(cfg, deps, set())
    (cfg.state_dir / "state.json").unlink()
    fake.calls.clear()

    assert d.tick(cfg, deps, set()) == "deployed"
    assert fake.updates() == []
    assert d.load_state(cfg.state_dir)["tag"] == "sha-aaaaaaa"
    assert "deploy sha-aaaaaaa: sundayclays_backup already on sha-aaaaaaa" in logs


def test_rollback_to_the_image_swarm_already_rolled_back_to_succeeds(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    """Swarm auto-rolled caddy back to the old image; its status still reads rollback_completed.
    Updating it to that same image would exit 1, so it is skipped and backup still updates."""
    seed_history(cfg, OLD_TAG)
    d.tick(cfg, deps, set())
    fake.images["sundayclays_caddy"] = ref("caddy", OLD_TAG)
    fake.status["sundayclays_caddy"] = "rollback_completed"
    fake.calls.clear()

    d.rollback(cfg, deps, OLD_TAG)

    assert fake.updates() == ["sundayclays_api", "sundayclays_worker", "sundayclays_backup"]
    assert fake.tags() == {OLD_TAG}
    assert d.load_state(cfg.state_dir)["tag"] == OLD_TAG


def test_paused_deployer_does_not_even_ask_github(cfg: Any, deps: Any, fake: Fake) -> None:
    d.set_paused(cfg.state_dir, "maintenance")

    assert d.tick(cfg, deps, set()) == "paused"
    assert fake.calls == []

    d.set_paused(cfg.state_dir, None)
    assert d.tick(cfg, deps, set()) == "deployed"


def test_rollback_deploys_the_old_tag_in_order_records_it_and_pauses(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    seed_history(cfg, OLD_TAG)
    d.tick(cfg, deps, set())
    fake.calls.clear()

    d.rollback(cfg, deps, OLD_TAG)

    assert fake.updates() == APP
    state = d.load_state(cfg.state_dir)
    assert (state["tag"], state["sha"]) == (OLD_TAG, "")
    assert state["paused"].startswith(f"rollback to {OLD_TAG}")
    assert [h["how"] for h in state["history"]] == ["rollback", "auto", "auto"]
    assert d.tick(cfg, deps, set()) == "paused"


@pytest.mark.parametrize("tag", ["latest", "sha-abc", "sha-ABCDEF0", "0000000"])
def test_rollback_refuses_anything_but_a_sha_tag(cfg: Any, deps: Any, fake: Fake, tag: str) -> None:
    with pytest.raises(d.DeployError, match="not a sha-<7> tag"):
        d.rollback(cfg, deps, tag)
    assert fake.calls == []


def test_rollback_to_an_unpublished_tag_changes_nothing(cfg: Any, deps: Any, fake: Fake) -> None:
    seed_history(cfg, "sha-1234567")
    before = d.load_state(cfg.state_dir)
    with pytest.raises(d.DeployError, match="not published to ghcr.io/gitgat"):
        d.rollback(cfg, deps, "sha-1234567")

    assert fake.updates() == []
    assert d.load_state(cfg.state_dir) == before


def test_rollback_refuses_a_tag_outside_the_deployers_history(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    """Published in the registry but never deployed by this deployer (maybe amd64-only or
    pre-rollback-safe): refused before any docker call, nothing paused."""
    d.tick(cfg, deps, set())
    fake.calls.clear()
    before = d.load_state(cfg.state_dir)

    with pytest.raises(d.DeployError, match="not in the deployer's history"):
        d.rollback(cfg, deps, OLD_TAG)

    assert fake.calls == []
    assert d.load_state(cfg.state_dir) == before


def test_a_failed_rollback_after_pausing_leaves_a_last_failure_for_status(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    seed_history(cfg, OLD_TAG)
    d.tick(cfg, deps, set())
    fake.fail_update.add("sundayclays_api")

    with pytest.raises(d.DeployError):
        d.rollback(cfg, deps, OLD_TAG)

    state = d.load_state(cfg.state_dir)
    assert state["paused"].startswith(f"rollback to {OLD_TAG}")
    assert state["last_failure"]["tag"] == OLD_TAG
    assert state["last_failure"]["reason"]


def test_deploy_lock_keeps_a_rollback_and_the_poll_loop_apart(tmp_path: Path) -> None:
    """`docker exec … rollback` runs beside the loop in the same container: one deploy at a time."""
    with d.deploy_lock(tmp_path), (tmp_path / "deploy.lock").open("w") as other:
        with pytest.raises(BlockingIOError):
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

    with (tmp_path / "deploy.lock").open("w") as other:
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)  # released on exit


def test_github_token_reaches_git_only_through_its_environment(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    d.tick(cfg, deps, set())

    git_env = fake.envs[0]
    assert git_env is not None
    assert GITHUB_TOKEN not in " ".join(fake.calls[0])
    assert git_env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert git_env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
    assert git_env["GIT_TERMINAL_PROMPT"] == "0"
    assert not any(GHCR_TOKEN in " ".join(c) or GITHUB_TOKEN in " ".join(c) for c in fake.calls)
    assert fake.inputs[1] == GHCR_TOKEN + "\n"  # docker login --password-stdin
    assert (
        list(cfg.state_dir.iterdir())
        and GITHUB_TOKEN not in (cfg.state_dir / "state.json").read_text()
    )


def test_git_failure_is_reported_without_the_token(cfg: Any, deps: Any, fake: Fake) -> None:
    fake.git_rc = 128
    fake.git_stderr = f"fatal: Authentication failed for token {GITHUB_TOKEN}"

    with pytest.raises(d.DeployError) as error:
        d.tick(cfg, deps, set())

    assert "exit 128" in str(error.value)
    assert GITHUB_TOKEN not in str(error.value)


def test_a_branch_git_cannot_find_is_an_error(cfg: Any, deps: Any, fake: Fake) -> None:
    deps.run = lambda argv, **_: subprocess.CompletedProcess(argv, 0, "", "")

    with pytest.raises(d.DeployError, match="refs/heads/main not found"):
        d.remote_sha(cfg, deps)


@pytest.mark.parametrize("content", [None, "", "  \n"])
def test_a_missing_or_blank_token_file_is_an_error(
    cfg: Any, deps: Any, content: str | None
) -> None:
    if content is None:
        cfg.github_token_file.unlink()
    else:
        cfg.github_token_file.write_text(content)

    with pytest.raises(d.DeployError, match="secret"):
        d.tick(cfg, deps, set())


def test_login_needs_a_user(cfg: Any, deps: Any) -> None:
    with pytest.raises(d.DeployError, match="GHCR_USER"):
        d.login(d.Config(ghcr_token_file=cfg.ghcr_token_file), deps)


def test_failed_login_is_reported_without_the_token(cfg: Any, deps: Any) -> None:
    deps.run = lambda argv, **_: subprocess.CompletedProcess(argv, 1, "", f"denied {GHCR_TOKEN}")

    with pytest.raises(d.DeployError) as error:
        d.login(cfg, deps)

    assert GHCR_TOKEN not in str(error.value)


@pytest.mark.parametrize(("rc", "stdout"), [(1, ""), (0, "not json"), (0, "[]"), (0, "[1]")])
def test_failed_or_unreadable_inspect_fails_the_update(
    cfg: Any, deps: Any, fake: Fake, rc: int, stdout: str
) -> None:
    def run(argv: Sequence[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        if list(argv[:3]) == ["docker", "service", "inspect"]:
            return subprocess.CompletedProcess(list(argv), rc, stdout, "boom")
        return fake.run(argv, **kw)

    deps.run = run
    with pytest.raises(d.DeployError, match="sundayclays_api"):
        d.update_service(cfg, "api", "sha-aaaaaaa", deps)


def test_health_wait_survives_connection_errors_and_garbage(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    answers: list[Any] = [
        ConnectionRefusedError(),
        "<html>",
        '["x"]',
        json.dumps({"status": "ok", "version": "sha-aaaaaaa"}),
    ]

    def fetch(url: str, timeout: float) -> str:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return str(answer)

    deps.fetch = fetch
    d.wait_for_version(cfg, "sha-aaaaaaa", deps)

    assert answers == []


def test_a_half_read_health_response_is_retried_not_fatal(cfg: Any, deps: Any) -> None:
    """uvicorn restarting can cut a response short: IncompleteRead is an HTTPException, not OSError."""
    import http.client

    answers: list[Any] = [
        http.client.IncompleteRead(b"{"),
        http.client.BadStatusLine("x"),
        json.dumps({"status": "ok", "version": "sha-aaaaaaa"}),
    ]

    def fetch(url: str, timeout: float) -> str:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return str(answer)

    deps.fetch = fetch
    d.wait_for_version(cfg, "sha-aaaaaaa", deps)

    assert answers == []


def test_a_generic_not_found_is_an_error_not_waiting(cfg: Any, deps: Any, fake: Fake) -> None:
    fake.published = set()
    fake.manifest_stderr = "proxy: upstream not found"

    with pytest.raises(d.DeployError, match="manifest inspect .* failed: proxy"):
        d.tick(cfg, deps, set())


def test_ghcr_manifest_not_found_still_counts_as_waiting(cfg: Any, deps: Any, fake: Fake) -> None:
    fake.published = set()
    fake.manifest_stderr = "manifest for {ref} not found: manifest unknown"

    assert d.tick(cfg, deps, set()) == "waiting"


def test_serve_survives_a_state_volume_error(
    cfg: Any, deps: Any, fake: Fake, logs: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_state_dir: Path) -> Any:
        raise OSError("read-only file system")

    monkeypatch.setattr(d, "deploy_lock", broken)
    polls: list[int] = []

    def stopping() -> bool:
        polls.append(1)
        return len(polls) > 2

    assert d.serve(cfg, deps, stopping) == 0
    assert any("poll failed: read-only file system" in line for line in logs)


@pytest.mark.parametrize("command", [["run"], ["once"], ["rollback", OLD_TAG]])
def test_cli_needs_ghcr_user_up_front(
    cfg: Any, deps: Any, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    env = {
        "GITHUB_TOKEN_FILE": str(cfg.github_token_file),
        "GHCR_TOKEN_FILE": str(cfg.ghcr_token_file),
        "STATE_DIR": str(cfg.state_dir),
    }

    assert d.main(command, env, deps) == 1
    assert "GHCR_USER is not set" in capsys.readouterr().err


def test_corrupt_state_file_is_treated_as_empty(cfg: Any, deps: Any) -> None:
    cfg.state_dir.mkdir()
    (cfg.state_dir / "state.json").write_text("{not json")

    assert d.load_state(cfg.state_dir) == {}
    assert d.tick(cfg, deps, set()) == "deployed"


def test_history_keeps_the_newest_twenty(cfg: Any) -> None:
    for i in range(25):
        d.record(
            cfg.state_dir, sha=f"{i:040x}", tag=f"sha-{i:07x}", when=datetime.now(UTC), how="auto"
        )

    history = d.load_state(cfg.state_dir)["history"]
    assert len(history) == 20
    assert history[0]["tag"] == "sha-0000018"


def test_environment_defaults_and_limits() -> None:
    cfg = d.Config.from_env({})
    assert (cfg.poll_interval, cfg.branch, cfg.stack) == (120.0, "main", "sundayclays")
    assert cfg.repo_url == "https://github.com/gitgat/sunday-clays.git"
    with pytest.raises(d.DeployError, match="POLL_INTERVAL must be at least 30"):
        d.Config.from_env({"POLL_INTERVAL": "5"})
    with pytest.raises(d.DeployError, match="bad number"):
        d.Config.from_env({"POLL_INTERVAL": "two minutes"})


def test_run_command_turns_a_timeout_into_a_deploy_error() -> None:
    with pytest.raises(d.DeployError, match="timed out"):
        d.run_command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)
    assert d.run_command([sys.executable, "-c", "print('hi')"]).stdout == "hi\n"


def test_serve_keeps_polling_after_errors_and_stops_on_request(
    cfg: Any, deps: Any, fake: Fake, logs: list[str]
) -> None:
    fake.git_rc = 1
    polls: list[int] = []

    def stopping() -> bool:
        polls.append(1)
        return len([c for c in fake.calls if c[0] == "git"]) >= 2

    assert d.serve(cfg, deps, stopping) == 0
    assert sum("poll failed" in line for line in logs) == 2
    assert cfg.heartbeat_file.exists()
    assert fake.now >= 1000.0 + cfg.poll_interval


def test_cli_pause_status_resume(cfg: Any, deps: Any, capsys: pytest.CaptureFixture[str]) -> None:
    env = {"STATE_DIR": str(cfg.state_dir)}

    assert d.main(["pause", "club", "shoot", "today"], env, deps) == 0
    assert d.main(["status"], env, deps) == 0
    assert json.loads(capsys.readouterr().out)["paused"] == "club shoot today"
    assert d.main(["resume"], env, deps) == 0
    assert d.main(["status"], env, deps) == 0
    assert "paused" not in json.loads(capsys.readouterr().out)


def test_cli_once_tag_and_rollback(cfg: Any, deps: Any, capsys: pytest.CaptureFixture[str]) -> None:
    env = {
        "GHCR_USER": "gitgat-bot",
        "GITHUB_TOKEN_FILE": str(cfg.github_token_file),
        "GHCR_TOKEN_FILE": str(cfg.ghcr_token_file),
        "STATE_DIR": str(cfg.state_dir),
    }

    assert d.main(["tag"], env, deps) == 1
    assert "no deploy recorded" in capsys.readouterr().err
    seed_history(cfg, OLD_TAG)
    assert d.main(["once"], env, deps) == 0
    assert capsys.readouterr().out.strip() == "deployed"
    assert d.main(["tag"], env, deps) == 0
    assert capsys.readouterr().out.strip() == "sha-aaaaaaa"
    assert d.main(["rollback", OLD_TAG], env, deps) == 0
    assert d.main(["rollback", "latest"], env, deps) == 1
    assert "not a sha-<7> tag" in capsys.readouterr().err


def test_cli_rejects_a_bad_environment(deps: Any, capsys: pytest.CaptureFixture[str]) -> None:
    assert d.main(["status"], {"POLL_INTERVAL": "1"}, deps) == 1
    assert "POLL_INTERVAL" in capsys.readouterr().err


def test_cli_run_stops_on_sigterm(cfg: Any, deps: Any, fake: Fake) -> None:
    import signal

    env = {
        "GHCR_USER": "gitgat-bot",
        "GITHUB_TOKEN_FILE": str(cfg.github_token_file),
        "GHCR_TOKEN_FILE": str(cfg.ghcr_token_file),
        "STATE_DIR": str(cfg.state_dir),
        "HEARTBEAT_FILE": str(cfg.heartbeat_file),
    }
    previous = signal.getsignal(signal.SIGTERM)
    deps.sleep = lambda _s: signal.raise_signal(signal.SIGTERM)
    try:
        assert d.main(["run"], env, deps) == 0
    finally:
        signal.signal(signal.SIGTERM, previous)
    assert d.load_state(cfg.state_dir)["tag"] == "sha-aaaaaaa"


def test_script_prints_help() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0
    assert "rollback" in result.stdout


# --- Task 8: mirror GHCR -> the fleet registry -------------------------------------------------


def local(kind: str, tag: str) -> str:
    return f"{REG}/sunday-clays-{kind}:{tag}"


def test_mirror_copies_all_three_indexes_and_checks_both_platforms(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    d.mirror(cfg, "sha-aaaaaaa", deps)

    assert fake.creates() == [local(k, "sha-aaaaaaa") for k in ("backend", "frontend", "deployer")]
    create = next(c for c in fake.calls if c[:4] == ["docker", "buildx", "imagetools", "create"])
    assert create[-1] == f"{SRC}/sunday-clays-backend:sha-aaaaaaa"  # registry to registry
    assert not any(c[:2] in (["docker", "pull"], ["docker", "push"]) for c in fake.calls)
    for raw in fake.local.values():
        platforms = {
            f"{m['platform']['os']}/{m['platform']['architecture']}"
            for m in json.loads(raw)["manifests"]
        }
        assert platforms == set(BOTH)


def test_mirror_runs_before_any_service_update_and_names_the_local_refs(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    assert d.tick(cfg, deps, set()) == "deployed"

    first_update = next(
        i for i, c in enumerate(fake.calls) if c[:3] == ["docker", "service", "update"]
    )
    last_create = max(
        i for i, c in enumerate(fake.calls) if c[:4] == ["docker", "buildx", "imagetools", "create"]
    )
    assert last_create < first_update
    assert all(image.startswith(f"{REG}/") for image in fake.images.values())
    assert len(fake.creates()) == 3


@pytest.mark.parametrize(
    "platforms",
    [
        ["linux/amd64"],
        ["linux/arm64"],
        [*BOTH, "unknown/unknown"],
        ["linux/amd64", "linux/arm/v7"],
        [],
    ],
)
def test_a_source_without_exactly_both_platforms_updates_nothing(
    cfg: Any, deps: Any, fake: Fake, logs: list[str], platforms: list[str]
) -> None:
    fake.platforms[f"{SRC}/sunday-clays-frontend:sha-aaaaaaa"] = platforms
    failed: set[str] = set()

    assert d.tick(cfg, deps, failed) == "failed"

    assert fake.updates() == []
    assert fake.tags() == {OLD_TAG}
    assert local("frontend", "sha-aaaaaaa") not in fake.local  # the bad index never lands
    assert failed == {MAIN}
    state = d.load_state(cfg.state_dir)
    assert "sha" not in state and "platforms are" in state["last_failure"]["reason"]


def test_a_copy_that_lands_with_the_wrong_platforms_is_caught(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    """Belt and braces: a per-arch copy in the fleet registry must fail the deploy."""
    src = f"{SRC}/sunday-clays-backend:sha-aaaaaaa"
    real = fake.run

    def run(argv: Sequence[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        result = real(argv, **kw)
        if list(argv[:4]) == ["docker", "buildx", "imagetools", "create"] and argv[-1] == src:
            fake.local[argv[argv.index("--tag") + 1]] = index("x", ["linux/amd64"])
        return result

    deps.run = run
    with pytest.raises(d.DeployError, match="platforms are linux/amd64"):
        d.mirror(cfg, "sha-aaaaaaa", deps)


@pytest.mark.parametrize(
    "raw", ["not json", "{}", '{"manifests": [1]}', '{"manifests": [{"platform": {}}]}']
)
def test_a_source_that_is_not_an_index_is_refused(
    cfg: Any, deps: Any, fake: Fake, raw: str
) -> None:
    real = fake.run

    def run(argv: Sequence[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        if list(argv[:4]) == ["docker", "buildx", "imagetools", "inspect"]:
            return subprocess.CompletedProcess(list(argv), 0, raw, "")
        return real(argv, **kw)

    deps.run = run
    with pytest.raises(d.DeployError, match="not a multi-arch index"):
        d.mirror(cfg, "sha-aaaaaaa", deps)
    assert fake.creates() == []


def test_mirror_skips_an_image_whose_index_already_matches(
    cfg: Any, deps: Any, fake: Fake, logs: list[str]
) -> None:
    d.mirror(cfg, "sha-aaaaaaa", deps)
    fake.calls.clear()

    d.mirror(cfg, "sha-aaaaaaa", deps)

    assert fake.creates() == []
    assert sum("already there" in line for line in logs) == 3


def test_mirror_recopies_only_the_image_that_is_missing_or_different(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    d.mirror(cfg, "sha-aaaaaaa", deps)
    del fake.local[local("frontend", "sha-aaaaaaa")]  # e.g. removed by a registry GC
    fake.local[local("deployer", "sha-aaaaaaa")] = index("stale")
    fake.calls.clear()

    d.mirror(cfg, "sha-aaaaaaa", deps)

    assert fake.creates() == [local("frontend", "sha-aaaaaaa"), local("deployer", "sha-aaaaaaa")]


def test_restart_with_the_release_already_mirrored_copies_nothing(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    d.tick(cfg, deps, set())
    (cfg.state_dir / "state.json").unlink()
    fake.calls.clear()

    assert d.tick(cfg, deps, set()) == "deployed"
    assert fake.creates() == []
    assert fake.updates() == []


def test_a_mirror_failure_updates_nothing_and_is_not_retried(
    cfg: Any, deps: Any, fake: Fake, logs: list[str]
) -> None:
    fake.fail_create.add(f"{SRC}/sunday-clays-frontend:sha-aaaaaaa")
    failed: set[str] = set()

    assert d.tick(cfg, deps, failed) == "failed"

    assert fake.updates() == [] and fake.rollbacks() == []
    assert failed == {MAIN}
    state = d.load_state(cfg.state_dir)
    assert "sha" not in state
    assert state["last_failure"]["tag"] == "sha-aaaaaaa"
    assert "cannot create" in state["last_failure"]["reason"]
    assert "FAILED" in logs[-1]
    fake.calls.clear()
    assert d.tick(cfg, deps, failed) == "failed-before"
    assert [c[0] for c in fake.calls] == ["git"]


def test_a_source_that_cannot_be_read_fails_the_mirror(cfg: Any, deps: Any, fake: Fake) -> None:
    fake.published.discard(f"{SRC}/sunday-clays-deployer:sha-aaaaaaa")

    with pytest.raises(d.DeployError, match="cannot read .*deployer:sha-aaaaaaa"):
        d.mirror(cfg, "sha-aaaaaaa", deps)


def test_a_copy_that_cannot_be_read_back_fails_the_mirror(cfg: Any, deps: Any, fake: Fake) -> None:
    real = fake.run

    def run(argv: Sequence[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        result = real(argv, **kw)
        if list(argv[:4]) == ["docker", "buildx", "imagetools", "create"]:
            fake.local.pop(argv[argv.index("--tag") + 1])  # pushed, yet not there
        return result

    deps.run = run
    with pytest.raises(d.DeployError, match="cannot read back"):
        d.mirror(cfg, "sha-aaaaaaa", deps)


def test_rollback_mirrors_the_old_tag_first_even_after_it_left_the_registry(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    seed_history(cfg, OLD_TAG)
    d.tick(cfg, deps, set())
    fake.local.clear()  # a registry GC removed every mirrored tag
    fake.calls.clear()

    d.rollback(cfg, deps, OLD_TAG)

    assert fake.creates() == [local(k, OLD_TAG) for k in ("backend", "frontend", "deployer")]
    first_update = next(
        i for i, c in enumerate(fake.calls) if c[:3] == ["docker", "service", "update"]
    )
    assert all(
        i < first_update
        for i, c in enumerate(fake.calls)
        if c[:4] == ["docker", "buildx", "imagetools", "create"]
    )
    assert fake.tags() == {OLD_TAG}


def test_a_rollback_whose_mirror_fails_changes_and_pauses_nothing(
    cfg: Any, deps: Any, fake: Fake
) -> None:
    seed_history(cfg, OLD_TAG)
    d.tick(cfg, deps, set())
    fake.local.clear()
    fake.fail_create.add(f"{SRC}/sunday-clays-backend:{OLD_TAG}")
    fake.calls.clear()
    before = d.load_state(cfg.state_dir)

    with pytest.raises(d.DeployError, match="cannot create"):
        d.rollback(cfg, deps, OLD_TAG)

    assert fake.updates() == []
    assert d.load_state(cfg.state_dir) == before


def test_drift_compares_the_local_registry_refs(cfg: Any, deps: Any, fake: Fake) -> None:
    d.tick(cfg, deps, set())
    assert d.drifted(cfg, "sha-aaaaaaa", deps) == []

    fake.images["sundayclays_worker"] = f"{SRC}/sunday-clays-backend:sha-aaaaaaa"  # a GHCR ref

    assert d.drifted(cfg, "sha-aaaaaaa", deps) == [
        f"sundayclays_worker runs {SRC}/sunday-clays-backend:sha-aaaaaaa"
    ]


def test_registries_come_from_the_environment(cfg: Any) -> None:
    default = d.Config.from_env({})
    assert (default.registry, default.source_registry) == ("registry.thehalf.io", "ghcr.io/gitgat")
    custom = d.Config.from_env({"REGISTRY": "r.example", "SOURCE_REGISTRY": "quay.io/x"})
    assert (
        d.image_ref(custom, "backend", "sha-1234567")
        == "r.example/sunday-clays-backend:sha-1234567"
    )
    assert (
        d.source_ref(custom, "backend", "sha-1234567")
        == "quay.io/x/sunday-clays-backend:sha-1234567"
    )


def test_login_goes_to_the_source_registry_host(cfg: Any, deps: Any, fake: Fake) -> None:
    d.login(cfg, deps)

    assert fake.calls[0][:3] == ["docker", "login", "ghcr.io"]


def test_cli_mirror_logs_in_mirrors_and_updates_nothing(
    cfg: Any, deps: Any, fake: Fake, capsys: pytest.CaptureFixture[str]
) -> None:
    env = {
        "GHCR_USER": "gitgat-bot",
        "GHCR_TOKEN_FILE": str(cfg.ghcr_token_file),
        "STATE_DIR": str(cfg.state_dir),
    }

    assert d.main(["mirror", "sha-aaaaaaa"], env, deps) == 0

    assert fake.calls[0][:2] == ["docker", "login"]
    assert fake.inputs[0] == GHCR_TOKEN + "\n"
    assert len(fake.creates()) == 3
    assert fake.updates() == [] and fake.rollbacks() == []
    assert d.load_state(cfg.state_dir) == {}

    assert d.main(["mirror", "latest"], env, deps) == 1
    assert "not a sha-<7> tag" in capsys.readouterr().err
    del env["GHCR_USER"]
    assert d.main(["mirror", "sha-aaaaaaa"], env, deps) == 1
    assert "GHCR_USER is not set" in capsys.readouterr().err


def test_each_image_copy_gets_its_own_ten_minute_timeout(cfg: Any, deps: Any, fake: Fake) -> None:
    timeouts: list[float] = []
    real = fake.run

    def run(argv: Sequence[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        if list(argv[:4]) == ["docker", "buildx", "imagetools", "create"]:
            timeouts.append(kw["timeout"])
        return real(argv, **kw)

    deps.run = run
    d.mirror(cfg, "sha-aaaaaaa", deps)

    assert timeouts == [600.0] * 3
