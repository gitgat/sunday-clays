from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def service(compose_file: str, name: str) -> dict[str, Any]:
    services: dict[str, dict[str, Any]] = yaml.safe_load((ROOT / compose_file).read_text())[
        "services"
    ]
    return services[name]


def test_caddy_healthcheck_probes_caddy_itself_not_the_api() -> None:
    """In the Swarm an api outage must not turn Caddy unhealthy and get it restarted too."""
    probe = " ".join(service("compose.yaml", "caddy")["healthcheck"]["test"])

    assert "http://127.0.0.1/" in probe
    assert "/api" not in probe


def test_caddy_still_starts_after_a_healthy_api_locally_and_in_ci() -> None:
    for compose_file in ("compose.override.yaml", "compose.test.yaml"):
        depends_on = service(compose_file, "caddy")["depends_on"]

        assert depends_on["api"]["condition"] == "service_healthy", compose_file


def test_the_swarm_overlay_names_no_registry_node_or_lan_host_by_default() -> None:
    """Deploy-time names come from the environment and must be set: no `:-default` for them."""
    text = (ROOT / "compose.swarm.yaml").read_text()
    for variable in ("SC_REGISTRY", "SC_DB_NODE", "SC_LAN_HOST"):
        assert f"${{{variable}:-" not in text, variable
        assert f"${{{variable}:?{variable} is required}}" in text, variable


def test_every_release_image_and_the_deployer_registry_come_from_sc_registry() -> None:
    for name in ("caddy", "api", "worker", "backup", "deployer"):
        image = service("compose.swarm.yaml", name)["image"]
        assert image.startswith("${SC_REGISTRY:?SC_REGISTRY is required}/"), name
    environment = service("compose.swarm.yaml", "deployer")["environment"]
    assert environment["REGISTRY"] == "${SC_REGISTRY:?SC_REGISTRY is required}"


def test_the_lan_router_host_comes_from_sc_lan_host() -> None:
    labels = service("compose.swarm.yaml", "caddy")["deploy"]["labels"]
    rules = [v for k, v in labels.items() if k.endswith(".rule")] if isinstance(labels, dict) else [
        i for i in labels if ".rule=" in i
    ]
    assert any("${SC_LAN_HOST:?SC_LAN_HOST is required}" in r for r in rules)


def test_swarm_restarts_the_worker_even_after_a_clean_exit() -> None:
    """An unhealthy task gets SIGTERM, finishes its job and exits 0; Swarm must restart it."""
    restart = service("compose.swarm.yaml", "worker")["deploy"]["restart_policy"]

    assert restart["condition"] == "any"


@pytest.mark.parametrize("name", ["caddy", "api", "mcp", "db", "backup"])
def test_swarm_restarts_every_long_running_service_even_after_a_clean_exit(name: str) -> None:
    """A task that gets SIGTERM and exits 0 must come back: on-failure left db and backup at 0/1.

    Postgres answers SIGTERM with a clean fast shutdown (exit 0), and so did backup.sh. With
    condition on-failure, Swarm marked both tasks Complete and never replaced them (2026-10-26,
    about 5.5 h without backups). A deliberate stop, scale or update still stops them, because
    Swarm sets the desired state to shutdown first.
    """
    restart = service("compose.swarm.yaml", name)["deploy"]["restart_policy"]

    assert restart["condition"] == "any"


def test_ci_e2e_stack_cannot_hit_the_login_rate_limit_mid_run() -> None:
    """Every e2e login comes from one IP; the limiter itself is covered by backend unit tests."""
    environment = service("compose.test.yaml", "api")["environment"]

    assert int(environment["LOGIN_MAX_FAILURES"]) >= 1000


def test_only_the_data_services_are_pinned_and_only_by_hostname() -> None:
    """Images are multi-arch, so caddy may run on any node; api and worker are x86-only (2026-10-02)."""
    assert "placement" not in service("compose.swarm.yaml", "caddy")["deploy"]
    for name in ("api", "worker"):
        placement = service("compose.swarm.yaml", name)["deploy"]["placement"]
        assert placement == {"constraints": ["node.platform.arch==x86_64"]}, name
    for name in ("db", "backup"):
        placement = service("compose.swarm.yaml", name)["deploy"]["placement"]
        assert placement == {"constraints": ["node.hostname==${SC_DB_NODE:?SC_DB_NODE is required}"]}, name


def test_the_worker_has_a_memory_limit_that_fits_a_raspberry_pi() -> None:
    """A rebuild + calibration peaks near 224 MiB (Plan 13 Decision 22); a Pi has 4 GB."""
    resources = service("compose.swarm.yaml", "worker")["deploy"]["resources"]

    assert resources == {"limits": {"memory": "1G"}, "reservations": {"memory": "256M"}}


def test_swarm_rolls_back_a_failed_update_of_every_app_service() -> None:
    """Plan 13: a task that never turns healthy rolls its service back to the previous image."""
    for name in ("api", "worker", "caddy", "backup"):
        deploy = service("compose.swarm.yaml", name)["deploy"]

        assert deploy["update_config"] == {
            "order": "stop-first",
            "failure_action": "rollback",
            "monitor": "60s",
        }, name
        assert deploy["rollback_config"] == {"order": "stop-first"}, name


def test_the_database_is_never_rolled_back_by_swarm() -> None:
    assert "failure_action" not in service("compose.swarm.yaml", "db")["deploy"]["update_config"]


