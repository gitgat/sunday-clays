"""Club summary, attendance, cohorts and score distribution (Plan 06 T7)."""

from collections import Counter, defaultdict
from datetime import date
from typing import Annotated, Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query
from pydantic import BaseModel

from sunday_clays.analytics import frames
from sunday_clays.analytics.cohorts import cohort_tables, first_round_scores
from sunday_clays.api.routes._convert import opt_float, opt_int, rows
from sunday_clays.api.routes._filters import check_window, in_window, round_type_param
from sunday_clays.db import SessionDep
from sunday_clays.domain.round_type import RoundType

router = APIRouter()

TARGETS_PER_ROUND = 50
ROW_STATUSES: tuple[str, ...] = ("member", "guest", "deceased")


class StatusYearOut(BaseModel):
    year: int
    member_rounds: int
    guest_rounds: int
    deceased_rounds: int
    unrecorded_rounds: int


class ClubSummaryOut(BaseModel):
    first_event: date | None
    last_event: date | None
    n_events: int
    n_scored_events: int
    n_held_events: int
    n_rounds: int
    n_shooters: int
    avg_score: float | None
    median_score: float | None
    top_score: int | None
    n_perfect: int
    clays_thrown: int
    clays_broken: int
    avg_head_count: float | None
    shooters_by_status: dict[str, int]
    status_by_year: list[StatusYearOut]


class AttendanceOut(BaseModel):
    event_date: date
    head_count: int | None
    n_rounds: int
    n_shooters: int
    has_scores: bool
    results_complete: bool


class RetentionOut(BaseModel):
    offset: int
    n_active: int
    share: float


class CohortOut(BaseModel):
    year: int
    n_new: int
    n_returned: int
    retention: list[RetentionOut]


class DistributionOut(BaseModel):
    key: str
    n: int
    mean: float
    median: float
    p10: float
    p25: float
    p75: float
    p90: float
    counts: list[int]  # index = score 0..50


class FirstRoundsOut(BaseModel):
    n: int
    median: float | None
    counts: list[int]  # index = score 0..50


def status_by_year(rounds: pd.DataFrame) -> list[StatusYearOut]:
    """Round counts per calendar year by each round's recorded `status` (C7).

    A round without a recognised status (NULL) counts as `unrecorded_rounds`.
    """
    counts: dict[int, Counter[str | None]] = defaultdict(Counter)
    for event_date, status in zip(rounds["event_date"], rounds["status"], strict=True):
        counts[event_date.year][status if status in ROW_STATUSES else None] += 1
    return [
        StatusYearOut(
            year=year,
            member_rounds=counts[year]["member"],
            guest_rounds=counts[year]["guest"],
            deceased_rounds=counts[year]["deceased"],
            unrecorded_rounds=counts[year][None],
        )
        for year in sorted(counts)
    ]


def score_distribution(rounds: pd.DataFrame) -> list[DistributionOut]:
    """Per calendar year: n, mean, median, P10/P25/P75/P90 (numpy linear) and a 0..50 histogram."""
    by_year: dict[int, list[int]] = defaultdict(list)
    for event_date, score in zip(rounds["event_date"], rounds["score"], strict=True):
        by_year[event_date.year].append(int(score))
    out = []
    for year in sorted(by_year):
        scores = np.asarray(by_year[year], dtype=np.int64)
        p10, p25, median, p75, p90 = np.percentile(scores, [10, 25, 50, 75, 90])
        out.append(
            DistributionOut(
                key=str(year),
                n=len(scores),
                mean=float(scores.mean()),
                median=float(median),
                p10=float(p10),
                p25=float(p25),
                p75=float(p75),
                p90=float(p90),
                counts=[int(c) for c in np.bincount(scores, minlength=TARGETS_PER_ROUND + 1)],
            )
        )
    return out


