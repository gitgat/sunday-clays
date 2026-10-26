"""A thrown-out Sunday keeps official metrics but no adjusted score or skill (T2c)."""

import math
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames

THROWN_OUT_SUNDAY = date(2026, 10, 25)


def test_thrown_out_sunday_keeps_official_metrics_without_adjusted_or_skill(
    fx_thrown_out_session: Session,
) -> None:
    s = fx_thrown_out_session
    rounds = frames.load_rounds(s)
    day = rounds[rounds["event_date"] == THROWN_OUT_SUNDAY]
    assert day["field_median"].tolist() == [35.0] * 9
    assert day["adjusted"].isna().all()
    assert day["expected"].isna().all()
    assert day["residual"].isna().all()
    assert (day["mu_before"] == day["mu_after"]).all()
    hadley = day[day["display_name"] == "Hadley, Ike"].iloc[0]
    assert (hadley["event_rank"], hadley["percentile"], bool(hadley["is_best_round"])) == (
        1.0,
        1.0,
        True,
    )
    prev = rounds[
        (rounds["event_date"] == date(2026, 10, 18)) & (rounds["display_name"] == "Hadley, Ike")
    ].iloc[0]
    assert prev["adjusted"] == 7.0
    assert not math.isnan(prev["residual"])
    events = frames.load_events(s).set_index("event_date")
    assert math.isnan(events.loc[THROWN_OUT_SUNDAY, "difficulty"])
    assert not math.isnan(events.loc[date(2026, 10, 18), "difficulty"])
    assert (
        events.loc[THROWN_OUT_SUNDAY, "median"],
        events.loc[THROWN_OUT_SUNDAY, "top_score"],
    ) == (35.0, 43.0)
    assert (
        s.execute(
            text("SELECT value FROM app_state WHERE key = 'skill_params'")
        ).scalar_one_or_none()
        is not None
    )
