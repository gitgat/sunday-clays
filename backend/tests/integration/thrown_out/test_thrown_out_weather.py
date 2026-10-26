"""Weather readers on the thrown-out world (T3c)."""

from datetime import date

from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, predictions, weather_effects

THROWN_OUT_SUNDAY = date(2026, 10, 25)


def test_weather_event_frame_carries_stats_excluded(fx_thrown_out_session: Session) -> None:
    weather = weather_effects.load_weather_events(fx_thrown_out_session)
    assert len(weather) == 10
    assert weather.loc[weather["stats_excluded"], "event_date"].tolist() == [THROWN_OUT_SUNDAY]


def test_attendance_probabilities_still_count_the_thrown_out_sunday(
    fx_thrown_out_session: Session,
) -> None:  # guard (spec 4)
    s = fx_thrown_out_session
    probs = predictions.attendance_probs(
        frames.load_rounds(s), predictions._scored_events(s), date(2026, 11, 1)
    )
    assert len(probs) == 9
    assert set(probs.values()) == {10 / 13}
