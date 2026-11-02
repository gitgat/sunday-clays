"""Entrypoint: ``python -m sunday_clays.mcp``."""

import os

import uvicorn

from sunday_clays.mcp.auth import load_auth_token
from sunday_clays.mcp.server import build_app, default_session_factory


def main() -> None:
    app = build_app(load_auth_token(), default_session_factory)
    uvicorn.run(
        app,
        host="0.0.0.0",  # noqa: S104  # reachable on the gateway network only; bearer-gated
        port=int(os.environ.get("MCP_PORT") or 8080),
        proxy_headers=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
