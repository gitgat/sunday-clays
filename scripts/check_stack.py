#!/usr/bin/env python3
"""Fleet rules for the rendered Swarm stack (C11 `stack-config`, amended by Plan 13 for the
multi-arch fleet: Raspberry Pis (arm64) and Proxmox VMs (amd64)).

IMAGE_TAG=sha-0000000 docker stack config -c compose.yaml -c compose.swarm.yaml \
    | uv run --no-project --with pyyaml python scripts/check_stack.py [rendered.yaml]
"""

import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

REQUIRED_SERVICES = ("caddy", "api", "worker", "db", "backup", "deployer")
# Single-writer data services: pinned by hostname, all to the same node, one replica each.
PINNED_SERVICES = ("db", "backup")
HOSTNAME = "node.hostname=="
DATA_ROOT = "/var/data/sunday-clays/"
# Services that run a release image: CI publishes every sha-<7> tag to GHCR for linux/amd64 and
# linux/arm64 (publish.yml), and the deployer mirrors that whole index into the fleet registry
# (Plan 13 T8), so Swarm can place them on any node and no node needs a GHCR login.
RELEASE_IMAGES = {
    "caddy": "frontend",
    "api": "backend",
    "worker": "backend",
    "backup": "backend",
    "deployer": "deployer",
}
FLEET_REGISTRY = "registry.thehalf.io"  # `SC_REGISTRY` in compose.swarm.yaml overrides it
RELEASE_TAG = re.compile(r"^sha-[0-9a-f]{7}$")
# node.labels.class (rpi4/rpi5) and node.labels.type (vm/physical) are the fleet's hardware labels:
# a constraint on them pins a service to one architecture just as node.platform.arch does.
ARCH_CONSTRAINT = re.compile(r"^node\.(platform\.arch|labels\.(arch|class|type))(==|!=)")
# Services allowed an architecture constraint. None: every image is multi-arch, and Swarm already
# keeps a task off nodes whose platform its image lacks.
ARCH_PINNED: frozenset[str] = frozenset()
# Plan 13: the pull-based deployer is the only service that holds the Docker socket, and it runs as
# one task on a manager (any architecture: the Swarm's managers are Raspberry Pis).
DEPLOYER = "deployer"
MANAGER = "node.role==manager"
DOCKER_SOCKETS = ("/var/run/docker.sock", "/run/docker.sock")
PUBLIC_EDGE = "edge_public"
CLOUDFLARE_IP = "CF-Connecting-IP"
ROUTER_LABEL = re.compile(r"^traefik\.http\.routers\.([^.]+)\.rule$")


def _labels(service: dict[str, Any]) -> dict[str, str]:
    raw = (service.get("deploy") or {}).get("labels") or {}
    if isinstance(raw, dict):
        return {str(k): "" if v is None else str(v) for k, v in raw.items()}
    return {k: v for k, _, v in (str(item).partition("=") for item in raw)}


def _network_names(service: dict[str, Any]) -> list[str]:
    networks = service.get("networks") or []
    return [str(n) for n in networks]  # a list, or a mapping (iterates its keys)


def _public_edge_rules(stack: dict[str, Any], caddy: dict[str, Any]) -> list[str]:
    """Caddy sits on the Cloudflare Tunnel's edge, and the LAN router drops CF-Connecting-IP."""
    problems: list[str] = []
    if PUBLIC_EDGE not in _network_names(caddy):
        problems.append(f"caddy: must join the external network {PUBLIC_EDGE}")
    if not ((stack.get("networks") or {}).get(PUBLIC_EDGE) or {}).get("external"):
        problems.append(f"network {PUBLIC_EDGE}: must be external")
    labels = _labels(caddy)
    for label in sorted(labels):
        router = ROUTER_LABEL.match(label)
        if not router:
            continue
        middlewares = labels.get(f"traefik.http.routers.{router[1]}.middlewares", "")
        strips = any(
            labels.get(
                f"traefik.http.middlewares.{m.strip().split('@', 1)[0]}"
                f".headers.customrequestheaders.{CLOUDFLARE_IP}"
            )
            == ""
            for m in middlewares.split(",")
        )
        if not strips:
            problems.append(
                f"caddy: router {router[1]} must strip {CLOUDFLARE_IP} "
                "(a middleware with an empty customrequestheaders value)"
            )
    return problems


def _constraints(service: dict[str, Any]) -> list[str]:
    placement = (service.get("deploy") or {}).get("placement") or {}
    return [str(c).replace(" ", "") for c in placement.get("constraints") or []]


def _bind_sources(service: dict[str, Any]) -> list[str]:
    sources = []
    for volume in service.get("volumes") or []:
        if isinstance(volume, dict) and volume.get("type") == "bind":
            sources.append(str(volume.get("source", "")))
        elif isinstance(volume, str) and volume.startswith("/"):
            sources.append(volume.split(":", 1)[0])
    return sources


