#!/usr/bin/env python3
"""Pull-based image deployer for the sundayclays Swarm stack (Plan 13). Standard library only.

Every POLL_INTERVAL seconds it reads main's SHA with `git ls-remote`. Once CI has published
ghcr.io/gitgat/sunday-clays-{backend,frontend,deployer}:sha-<7>, it mirrors the three multi-arch
indexes into the fleet registry (registry.thehalf.io), then updates api (and waits until api
reports that version), then worker, caddy and backup, and only then records the SHA in STATE_DIR. A failed
step rolls the services this run already updated back to their previous image, so the stack stays
on one coherent release. While main is unchanged it checks that the services still run the
recorded tag and redeploys it if they drifted. db and the deployer itself are never updated here
(deploy/README.md, "Automatic deploys").

    deployer.py run | once | status | tag | pause [reason...] | resume | rollback sha-<7>
                | mirror sha-<7>
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import http.client
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType
from typing import Any

ORDER = ("api", "worker", "caddy", "backup")
IMAGE_OF = {
    "api": "backend",
    "worker": "backend",
    "caddy": "frontend",
    "backup": "backend",
}
KINDS = ("backend", "frontend", "deployer")
# Exactly these two platforms, as one OCI index per image (never per-arch tags: they strand the
# nodes of the other architecture). An attestation entry (unknown/unknown) is not allowed either.
PLATFORMS = ("linux/amd64", "linux/arm64")
TAG = re.compile(r"^sha-[0-9a-f]{7}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
ABSENT = re.compile(r"no such manifest|manifest unknown|manifest .* not found", re.IGNORECASE)
UNSETTLED = {"updating", "paused", "rollback_started", "rollback_paused"}
HISTORY = 20
MIN_POLL_INTERVAL = 30.0
HEALTH_POLL_SECONDS = 5.0


class DeployError(Exception):
    """A step failed. Messages never contain a token."""


Run = Callable[..., "subprocess.CompletedProcess[str]"]
Fetch = Callable[[str, float], str]


def run_command(
    argv: Sequence[str],
    *,
    input: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(argv),
            input=input,
            env=None if env is None else dict(env),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise DeployError(f"{' '.join(argv[:3])} timed out after {timeout:.0f}s") from None


def fetch_url(url: str, timeout: float) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (fixed http URL)
        body: bytes = response.read()
    return body.decode("utf-8")


def _log(message: str) -> None:
    print(f"{datetime.now(UTC).isoformat(timespec='seconds')} {message}", flush=True)


@dataclass
class Deps:
    run: Run = run_command
    fetch: Fetch = fetch_url
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    log: Callable[[str], None] = _log


@dataclass(frozen=True)
class Config:
    repo_url: str = "https://github.com/gitgat/sunday-clays.git"
    branch: str = "main"
    stack: str = "sundayclays"
    registry: str = "registry.thehalf.io"  # where the stack pulls from: the fleet registry
    source_registry: str = "ghcr.io/gitgat"  # where CI publishes
    ghcr_user: str = ""
    github_token_file: Path = Path("/run/secrets/deployer_github_token")
    ghcr_token_file: Path = Path("/run/secrets/deployer_ghcr_token")
    state_dir: Path = Path("/state")
    heartbeat_file: Path = Path("/tmp/deployer-heartbeat")  # noqa: S108 (container-local)
    poll_interval: float = 120.0
    health_url: str = "http://api:8000/api/health"
    health_timeout: float = 600.0
    update_timeout: float = 1200.0
    mirror_timeout: float = 600.0  # per image copy

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Config:
        d = cls()
        try:
            poll = float(env.get("POLL_INTERVAL", d.poll_interval))
            health_timeout = float(env.get("HEALTH_TIMEOUT", d.health_timeout))
            update_timeout = float(env.get("UPDATE_TIMEOUT", d.update_timeout))
        except ValueError as exc:
            raise DeployError(f"bad number in the environment: {exc}") from None
        if poll < MIN_POLL_INTERVAL:
            raise DeployError(f"POLL_INTERVAL must be at least {MIN_POLL_INTERVAL:.0f} seconds")
        return cls(
            repo_url=env.get("REPO_URL", d.repo_url),
            branch=env.get("BRANCH", d.branch),
            stack=env.get("STACK", d.stack),
            registry=env.get("REGISTRY", d.registry),
            source_registry=env.get("SOURCE_REGISTRY", d.source_registry),
            ghcr_user=env.get("GHCR_USER", d.ghcr_user),
            github_token_file=Path(env.get("GITHUB_TOKEN_FILE", str(d.github_token_file))),
            ghcr_token_file=Path(env.get("GHCR_TOKEN_FILE", str(d.ghcr_token_file))),
            state_dir=Path(env.get("STATE_DIR", str(d.state_dir))),
            heartbeat_file=Path(env.get("HEARTBEAT_FILE", str(d.heartbeat_file))),
            poll_interval=poll,
            health_url=env.get("HEALTH_URL", d.health_url),
            health_timeout=health_timeout,
            update_timeout=update_timeout,
        )


def read_secret(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise DeployError(f"cannot read secret {path}: {exc.strerror}") from None
    if not value:
        raise DeployError(f"secret {path} is empty")
    return value


def _redact(text: str, *secrets: str) -> str:
    for secret in secrets:
        text = text.replace(secret, "***")
    return text.strip()[-500:]


def tag_for(sha: str) -> str:
    return f"sha-{sha[:7]}"


def image_ref(cfg: Config, kind: str, tag: str) -> str:
    """The ref the services run: the fleet registry's copy."""
    return f"{cfg.registry}/sunday-clays-{kind}:{tag}"


