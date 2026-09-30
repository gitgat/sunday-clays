import pytest
from sqlalchemy.orm import Session

from sunday_clays.analytics import pipeline
from sunday_clays.analytics.pipeline import (
    RecomputeStep,
    bump_data_version,
    get_data_version,
    run_pipeline,
)


def test_data_version_starts_at_1_and_increments(session: Session) -> None:
    assert get_data_version(session) == 0
    assert bump_data_version(session) == 1
    assert bump_data_version(session) == 2
    assert get_data_version(session) == 2


def test_run_pipeline_runs_steps_in_order_then_bumps(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, int]] = []
    steps = [
        RecomputeStep("metrics", 10, lambda s: seen.append(("metrics", get_data_version(s)))),
        RecomputeStep("skill", 30, lambda s: seen.append(("skill", get_data_version(s)))),
    ]
    monkeypatch.setattr(pipeline, "discover_steps", lambda: steps)
    assert run_pipeline(session) == ["metrics", "skill"]
    assert seen == [("metrics", 0), ("skill", 0)]  # the bump happens after every step
    assert get_data_version(session) == 1
