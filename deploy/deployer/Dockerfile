# Deployer image (Plan 13): deployer.py (standard library only) + git + the Docker CLI.
# Build context: deploy/deployer/. Runs only in the Swarm (compose.swarm.yaml `deployer`).
# Pinned to a patch release; Dependabot does not track this file, so bump it by hand.
FROM docker:28.5.2-cli AS docker-cli

FROM python:3.13.15-slim-trixie
RUN set -eux; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates git; \
    rm -rf /var/lib/apt/lists/*
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
# buildx: `docker buildx imagetools create` copies a release's whole multi-arch index from GHCR
# into the fleet registry, registry to registry, without pulling it onto the node.
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-buildx \
    /usr/local/libexec/docker/cli-plugins/docker-buildx
COPY deployer.py /app/deployer.py
# DOCKER_CONFIG lives in the container layer, never in the /state volume, so the registry login
# is gone with the container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DOCKER_CONFIG=/tmp/docker-config \
    STATE_DIR=/state
# Runs as root: the host's /var/run/docker.sock is root:docker 0660 and Swarm services cannot
# join host groups. Whoever holds the socket is root on the manager anyway (deploy/README.md).
# The heartbeat is touched before every poll; 4 h covers the slowest full deploy (3 × 10 min
# mirror copies + 4 × 20 min update timeout + 10 min api version wait + 3 × 20 min rolling back
# after a failure = 3 h, plus the inspect calls).
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python3", "-c", "import os,sys,time; sys.exit(time.time()-os.path.getmtime('/tmp/deployer-heartbeat')>14400)"]
ENTRYPOINT ["python3", "/app/deployer.py"]
CMD ["run"]
