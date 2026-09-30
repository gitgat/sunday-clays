"""s60 guard: the fx world's insight recompute must not blow up. The ceiling catches gross
regressions only (an accidental O(n^2) over every shooter), not runner noise: CI runners vary
too much for a tight budget (owner, 2026-09-29)."""

from __future__ import annotations

import time

import pytest

from sunday_clays.analytics.steps import s60_insights

CEILING_SECONDS = 60.0  # ~3-4 s locally, ~10-20 s on CI with coverage


@pytest.mark.slow
def test_s60_stays_under_the_ceiling(fx_session):
    start = time.perf_counter()
    s60_insights.run(fx_session)
    assert time.perf_counter() - start < CEILING_SECONDS
