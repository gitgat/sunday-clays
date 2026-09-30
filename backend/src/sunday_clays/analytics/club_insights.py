"""Club insights (Plan 06 T9): regulars/lapsed, guest conversion, parity, trends."""

import calendar
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

REGULAR_WINDOW = timedelta(days=364)
REGULAR_SHARE = 0.5
LAPSED_LOOKBACK = timedelta(days=180)
LAPSED_QUIET = timedelta(days=90)
ROLLING_EVENTS = 8


@dataclass(frozen=True)
class CoreShooter:
    shooter_id: int
    display_name: str
    events_attended: int
    share: float


@dataclass(frozen=True)
class LapsedShooter:
    shooter_id: int
    display_name: str
    last_event: date


@dataclass(frozen=True)
class Regulars:
    as_of: date
    n_held_window: int
    core: tuple[CoreShooter, ...]
    lapsed: tuple[LapsedShooter, ...]


@dataclass(frozen=True)
class ConversionYear:
    year: int
    new_guests: int
    converted: int
    median_days_to_convert: float | None


@dataclass(frozen=True)
class ParityYear:
    year: int
    n_events: int
    distinct_winners: int
    top3_share: float | None
    favorite_win_rate: float | None


@dataclass(frozen=True)
class YearTrend:
    year: int
    events_held: int
    mean_head_count: float | None
    unique_shooters: int
    ytd_events: int
    ytd_rounds: int
    ytd_unique_shooters: int
    ytd_events_yoy: float | None  # fractional change vs the previous year's same window


@dataclass(frozen=True)
class EventTrend:
    event_date: date
    top_score: int
    median: float
    difficulty: float | None
    top_score_rolling8: float
    median_rolling8: float
    difficulty_rolling8: float | None


@dataclass(frozen=True)
class MonthTrend:
    month: int
    n_events: int
    mean_head_count: float | None
    mean_median: float | None


