"""Ordered recompute steps discovered from ``analytics/steps`` and the data_version counter (C6)."""

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from sunday_clays.models import AppState

STEPS_PACKAGE = "sunday_clays.analytics.steps"
DATA_VERSION_KEY = "data_version"


@dataclass(frozen=True)
class RecomputeStep:
    name: str
    order: int
    run: Callable[[Session], None]


def discover_steps(package: str = STEPS_PACKAGE) -> list[RecomputeStep]:
    """Every ``STEP`` of every non-underscore module in ``package``, sorted by (order, name)."""
    pkg = importlib.import_module(package)
    steps: list[RecomputeStep] = []
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{info.name}")
        step = getattr(module, "STEP", None)
        if not isinstance(step, RecomputeStep):
            raise TypeError(f"{package}.{info.name} must define STEP: RecomputeStep")
        steps.append(step)
    return sorted(steps, key=lambda s: (s.order, s.name))


def get_data_version(session: Session) -> int:
    value = session.scalar(select(AppState.value).where(AppState.key == DATA_VERSION_KEY))
    return 0 if value is None else int(value)


def bump_data_version(session: Session) -> int:
    """Atomically increment ``app_state.data_version`` (starting at 1) and return the new value."""
    stmt = (
        insert(AppState)
        .values(key=DATA_VERSION_KEY, value=1)
        .on_conflict_do_update(
            index_elements=[AppState.key],
            set_={"value": func.to_jsonb(cast(AppState.value, Integer) + 1)},
        )
        .returning(AppState.value)
    )
    return int(session.execute(stmt).scalar_one())


def run_pipeline(session: Session) -> list[str]:
    """Run every discovered step in order, then bump data_version; returns the step names run."""
    names: list[str] = []
    for step in discover_steps():
        step.run(session)
        names.append(step.name)
    bump_data_version(session)
    return names
