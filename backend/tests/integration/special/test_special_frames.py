"""No leak at the frames seam and the raw-SQL readers (Plan 17 Task 3, Review Focus 1).

Every score frame of the special world must equal the regular world's: same rounds, metrics,
ratings, events and station hits. Round ids differ between the worlds (each rebuild renumbers),
so they are dropped before comparing.
"""

from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, predictions, weather_effects
from sunday_clays.analytics.achievements.context import load_station_entries
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.insights.store import readiness_from_db
from sunday_clays.analytics.stations import load_station_frame

SPECIAL = date(2026, 9, 20)
SCORES = {
    "Hadley, Ike": 55,
    "Kaplan, Noel": 51,
    "Devlin, Sid": 48,
    "Abernathy, Preston": 44,
    "Kim, Pat": 39,
}


def _both(fn: Callable[[Session], Any], base: Session, special: Session) -> tuple[Any, Any]:
    clear_cache()
    left = fn(base)
    clear_cache()
    return left, fn(special)


def _norm(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    out = df.drop(columns=[c for c in ("round_id",) if c in df.columns])
    return out.sort_values(keys, kind="mergesort").reset_index(drop=True)


SCORE_FRAMES = [
    (frames.load_rounds, ["event_date", "shooter_id", "name_key", "ordinal"]),
    (frames.load_events, ["event_date"]),
    (frames.load_station_hits, ["event_date", "entry_row", "station_label"]),
    (frames.load_rating_history, ["shooter_id", "event_date"]),
    (load_station_frame, ["event_date", "entry_row", "station_label"]),
    (load_station_entries, ["event_date", "entry_row", "station_label"]),
]


@pytest.mark.parametrize(
    ("loader", "keys"),
    SCORE_FRAMES,
    ids=["rounds", "events", "station_hits", "ratings", "stations_page", "ach_stations"],
)
def test_special_world_frames_match_the_regular_world(
    loader: Callable[[Session], pd.DataFrame],
    keys: list[str],
    fx_session: Session,
    fx_special_session: Session,
) -> None:
    base, special = _both(loader, fx_session, fx_special_session)

    pd.testing.assert_frame_equal(_norm(base, keys), _norm(special, keys))


def test_no_score_frame_holds_a_score_above_fifty(fx_special_session: Session) -> None:
    clear_cache()
    assert frames.load_rounds(fx_special_session)["score"].max() <= 50
    assert SPECIAL not in set(frames.load_rounds(fx_special_session)["event_date"])
    assert SPECIAL not in set(frames.load_events(fx_special_session)["event_date"])
    assert SPECIAL not in set(frames.load_station_hits(fx_special_session)["event_date"])


def test_the_calendar_is_the_events_plus_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    base, calendar = _both(frames.load_calendar, fx_session, fx_special_session)

    assert list(calendar.columns) == list(frames.CALENDAR_COLUMNS)
    regular = calendar[calendar["kind"] == "regular"].reset_index(drop=True)
    pd.testing.assert_frame_equal(regular, base.reset_index(drop=True))
    (row,) = calendar[calendar["kind"] == "special"].to_dict("records")
    assert (row["event_date"], row["label"], row["target_total"]) == (
        SPECIAL,
        "3-Bird Shoot",
        60,
    )
    assert (row["n_shooters"], row["has_scores"], row["results_complete"]) == (5, True, True)
    assert all(pd.isna(row[c]) for c in ("median", "top_score", "difficulty"))
    assert calendar["target_total"].dtype == "int64"


def test_appearances_add_one_special_row_per_shooter_who_came(
    fx_session: Session, fx_special_session: Session
) -> None:
    base, appearances = _both(frames.load_appearances, fx_session, fx_special_session)

    assert list(appearances.columns) == list(frames.APPEARANCE_COLUMNS)
    regular = appearances[appearances["kind"] == "regular"].reset_index(drop=True)
    pd.testing.assert_frame_equal(regular, base.reset_index(drop=True))
    special = appearances[appearances["kind"] == "special"]
    assert set(special["event_date"]) == {SPECIAL}
    assert set(special["display_name"]) == set(SCORES)
    assert special["held"].all()
    clear_cache()
    rounds = frames.load_rounds(fx_session)
    implied = frames.appearances_from_rounds(rounds).reset_index(drop=True)
    pd.testing.assert_frame_equal(implied, base.reset_index(drop=True))


def test_special_rounds_and_station_hits_are_the_special_sunday_only(
    fx_session: Session, fx_special_session: Session
) -> None:
    clear_cache()
    assert frames.load_special_rounds(fx_session).empty
    assert frames.load_special_station_hits(fx_session).empty
    clear_cache()
    rounds = frames.load_special_rounds(fx_special_session)
    assert list(rounds.columns) == list(frames.SPECIAL_ROUND_COLUMNS)
    assert dict(zip(rounds["display_name"], rounds["score"], strict=True)) == SCORES
    assert list(rounds["score"]) == sorted(SCORES.values(), reverse=True)
    assert set(rounds["label"]) == {"3-Bird Shoot"}
    assert set(rounds["target_total"]) == {60}
    hits = frames.load_special_station_hits(fx_special_session)
    assert list(hits.columns) == list(frames.STATION_HIT_COLUMNS)
    assert len(hits) == 50
    assert set(hits["target_count"]) == {6}
    assert set(hits["round_id"].astype(int)) == set(rounds["round_id"])


def test_the_station_readiness_count_skips_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    base, special = _both(readiness_from_db, fx_session, fx_special_session)
    assert special.station_sundays == base.station_sundays


def _give_the_special_sunday_weather(session: Session) -> None:
    """Copy 2026-09-13's weather row onto SPECIAL, so only the kind filter can exclude it."""
    cols = [
        c["name"]
        for c in inspect(session.connection()).get_columns("event_weather")
        if c["name"] != "event_date"
    ]
    names = ", ".join(cols)
    session.execute(
        text(
            f"INSERT INTO event_weather (event_date, {names}) "  # noqa: S608 - schema names
            f"SELECT :special, {names} FROM event_weather WHERE event_date = :src"
        ),
        {"special": SPECIAL, "src": date(2026, 9, 13)},
    )
    clear_cache()


def test_the_weather_frame_and_club_model_skip_a_special_sunday_that_has_weather(
    fx_session: Session, fx_special_session: Session
) -> None:
    _give_the_special_sunday_weather(fx_special_session)

    base, special = _both(weather_effects.load_weather_events, fx_session, fx_special_session)
    assert SPECIAL not in set(special["event_date"])
    assert len(special) == len(base)
    pd.testing.assert_frame_equal(base.reset_index(drop=True), special.reset_index(drop=True))
    base_model, special_model = _both(
        lambda s: weather_effects.club_regression(s, (), weather_effects.COVARIATES),
        fx_session,
        fx_special_session,
    )
    assert special_model == base_model


def test_predictions_are_unchanged(fx_session: Session, fx_special_session: Session) -> None:
    target = date(2026, 10, 4)
    base, special = _both(
        lambda s: predictions.next_predictions(s, target, None, None),
        fx_session,
        fx_special_session,
    )
    assert special == base


def test_a_dropped_repeats_station_hits_never_reach_a_station_frame(
    fx_special_session: Session,
) -> None:
    """P17-R3 leaves round_id NULL on a dropped repeat's hits; special dates are still excluded
    by the event's kind, not by round_id."""
    session = fx_special_session
    session.execute(
        text(
            "UPDATE station_hits SET round_id = NULL WHERE event_date = :d"
            " AND entry_row = (SELECT min(entry_row) FROM station_hits WHERE event_date = :d)"
        ),
        {"d": SPECIAL},
    )
    orphaned = session.execute(
        text(
            "SELECT count(*) FROM station_hits WHERE event_date = :d AND round_id IS NULL"
            " AND shooter_id IS NOT NULL"
        ),
        {"d": SPECIAL},
    ).scalar_one()
    assert orphaned > 0
    clear_cache()
    for frame in (
        frames.load_station_hits(session),
        load_station_frame(session),
        load_station_entries(session),
    ):
        assert SPECIAL not in set(frame["event_date"])