def _held_events(events: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Held (`results_complete`, C4) events dated on or before as_of."""
    return events.loc[events["results_complete"] & (events["event_date"] <= as_of)]


def _names(rounds: pd.DataFrame) -> dict[int, str]:
    return {
        int(s): str(n) for s, n in zip(rounds["shooter_id"], rounds["display_name"], strict=True)
    }


def _core_counts(
    rounds: pd.DataFrame, events: pd.DataFrame, as_of: date
) -> tuple[int, dict[int, int]]:
    held_dates = _held_events(events, as_of)["event_date"]
    window = [d for d in held_dates if d > as_of - REGULAR_WINDOW]
    held = set(window)
    counts: dict[int, int] = defaultdict(int)
    for shooter_id, event_date in set(zip(rounds["shooter_id"], rounds["event_date"], strict=True)):
        if event_date in held:
            counts[int(shooter_id)] += 1
    core = {s: n for s, n in counts.items() if window and n >= REGULAR_SHARE * len(window)}
    return len(window), core


def regulars(rounds: pd.DataFrame, events: pd.DataFrame, as_of: date) -> Regulars:
    """Core and lapsed regulars as of `as_of`.

    Core = attended >= 50% of held events in (as_of - 364d, as_of]; lapsed = core at
    as_of - 180d with no round in (as_of - 90d, as_of]. Deceased (current status)
    shooters are excluded from both.
    """
    upto = rounds.loc[rounds["event_date"] <= as_of]
    deceased = {int(s) for s in upto.loc[upto["shooter_status"] == "deceased", "shooter_id"]}
    names = _names(upto)
    n_window, core = _core_counts(upto, events, as_of)
    _, earlier_core = _core_counts(upto, events, as_of - LAPSED_LOOKBACK)
    last_seen: dict[int, date] = {}
    for shooter_id, event_date in zip(upto["shooter_id"], upto["event_date"], strict=True):
        sid = int(shooter_id)
        last_seen[sid] = max(event_date, last_seen.get(sid, event_date))
    core_rows = sorted(
        (CoreShooter(s, names[s], n, n / n_window) for s, n in core.items() if s not in deceased),
        key=lambda c: (-c.events_attended, c.display_name),
    )
    lapsed_rows = sorted(
        (
            LapsedShooter(s, names[s], last_seen[s])
            for s in earlier_core
            if s not in deceased and last_seen[s] <= as_of - LAPSED_QUIET
        ),
        key=lambda x: (x.last_event, x.display_name),
    )
    return Regulars(as_of, n_window, tuple(core_rows), tuple(lapsed_rows))


def guest_conversion(rounds: pd.DataFrame) -> list[ConversionYear]:
    """Per first-guest year: the cohort of new guests and how many of them later joined.

    A guest belongs to the year of their first guest round. They converted if they have a
    member round dated after it; the wait is counted from the guest round to their first such
    member round. Joiners stay in their guest year's cohort, so converted <= new_guests.
    Uses the per-row `status` (C7).
    """
    first_guest: dict[int, date] = {}
    member_dates: dict[int, list[date]] = defaultdict(list)
    for shooter_id, event_date, status in zip(
        rounds["shooter_id"], rounds["event_date"], rounds["status"], strict=True
    ):
        sid = int(shooter_id)
        if status == "guest" and (sid not in first_guest or event_date < first_guest[sid]):
            first_guest[sid] = event_date
        elif status == "member":
            member_dates[sid].append(event_date)
    new_guests: dict[int, int] = defaultdict(int)
    days: dict[int, list[int]] = defaultdict(list)
    for sid, guest_date in first_guest.items():
        new_guests[guest_date.year] += 1
        later = [d for d in member_dates[sid] if d > guest_date]
        if later:
            days[guest_date.year].append((min(later) - guest_date).days)
    return [
        ConversionYear(
            year=year,
            new_guests=count,
            converted=len(days.get(year, [])),
            median_days_to_convert=float(statistics.median(days[year])) if days.get(year) else None,
        )
        for year, count in sorted(new_guests.items())
    ]


def parity(rounds: pd.DataFrame) -> list[ParityYear]:
    """Per year: distinct winners, top-3 winners' share of wins, favorite win rate.

    A tie for first gives each tied shooter a win. The favorite is the one attendee with
    the highest mu_before; an event without any mu_before, or whose highest mu_before is
    shared (e.g. everyone still on the prior at the first event), is left out of that rate.
    """
    best = rounds.loc[rounds["is_best_round"]]
    out = []
    years: list[int] = [d.year for d in best["event_date"]]
    for year in sorted(set(years)):
        group = best.loc[[y == year for y in years]]
        winners = group.loc[group["event_rank"] == 1]
        if winners.empty:
            continue
        wins = winners["shooter_id"].value_counts()
        top3 = sorted(wins.tolist(), reverse=True)[:3]
        rated = favorite_won = 0
        for _, day in group.groupby("event_date"):
            favorites = day.loc[day["mu_before"] == day["mu_before"].max()]  # none if all NaN
            if len(favorites) == 1:
                rated += 1
                favorite_won += int(favorites["event_rank"].iloc[0] == 1)
        out.append(
            ParityYear(
                year=year,
                n_events=int(winners["event_date"].nunique()),
                distinct_winners=len(wins),
                top3_share=sum(top3) / int(wins.sum()),
                favorite_win_rate=None if rated == 0 else favorite_won / rated,
            )
        )
    return out


def _ytd_cutoff(year: int, as_of: date) -> date:
    """as_of's month/day in `year` (Feb 29 clamps to Feb 28 in a non-leap year)."""
    if (as_of.month, as_of.day) == (2, 29) and not calendar.isleap(year):
        return date(year, 2, 28)
    return date(year, as_of.month, as_of.day)


def yearly_trends(rounds: pd.DataFrame, events: pd.DataFrame, as_of: date) -> list[YearTrend]:
    """Per calendar year up to as_of; the YTD window ends on as_of's month/day."""
    held = list(_held_events(events, as_of)["event_date"])
    upto = rounds.loc[rounds["event_date"] <= as_of]
    heads = events.loc[events["event_date"] <= as_of]
    years = sorted({d.year for d in heads["event_date"]} | {d.year for d in upto["event_date"]})
    out: list[YearTrend] = []
    ytd_by_year: dict[int, int] = {}
    for year in years:
        cutoff = _ytd_cutoff(year, as_of)
        in_year = upto.loc[[d.year == year for d in upto["event_date"]]]
        ytd = in_year.loc[in_year["event_date"] <= cutoff]
        head_counts = heads.loc[
            [d.year == year for d in heads["event_date"]], "head_count"
        ].dropna()
        ytd_events = sum(1 for d in held if d.year == year and d <= cutoff)
        previous_ytd = ytd_by_year.get(year - 1, 0)  # a year absent from `years` held none
        out.append(
            YearTrend(
                year=year,
                events_held=sum(1 for d in held if d.year == year),
                mean_head_count=None if head_counts.empty else float(head_counts.mean()),
                unique_shooters=int(in_year["shooter_id"].nunique()),
                ytd_events=ytd_events,
                ytd_rounds=len(ytd),
                ytd_unique_shooters=int(ytd["shooter_id"].nunique()),
                ytd_events_yoy=None
                if previous_ytd == 0
                else (ytd_events - previous_ytd) / previous_ytd,
            )
        )
        ytd_by_year[year] = ytd_events
    return out


def event_trends(events: pd.DataFrame, as_of: date) -> list[EventTrend]:
    """Held events up to as_of: top score, median, difficulty and rolling-8 means.

    A held event without event metrics (s10 has not run on it yet) is left out.
    """
    held = (
        _held_events(events, as_of).dropna(subset=["top_score", "median"]).sort_values("event_date")
    )
    rolling = (
        held[["top_score", "median", "difficulty"]].rolling(ROLLING_EVENTS, min_periods=1).mean()
    )
    out = []
    for (_, e), (_, r) in zip(held.iterrows(), rolling.iterrows(), strict=True):
        out.append(
            EventTrend(
                event_date=e["event_date"],
                top_score=int(e["top_score"]),
                median=float(e["median"]),
                difficulty=None if pd.isna(e["difficulty"]) else float(e["difficulty"]),
                top_score_rolling8=float(r["top_score"]),
                median_rolling8=float(r["median"]),
                difficulty_rolling8=None if pd.isna(r["difficulty"]) else float(r["difficulty"]),
            )
        )
    return out


def seasonality(events: pd.DataFrame, as_of: date) -> list[MonthTrend]:
    """Month-of-year profile over held events up to as_of."""
    held = _held_events(events, as_of)
    out = []
    for month in range(1, 13):
        in_month = held.loc[[d.month == month for d in held["event_date"]]]
        heads = in_month["head_count"].dropna()
        medians = in_month["median"].dropna()
        out.append(
            MonthTrend(
                month=month,
                n_events=len(in_month),
                mean_head_count=None if heads.empty else float(heads.mean()),
                mean_median=None if medians.empty else float(medians.mean()),
            )
        )
    return out