def source_ref(cfg: Config, kind: str, tag: str) -> str:
    """The ref CI published: GHCR."""
    return f"{cfg.source_registry}/sunday-clays-{kind}:{tag}"


def remote_sha(cfg: Config, deps: Deps) -> str:
    """main's SHA. The token reaches only this git process's environment: no argv, no file."""
    token = read_secret(cfg.github_token_file)
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
    }
    ref = f"refs/heads/{cfg.branch}"
    result = deps.run(["git", "ls-remote", cfg.repo_url, ref], env=env, timeout=60.0)
    if result.returncode != 0:
        detail = _redact(result.stderr, token, basic)
        raise DeployError(f"git ls-remote failed (exit {result.returncode}): {detail}")
    for line in result.stdout.splitlines():
        sha, _, name = line.partition("\t")
        if name == ref and SHA.match(sha):
            return sha
    raise DeployError(f"{ref} not found at {cfg.repo_url}")


def login(cfg: Config, deps: Deps) -> None:
    if not cfg.ghcr_user:
        raise DeployError("GHCR_USER is not set")
    token = read_secret(cfg.ghcr_token_file)
    host = cfg.source_registry.split("/", 1)[0]
    result = deps.run(
        ["docker", "login", host, "--username", cfg.ghcr_user, "--password-stdin"],
        input=token + "\n",
        timeout=60.0,
    )
    if result.returncode != 0:
        raise DeployError(f"docker login {host} failed: {_redact(result.stderr, token)}")


def missing_images(cfg: Config, tag: str, deps: Deps) -> list[str]:
    """The source refs not (yet) published. Any other manifest error is a DeployError."""
    missing = []
    for kind in KINDS:
        ref = source_ref(cfg, kind, tag)
        result = deps.run(["docker", "manifest", "inspect", ref], timeout=60.0)
        if result.returncode == 0:
            continue
        if not ABSENT.search(result.stderr):
            raise DeployError(f"docker manifest inspect {ref} failed: {_redact(result.stderr)}")
        missing.append(ref)
    return missing


def _raw_index(ref: str, deps: Deps) -> subprocess.CompletedProcess[str]:
    return deps.run(["docker", "buildx", "imagetools", "inspect", "--raw", ref], timeout=60.0)


def _platforms(raw: str, ref: str) -> None:
    """Fail unless ``raw`` is an index listing exactly linux/amd64 and linux/arm64."""
    try:
        found = sorted(
            f"{m['platform']['os']}/{m['platform']['architecture']}"
            for m in json.loads(raw)["manifests"]
        )
    except (ValueError, LookupError, TypeError):
        raise DeployError(f"{ref}: not a multi-arch index (want {' + '.join(PLATFORMS)})") from None
    if found != sorted(PLATFORMS):
        raise DeployError(f"{ref}: platforms are {', '.join(found)}; want {' + '.join(PLATFORMS)}")