def test_the_deployer_exists_only_in_the_swarm_overlay() -> None:
    """compose.yaml keeps exactly the five app services and no host binds (Global Constraints)."""
    services = yaml.safe_load((ROOT / "compose.yaml").read_text())["services"]

    assert set(services) == {"caddy", "api", "worker", "db", "backup"}
    for compose_file in ("compose.override.yaml", "compose.test.yaml"):
        assert "deployer" not in yaml.safe_load((ROOT / compose_file).read_text())["services"]


def test_deployer_tokens_rotate_without_touching_the_app_secrets() -> None:
    secrets = yaml.safe_load((ROOT / "compose.swarm.yaml").read_text())["secrets"]

    for key in ("deployer_github_token", "deployer_ghcr_token"):
        assert secrets[key] == {
            "file": f"./secrets/{key}",
            "name": f"sundayclays_{key}_v${{DEPLOYER_SECRETS_REV:-1}}",
        }
    assert service("compose.swarm.yaml", "deployer")["secrets"] == [
        "deployer_github_token",
        "deployer_ghcr_token",
    ]


def test_the_deployer_runs_on_any_manager_whatever_its_architecture() -> None:
    """The Swarm's schedulable managers are arm64 Raspberry Pis (pi-manager-1); the image is multi-arch."""
    deploy = service("compose.swarm.yaml", "deployer")["deploy"]

    assert deploy["placement"] == {"constraints": ["node.role==manager"]}
    assert deploy["resources"] == {"limits": {"memory": "256M"}}


def test_caddy_takes_the_client_ip_from_cloudflare_then_the_internal_proxy() -> None:
    """Plan 13 T7: the tunnel path carries CF-Connecting-IP, the LAN path X-Forwarded-For."""
    caddyfile = (ROOT / "deploy/caddy/Caddyfile").read_text()
    servers = caddyfile.split("servers {", 1)[1].split("\n\t}\n", 1)[0]

    assert "client_ip_headers CF-Connecting-IP X-Forwarded-For" in servers
    assert "trusted_proxies static {$TRUSTED_PROXIES:127.0.0.1/32}" in servers
    assert "trusted_proxies_strict" in servers


def test_the_api_snippet_still_sets_x_real_ip_from_the_resolved_client_ip() -> None:
    caddyfile = (ROOT / "deploy/caddy/Caddyfile").read_text()

    assert "header_up X-Real-IP {client_ip}" in caddyfile


def test_caddy_joins_the_public_edge_and_the_internal_router_strips_the_cloudflare_header() -> None:
    caddy = service("compose.swarm.yaml", "caddy")
    labels = caddy["deploy"]["labels"]
    networks = yaml.safe_load((ROOT / "compose.swarm.yaml").read_text())["networks"]

    assert caddy["networks"] == ["default", "traefik_public", "edge_public"]
    assert networks["edge_public"] == {"external": True}
    assert caddy["environment"]["TRUSTED_PROXIES"] == "private_ranges"
    assert (
        "traefik.http.middlewares.sundayclays-strip-cf.headers.customrequestheaders.CF-Connecting-IP="
        in labels
    )
    assert "traefik.http.routers.sundayclays.middlewares=sundayclays-strip-cf" in labels


def test_api_runs_without_proxy_headers_and_without_an_access_log() -> None:
    """The access log holds URLs (device id, shooter id) and peer addresses; the About page
    promises neither is tied to a name, so uvicorn must not write it."""
    compose_command = " ".join(service("compose.yaml", "api")["command"])
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text()
    cmd_line = next(line for line in dockerfile.splitlines() if line.startswith("CMD "))

    for command in (compose_command, cmd_line):
        assert "--no-access-log" in command
        assert "--no-proxy-headers" in command


def test_caddy_writes_no_access_log() -> None:
    caddyfile = (ROOT / "deploy" / "caddy" / "Caddyfile").read_text()
    directives = [line.strip().split()[0] for line in caddyfile.splitlines() if line.strip()]

    assert "log" not in directives


def test_stack_has_mcp_service() -> None:
    """The scores MCP server: the backend image, its own command, on the gateway network only."""
    mcp = service("compose.swarm.yaml", "mcp")
    api = service("compose.swarm.yaml", "api")
    overlay = yaml.safe_load((ROOT / "compose.swarm.yaml").read_text())

    assert mcp["image"] == api["image"]
    assert mcp["command"] == ["python", "-m", "sunday_clays.mcp"]
    assert mcp["environment"]["MCP_PORT"] == "8080"
    assert mcp["networks"]["mcp_gateway"] == {"aliases": ["sundayclays-mcp"]}
    assert "traefik_public" not in mcp["networks"]
    assert "edge_public" not in mcp["networks"]
    assert "healthcheck" in mcp and "/healthz" in " ".join(mcp["healthcheck"]["test"])
    assert overlay["networks"]["mcp_gateway"] == {
        "external": True,
        "name": "${SC_MCP_NETWORK:-mcp_gateway}",
    }
    assert overlay["secrets"]["mcp_token"] == {
        "external": True,
        "name": "${SC_MCP_TOKEN_SECRET:-sundayclays_mcp_token}",
    }
    assert [n for n, s in overlay["services"].items() if "mcp_gateway" in (s.get("networks") or {})] == [
        "mcp"
    ]
