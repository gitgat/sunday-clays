"""Job handler registry (``@handler``), handler-module discovery and the recompute handler (C6)."""

import importlib
import importlib.util
import pkgutil
from collections.abc import Callable
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import run_pipeline
from sunday_clays.models import AppState

Handler = Callable[[Session, dict[str, Any]], None]
HANDLERS: dict[str, Handler] = {}
HANDLER_PACKAGES = ("sunday_clays.jobs", "sunday_clays.weather")


def handler(kind: str) -> Callable[[Handler], Handler]:
    """Register the decorated function as the handler for job ``kind`` (one handler per kind)."""

    def register(fn: Handler) -> Handler:
        existing = HANDLERS.get(kind)
        if existing is not None and existing is not fn:
            raise ValueError(f"job kind {kind!r} already has a handler")
        HANDLERS[kind] = fn
        return fn

    return register


def load_handlers() -> dict[str, Handler]:
    """Import every module of the handler packages (skipping absent packages); returns HANDLERS."""
    for package_name in HANDLER_PACKAGES:
        if importlib.util.find_spec(package_name) is None:
            continue
        package = importlib.import_module(package_name)
        for info in pkgutil.iter_modules(package.__path__):
            importlib.import_module(f"{package_name}.{info.name}")
    return HANDLERS


@handler("recompute")
def handle_recompute(session: Session, payload: dict[str, Any]) -> None:
    """Re-run the pipeline; ``{"recalibrate": true}`` first drops the stored skill params (C6)."""
    if payload.get("recalibrate"):
        session.execute(delete(AppState).where(AppState.key == "skill_params"))
    run_pipeline(session)