def mirror(cfg: Config, tag: str, deps: Deps) -> None:
    """Copy the three release indexes from the source registry into the fleet registry.

    `imagetools create` copies the whole index registry to registry (no pull onto this node), so
    the local tag lists both platforms. An image whose local index is already byte-identical to
    the source's is skipped, so a restart or a repeated rollback copies nothing. Runs before any
    `docker service update`: a failure here leaves every service alone."""
    for kind in KINDS:
        src, dst = source_ref(cfg, kind, tag), image_ref(cfg, kind, tag)
        source = _raw_index(src, deps)
        if source.returncode != 0:
            raise DeployError(f"mirror: cannot read {src}: {_redact(source.stderr)}")
        _platforms(source.stdout, src)
        local = _raw_index(dst, deps)
        if local.returncode == 0 and local.stdout == source.stdout:
            deps.log(f"mirror {tag}: {dst} already there")
            continue
        deps.log(f"mirror {tag}: {src} -> {dst}")
        made = deps.run(
            ["docker", "buildx", "imagetools", "create", "--tag", dst, src],
            timeout=cfg.mirror_timeout,
        )
        if made.returncode != 0:
            raise DeployError(f"mirror: cannot create {dst}: {_redact(made.stderr)}")
        copy = _raw_index(dst, deps)
        if copy.returncode != 0:
            raise DeployError(f"mirror: cannot read back {dst}: {_redact(copy.stderr)}")
        _platforms(copy.stdout, dst)


