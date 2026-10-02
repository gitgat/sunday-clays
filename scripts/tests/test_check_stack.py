import copy
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "check_stack.py"
DB_NODE = ["node.hostname==autopirate"]
MANAGER = ["node.role==manager"]
SOCKET = {"type": "bind", "source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}
STRIP = (
    "traefik.http.middlewares.sundayclays-strip-cf.headers.customrequestheaders.CF-Connecting-IP"
)
CADDY_LABELS = {
    "traefik.enable": "true",
    "traefik.http.routers.sundayclays.rule": "Host(`sundayclays.claysmasher.com`)",
    "traefik.http.routers.sundayclays.middlewares": "sundayclays-strip-cf",
    STRIP: "",
}


def backend(**extra: Any) -> dict[str, Any]:
    return {
        "image": "registry.thehalf.io/sunday-clays-backend:sha-0000000",
        "deploy": {"placement": {"constraints": []}},
        **extra,
    }


VALID: dict[str, Any] = {
    "services": {
        "caddy": {
            "image": "registry.thehalf.io/sunday-clays-frontend:sha-0000000",
            "deploy": {"placement": {"constraints": []}, "labels": dict(CADDY_LABELS)},
            "networks": {"default": None, "traefik_public": None, "edge_public": None},
        },
        "api": backend(),
        "worker": backend(),
        "db": {
            "image": "postgres:17",
            "deploy": {"replicas": 1, "placement": {"constraints": list(DB_NODE)}},
            "volumes": [
                {
                    "type": "bind",
                    "source": "/var/data/sunday-clays/db",
                    "target": "/var/lib/postgresql/data",
                }
            ],
        },
        "backup": backend(
            deploy={"replicas": 1, "placement": {"constraints": list(DB_NODE)}},
            volumes=[
                {"type": "bind", "source": "/var/data/sunday-clays/backups", "target": "/backups"}
            ],
        ),
        "deployer": {
            "image": "registry.thehalf.io/sunday-clays-deployer:sha-0000000",
            "deploy": {"replicas": 1, "placement": {"constraints": list(MANAGER)}},
            "volumes": [
                dict(SOCKET),
                {"type": "bind", "source": "/var/data/sunday-clays/deployer", "target": "/state"},
            ],
        },
    },
    "networks": {"edge_public": {"name": "edge_public", "external": True}},
    "secrets": {
        "db_password": {"name": "sundayclays_db_password_v1", "file": "/x/secrets/db_password"},
    },
}


def run(stack: dict[str, Any], sc_registry: str = "") -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "SC_REGISTRY"}
    if sc_registry:
        env["SC_REGISTRY"] = sc_registry
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=yaml.safe_dump(stack),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_stack_passes() -> None:
    result = run(VALID)

    assert result.returncode == 0, result.stderr
    assert "6 services ok" in result.stdout


def caddy_off_the_public_edge(stack: dict[str, Any]) -> None:
    del stack["services"]["caddy"]["networks"]["edge_public"]


