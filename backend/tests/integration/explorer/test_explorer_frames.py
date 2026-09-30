"""load_explorer_frames over the committed fixtures (`fx_session`, Plan 03 T6)."""

from sqlalchemy.orm import Session

from sunday_clays.explorer.engine import WEATHER_COLUMNS, load_explorer_frames


def test_frames_cover_the_committed_fixtures(fx_session: Session) -> None:
    frames = load_explorer_frames(fx_session)

    assert len(frames.rounds) == 7480
    assert {"temp_band", "wind_band", "precip_band"} <= set(frames.rounds.columns)
    assert "klass" not in frames.rounds.columns
    assert len(frames.events) == 360
    assert set(WEATHER_COLUMNS) <= set(frames.events.columns)
    # 37 station-sheet entries x 7 stations on the two station events, every one linked.
    assert len(frames.station_hits) == 259
    assert frames.station_hits["round_id"].notna().all()
    assert set(frames.station_hits["target_count"]) == {7, 8}
