"""Year in Review (club and shooter) and "On this day"."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Final

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.domain.round_type import RoundType

TARGETS_PER_ROUND: Final = 50
PB_MIN_EARLIER_ROUNDS: Final = 5
ON_THIS_DAY_YEARS: Final[tuple[int, ...]] = (1, 2, 3)
ON_THIS_DAY_WINDOW_DAYS: Final = 3
_EVENTS_SQL: Final = """
SELECT e.event_date, e.round_type, e.has_scores, e.results_complete, e.head_count, e.n_shooters,
       m.median, m.top_score, m.difficulty
FROM events AS e
LEFT JOIN event_metrics AS m ON m.event_date = e.event_date
ORDER BY e.event_date
"""
_EVENT_COLUMNS: Final = (
    "event_date",
    "round_type",
    "has_scores",
    "results_complete",
    "head_count",
    "n_shooters",
    "median",
    "top_score",
    "difficulty",
)


@dataclass(frozen=True)
class YirFrames:
    rounds: pd.DataFrame  # event_date, round_type, shooter_id, display_name, score, ...
    events: pd.DataFrame  # _EVENT_COLUMNS
    profiles: pd.DataFrame  # shooter_id, display_name, left_censored
    trophies: pd.DataFrame  # shooter_id, code, event_date
    history: pd.DataFrame  # shooter_id, event_date, mu


@dataclass(frozen=True)
class YearTotals:
    year: int
    scored_events: int
    held_events: int
    rounds: int
    shooters: int
    clays_thrown: int
    clays_broken: int
    avg_score: float | None


@dataclass(frozen=True)
class TopRound:
    shooter_id: int
    display_name: str
    event_date: date
    score: int


@dataclass(frozen=True)
class EventStat:
    event_date: date
    value: float


@dataclass(frozen=True)
class MonthStat:
    month: int
    events: int
    rounds: int
    avg_score: float | None


@dataclass(frozen=True)
class ClubYear:
    year: int
    totals: YearTotals
    events: int
    newcomers: int
    perfect_rounds: int
    top_rounds: tuple[TopRound, ...]
    mean_head_count: float | None
    busiest: EventStat | None
    hardest: EventStat | None
    easiest: EventStat | None
    trophies: int
    months: tuple[MonthStat, ...]
    previous: YearTotals | None


@dataclass(frozen=True)
class ShooterTotals:
    year: int
    events: int
    rounds: int
    clays_thrown: int
    clays_broken: int
    avg_score: float | None


@dataclass(frozen=True)
class PbDay:
    event_date: date
    score: int


@dataclass(frozen=True)
class ShooterMonth:
    month: int
    rounds: int
    avg_score: float | None
    club_avg_score: float | None


@dataclass(frozen=True)
class ShooterYear:
    year: int
    shooter_id: int
    display_name: str
    totals: ShooterTotals
    best: TopRound | None
    wins: int
    podiums: int
    best_finish: int | None
    pbs: tuple[PbDay, ...]
    trophies: int
    rating_start: float | None
    rating_end: float | None
    attendance_rank: int | None
    n_shooters: int
    months: tuple[ShooterMonth, ...]
    previous: ShooterTotals | None


@dataclass(frozen=True)
class Winner:
    shooter_id: int
    display_name: str
    score: int


@dataclass(frozen=True)
class OnThisDayItem:
    years_ago: int
    event_date: date
    has_scores: bool
    head_count: int | None
    n_shooters: int
    top_score: int | None
    median: float | None
    winners: tuple[Winner, ...]


def _opt_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not math.isnan(value):
        return float(value)
    return None


def _opt_int(value: object) -> int | None:
    number = _opt_float(value)
    return None if number is None else round(number)


def _in_year(dates: pd.Series, year: int) -> pd.Series:
    return pd.Series([d.year == year for d in dates], index=dates.index, dtype=bool)


def _mean(values: pd.Series) -> float | None:
    return _opt_float(values.astype(float).mean())


def year_totals(data: YirFrames, year: int) -> YearTotals:
    rounds = data.rounds[_in_year(data.rounds["event_date"], year)]
    events = data.events[_in_year(data.events["event_date"], year)]
    return YearTotals(
        year=year,
        scored_events=int(events["has_scores"].sum()),
        held_events=int(events["results_complete"].sum()),
        rounds=len(rounds),
        shooters=int(rounds["shooter_id"].nunique()),
        clays_thrown=TARGETS_PER_ROUND * len(rounds),
        clays_broken=int(rounds["score"].sum()),
        avg_score=_mean(rounds["score"]),
    )


def _extreme(events: pd.DataFrame, column: str, *, largest: bool) -> EventStat | None:
    rows = events.dropna(subset=[column]).sort_values(
        [column, "event_date"], ascending=[not largest, True]
    )
    if rows.empty:
        return None
    first = rows.iloc[0]
    return EventStat(event_date=first["event_date"], value=float(first[column]))


def _months(rounds: pd.DataFrame) -> dict[int, pd.DataFrame]:
    months = pd.Series([d.month for d in rounds["event_date"]], index=rounds.index, dtype=int)
    return {m: rounds[months == m] for m in range(1, 13)}


def club_year(data: YirFrames, year: int) -> ClubYear:
    """The club's calendar year; only data dated on or before Dec 31 of `year` is read."""
    rounds = data.rounds[_in_year(data.rounds["event_date"], year)]
    events = data.events[_in_year(data.events["event_date"], year)]
    firsts = data.rounds.groupby("shooter_id")["event_date"].min()
    censored = set(data.profiles.loc[data.profiles["left_censored"], "shooter_id"])
    newcomers = [s for s, d in firsts.items() if d.year == year and s not in censored]
    top = rounds[rounds["score"] == rounds["score"].max()].sort_values(
        ["event_date", "display_name"]
    )
    held = events[events["results_complete"].astype(bool)]
    trophies = data.trophies[_in_year(data.trophies["event_date"], year)]
    months = tuple(
        MonthStat(
            month=m,
            events=int(group["event_date"].nunique()),
            rounds=len(group),
            avg_score=_mean(group["score"]),
        )
        for m, group in _months(rounds).items()
    )
    previous = year_totals(data, year - 1)
    return ClubYear(
        year=year,
        totals=year_totals(data, year),
        events=len(events),
        newcomers=len(newcomers),
        perfect_rounds=int((rounds["score"] == TARGETS_PER_ROUND).sum()),
        top_rounds=tuple(
            TopRound(int(r["shooter_id"]), str(r["display_name"]), r["event_date"], int(r["score"]))
            for r in top.to_dict("records")
        ),
        mean_head_count=_mean(events["head_count"].dropna()),
        busiest=_extreme(events, "head_count", largest=True),
        hardest=_extreme(held, "difficulty", largest=True),
        easiest=_extreme(held, "difficulty", largest=False),
        trophies=len(trophies),
        months=months,
        previous=previous if previous.scored_events else None,
    )