def caddy_off_the_public_edge_list_form(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["networks"] = ["default", "traefik_public"]


def edge_public_not_external(stack: dict[str, Any]) -> None:
    stack["networks"]["edge_public"] = {"name": "edge_public"}


def router_without_the_strip_middleware(stack: dict[str, Any]) -> None:
    del stack["services"]["caddy"]["deploy"]["labels"][
        "traefik.http.routers.sundayclays.middlewares"
    ]


def strip_middleware_that_sets_a_value(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["deploy"]["labels"][STRIP] = "1.2.3.4"


def strip_middleware_not_declared(stack: dict[str, Any]) -> None:
    del stack["services"]["caddy"]["deploy"]["labels"][STRIP]


def arch_on_worker(stack: dict[str, Any]) -> None:
    stack["services"]["worker"]["deploy"]["placement"]["constraints"] = [
        "node.platform.arch==x86_64"
    ]


def arm_label_on_caddy(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["deploy"]["placement"]["constraints"] = ["node.labels.arch==arm64"]


def vm_label_on_api(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["deploy"]["placement"]["constraints"] = ["node.labels.type==vm"]


def arch_on_db(stack: dict[str, Any]) -> None:
    stack["services"]["db"]["deploy"]["placement"]["constraints"].append(
        "node.platform.arch!=aarch64"
    )


def drop_hostname(stack: dict[str, Any]) -> None:
    stack["services"]["db"]["deploy"]["placement"]["constraints"] = []


def backup_on_another_node(stack: dict[str, Any]) -> None:
    stack["services"]["backup"]["deploy"]["placement"]["constraints"] = ["node.hostname==lakitu"]


def api_on_a_ci_tag(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["image"] = "registry.thehalf.io/sunday-clays-backend:ci"


def caddy_runs_the_backend(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["image"] = "registry.thehalf.io/sunday-clays-backend:sha-0000000"


def worker_from_another_registry(stack: dict[str, Any]) -> None:
    stack["services"]["worker"]["image"] = "docker.io/gitgat/sunday-clays-backend:sha-0000000"


def backup_runs_the_frontend(stack: dict[str, Any]) -> None:
    stack["services"]["backup"]["image"] = "registry.thehalf.io/sunday-clays-frontend:sha-0000000"


def spaced_arch_on_worker(stack: dict[str, Any]) -> None:
    stack["services"]["worker"]["deploy"]["placement"]["constraints"] = [
        "node.platform.arch == x86_64"
    ]


def api_pinned_to_a_node(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["deploy"]["placement"]["constraints"] = list(DB_NODE)


def db_on_two_nodes(stack: dict[str, Any]) -> None:
    stack["services"]["db"]["deploy"]["placement"]["constraints"] = [
        "node.hostname==autopirate",
        "node.hostname==pi-two",
    ]


def missing_worker(stack: dict[str, Any]) -> None:
    del stack["services"]["worker"]


def two_replicas(stack: dict[str, Any]) -> None:
    stack["services"]["backup"]["deploy"]["replicas"] = 2


def named_volume(stack: dict[str, Any]) -> None:
    stack["services"]["db"]["volumes"] = [
        {"type": "volume", "source": "db-data", "target": "/var/lib/postgresql/data"}
    ]


def unprefixed_secret(stack: dict[str, Any]) -> None:
    stack["secrets"]["db_password"]["name"] = "db_password"


def caddy_ports(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["ports"] = [{"target": 80, "published": 443, "mode": "host"}]


def latest_image(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["image"] = "registry.thehalf.io/sunday-clays-backend:latest"


def untagged_image(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["image"] = "registry.thehalf.io/sunday-clays-backend"


def missing_backup(stack: dict[str, Any]) -> None:
    del stack["services"]["backup"]


def short_named_volume(stack: dict[str, Any]) -> None:
    stack["services"]["db"]["volumes"] = ["db-data:/var/lib/postgresql/data"]


def short_bind_elsewhere(stack: dict[str, Any]) -> None:
    stack["services"]["backup"]["volumes"] = ["/srv/backups:/backups"]


def socket_on_api(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["volumes"] = [dict(SOCKET)]


def run_socket_on_worker(stack: dict[str, Any]) -> None:
    stack["services"]["worker"]["volumes"] = ["/run/docker.sock:/var/run/docker.sock"]


def var_run_on_api(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["volumes"] = ["/var/run:/host-run"]


def host_root_on_caddy(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["volumes"] = [{"type": "bind", "source": "/", "target": "/host"}]


def caddy_on_a_manager(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["deploy"]["placement"]["constraints"] = list(MANAGER)


def deployer_off_the_managers(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["deploy"]["placement"]["constraints"] = []


def deployer_on_amd64_only(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["deploy"]["placement"]["constraints"].append(
        "node.platform.arch==x86_64"
    )


def two_deployers(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["deploy"]["replicas"] = 2


def deployer_without_the_socket(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["volumes"] = stack["services"]["deployer"]["volumes"][1:]


def deployer_binds_the_host(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["volumes"].append("/etc:/host-etc:ro")


def deployer_state_on_a_named_volume(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["volumes"] = [
        dict(SOCKET),
        {"type": "volume", "source": "deployer-state", "target": "/state"},
    ]


def deployer_state_in_the_wrong_directory(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["volumes"] = [dict(SOCKET), "/var/data/sunday-clays/db:/state"]


def deployer_state_at_the_wrong_target(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["volumes"] = [
        dict(SOCKET),
        "/var/data/sunday-clays/deployer:/data",
    ]


def named_volume_on_api(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["volumes"] = [{"type": "volume", "source": "x", "target": "/x"}]


def short_named_volume_on_worker(stack: dict[str, Any]) -> None:
    stack["services"]["worker"]["volumes"] = ["scratch:/scratch"]


def anonymous_volume_on_caddy(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["volumes"] = ["/data"]


def deployer_publishes_a_port(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["ports"] = [{"target": 8080, "published": 8080}]


def deployer_on_latest(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["image"] = "registry.thehalf.io/sunday-clays-deployer:latest"


def deployer_runs_another_image(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["image"] = "registry.thehalf.io/sunday-clays-backend:sha-0000000"


def api_on_ghcr(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["image"] = "ghcr.io/gitgat/sunday-clays-backend:sha-0000000"


def deployer_on_ghcr(stack: dict[str, Any]) -> None:
    stack["services"]["deployer"]["image"] = "ghcr.io/gitgat/sunday-clays-deployer:sha-0000000"


def caddy_on_a_per_arch_tag(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["image"] = (
        "registry.thehalf.io/sunday-clays-frontend:sha-0000000-arm64"
    )


def worker_on_another_fleet_registry(stack: dict[str, Any]) -> None:
    stack["services"]["worker"]["image"] = "registry.example.com/sunday-clays-backend:sha-0000000"


def missing_deployer(stack: dict[str, Any]) -> None:
    del stack["services"]["deployer"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (socket_on_api, "api: only deployer may mount /var/run/docker.sock"),
        (run_socket_on_worker, "worker: only deployer may mount /run/docker.sock"),
        (var_run_on_api, "api: only deployer may mount /var/run"),
        (host_root_on_caddy, "caddy: only deployer may mount /"),
        (caddy_on_a_manager, "caddy: only deployer may be placed with node.role==manager"),
        (deployer_off_the_managers, "deployer: missing placement constraint node.role==manager"),
        (deployer_on_amd64_only, "deployer: must not be constrained to an architecture"),
        (two_deployers, "deployer: deploy.replicas must be 1"),
        (deployer_without_the_socket, "deployer: needs a bind mount of /var/run/docker.sock"),
        (deployer_binds_the_host, "deployer: bind mount '/etc' is not allowed"),
        (deployer_publishes_a_port, "deployer: must not publish ports"),
        (deployer_on_latest, "deployer: image 'registry.thehalf.io/sunday-clays-deployer:latest'"),
        (
            deployer_runs_another_image,
            "deployer: image must be registry.thehalf.io/sunday-clays-deployer:sha-<7>",
        ),
        (api_on_ghcr, "api: image must be registry.thehalf.io/sunday-clays-backend:sha-<7>"),
        (
            deployer_on_ghcr,
            "deployer: image must be registry.thehalf.io/sunday-clays-deployer:sha-<7>",
        ),
        (
            caddy_on_a_per_arch_tag,
            "caddy: image must be registry.thehalf.io/sunday-clays-frontend:sha-<7>",
        ),
        (
            worker_on_another_fleet_registry,
            "worker: image must be registry.thehalf.io/sunday-clays-backend:sha-<7>",
        ),
        (missing_deployer, "deployer: service missing"),
        (
            arch_on_worker,
            "worker: must not be constrained to an architecture (node.platform.arch==x86_64)",
        ),
        (
            arm_label_on_caddy,
            "caddy: must not be constrained to an architecture (node.labels.arch==arm64)",
        ),
        (
            vm_label_on_api,
            "api: must not be constrained to an architecture (node.labels.type==vm)",
        ),
        (
            arch_on_db,
            "db: must not be constrained to an architecture (node.platform.arch!=aarch64)",
        ),
        (backup_on_another_node, "db and backup must be pinned to one node"),
        (api_on_a_ci_tag, "api: image must be registry.thehalf.io/sunday-clays-backend:sha-<7>"),
        (
            caddy_runs_the_backend,
            "caddy: image must be registry.thehalf.io/sunday-clays-frontend:sha-<7>",
        ),
        (
            worker_from_another_registry,
            "worker: image must be registry.thehalf.io/sunday-clays-backend:sha-<7>",
        ),
        (
            backup_runs_the_frontend,
            "backup: image must be registry.thehalf.io/sunday-clays-backend:sha-<7>",
        ),
        (
            spaced_arch_on_worker,
            "worker: must not be constrained to an architecture (node.platform.arch==x86_64)",
        ),
        (api_pinned_to_a_node, "api: must not be pinned to a node (node.hostname==autopirate)"),
        (db_on_two_nodes, "db: more than one node.hostname== constraint"),
        (missing_worker, "worker: service missing"),
        (drop_hostname, "db: missing node.hostname== placement constraint"),
        (two_replicas, "backup: deploy.replicas must be 1"),
        (named_volume, "db: needs a bind mount under /var/data/sunday-clays/"),
        (unprefixed_secret, "secret db_password: name 'db_password' must start with sundayclays_"),
        (caddy_ports, "caddy: must not publish ports"),
        (caddy_off_the_public_edge, "caddy: must join the external network edge_public"),
        (caddy_off_the_public_edge_list_form, "caddy: must join the external network edge_public"),
        (edge_public_not_external, "network edge_public: must be external"),
        (
            router_without_the_strip_middleware,
            "caddy: router sundayclays must strip CF-Connecting-IP",
        ),
        (
            strip_middleware_that_sets_a_value,
            "caddy: router sundayclays must strip CF-Connecting-IP",
        ),
        (
            strip_middleware_not_declared,
            "caddy: router sundayclays must strip CF-Connecting-IP",
        ),
        (latest_image, "api: image 'registry.thehalf.io/sunday-clays-backend:latest'"),
        (untagged_image, "api: image 'registry.thehalf.io/sunday-clays-backend'"),
        (missing_backup, "backup: service missing"),
        (short_named_volume, "db: needs a bind mount under /var/data/sunday-clays/"),
        (short_named_volume, "db: named volume 'db-data' is not allowed"),
        (named_volume, "db: named volume 'db-data' is not allowed"),
        (named_volume_on_api, "api: named volume 'x' is not allowed"),
        (short_named_volume_on_worker, "worker: named volume 'scratch' is not allowed"),
        (anonymous_volume_on_caddy, "caddy: named volume"),
        (
            deployer_state_on_a_named_volume,
            "deployer: must bind /var/data/sunday-clays/deployer to /state",
        ),
        (
            deployer_state_in_the_wrong_directory,
            "deployer: must bind /var/data/sunday-clays/deployer to /state",
        ),
        (
            deployer_state_at_the_wrong_target,
            "deployer: must bind /var/data/sunday-clays/deployer to /state",
        ),
        (short_bind_elsewhere, "backup: needs a bind mount under /var/data/sunday-clays/"),
    ],
)
def test_each_rule_rejects_its_violation(
    mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    stack = copy.deepcopy(VALID)
    mutate(stack)

    result = run(stack)

    assert result.returncode == 1
    assert message in result.stderr


def spaced_constraints(stack: dict[str, Any]) -> None:
    for service in stack["services"].values():
        placement = service["deploy"]["placement"]
        placement["constraints"] = [c.replace("==", " == ") for c in placement["constraints"]]


def short_syntax_binds(stack: dict[str, Any]) -> None:
    stack["services"]["db"]["volumes"] = ["/var/data/sunday-clays/db:/var/lib/postgresql/data"]
    stack["services"]["backup"]["volumes"] = ["/var/data/sunday-clays/backups:/backups"]


def list_form_labels(stack: dict[str, Any]) -> None:
    caddy = stack["services"]["caddy"]
    caddy["deploy"]["labels"] = [f"{k}={v}" for k, v in caddy["deploy"]["labels"].items()]
    caddy["networks"] = ["default", "traefik_public", "edge_public"]


def provider_suffixed_middlewares(stack: dict[str, Any]) -> None:
    labels = stack["services"]["caddy"]["deploy"]["labels"]
    labels["traefik.http.routers.sundayclays.middlewares"] = (
        "other@swarm, sundayclays-strip-cf@swarm"
    )


@pytest.mark.parametrize(
    "respell",
    [spaced_constraints, short_syntax_binds, list_form_labels, provider_suffixed_middlewares],
)
def test_equivalent_spellings_of_a_valid_stack_pass(
    respell: Callable[[dict[str, Any]], None],
) -> None:
    stack = copy.deepcopy(VALID)
    respell(stack)

    result = run(stack)

    assert result.returncode == 0, result.stderr


def _on_registry(stack: dict[str, Any], registry: str) -> None:
    for service in stack["services"].values():
        image = service.get("image", "")
        if image.startswith("registry.thehalf.io/"):
            service["image"] = registry + image.removeprefix("registry.thehalf.io")


def test_sc_registry_moves_the_pull_registry_for_every_release_image() -> None:
    stack = copy.deepcopy(VALID)
    _on_registry(stack, "reg.lan:5000")

    assert run(stack, sc_registry="reg.lan:5000").returncode == 0
    refused = run(stack)  # the render used SC_REGISTRY but the check was told nothing
    assert refused.returncode == 1
    assert "must be registry.thehalf.io/sunday-clays-backend:sha-<7>" in refused.stderr


def test_ghcr_is_refused_even_when_sc_registry_names_it() -> None:
    stack = copy.deepcopy(VALID)
    _on_registry(stack, "ghcr.io/gitgat")

    result = run(stack, sc_registry="ghcr.io/gitgat")

    assert result.returncode == 1
    assert "not ghcr.io" in result.stderr


def test_reads_a_file_argument(tmp_path: Path) -> None:
    rendered = tmp_path / "stack.yaml"
    rendered.write_text(yaml.safe_dump(VALID))

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(rendered)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


def test_non_mapping_input_is_rejected() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="- just\n- a list\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "not a rendered stack" in result.stderr
