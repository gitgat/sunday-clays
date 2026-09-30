import sys
from pathlib import Path

import pytest

from sunday_clays.analytics.pipeline import RecomputeStep, discover_steps


def _package(tmp_path: Path, name: str, modules: dict[str, str]) -> None:
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    for module, body in modules.items():
        (pkg / f"{module}.py").write_text(body)


STEP = (
    "from sunday_clays.analytics.pipeline import RecomputeStep\n"
    "STEP = RecomputeStep({name!r}, {order}, lambda session: None)\n"
)


def test_real_steps_package_is_discoverable() -> None:
    assert all(isinstance(step, RecomputeStep) for step in discover_steps())


def test_steps_are_sorted_by_order_and_private_modules_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _package(
        tmp_path,
        "fake_steps_ok",
        {
            "s30_skill": STEP.format(name="skill", order=30),
            "s10_metrics": STEP.format(name="metrics", order=10),
            "_helpers": "VALUE = 1\n",
        },
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        assert [s.name for s in discover_steps("fake_steps_ok")] == ["metrics", "skill"]
    finally:
        for mod in [m for m in sys.modules if m.startswith("fake_steps_ok")]:
            del sys.modules[mod]


def test_a_step_module_without_step_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _package(tmp_path, "fake_steps_bad", {"s10_broken": "X = 1\n"})
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        with pytest.raises(TypeError, match="s10_broken"):
            discover_steps("fake_steps_bad")
    finally:
        for mod in [m for m in sys.modules if m.startswith("fake_steps_bad")]:
            del sys.modules[mod]
