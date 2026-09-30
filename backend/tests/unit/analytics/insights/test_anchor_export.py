"""The anchor registry and the file the frontend's anchor-resolution test reads (spec §3.6.4)."""

import json
from pathlib import Path

from sunday_clays.analytics.insights.anchors import ANCHORS

EXPORT = Path(__file__).parents[3] / "golden" / "insight_anchors.json"


def test_the_exported_anchor_list_matches_the_registry():
    exported = json.loads(EXPORT.read_text())
    assert exported == {
        a.id: {"route": a.route, "urlKey": a.id}
        for a in sorted(ANCHORS.values(), key=lambda a: a.id)
    }
