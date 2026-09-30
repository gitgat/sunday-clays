"""Dormant kinds wake when their inputs arrive (spec §4.5), on the fx world.

The fx workbook has station sheets for 2 Sundays, so the station kinds sleep; copying the latest
sheet onto 6 more held Sundays gives the 8 they wait for. The fx world has trophies, so the
trophy kinds are awake; taking the awards away puts them to sleep.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sunday_clays.analytics.insights.context import InsightFrames
from sunday_clays.analytics.insights.engine import evaluate_all, readiness_of
from sunday_clays.analytics.insights.registry import get
from sunday_clays.analytics.steps.s60_insights import build_frames

STATION_KINDS = ("st.hardest-easiest", "pf.station-best")
TROPHY_KINDS = ("pf.trophy-rare", "pf.next-trophy")
STATION_SUNDAYS = 8


def emitted(fr: InsightFrames, kind_ids: tuple[str, ...]) -> set[str]:
    return {p.kind.id for p in evaluate_all(fr, kinds=[get(k) for k in kind_ids])}


def with_station_sundays(fr: InsightFrames, n: int) -> InsightFrames:
    """The latest station sheet copied onto earlier held Sundays until `n` Sundays have one."""
    sheets = fr.stations
    have = sorted(set(sheets["event_date"]))
    latest = sheets[sheets["event_date"] == have[-1]]
    extra = [d for d in reversed(fr.held_dates()) if d not in have][: n - len(have)]
    copies = [latest.assign(event_date=day) for day in extra]
    return replace(fr, stations=pd.concat([sheets, *copies], ignore_index=True))


def test_station_kinds_wake_at_eight_station_sundays(fx_session):
    fr = build_frames(fx_session)
    assert readiness_of(fr).station_sundays < STATION_SUNDAYS
    assert emitted(fr, STATION_KINDS) == set()
    woken = with_station_sundays(fr, STATION_SUNDAYS)
    assert readiness_of(woken).station_sundays == STATION_SUNDAYS
    assert "st.hardest-easiest" in emitted(woken, STATION_KINDS)


def test_trophy_kinds_sleep_without_awards(fx_session):
    fr = build_frames(fx_session)
    assert emitted(fr, TROPHY_KINDS) != set()
    asleep = replace(fr, awards=fr.awards.iloc[0:0])
    assert readiness_of(asleep).trophy_awards == 0
    assert emitted(asleep, TROPHY_KINDS) == set()
