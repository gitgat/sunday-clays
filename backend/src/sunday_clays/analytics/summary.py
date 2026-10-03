"""The summary card's facts for one shooter and one window (Plan 19 §3.6.1, D18).

Round-type filters never apply: a PB set in a round-type slice is not a PB. Competition trophies
(First Win, Podium, Station Top Gun, Hardest-Station Clean) are never counted or named (D14).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, cast

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.achievements.registry import trophy
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.personal_best import is_new_pb
from sunday_clays.analytics.streaks import streaks

TROPHY_NAMES_SHOWN: Final = 3
#: D14's four: First Win and Podium (category "competition"), Station Top Gun and Hardest-Station
#: Clean (category "stations" in the registry). By code, so a category filter cannot miss two.
LEFT_OUT_TROPHY_CODES: Final = frozenset(
    {"first_win", "podium", "station_top_gun", "hardest_station_clean"}
)


def trophy_title(code: str) -> str | None:
    """ "Events Attended — Silver" for a tier, the achievement name for a one-off, None for an
    unknown trophy or one of D14's four."""
    found = trophy(code)
    if found is None or found.achievement.code in LEFT_OUT_TROPHY_CODES:
        return None
    if found.tier is None:
        return found.achievement.name
    return f"{found.achievement.name} — {found.tier.metal.value.title()}"


@dataclass(frozen=True)
class BestRound:
    score: int
    event_date: date


@dataclass(frozen=True)
class ShooterSummary:
    shooter_id: int
    display_name: str
    date_from: date | None
    date_to: date
    sundays: int
    special_sundays: int
    rounds: int
    average: float | None
    best: BestRound | None
    pbs_set: int
    trophies: int
    trophy_names: tuple[str, ...]
    longest_streak: int


def _inside(day: date, date_from: date | None, date_to: date) -> bool:
    return (date_from is None or day >= date_from) and day <= date_to


def _pbs_set(mine: pd.DataFrame, date_from: date | None, date_to: date) -> int:
    count = 0
    best_before: int | None = None
    n_before = 0
    for key, scores in mine.groupby("event_date", sort=True)["score"]:
        day = cast(date, key)
        top = int(scores.max())
        if _inside(day, date_from, date_to) and is_new_pb(top, best_before, n_before):
            count += 1
        best_before = top if best_before is None else max(best_before, top)
        n_before += len(scores)
    return count


def compute_summary(
    shooter_id: int,
    display_name: str,
    rounds: pd.DataFrame,
    appearances: pd.DataFrame,
    calendar: pd.DataFrame,
    awards: Sequence[tuple[str, date]],
    date_from: date | None,
    date_to: date,
) -> ShooterSummary:
    """`rounds`: regular rounds (any shooters; filtered here); `appearances`: shooter_id and
    event_date, special included; `calendar`: event_date, results_complete, kind."""
    mine = rounds.loc[rounds["shooter_id"] == shooter_id]
    mine = mine.loc[mine["event_date"] <= date_to]
    window = mine.loc[[_inside(d, date_from, date_to) for d in mine["event_date"]]]
    came = appearances.loc[appearances["shooter_id"] == shooter_id]
    came = came.loc[[_inside(d, date_from, date_to) for d in came["event_date"]]]
    cal = calendar.loc[[_inside(d, date_from, date_to) for d in calendar["event_date"]]]
    special_days = set(cal.loc[cal["kind"].eq(frames.EVENT_KIND_SPECIAL), "event_date"])
    sundays = set(came["event_date"])
    best: BestRound | None = None
    if not window.empty:
        top = int(window["score"].max())
        first_day = min(
            d for d, s in zip(window["event_date"], window["score"], strict=True) if s == top
        )
        best = BestRound(top, first_day)
    streak_rows = streaks(came, cal, date_to)
    mine_streak = streak_rows.loc[streak_rows["shooter_id"] == shooter_id, "longest_streak"]
    kept = sorted(
        (
            (day, title)
            for code, day in awards
            if _inside(day, date_from, date_to) and (title := trophy_title(code)) is not None
        ),
        key=lambda item: (-item[0].toordinal(), item[1]),
    )
    # date_from=None (an open start) is a stable cache key on purpose.
    return ShooterSummary(
        shooter_id=shooter_id,
        display_name=display_name,
        date_from=date_from,
        date_to=date_to,
        sundays=len(sundays),
        special_sundays=len(sundays & special_days),
        rounds=len(window),
        average=None if window.empty else round(float(window["score"].mean()), 1),
        best=best,
        pbs_set=_pbs_set(mine, date_from, date_to),
        trophies=len(kept),
        trophy_names=tuple(title for _, title in kept[:TROPHY_NAMES_SHOWN]),
        longest_streak=int(mine_streak.iloc[0]) if not mine_streak.empty else 0,
    )


@cached_by_data_version
def shooter_summary(
    session: Session, shooter_id: int, date_from: date | None, date_to: date
) -> ShooterSummary:
    display_name: object = session.execute(
        text("SELECT display_name FROM shooter_profiles WHERE shooter_id = :s"), {"s": shooter_id}
    ).scalar_one()
    awards = [
        (str(code), day)
        for code, day in session.execute(
            text("SELECT code, event_date FROM achievements_awarded WHERE shooter_id = :s"),
            {"s": shooter_id},
        ).all()
    ]
    return compute_summary(
        shooter_id,
        str(display_name),
        frames.load_rounds(session),
        frames.load_appearances(session),
        frames.load_calendar(session),
        awards,
        date_from,
        date_to,
    )