def pb_days(rounds: pd.DataFrame) -> tuple[PbDay, ...]:
    """C12 `personal_bests`: the day's best beats every round on >= 5 earlier-dated rounds."""
    out: list[PbDay] = []
    earlier_best, earlier_count = -1, 0
    for _, group in rounds.sort_values("event_date").groupby("event_date", sort=True):
        best = int(group["score"].max())
        if earlier_count >= PB_MIN_EARLIER_ROUNDS and best > earlier_best:
            out.append(PbDay(event_date=group["event_date"].iloc[0], score=best))
        earlier_best, earlier_count = max(earlier_best, best), earlier_count + len(group)
    return tuple(out)


def _shooter_totals(rounds: pd.DataFrame, year: int) -> ShooterTotals:
    mine = rounds[_in_year(rounds["event_date"], year)]
    return ShooterTotals(
        year=year,
        events=int(mine["event_date"].nunique()),
        rounds=len(mine),
        clays_thrown=TARGETS_PER_ROUND * len(mine),
        clays_broken=int(mine["score"].sum()),
        avg_score=_mean(mine["score"]),
    )


def _last_mu(history: pd.DataFrame, until: date) -> float | None:
    rows = history[[d <= until for d in history["event_date"]]]
    return float(rows.sort_values("event_date")["mu"].iloc[-1]) if len(rows) else None


def shooter_year(data: YirFrames, shooter_id: int, year: int) -> ShooterYear:
    """One shooter's calendar year; reads only data dated on or before Dec 31 of `year`."""
    all_mine = data.rounds[data.rounds["shooter_id"] == shooter_id]
    year_rounds = data.rounds[_in_year(data.rounds["event_date"], year)]
    mine = all_mine[_in_year(all_mine["event_date"], year)]
    best_rounds = mine[mine["is_best_round"]]
    top = mine.sort_values(["score", "event_date"], ascending=[False, True])
    events_by_shooter = year_rounds.groupby("shooter_id")["event_date"].nunique()
    my_events = int(mine["event_date"].nunique())
    history = data.history[data.history["shooter_id"] == shooter_id]
    club_months, my_months = _months(year_rounds), _months(mine)
    trophies = data.trophies[
        (data.trophies["shooter_id"] == shooter_id) & _in_year(data.trophies["event_date"], year)
    ]
    previous = _shooter_totals(all_mine, year - 1)
    names = data.profiles.set_index("shooter_id")["display_name"]
    return ShooterYear(
        year=year,
        shooter_id=shooter_id,
        display_name=str(names[shooter_id]),
        totals=_shooter_totals(all_mine, year),
        best=None
        if top.empty
        else TopRound(
            shooter_id, str(names[shooter_id]), top.iloc[0]["event_date"], int(top.iloc[0]["score"])
        ),
        wins=int((best_rounds["event_rank"] == 1).sum()),
        podiums=int((best_rounds["event_rank"] <= 3).sum()),
        best_finish=_opt_int(best_rounds["event_rank"].min()),
        pbs=tuple(p for p in pb_days(all_mine) if p.event_date.year == year),
        trophies=len(trophies),
        rating_start=_last_mu(history, date(year - 1, 12, 31)),
        rating_end=_last_mu(history, date(year, 12, 31)),
        attendance_rank=1 + int((events_by_shooter > my_events).sum()) if my_events else None,
        n_shooters=len(events_by_shooter),
        months=tuple(
            ShooterMonth(
                month=m,
                rounds=len(my_months[m]),
                avg_score=_mean(my_months[m]["score"]),
                club_avg_score=_mean(club_months[m]["score"]),
            )
            for m in range(1, 13)
        ),
        previous=previous if previous.rounds else None,
    )