def _release_registry() -> str:
    """The registry the stack pulls from: SC_REGISTRY (as exported for the render) or the fleet's."""
    return os.environ.get("SC_REGISTRY") or FLEET_REGISTRY


def _release_image_rule(name: str, image: str) -> list[str]:
    kind = RELEASE_IMAGES.get(name)
    if kind is None:
        return []
    expected = f"{_release_registry()}/sunday-clays-{kind}"
    repository, _, tag = image.rpartition(":")
    if not image.startswith("ghcr.io/") and repository == expected and RELEASE_TAG.match(tag):
        return []
    return [
        f"{name}: image must be {expected}:sha-<7> (the fleet registry's multi-arch index; "
        f"not ghcr.io, not a per-arch tag), not {image!r}"
    ]


def _exposes_the_socket(source: str) -> bool:
    """The socket itself, or a directory that holds it (`/`, `/run`, `/var/run`, `/var`)."""
    directory = source.rstrip("/")
    return not directory or any(
        s == directory or s.startswith(directory + "/") for s in DOCKER_SOCKETS
    )


def _socket_and_manager_rules(
    name: str, service: dict[str, Any], constraints: list[str]
) -> list[str]:
    """Only the deployer may hold the Docker socket, and it runs as one task on a manager."""
    binds = _bind_sources(service)
    problems: list[str] = []
    if name != DEPLOYER:
        problems += [
            f"{name}: only {DEPLOYER} may mount {s}" for s in binds if _exposes_the_socket(s)
        ]
        if MANAGER in constraints:
            problems.append(f"{name}: only {DEPLOYER} may be placed with {MANAGER}")
        return problems
    if MANAGER not in constraints:
        problems.append(f"{name}: missing placement constraint {MANAGER}")
    if (service.get("deploy") or {}).get("replicas") != 1:
        problems.append(f"{name}: deploy.replicas must be 1")
    if DOCKER_SOCKETS[0] not in binds:
        problems.append(f"{name}: needs a bind mount of {DOCKER_SOCKETS[0]}")
    problems += [
        f"{name}: bind mount {s!r} is not allowed (only {DOCKER_SOCKETS[0]})"
        for s in binds
        if s != DOCKER_SOCKETS[0]
    ]
    if service.get("ports"):
        problems.append(f"{name}: must not publish ports")
    return problems


def violations(stack: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    services: dict[str, dict[str, Any]] = stack.get("services") or {}
    for name in REQUIRED_SERVICES:
        if name not in services:
            problems.append(f"{name}: service missing")
    pinned_to: set[str] = set()
    for name, service in sorted(services.items()):
        constraints = _constraints(service)
        if name not in ARCH_PINNED:
            problems += [
                f"{name}: must not be constrained to an architecture ({c}); images are multi-arch"
                for c in constraints
                if ARCH_CONSTRAINT.match(c)
            ]
        hosts = [c for c in constraints if c.startswith(HOSTNAME)]
        if name not in PINNED_SERVICES:
            problems += [f"{name}: must not be pinned to a node ({c})" for c in hosts]
        image = str(service.get("image", ""))
        if image.endswith(":latest") or ":" not in image.rsplit("/", 1)[-1]:
            problems.append(f"{name}: image {image!r} must carry an explicit tag other than latest")
        problems += _release_image_rule(name, image)
        if name in PINNED_SERVICES:
            if not hosts:
                problems.append(f"{name}: missing {HOSTNAME} placement constraint")
            if len(hosts) > 1:
                problems.append(f"{name}: more than one {HOSTNAME} constraint ({hosts})")
            pinned_to.update(hosts)
            if (service.get("deploy") or {}).get("replicas") != 1:
                problems.append(f"{name}: deploy.replicas must be 1")
            if not any(source.startswith(DATA_ROOT) for source in _bind_sources(service)):
                problems.append(f"{name}: needs a bind mount under {DATA_ROOT}")
        problems.extend(_socket_and_manager_rules(name, service, constraints))
    if len(pinned_to) > 1:
        problems.append(f"db and backup must be pinned to one node, not {sorted(pinned_to)}")
    caddy = services.get("caddy") or {}
    if caddy.get("ports"):
        problems.append("caddy: must not publish ports (Traefik reaches it over traefik_public)")
    if caddy:
        problems += _public_edge_rules(stack, caddy)
    for key, secret in sorted((stack.get("secrets") or {}).items()):
        secret_name = str((secret or {}).get("name", ""))
        if not secret_name.startswith("sundayclays_"):
            problems.append(f"secret {key}: name {secret_name!r} must start with sundayclays_")
    return problems


def main(argv: Sequence[str]) -> int:
    text = Path(argv[0]).read_text(encoding="utf-8") if argv else sys.stdin.read()
    stack = yaml.safe_load(text)
    if not isinstance(stack, dict):
        print("check_stack: input is not a rendered stack", file=sys.stderr)
        return 2
    problems = violations(stack)
    for problem in problems:
        print(f"check_stack: {problem}", file=sys.stderr)
    if not problems:
        print(f"check_stack: {len(stack.get('services') or {})} services ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
