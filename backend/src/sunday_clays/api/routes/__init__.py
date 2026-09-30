"""Router auto-discovery (C2): every public module here defines ``router: APIRouter``."""

import importlib
import pkgutil

from fastapi import APIRouter


def discover_routers() -> list[tuple[str, APIRouter]]:
    """(module name, router) for every module not starting with ``_``, sorted by module name."""
    found: list[tuple[str, APIRouter]] = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            raise TypeError(f"{module.__name__} must define router: APIRouter")
        found.append((info.name, router))
    return sorted(found, key=lambda item: item[0])
