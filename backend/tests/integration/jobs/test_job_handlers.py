import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.jobs import handlers
from sunday_clays.jobs.handlers import HANDLERS, handler, load_handlers
from sunday_clays.models import AppState


def test_load_handlers_finds_recompute_and_skips_absent_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        handlers, "HANDLER_PACKAGES", ("sunday_clays.jobs", "sunday_clays.no_such_package")
    )
    assert "recompute" in load_handlers()


def test_load_handlers_imports_every_module_of_a_handler_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = tmp_path / "fake_handlers_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "auto.py").write_text(
        "from sunday_clays.jobs.handlers import handler\n"
        "@handler('t_auto')\n"
        "def run(session, payload):\n"
        "    return None\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(handlers, "HANDLER_PACKAGES", ("fake_handlers_pkg",))
    try:
        assert "t_auto" in load_handlers()
    finally:
        HANDLERS.pop("t_auto", None)
        for mod in [m for m in sys.modules if m.startswith("fake_handlers_pkg")]:
            del sys.modules[mod]


def test_a_second_handler_for_the_same_kind_is_rejected() -> None:
    def first(session: Session, payload: dict[str, Any]) -> None: ...

    def second(session: Session, payload: dict[str, Any]) -> None: ...

    try:
        handler("t_dup")(first)
        assert handler("t_dup")(first) is first  # re-registering the same function is fine
        with pytest.raises(ValueError, match="t_dup"):
            handler("t_dup")(second)
    finally:
        HANDLERS.pop("t_dup", None)


def test_recompute_runs_the_pipeline(session: Session) -> None:
    before = get_data_version(session)
    load_handlers()["recompute"](session, {})
    assert get_data_version(session) == before + 1


@pytest.mark.parametrize(("payload", "params_seen"), [({}, [1]), ({"recalibrate": True}, [0])])
def test_recompute_drops_skill_params_before_the_pipeline_only_when_recalibrating(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
    params_seen: list[int],
) -> None:
    session.add(AppState(key="skill_params", value={"obs_var": 14}))
    session.flush()
    seen: list[int] = []

    def pipeline(s: Session) -> list[str]:
        count = select(func.count()).where(AppState.key == "skill_params")
        seen.append(s.scalar(count) or 0)
        return []

    monkeypatch.setattr(handlers, "run_pipeline", pipeline)
    load_handlers()["recompute"](session, payload)
    assert seen == params_seen
