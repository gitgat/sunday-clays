"""Fixtures for achievement integration tests in the committed-fixtures (fx) world."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd
import pytest

from sunday_clays.analytics.achievements import registry
from sunday_clays.analytics.achievements.context import AchContext
from sunday_clays.analytics.achievements.registry import Achievement, Award, Category


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Achievement]:
    registry.load_all()
    fresh: dict[str, Achievement] = {}
    monkeypatch.setattr(registry, "_REGISTRY", fresh)
    return fresh


def _events_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    return pd.DataFrame(
        {
            "shooter_id": days["shooter_id"],
            "event_date": days["event_ts"],
            "value": days["n_events"].astype(float),
        }
    )


def _perfect_round(ctx: AchContext) -> Iterator[Award]:
    perfect = ctx.rounds[ctx.rounds["score"] == 50]
    for sid, ts, rid in zip(
        perfect["shooter_id"], perfect["event_ts"], perfect["round_id"], strict=True
    ):
        yield Award(int(sid), "toy_perfect", ts.date(), int(rid), {})


@pytest.fixture
def toy_trophies(isolated_registry: dict[str, Achievement]) -> dict[str, Achievement]:
    """Two toys: tiered toy_events (1 / 10 events) and one-off toy_perfect (first 50)."""
    registry.register(
        Achievement(
            code="toy_events",
            name="Toy Events",
            description="Events attended.",
            category=Category.MILESTONE,
            art_key="toy_events",
            tiers=registry.make_tiers((1, 10), "events", singular="event"),
            value=_events_value,
        )
    )
    registry.register(
        Achievement(
            code="toy_perfect",
            name="Toy Perfect",
            description="Shot a 50.",
            category=Category.SCORING,
            art_key="toy_perfect",
            evaluate=_perfect_round,
        )
    )
    return isolated_registry
