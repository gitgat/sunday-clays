from pathlib import Path
from typing import Any

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


def test_swarm_restarts_the_worker_even_after_a_clean_exit() -> None:
    """An unhealthy task gets SIGTERM, finishes its job and exits 0; Swarm must restart it."""
    restart = service("compose.swarm.yaml", "worker")["deploy"]["restart_policy"]

    assert restart["condition"] == "any"


def test_ci_e2e_stack_cannot_hit_the_login_rate_limit_mid_run() -> None:
    """Every e2e login comes from one IP; the limiter itself is covered by backend unit tests."""
    environment = service("compose.test.yaml", "api")["environment"]

    assert int(environment["LOGIN_MAX_FAILURES"]) >= 1000


def test_only_the_data_services_are_pinned_and_only_by_hostname() -> None:
    """Plan 13: images are multi-arch, so caddy, api and worker may run on any node, Pi or VM."""
    for name in ("caddy", "api", "worker"):
        assert "placement" not in service("compose.swarm.yaml", name)["deploy"], name
    for name in ("db", "backup"):
        placement = service("compose.swarm.yaml", name)["deploy"]["placement"]
        assert placement == {"constraints": ["node.hostname==${SC_DB_NODE:-autopirate}"]}, name


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
    """The Swarm's schedulable managers are arm64 Raspberry Pis (birdo); the image is multi-arch."""
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
