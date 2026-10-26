"""The Year in Review frames carry the thrown-out flag (T3d)."""

from datetime import date

from sqlalchemy.orm import Session

from sunday_clays.analytics.yir import load_yir_frames

THROWN_OUT_SUNDAY = date(2026, 10, 25)


def test_yir_event_frame_carries_stats_excluded(fx_thrown_out_session: Session) -> None:
    events = load_yir_frames(fx_thrown_out_session).events
    assert events.loc[events["stats_excluded"], "event_date"].tolist() == [THROWN_OUT_SUNDAY]
