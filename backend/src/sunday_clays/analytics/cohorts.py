"""Newcomer cohorts and retention by calendar year (left-censored excluded, C4)."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import pandas as pd

COHORT_COLUMNS: tuple[str, ...] = (
    "cohort_year",
    "offset",
    "n_cohort",
    "n_active",
    "share",
)
RETURN_COLUMNS: tuple[str, ...] = ("cohort_year", "n_cohort", "n_returned")


@dataclass(frozen=True, slots=True)
class _Member:
    """One cohort member: the year of their first round, active years, distinct event dates."""

    cohort_year: int
    years: frozenset[int]
    n_dates: int


def _cohort_members(rounds: pd.DataFrame, shooters: pd.DataFrame) -> list[_Member]:
    """Every shooter with a round, leaving out C4 left-censored shooters.

    The one definition of cohort membership both tables below are built from.
    """
    censored = {int(s) for s in shooters.loc[shooters["left_censored"], "shooter_id"]}
    dates: dict[int, set[date]] = defaultdict(set)
    for shooter_id, event_date in zip(rounds["shooter_id"], rounds["event_date"], strict=True):
        if int(shooter_id) not in censored:
            dates[int(shooter_id)].add(event_date)
    return [
        _Member(cohort_year=min(ds).year, years=frozenset(d.year for d in ds), n_dates=len(ds))
        for ds in dates.values()
    ]


def _retention_table(members: list[_Member], rounds: pd.DataFrame) -> pd.DataFrame:
    if not members:
        return pd.DataFrame(
            {c: pd.Series(dtype="float64" if c == "share" else "int64") for c in COHORT_COLUMNS}
        )
    last_year = max(d.year for d in rounds["event_date"])
    by_cohort: dict[int, list[_Member]] = defaultdict(list)
    for member in members:
        by_cohort[member.cohort_year].append(member)
    out = []
    for cohort_year in sorted(by_cohort):
        group = by_cohort[cohort_year]
        for year in range(cohort_year, last_year + 1):
            n_active = sum(1 for m in group if year in m.years)
            out.append(
                (
                    cohort_year,
                    year - cohort_year,
                    len(group),
                    n_active,
                    n_active / len(group),
                )
            )
    return pd.DataFrame(out, columns=list(COHORT_COLUMNS))


def _returns_table(members: list[_Member]) -> pd.DataFrame:
    size: dict[int, int] = defaultdict(int)
    returned: dict[int, int] = defaultdict(int)
    for member in members:
        size[member.cohort_year] += 1
        returned[member.cohort_year] += int(member.n_dates >= 2)
    out = [(year, size[year], returned[year]) for year in sorted(size)]
    return pd.DataFrame(out, columns=list(RETURN_COLUMNS), dtype="int64")


def newcomer_cohorts(rounds: pd.DataFrame, shooters: pd.DataFrame) -> pd.DataFrame:
    """Rows (cohort_year, offset k, n_cohort, n_active in cohort_year + k, share).

    A shooter's cohort is the year of their first round; offsets run to the last
    year with data in `rounds` (left-censored shooters' rounds count as data).
    """
    return _retention_table(_cohort_members(rounds, shooters), rounds)


def cohort_returns(rounds: pd.DataFrame, shooters: pd.DataFrame) -> pd.DataFrame:
    """Per cohort year: size and how many came back for a second event date."""
    return _returns_table(_cohort_members(rounds, shooters))


def cohort_tables(
    rounds: pd.DataFrame, shooters: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(newcomer_cohorts, cohort_returns) from a single pass over `rounds`."""
    members = _cohort_members(rounds, shooters)
    return _retention_table(members, rounds), _returns_table(members)


def first_round_scores(rounds: pd.DataFrame, start: date | None, end: date | None) -> list[int]:
    """Each shooter's first-Sunday best score, for first Sundays in [start, end] (None = open).

    Same rule as `ev.new-faces`: the first date a shooter has any round, best round that day.
    Left-censored shooters are kept (their first round on record is still a first round here).
    """
    if rounds.empty:
        return []
    first = rounds.groupby("shooter_id")["event_date"].transform("min")
    firsts = rounds.loc[rounds["event_date"] == first]
    best = firsts.groupby("shooter_id").agg(day=("event_date", "first"), score=("score", "max"))
    return sorted(
        int(score)
        for day, score in zip(best["day"], best["score"], strict=True)
        if (start is None or day >= start) and (end is None or day <= end)
    )