@router.get("/api/club/summary")
def club_summary(
    session: SessionDep,
    round_types: list[RoundType] = round_type_param,
    since: date | None = None,
    as_of: date | None = None,
) -> ClubSummaryOut:
    """Headline numbers over Sundays in [since, as_of] (both optional; none = all time).

    `status_by_year` is the year-by-year table and always covers every year.
    """
    check_window(since, as_of)
    every_round = frames.apply_round_type_filter(frames.load_rounds(session), round_types)
    events = in_window(
        frames.apply_round_type_filter(frames.load_events(session), round_types), since, as_of
    )
    rounds = in_window(every_round, since, as_of)
    scored = events.loc[events["has_scores"]]
    shooters = rounds.drop_duplicates("shooter_id")
    by_status = shooters["shooter_status"].value_counts()
    scores = rounds["score"]
    return ClubSummaryOut(
        first_event=None if scored.empty else scored["event_date"].min(),
        last_event=None if scored.empty else scored["event_date"].max(),
        n_events=len(events),
        n_scored_events=len(scored),
        n_held_events=int(events["results_complete"].sum()),
        n_rounds=len(rounds),
        n_shooters=len(shooters),
        avg_score=None if rounds.empty else float(scores.mean()),
        median_score=None if rounds.empty else float(scores.median()),
        top_score=None if rounds.empty else int(scores.max()),
        n_perfect=int((scores == TARGETS_PER_ROUND).sum()),
        clays_thrown=len(rounds) * TARGETS_PER_ROUND,
        clays_broken=int(scores.sum()),
        avg_head_count=opt_float(events["head_count"].mean()),
        shooters_by_status={str(k): int(v) for k, v in by_status.items()},
        status_by_year=status_by_year(every_round),
    )


@router.get("/api/club/attendance")
def club_attendance(session: SessionDep) -> list[AttendanceOut]:
    """Every event (attendance-only included), date ascending."""
    return [
        AttendanceOut(
            event_date=r["event_date"],
            head_count=opt_int(r["head_count"]),
            n_rounds=int(r["n_rounds"]),
            n_shooters=int(r["n_shooters"]),
            has_scores=bool(r["has_scores"]),
            results_complete=bool(r["results_complete"]),
        )
        for r in rows(frames.load_events(session))
    ]


@router.get("/api/club/cohorts")
def club_cohorts(session: SessionDep) -> list[CohortOut]:
    """Newcomer cohorts by first-round year with retention per year offset (C4 exclusions)."""
    table, returns = cohort_tables(frames.load_rounds(session), frames.load_shooters(session))
    retention: dict[int, list[RetentionOut]] = defaultdict(list)
    for r in rows(table):
        retention[int(r["cohort_year"])].append(
            RetentionOut(
                offset=int(r["offset"]), n_active=int(r["n_active"]), share=float(r["share"])
            )
        )
    return [
        CohortOut(
            year=int(c["cohort_year"]),
            n_new=int(c["n_cohort"]),
            n_returned=int(c["n_returned"]),
            retention=retention[int(c["cohort_year"])],
        )
        for c in rows(returns)
    ]


@router.get("/api/club/distribution")
def club_distribution(
    session: SessionDep,
    by: Literal["year"] = "year",
    round_types: list[RoundType] = round_type_param,
    since: date | None = None,
    as_of: date | None = None,
) -> list[DistributionOut]:
    """Score distribution per calendar year; `by` accepts only `year` (anything else: 422).

    `since` / `as_of` keep only rounds in that span (years outside it disappear).
    """
    check_window(since, as_of)
    rounds = frames.apply_round_type_filter(frames.load_rounds(session), round_types)
    return score_distribution(in_window(rounds, since, as_of))


@router.get("/api/club/first-rounds")
def club_first_rounds(
    session: SessionDep,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> FirstRoundsOut:
    """Histogram of each shooter's first-Sunday best score, first Sundays in [from, to]."""
    scores = first_round_scores(frames.load_rounds(session), date_from, date_to)
    return FirstRoundsOut(
        n=len(scores),
        median=float(np.median(scores)) if scores else None,
        counts=[int(c) for c in np.bincount(scores, minlength=TARGETS_PER_ROUND + 1)],
    )
