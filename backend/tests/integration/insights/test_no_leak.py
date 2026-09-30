"""No-leak property (spec §5): a row anchored at Sunday S is the same whether or not the data
after S exists. The skill model's residuals come from the full-data run (pinned), as in s30."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sunday_clays.analytics.insights.engine import evaluate_all
from sunday_clays.analytics.insights.registry import all_kinds
from sunday_clays.analytics.steps.s60_insights import build_frames

ANCHORED = [k for k in all_kinds() if k.anchored]


def anchored_at(fr, day):
    return sorted(
        (
            p.kind.id,
            p.fact.subject_id,
            p.fact.variant,
            repr(sorted(p.fact.params.items())),
            round(p.fact.strength, 9),
        )
        for p in evaluate_all(fr, kinds=ANCHORED, sundays=[day])
        if p.fact.anchor_date == day
    )


@settings(
    max_examples=12,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(position=st.integers(min_value=30, max_value=308))
def test_rows_anchored_at_a_sunday_ignore_later_data(fx_session, position):
    fr = build_frames(fx_session)
    day = fr.sundays[position].date
    full = anchored_at(fr, day)
    cut = anchored_at(fr.until(day), day)
    assert full == cut
