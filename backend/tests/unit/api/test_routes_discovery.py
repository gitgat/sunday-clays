import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

import sunday_clays.api.routes as routes_pkg
from sunday_clays.api.app import create_app
from sunday_clays.api.routes import discover_routers

PROBE_ROUTER = """
from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/{name}")
def probe() -> dict[str, str]:
    return {{"module": "{name}"}}
"""


@pytest.fixture
def routes_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, Path]]:
    """Replaces the routes package search path with two empty directories for one test.

    Only the probe modules a test writes are discovered, so these tests keep passing as later
    plans add real route modules. Two directories, because pkgutil already sorts the modules
    within one directory, and only a cross-directory order exercises discover_routers' sort.
    """
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setattr(routes_pkg, "__path__", [str(first), str(second)])
    before = set(sys.modules)
    yield first, second
    for name in set(sys.modules) - before:
        if name.startswith("sunday_clays.api.routes."):
            del sys.modules[name]


def test_discovery_is_sorted_and_skips_underscore_modules(routes_dirs: tuple[Path, Path]) -> None:
    first, second = routes_dirs
    (first / "zz_probe.py").write_text(PROBE_ROUTER.format(name="zz_probe"))
    (first / "_shared_helpers.py").write_text("VALUE = 1\n")
    (second / "aa_probe.py").write_text(PROBE_ROUTER.format(name="aa_probe"))

    names = [name for name, _router in discover_routers()]

    assert names == ["aa_probe", "zz_probe"]


def test_module_without_router_is_rejected(routes_dirs: tuple[Path, Path]) -> None:
    first, _second = routes_dirs
    (first / "broken.py").write_text("VALUE = 1\n")

    with pytest.raises(TypeError, match=r"sunday_clays\.api\.routes\.broken"):
        discover_routers()


def test_create_app_includes_a_newly_added_module(routes_dirs: tuple[Path, Path]) -> None:
    first, _second = routes_dirs
    (first / "zz_probe.py").write_text(PROBE_ROUTER.format(name="zz_probe"))

    assert "/api/zz_probe" in create_app().openapi()["paths"]