def inspect_services(
    cfg: Config, services: Sequence[str], deps: Deps
) -> dict[str, tuple[str, str]]:
    """{service: (spec image without @digest, update state)} from one `docker service inspect`."""
    names = [f"{cfg.stack}_{s}" for s in services]
    label = ", ".join(names)
    result = deps.run(["docker", "service", "inspect", *names], timeout=60.0)
    if result.returncode != 0:
        raise DeployError(f"{label}: docker service inspect failed: {_redact(result.stderr)}")
    try:
        found: dict[str, tuple[str, str]] = {}
        for item in json.loads(result.stdout):
            image = str(item["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]).split("@", 1)[0]
            state = str((item.get("UpdateStatus") or {}).get("State", "completed"))
            found[str(item["Spec"]["Name"])] = (image, state)
        return {s: found[f"{cfg.stack}_{s}"] for s in services}
    except (ValueError, LookupError, TypeError, AttributeError):
        raise DeployError(f"{label}: unreadable docker service inspect output") from None


def update_service(cfg: Config, service: str, tag: str, deps: Deps) -> bool:
    """Put one service on ``tag``. False when it already runs it (no `service update` at all)."""
    name = f"{cfg.stack}_{service}"
    ref = image_ref(cfg, IMAGE_OF[service], tag)
    current, state = inspect_services(cfg, [service], deps)[service]
    if current == ref and state not in UNSETTLED:
        deps.log(f"deploy {tag}: {name} already on {tag}")
        return False
    deps.log(f"deploy {tag}: updating {name}")
    result = deps.run(
        [
            "docker", "service", "update", "--detach=false", "--quiet", "--image", ref, name,
        ],
        timeout=cfg.update_timeout,
    )  # fmt: skip
    if result.returncode != 0:
        raise DeployError(f"{name}: docker service update failed: {_redact(result.stderr)}")
    current, state = inspect_services(cfg, [service], deps)[service]
    if current != ref or state in UNSETTLED:
        raise DeployError(f"{name}: runs {current} (update state {state}), not {ref}")
    return True


def revert(cfg: Config, services: Sequence[str], deps: Deps) -> list[str]:
    """`docker service rollback` each service (callers pass reverse ORDER); returns those done."""
    done = []
    for service in services:
        name = f"{cfg.stack}_{service}"
        result = deps.run(
            ["docker", "service", "rollback", "--detach=false", "--quiet", name],
            timeout=cfg.update_timeout,
        )
        if result.returncode != 0:
            deps.log(f"{name}: docker service rollback failed: {_redact(result.stderr)}")
            continue
        deps.log(f"rolled back {name} to its previous image")
        done.append(name)
    return done


def wait_for_version(cfg: Config, tag: str, deps: Deps) -> None:
    deadline = deps.clock() + cfg.health_timeout
    last = "no answer"
    while True:
        try:
            body = json.loads(deps.fetch(cfg.health_url, HEALTH_POLL_SECONDS))
            if body.get("status") == "ok" and body.get("version") == tag:
                return
            last = f"version {body.get('version')!r}"
        except (OSError, http.client.HTTPException, ValueError, AttributeError) as exc:
            last = type(exc).__name__
        if deps.clock() >= deadline:
            raise DeployError(f"api did not report {tag} within {cfg.health_timeout:.0f}s ({last})")
        deps.sleep(HEALTH_POLL_SECONDS)


def deploy(cfg: Config, tag: str, deps: Deps) -> None:
    """Update the four app services in ORDER. On a failure, roll the ones this run updated back
    (reverse ORDER), so the stack never stays split between two releases. db is never touched."""
    updated: list[str] = []
    try:
        for service in ORDER:
            if update_service(cfg, service, tag, deps):
                updated.append(service)
            if service == "api":
                wait_for_version(cfg, tag, deps)
    except DeployError as exc:
        reverted = revert(cfg, updated[::-1], deps)
        raise DeployError(f"{exc}; rolled back {', '.join(reverted) or 'nothing'}") from None


def load_state(state_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(state_dir: Path, state: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    tmp = state_dir / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, state_dir / "state.json")


def record(state_dir: Path, *, sha: str, tag: str, when: datetime, how: str) -> None:
    state = load_state(state_dir)
    entry = {
        "sha": sha,
        "tag": tag,
        "at": when.isoformat(timespec="seconds"),
        "how": how,
    }
    state.update(sha=sha, tag=tag, deployed_at=entry["at"])
    state["history"] = [entry, *state.get("history", [])][:HISTORY]
    save_state(state_dir, state)


def note_failure(state_dir: Path, *, sha: str, tag: str, reason: str, when: datetime) -> None:
    """For `status` only. Never touches sha/tag: a failed deploy records nothing as deployed."""
    state = load_state(state_dir)
    at = when.isoformat(timespec="seconds")
    state["last_failure"] = {"sha": sha, "tag": tag, "at": at, "reason": reason}
    save_state(state_dir, state)


def set_paused(state_dir: Path, reason: str | None) -> None:
    state = load_state(state_dir)
    if reason is None:
        state.pop("paused", None)
    else:
        state["paused"] = reason
    save_state(state_dir, state)


@contextmanager
def deploy_lock(state_dir: Path) -> Iterator[None]:
    """Serialises the poll loop and a `docker exec … rollback` in the same container."""
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "deploy.lock").open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def drifted(cfg: Config, tag: str, deps: Deps) -> list[str]:
    """Settled app services whose spec image is not ``tag`` (a hand deploy, a later Swarm
    rollback): the recorded state no longer describes what runs."""
    return [
        f"{cfg.stack}_{service} runs {image}"
        for service, (image, state) in inspect_services(cfg, ORDER, deps).items()
        if image != image_ref(cfg, IMAGE_OF[service], tag) and state not in UNSETTLED
    ]


def _roll_out(cfg: Config, deps: Deps, sha: str, tag: str, failed: set[str], how: str) -> str:
    try:
        mirror(cfg, tag, deps)
        deploy(cfg, tag, deps)
    except DeployError as exc:
        failed.add(sha)
        note_failure(cfg.state_dir, sha=sha, tag=tag, reason=str(exc), when=deps.now())
        deps.log(
            f"deploy {tag} FAILED: {exc}. The deployed release is unchanged; {tag} is not retried"
            " until main moves or the deployer restarts."
        )
        return "failed"
    record(cfg.state_dir, sha=sha, tag=tag, when=deps.now(), how=how)
    deps.log(f"deploy {tag}: done")
    return "deployed"


def tick(cfg: Config, deps: Deps, failed: set[str], waiting: set[str] | None = None) -> str:
    """One poll. Returns paused | unchanged | failed-before | waiting | failed | deployed.

    ``failed`` and ``waiting`` live as long as the loop: a failed SHA is not retried, and
    "waiting for" is logged once per SHA."""
    waiting = set() if waiting is None else waiting
    with deploy_lock(cfg.state_dir):
        state = load_state(cfg.state_dir)
        if state.get("paused"):
            return "paused"
        sha = remote_sha(cfg, deps)
        if sha in failed:
            return "failed-before"
        if sha == state.get("sha"):
            tag = str(state.get("tag", ""))
            drift = drifted(cfg, tag, deps)
            if not drift:
                return "unchanged"
            deps.log(f"drift: {'; '.join(drift)}; recorded {tag}, redeploying it")
            login(cfg, deps)
            return _roll_out(cfg, deps, sha, tag, failed, how="drift")
        tag = tag_for(sha)
        login(cfg, deps)
        missing = missing_images(cfg, tag, deps)
        if missing:
            if sha not in waiting:
                deps.log(f"{tag}: waiting for {', '.join(missing)}")
                waiting.add(sha)
            return "waiting"
        return _roll_out(cfg, deps, sha, tag, failed, how="auto")


def rollback(cfg: Config, deps: Deps, tag: str) -> None:
    """Deploy an older sha-<7> in the same order and pause automatic deploys."""
    if not TAG.match(tag):
        raise DeployError(f"{tag!r} is not a sha-<7> tag")
    with deploy_lock(cfg.state_dir):
        deployed = {h.get("tag") for h in load_state(cfg.state_dir).get("history", [])}
        if tag not in deployed:
            raise DeployError(f"{tag} is not in the deployer's history; see deploy/README.md")
        login(cfg, deps)
        missing = missing_images(cfg, tag, deps)
        if missing:
            raise DeployError(
                f"{tag}: not published to {cfg.source_registry}: {', '.join(missing)}"
            )
        mirror(cfg, tag, deps)  # again: idempotent, and copes with a registry GC that removed it
        set_paused(
            cfg.state_dir,
            f"rollback to {tag} at {deps.now().isoformat(timespec='seconds')}",
        )
        try:
            deploy(cfg, tag, deps)
        except DeployError as exc:
            note_failure(cfg.state_dir, sha="", tag=tag, reason=str(exc), when=deps.now())
            raise
        record(cfg.state_dir, sha="", tag=tag, when=deps.now(), how="rollback")
    deps.log(f"rolled back to {tag}; automatic deploys stay paused until `deployer.py resume`")


def mirror_only(cfg: Config, deps: Deps, tag: str) -> None:
    """For a hand deploy: mirror ``tag`` and update nothing."""
    if not TAG.match(tag):
        raise DeployError(f"{tag!r} is not a sha-<7> tag")
    with deploy_lock(cfg.state_dir):
        login(cfg, deps)
        mirror(cfg, tag, deps)


def recorded_tag(state_dir: Path) -> str:
    """The live release as recorded: what a hand `docker stack deploy` must use as IMAGE_TAG."""
    tag = str(load_state(state_dir).get("tag", ""))
    if not TAG.match(tag):
        raise DeployError("no deploy recorded (state is empty); read the tag from /api/health")
    return tag


def serve(cfg: Config, deps: Deps, stopping: Callable[[], bool]) -> int:
    deps.log(f"deployer: watching {cfg.repo_url} {cfg.branch} every {cfg.poll_interval:.0f}s")
    failed: set[str] = set()
    waiting: set[str] = set()
    while not stopping():
        cfg.heartbeat_file.touch()  # before the poll: a deploy can take far longer than one
        try:
            tick(cfg, deps, failed, waiting)
        except (DeployError, OSError) as exc:
            deps.log(f"poll failed: {exc}")
        waited = 0.0
        while waited < cfg.poll_interval and not stopping():
            deps.sleep(1.0)
            waited += 1.0
    deps.log("deployer: stopped")
    return 0


def main(argv: Sequence[str], env: Mapping[str, str] = os.environ, deps: Deps | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deployer.py", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="poll and deploy until SIGTERM")
    commands.add_parser("once", help="one poll, then exit")
    commands.add_parser("status", help="print the recorded state as JSON")
    commands.add_parser("tag", help="print the recorded live tag (for a hand stack deploy)")
    pause = commands.add_parser("pause", help="stop automatic deploys")
    pause.add_argument("reason", nargs="*")
    commands.add_parser("resume", help="resume automatic deploys")
    copy = commands.add_parser(
        "mirror", help="copy a release into the fleet registry, deploy nothing"
    )
    copy.add_argument("tag")
    back = commands.add_parser("rollback", help="deploy an older sha-<7> and pause")
    back.add_argument("tag")
    args = parser.parse_args(argv)
    deps = deps or Deps()
    try:
        cfg = Config.from_env(env)
        if args.command in ("run", "once", "rollback", "mirror") and not cfg.ghcr_user:
            raise DeployError("GHCR_USER is not set")
        if args.command == "run":
            stop: list[bool] = []

            def on_term(_signum: int, _frame: FrameType | None) -> None:
                stop.append(True)

            signal.signal(signal.SIGTERM, on_term)
            return serve(cfg, deps, lambda: bool(stop))
        if args.command == "once":
            print(tick(cfg, deps, set()))
        elif args.command == "status":
            print(json.dumps(load_state(cfg.state_dir), indent=2, sort_keys=True))
        elif args.command == "tag":
            print(recorded_tag(cfg.state_dir))
        elif args.command == "pause":
            with deploy_lock(cfg.state_dir):
                set_paused(cfg.state_dir, " ".join(args.reason) or "paused by hand")
        elif args.command == "resume":
            with deploy_lock(cfg.state_dir):
                set_paused(cfg.state_dir, None)
        elif args.command == "mirror":
            mirror_only(cfg, deps, args.tag)
        else:
            rollback(cfg, deps, args.tag)
    except DeployError as exc:
        print(f"deployer: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
