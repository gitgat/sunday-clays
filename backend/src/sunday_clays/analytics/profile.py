"""Per-shooter insights as of a date (Plan 06 T8): pure functions over frames."""

import itertools
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd

RECENT_ROUNDS = 20
BAD_DAY_RESIDUAL = -6.0
FORM_ROUNDS = 5
HOT = 3.0
COLD = -3.0
LAYOFF = timedelta(days=28)  # 3+ Sundays missed
RATE_WINDOW = timedelta(days=182)  # 26 weeks
RATE_WEEKS = 26
# C12 `events` tiers
EVENT_MILESTONES: tuple[int, ...] = (1, 10, 25, 50, 100, 150, 200, 250)

FormLabel = Literal["hot", "cold", "steady"]


@dataclass(frozen=True)
class LearningPoint:
    k: int
    value: float
    club_median: float | None
    n_club: int


@dataclass(frozen=True)
class Rust:
    effect: float | None
    n: int
    club_effect: float | None


@dataclass(frozen=True)
class Milestone:
    next_events: int | None
    events_to_go: int | None
    weekly_rate: float
    projected_date: date | None


@dataclass(frozen=True)
class ShooterInsights:
    as_of: date
    n_rounds: int
    floor: float | None
    ceiling: float | None
    recent_n: int
    bad_day_rate: float | None
    form: float | None
    form_label: FormLabel | None
    wins: int
    podiums: int
    avg_percentile: float | None
    peak_mu: float | None
    peak_date: date | None
    learning_curve: tuple[LearningPoint, ...]
    rust: Rust
    milestone: Milestone


