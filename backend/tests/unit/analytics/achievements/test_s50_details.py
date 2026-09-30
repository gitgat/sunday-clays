"""s50 stores Award.details as JSON text, numpy scalars included (Plan 10 T1, fix round 1)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from sunday_clays.analytics.steps.s50_achievements import details_json


def test_details_json_converts_numpy_scalars_to_python():
    """Definitions often read details off a frame, which yields numpy scalars."""
    details = {
        "score": np.int64(50),
        "hits": np.int32(7),
        "mean": np.float64(1.5),
        "pct": np.float32(0.5),
        "clean": np.bool_(True),
        "n": 3,
    }
    assert details_json(details) == (
        '{"clean": true, "hits": 7, "mean": 1.5, "n": 3, "pct": 0.5, "score": 50}'
    )


def test_details_json_rejects_other_non_json_values():
    with pytest.raises(TypeError, match="date is not JSON serializable"):
        details_json({"when": date(2025, 1, 5)})
