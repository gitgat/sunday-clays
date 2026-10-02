# Backend image: api, worker and backup services (C1). Build context: backend/.
FROM python:3.13.15-slim-trixie AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /bin/uv
# Use the image's interpreter (never a uv-managed one) so the venv works in the runtime stage.
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13.15-slim-trixie
# pg_dump/pg_restore/psql 17 from PGDG so the client matches the postgres:17 server.
RUN set -eux; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl tzdata; \
    install -d /usr/share/postgresql-common/pgdg; \
    curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc; \
    . /etc/os-release; \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client-17; \
    apt-get purge -y curl; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --no-create-home app \
    && install -d -o 10001 -g 10001 -m 0750 /backups
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY backup/ ./backup/
RUN chmod 0755 /app/backup/*.sh
ARG APP_VERSION=dev
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_VERSION=$APP_VERSION
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "sunday_clays.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