def _upto(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    return df.loc[df["event_date"] <= as_of]


def _chronological(rounds: pd.DataFrame) -> pd.DataFrame:
    return rounds.sort_values(["event_date", "ordinal", "round_id"], kind="mergesort")


def floor_ceiling(rounds: pd.DataFrame) -> tuple[float | None, float | None, int]:
    """P10/P90 (linear) of the last 20 rounds, and how many rounds were used."""
    recent = _chronological(rounds).tail(RECENT_ROUNDS)["score"].to_numpy(dtype=np.float64)
    if recent.size == 0:
        return None, None, 0
    p10, p90 = np.percentile(recent, [10, 90])
    return float(p10), float(p90), int(recent.size)


def bad_day_rate(rounds: pd.DataFrame) -> float | None:
    """Share of rounds (with a residual) whose residual is <= -6."""
    residuals = rounds["residual"].dropna()
    return None if residuals.empty else float((residuals <= BAD_DAY_RESIDUAL).mean())


def form(rounds: pd.DataFrame) -> tuple[float | None, FormLabel | None]:
    """Mean residual of the last 5 rounds with a residual; None with fewer than 5."""
    with_residual = _chronological(rounds.loc[rounds["residual"].notna()])
    if len(with_residual) < FORM_ROUNDS:
        return None, None
    value = float(with_residual.tail(FORM_ROUNDS)["residual"].mean())
    label: FormLabel = "hot" if value >= HOT else "cold" if value <= COLD else "steady"
    return value, label


def event_values(rounds: pd.DataFrame) -> pd.DataFrame:
    """[shooter_id, k, value]: mean `adjusted` per (shooter, held event), k by date."""
    held = rounds.loc[rounds["adjusted"].notna()]
    per_event = (
        held.groupby(["shooter_id", "event_date"])["adjusted"]
        .mean()
        .reset_index()
        .sort_values(["shooter_id", "event_date"])
    )
    per_event["k"] = per_event.groupby("shooter_id").cumcount() + 1
    return per_event.rename(columns={"adjusted": "value"})[["shooter_id", "k", "value"]]


def learning_curve(
    rounds: pd.DataFrame, shooters: pd.DataFrame, shooter_id: int
) -> tuple[LearningPoint, ...]:
    """The shooter's adjusted score by career event index k vs the club median at k.

    The club median excludes left_censored shooters (C4).
    """
    values = event_values(rounds)
    censored = set(shooters.loc[shooters["left_censored"], "shooter_id"])
    club = values.loc[~values["shooter_id"].isin(censored)].groupby("k")["value"]
    medians, sizes = club.median(), club.size()
    mine = values.loc[values["shooter_id"] == shooter_id]
    return tuple(
        LearningPoint(
            k=int(k),
            value=float(v),
            club_median=float(medians[k]) if k in medians.index else None,
            n_club=int(sizes[k]) if k in sizes.index else 0,
        )
        for k, v in zip(mine["k"], mine["value"], strict=True)
    )


def _post_layoff_mask(rounds: pd.DataFrame) -> pd.Series:
    """True for rounds at a shooter's first event after a gap of >= 28 days (3+ Sundays missed)."""
    dates: dict[int, set[date]] = defaultdict(set)
    for shooter_id, event_date in zip(rounds["shooter_id"], rounds["event_date"], strict=True):
        dates[int(shooter_id)].add(event_date)
    after: set[tuple[int, date]] = set()
    for shooter_id, attended in dates.items():
        ordered = sorted(attended)
        for previous, current in itertools.pairwise(ordered):
            if current - previous >= LAYOFF:
                after.add((shooter_id, current))
    flags = [
        (int(s), d) in after
        for s, d in zip(rounds["shooter_id"], rounds["event_date"], strict=True)
    ]
    return pd.Series(flags, index=rounds.index, dtype=bool)


def rust_effect(rounds: pd.DataFrame) -> tuple[float | None, int]:
    """Mean residual after a >= 28-day layoff (3+ Sundays off) minus the mean elsewhere, and n.

    Gaps are measured between attended dates (held or not); only rounds with a residual
    enter either mean. None when either side is empty.
    """
    after_layoff = _post_layoff_mask(rounds)
    has_residual = rounds["residual"].notna()
    post, other = after_layoff & has_residual, ~after_layoff & has_residual
    n = int(post.sum())
    if n == 0 or not other.any():
        return None, n
    residual = rounds["residual"]
    return float(residual[post].mean() - residual[other].mean()), n


def peak(history: pd.DataFrame) -> tuple[float | None, date | None]:
    """Highest published mu (earliest date on ties)."""
    if history.empty:
        return None, None
    top = history.sort_values(["mu", "event_date"], ascending=[False, True]).iloc[0]
    return float(top["mu"]), top["event_date"]


def milestone(event_dates: set[date], as_of: date) -> Milestone:
    """Next `events` tier and a date projected from the 26-week attendance rate.

    Only dates <= as_of count (no-leak), toward both the total and the rate.
    """
    dates = {d for d in event_dates if d <= as_of}
    n_events = len(dates)
    n_recent = sum(1 for d in dates if d > as_of - RATE_WINDOW)
    rate = n_recent / RATE_WEEKS
    upcoming = [m for m in EVENT_MILESTONES if m > n_events]
    if not upcoming:
        return Milestone(next_events=None, events_to_go=None, weekly_rate=rate, projected_date=None)
    to_go = upcoming[0] - n_events
    # ceil(to_go / rate) weeks in integer arithmetic: float division can land just above
    # a whole number (15 / (15 / 26) = 26.000000000000004) and add a spurious week
    projected = (
        None if n_recent == 0 else as_of + timedelta(weeks=-(-to_go * RATE_WEEKS // n_recent))
    )
    return Milestone(
        next_events=upcoming[0],
        events_to_go=to_go,
        weekly_rate=rate,
        projected_date=projected,
    )


def _sundays_shot(
    mine: pd.DataFrame, appearances: pd.DataFrame | None, shooter_id: int, as_of: date
) -> pd.Series:
    if appearances is None:
        return mine["event_date"]
    seen = _upto(appearances, as_of)
    return seen.loc[seen["shooter_id"] == shooter_id, "event_date"]


def shooter_insights(
    rounds: pd.DataFrame,
    history: pd.DataFrame,
    shooters: pd.DataFrame,
    shooter_id: int,
    as_of: date,
    appearances: pd.DataFrame | None = None,
) -> ShooterInsights:
    """Everything is computed from rows dated <= as_of (no-leak).

    The Sundays milestone counts `appearances` (special Sundays included, Plan 17) when given.
    """
    club_rounds = _upto(rounds, as_of)
    mine = club_rounds.loc[club_rounds["shooter_id"] == shooter_id]
    best = mine.loc[mine["is_best_round"]]
    floor, ceiling, recent_n = floor_ceiling(mine)
    form_value, form_label = form(mine)
    peak_mu, peak_date = peak(_upto(history.loc[history["shooter_id"] == shooter_id], as_of))
    effect, n = rust_effect(mine)
    club_effect, _ = rust_effect(club_rounds)
    percentiles = best["percentile"].dropna()
    return ShooterInsights(
        as_of=as_of,
        n_rounds=len(mine),
        floor=floor,
        ceiling=ceiling,
        recent_n=recent_n,
        bad_day_rate=bad_day_rate(mine),
        form=form_value,
        form_label=form_label,
        wins=int((best["event_rank"] == 1).sum()),
        podiums=int((best["event_rank"] <= 3).sum()),
        avg_percentile=None if percentiles.empty else float(percentiles.mean()),
        peak_mu=peak_mu,
        peak_date=peak_date,
        learning_curve=learning_curve(club_rounds, shooters, shooter_id),
        rust=Rust(effect=effect, n=n, club_effect=club_effect),
        milestone=milestone(set(_sundays_shot(mine, appearances, shooter_id, as_of)), as_of),
    )
