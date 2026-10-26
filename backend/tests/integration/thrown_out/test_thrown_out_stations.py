"""The station page frame leaves out a thrown-out station (T4a)."""

from datetime import date

from sqlalchemy.orm import Session

from sunday_clays.analytics.stations import load_station_frame

THROWN_OUT_SUNDAY = date(2026, 10, 25)


def test_station_page_frame_leaves_out_the_thrown_out_station(
    fx_thrown_out_session: Session,
) -> None:
    frame = load_station_frame(fx_thrown_out_session)
    assert "dropped" in frame.columns
    assert not frame["dropped"].any()
    assert len(frame) == 621
    assert not ((frame["event_date"] == THROWN_OUT_SUNDAY) & (frame["station_label"] == "11")).any()
    hadley = frame[
        (frame["event_date"] == THROWN_OUT_SUNDAY) & (frame["display_name"] == "Hadley, Ike")
    ]
    assert hadley["sheet_total"].unique().tolist() == [36]
