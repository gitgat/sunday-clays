# Frontend image = Caddy serving the built SPA and proxying /api (C1).
# Build context: the repo root (docker build -f frontend/Dockerfile .), for deploy/caddy/Caddyfile.
FROM node:22.23.3-trixie-slim AS build
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /src/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM caddy:2.11.4-alpine
# Unprivileged: the image's caddy binary carries cap_net_bind_service, so it can still bind :80;
# /config and /data (XDG_CONFIG_HOME/XDG_DATA_HOME: autosave, storage) must be writable.
RUN addgroup -S -g 10002 caddy \
    && adduser -S -D -H -u 10002 -G caddy -h /data -s /sbin/nologin caddy \
    && chown -R 10002:10002 /config /data
COPY deploy/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/frontend/dist /srv
USER 10002:10002
