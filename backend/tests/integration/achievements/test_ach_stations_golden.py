"""Station trophies on the committed fixtures (Plan 10 T4b golden).

Hand-checked from backend/tests/fixtures/stations_2026-09-27.xlsx:
- On both days station 9 was hardest (86/168 on 09-06, 44/91 on 09-13 → 0.512 and 0.484) and
  nobody cleaned it.
- 2026-09-06 (24 entries) has no station with a sole top score.
- 2026-09-13 (13 entries) has sole top scores at station 4 (Kingsley, Teddy, 6),
  5 (Abernathy, Preston, 7) and 10 (McGinnis, Alvin, 8).
- Grimsby, Gregor is the only shooter with 5 cleaned stations (all on 09-06).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def scalar(session: Any, sql: str, **params: Any) -> int:
    return int(session.execute(text(sql), params).scalar_one())


def name_keys(session: Any, code: str) -> set[tuple[str, str]]:
    return {
        (key, day.isoformat())
        for key, day in session.execute(
            text(
                "SELECT DISTINCT r.name_key, a.event_date FROM achievements_awarded a "
                "JOIN rounds r ON r.shooter_id = a.shooter_id WHERE a.code = :c"
            ),
            {"c": code},
        ).all()
    }


def test_station_top_guns_on_fixture(fx_session):
    assert name_keys(fx_session, "station_top_gun") == {
        ("kingsley teddy", "2026-09-13"),
        ("abernathy preston", "2026-09-13"),
        ("mcginnis alvin", "2026-09-13"),
    }
    stations = sorted(
        int(details["stations"][0])
        for (details,) in fx_session.execute(
            text("SELECT details FROM achievements_awarded WHERE code = 'station_top_gun'")
        ).all()
    )
    assert stations == [4, 5, 10]


def test_nobody_cleaned_the_hardest_station_on_fixture(fx_session):
    assert (
        scalar(
            fx_session,
            "SELECT count(*) FROM achievements_awarded WHERE code = 'hardest_station_clean'",
        )
        == 0
    )


def test_station_cleaner_holders_match_raw_station_hits(fx_session):
    cleaners = scalar(
        fx_session,
        "SELECT count(DISTINCT h.shooter_id) FROM station_hits h JOIN station_layouts l "
        "ON l.event_date = h.event_date AND l.station_label = h.station_label "
        "WHERE h.hits = l.target_count AND h.shooter_id IS NOT NULL",
    )
    assert (
        scalar(
            fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'station_cleaner:1'"
        )
        == cleaners
    )
    assert name_keys(fx_session, "station_cleaner:2") == {("grimsby gregor", "2026-09-06")}