def _years_back(on: date, years: int) -> date:
    try:
        return on.replace(year=on.year - years)
    except ValueError:  # Feb 29 -> Feb 28
        return on.replace(year=on.year - years, day=28)


def on_this_day(data: YirFrames, on: date) -> tuple[OnThisDayItem, ...]:
    """The event closest to the same date 1, 2 and 3 years back (within 3 days; ties -> earlier)."""
    events = data.events
    best = data.rounds[data.rounds["is_best_round"]]
    items: list[OnThisDayItem] = []
    for years in ON_THIS_DAY_YEARS:
        target = _years_back(on, years)
        window = timedelta(days=ON_THIS_DAY_WINDOW_DAYS)
        near = events[[target - window <= d <= target + window for d in events["event_date"]]]
        if near.empty:
            continue
        distance = pd.Series([abs((d - target).days) for d in near["event_date"]], index=near.index)
        event = near.assign(distance=distance).sort_values(["distance", "event_date"]).iloc[0]
        day = event["event_date"]
        winners = best[(best["event_date"] == day) & (best["event_rank"] == 1)].sort_values(
            ["display_name", "shooter_id"]
        )
        items.append(
            OnThisDayItem(
                years_ago=years,
                event_date=day,
                has_scores=bool(event["has_scores"]),
                head_count=_opt_int(event["head_count"]),
                n_shooters=int(event["n_shooters"]),
                top_score=_opt_int(event["top_score"]),
                median=_opt_float(event["median"]),
                winners=tuple(
                    Winner(int(w["shooter_id"]), str(w["display_name"]), int(w["score"]))
                    for w in winners.to_dict("records")
                ),
            )
        )
    return tuple(items)


def filter_round_types(data: YirFrames, round_types: Sequence[RoundType]) -> YirFrames:
    """Keep only Sundays of the chosen round types (rounds, events and trophies); empty = all.

    `profiles` and `history` are not round-type specific and pass through. `scored_years` should
    be taken from the unfiltered frames so the year picker stays complete.
    """
    if not round_types:
        return data
    events = frames.apply_round_type_filter(data.events, round_types)
    kept = set(events["event_date"])
    return replace(
        data,
        rounds=frames.apply_round_type_filter(data.rounds, round_types),
        events=events,
        trophies=data.trophies[data.trophies["event_date"].isin(kept)],
    )


def scored_years(data: YirFrames) -> list[int]:
    scored = data.events[data.events["has_scores"]]
    return sorted({d.year for d in scored["event_date"]})


def _as_dates(values: pd.Series) -> pd.Series:
    return pd.Series(pd.to_datetime(values).dt.date, index=values.index, dtype=object)


def _frame(session: Session, sql: str, columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame([tuple(r) for r in session.execute(text(sql))], columns=list(columns))


@cached_by_data_version
def load_yir_frames(session: Session) -> YirFrames:
    rounds = frames.load_rounds(session)
    rounds = rounds[
        [
            "event_date",
            "round_type",
            "shooter_id",
            "display_name",
            "score",
            "is_best_round",
            "event_rank",
        ]
    ].copy()
    rounds["event_date"] = _as_dates(rounds["event_date"])
    rounds["is_best_round"] = rounds["is_best_round"].astype("boolean").fillna(False).astype(bool)
    rounds["event_rank"] = pd.to_numeric(rounds["event_rank"], errors="coerce").astype(float)
    events = _frame(session, _EVENTS_SQL, _EVENT_COLUMNS)
    events["event_date"] = _as_dates(events["event_date"])
    for name in ("head_count", "n_shooters", "median", "top_score", "difficulty"):
        events[name] = pd.to_numeric(events[name], errors="coerce").astype(float)
    events["has_scores"] = events["has_scores"].astype(bool)
    events["results_complete"] = events["results_complete"].astype(bool)
    profiles = _frame(
        session,
        "SELECT shooter_id, display_name, left_censored FROM shooter_profiles",
        ("shooter_id", "display_name", "left_censored"),
    )
    profiles["left_censored"] = profiles["left_censored"].astype(bool)
    trophies = _frame(
        session,
        "SELECT shooter_id, code, event_date FROM achievements_awarded",
        ("shooter_id", "code", "event_date"),
    )
    trophies["event_date"] = _as_dates(trophies["event_date"])
    history = frames.load_rating_history(session)[["shooter_id", "event_date", "mu"]].copy()
    history["event_date"] = _as_dates(history["event_date"])
    return YirFrames(
        rounds=rounds, events=events, profiles=profiles, trophies=trophies, history=history
    )
