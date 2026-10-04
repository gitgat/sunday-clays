"""Club milestones (Plan 19 §3.5.1, D17): running club totals, dated at the Sunday each round
number was first reached. Computed on read from the cached frames."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import cached_by_data_version

Metric = Literal["sundays_held", "clays_thrown", "shooters", "rounds"]
#: Also the order of crossings that share a Sunday (§3.5.2).
METRICS: Final[tuple[Metric, ...]] = ("sundays_held", "clays_thrown", "shooters", "rounds")
THRESHOLDS: dict[Metric, tuple[int, ...]] = {
    "clays_thrown": (
        10_000,
        25_000,
        50_000,
        100_000,
        150_000,
        200_000,
        250_000,
        300_000,
        350_000,
        400_000,
        450_000,
        500_000,
        600_000,
        700_000,
        800_000,
        900_000,
        1_000_000,
    ),
    "sundays_held": (25, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500),
    "shooters": (25, 50, 100, 150, 200, 250, 300, 400, 500),
    "rounds": (100, 500, 1_000, 2_500, 5_000, 7_500, 10_000, 12_500, 15_000, 20_000),
}
_UNITS: Final[dict[Metric, str]] = {
    "clays_thrown": "clays thrown",
    "sundays_held": "Sundays held",
    "shooters": "different shooters",
    "rounds": "rounds shot",
}


def milestone_label(metric: Metric, threshold: int) -> str:
    return f"{threshold:,} {_UNITS[metric]}"


@dataclass(frozen=True)
class Crossing:
    metric: Metric
    threshold: int
    event_date: date
    label: str
    first_on_record: bool


@dataclass(frozen=True)
class NextUp:
    metric: Metric
    threshold: int
    current: int
    remaining: int
    label: str


@dataclass(frozen=True)
class TotalsRow:
    event_date: date
    clays_thrown: int
    sundays_held: int
    shooters: int
    rounds: int


@dataclass(frozen=True)
class ClubMilestones:
    as_of: date
    milestones: tuple[Crossing, ...]
    latest: Crossing | None
    next: tuple[NextUp, ...]
    series: tuple[TotalsRow, ...]


def compute_milestones(
    rounds: pd.DataFrame, appearances: pd.DataFrame, calendar: pd.DataFrame, as_of: date
) -> ClubMilestones:
    """Evaluate every Sunday <= as_of with a regular round or an appearance (special included).

    Clays and rounds count regular rounds only (a partial-results Sunday included); Sundays held
    counts `results_complete` Sundays of both kinds; shooters counts distinct appearances.
    """
    regular = Counter(d for d in rounds["event_date"] if d <= as_of)
    seen_by_day: dict[date, set[int]] = defaultdict(set)
    for day, shooter in zip(appearances["event_date"], appearances["shooter_id"], strict=True):
        if day <= as_of:
            seen_by_day[day].add(int(shooter))
    held = {
        d
        for d, done in zip(calendar["event_date"], calendar["results_complete"], strict=True)
        if bool(done) and d <= as_of
    }
    days = sorted(set(regular) | set(seen_by_day))
    series: list[TotalsRow] = []
    seen: set[int] = set()
    n_rounds = n_held = 0
    for day in days:
        n_rounds += regular.get(day, 0)
        n_held += day in held
        seen |= seen_by_day.get(day, set())
        series.append(
            TotalsRow(day, frames.REGULAR_TARGETS * n_rounds, n_held, len(seen), n_rounds)
        )
    crossings: list[Crossing] = []
    for metric in METRICS:
        for threshold in THRESHOLDS[metric]:
            hit = next((row for row in series if getattr(row, metric) >= threshold), None)
            if hit is None:
                break
            crossings.append(
                Crossing(
                    metric,
                    threshold,
                    hit.event_date,
                    milestone_label(metric, threshold),
                    hit.event_date == days[0],
                )
            )
    order = {metric: i for i, metric in enumerate(METRICS)}
    crossings.sort(key=lambda c: (-c.event_date.toordinal(), order[c.metric], -c.threshold))
    last = series[-1] if series else None
    nexts: list[NextUp] = []
    for metric in METRICS:
        current = int(getattr(last, metric)) if last is not None else 0
        upcoming = next((t for t in THRESHOLDS[metric] if t > current), None)
        if upcoming is not None:
            nexts.append(
                NextUp(
                    metric, upcoming, current, upcoming - current, milestone_label(metric, upcoming)
                )
            )
    return ClubMilestones(
        as_of=as_of,
        milestones=tuple(crossings),
        latest=crossings[0] if crossings else None,
        next=tuple(nexts),
        series=tuple(series),
    )


@cached_by_data_version
def club_milestones(session: Session, as_of: date) -> ClubMilestones:
    return compute_milestones(
        frames.load_rounds(session),
        frames.load_appearances(session),
        frames.load_calendar(session),
        as_of,
    )
