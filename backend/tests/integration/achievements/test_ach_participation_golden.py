"""Participation trophies on the committed fixtures (Plan 10 T2 golden).

Expected holder counts are derived from the raw `rounds` table with SQL, never from the achievement
code. The fx world ran the whole pipeline (incl. s50) once per pytest run.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

FAMILY_SQL = {
    "clays_broken": "sum(score)",
    "clays_thrown": "count(*) * 50",
    "events": "count(DISTINCT event_date)",
    "years_active": "count(DISTINCT extract(year FROM event_date))",
}
THRESHOLDS = {
    "clays_broken": (100, 500, 1000, 2500, 5000, 10000),
    "clays_thrown": (500, 1000, 2500, 5000, 10000),
    "events": (1, 10, 25, 50, 100, 150, 200, 250),
    "years_active": (2, 3, 5, 7),
}


def scalar(session: Any, sql: str, **params: Any) -> int:
    return int(session.execute(text(sql), params).scalar_one())


def awarded(session: Any, code: str) -> int:
    return scalar(session, "SELECT count(*) FROM achievements_awarded WHERE code = :c", c=code)


@pytest.mark.parametrize(
    ("family", "level", "threshold"),
    [
        (family, level, t)
        for family, ts in THRESHOLDS.items()
        for level, t in enumerate(ts, start=1)
    ],
)
def test_family_holder_counts_match_raw_rounds(fx_session, family, level, threshold):
    # FAMILY_SQL holds module constants only; the threshold is a bound parameter.
    holders = (
        "SELECT count(*) FROM (SELECT shooter_id FROM rounds GROUP BY shooter_id "  # noqa: S608
        f"HAVING {FAMILY_SQL[family]} >= :t) h"
    )
    expected = scalar(fx_session, holders, t=threshold)
    assert awarded(fx_session, f"{family}:{level}") == expected


@pytest.mark.parametrize(("level", "threshold"), [(1, 20), (2, 30), (3, 40)])
def test_big_year_holder_counts_match_raw_rounds(fx_session, level, threshold):
    expected = scalar(
        fx_session,
        "SELECT count(*) FROM (SELECT shooter_id FROM ("
        "SELECT shooter_id, extract(year FROM event_date) AS y, "
        "count(DISTINCT event_date) AS n FROM rounds GROUP BY 1, 2) per_year "
        "GROUP BY shooter_id HAVING max(n) >= :t) h",
        t=threshold,
    )
    assert awarded(fx_session, f"big_year:{level}") == expected


def test_documented_anchor_counts(fx_session):
    # Hand-checked against the raw workbook when this plan was written (332 identity keys).
    assert awarded(fx_session, "clays_broken:3") == 65
    assert awarded(fx_session, "events:2") == 107


def test_clays_broken_awards_are_dated_at_first_crossing(fx_session):
    expected = dict(
        fx_session.execute(
            text(
                "SELECT shooter_id, min(event_date) FROM ("
                " SELECT shooter_id, event_date,"
                "  sum(day_sum) OVER (PARTITION BY shooter_id ORDER BY event_date) AS running"
                " FROM (SELECT shooter_id, event_date, sum(score) AS day_sum"
                "  FROM rounds GROUP BY 1, 2) d"
                ") c WHERE running >= 1000 GROUP BY shooter_id"
            )
        ).all()
    )
    got = dict(
        fx_session.execute(
            text(
                "SELECT shooter_id, event_date FROM achievements_awarded "
                "WHERE code = 'clays_broken:3'"
            )
        ).all()
    )
    assert got == expected


def test_doubleheader_holders_match_raw_rounds(fx_session):
    expected = scalar(
        fx_session,
        "SELECT count(DISTINCT shooter_id) FROM (SELECT shooter_id, event_date FROM rounds "
        "GROUP BY 1, 2 HAVING count(*) >= 2) d",
    )
    assert awarded(fx_session, "doubleheader") == expected


def test_joined_club_holders_match_raw_rounds(fx_session):
    expected = scalar(
        fx_session,
        "SELECT count(DISTINCT m.shooter_id) FROM rounds m JOIN rounds g "
        "ON g.shooter_id = m.shooter_id AND g.event_date < m.event_date "
        "WHERE m.status = 'member' AND g.status = 'guest'",
    )
    assert awarded(fx_session, "joined_club") == expected


def test_welcome_back_awards_match_raw_gaps(fx_session):
    gaps = (
        "SELECT shooter_id, event_date - lag(event_date) "
        "OVER (PARTITION BY shooter_id ORDER BY event_date) AS gap "
        "FROM (SELECT DISTINCT shooter_id, event_date FROM rounds) d"
    )
    # `gaps` is the constant above; nothing user-supplied reaches these f-strings.
    returns = f"SELECT count(*) FROM ({gaps}) g WHERE gap >= 180"  # noqa: S608
    returners = f"SELECT count(DISTINCT shooter_id) FROM ({gaps}) g WHERE gap >= 180"  # noqa: S608
    awarded_shooters = (
        "SELECT count(DISTINCT shooter_id) FROM achievements_awarded WHERE code = 'welcome_back'"
    )
    assert awarded(fx_session, "welcome_back") == scalar(fx_session, returns)
    assert scalar(fx_session, awarded_shooters) == scalar(fx_session, returners)


def test_anniversary_holders_match_raw_rounds(fx_session):
    for years in (1, 5):
        expected = scalar(
            fx_session,
            "SELECT count(DISTINCT d.shooter_id) FROM (SELECT DISTINCT shooter_id, event_date "
            "FROM rounds) d JOIN (SELECT shooter_id, min(event_date) AS first FROM rounds "
            "GROUP BY 1) f ON f.shooter_id = d.shooter_id "
            "WHERE d.event_date - f.first BETWEEN :lo AND :hi",
            lo=365 * years - 7,
            hi=365 * years + 7,
        )
        assert awarded(fx_session, f"anniversary_{years}") == expected


def test_both_disciplines_holders_match_raw_rounds(fx_session):
    expected = scalar(
        fx_session,
        "SELECT count(*) FROM (SELECT r.shooter_id FROM rounds r JOIN events e "
        "ON e.event_date = r.event_date GROUP BY r.shooter_id "
        "HAVING count(DISTINCT e.round_type) = 2) h",
    )
    assert awarded(fx_session, "both_disciplines") == expected


def test_four_seasons_holders_match_raw_rounds(fx_session):
    expected = scalar(
        fx_session,
        "SELECT count(DISTINCT shooter_id) FROM ("
        " SELECT shooter_id,"
        "  extract(year FROM event_date) + (extract(month FROM event_date) = 12)::int AS sy,"
        "  count(DISTINCT (extract(month FROM event_date)::int % 12) / 3) AS n"
        " FROM rounds GROUP BY 1, 2) s WHERE n >= 4",
    )
    assert awarded(fx_session, "four_seasons") == expected
