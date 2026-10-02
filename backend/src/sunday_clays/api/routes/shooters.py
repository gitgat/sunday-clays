"""Shooter directory, detail (stats, odometer, PBs), rounds, rating and splits."""

import math
from collections import Counter
from collections.abc import Callable, Collection
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.leaderboards import active_shooter_ids
from sunday_clays.analytics.streaks import streaks
from sunday_clays.api.routes._convert import opt_float, opt_int, opt_str, rows
from sunday_clays.api.routes._filters import (
    check_window,
    in_window,
    latest_scored_day,
    resolve_as_of,
    round_type_param,
)
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()

# C8 path template `{id}`, bound to a descriptive argument (as Plan 04 D2 does).
ShooterId = Annotated[int, Path(alias="id")]
SettingsDep = Annotated[Settings, Depends(get_settings)]

TARGETS_PER_ROUND = 50
BAND_Z = 1.96
NO_WEATHER = "no_data"


class SplitBy(StrEnum):
    SEASON = "season"
    MONTH = "month"
    YEAR = "year"
    ROUND_TYPE = "round_type"
    GAUGE = "gauge"
    TEMP_BAND = "temp_band"
    WIND_BAND = "wind_band"
    PRECIP_BAND = "precip_band"


class ShooterSummaryOut(BaseModel):
    shooter_id: int
    display_name: str
    status: str
    first_event: date
    last_event: date
    n_rounds: int
    n_events: int
    active: bool
    mu: float | None


class ShooterStatsOut(BaseModel):
    n_rounds: int
    n_events: int
    avg_score: float | None
    median_score: float | None
    best_score: int | None
    avg_adjusted: float | None
    wins: int
    podiums: int
    avg_percentile: float | None


class OdometerOut(BaseModel):
    clays_thrown: int
    clays_broken: int
    hit_pct: float | None
    rounds: int
    events: int
    years_active: int
    current_streak: int
    longest_streak: int
    favorite_month: int | None
    trophies: int


class PbOut(BaseModel):
    scope: Literal["overall", "year"]
    key: str
    score: int
    event_date: date
    round_id: int


class ShooterDetailOut(BaseModel):
    shooter_id: int
    display_name: str
    status: str
    deceased: bool
    first_event: date
    last_event: date
    left_censored: bool
    current_mu: float | None
    current_var: float | None
    stats: ShooterStatsOut
    odometer: OdometerOut
    pbs: list[PbOut]
    # Stats over [since, as_of] only; None when the request carried neither.
    window_stats: ShooterStatsOut | None = None


class ShooterRoundOut(BaseModel):
    round_id: int
    event_date: date
    ordinal: int
    score: int
    gauge_class: str | None
    status: str | None
    round_type: RoundType
    is_best_round: bool
    event_rank: int | None
    percentile: float | None
    field_median: float | None
    adjusted: float | None
    expected: float | None
    residual: float | None
    mu_before: float | None
    mu_after: float | None
    condition: str | None


class RatingPointOut(BaseModel):
    event_date: date
    mu: float
    var: float
    lo: float
    hi: float


class RatingOut(BaseModel):
    shooter_id: int
    points: list[RatingPointOut]
    current_mu: float | None
    peak_mu: float | None
    peak_date: date | None


class SpecialRoundOut(BaseModel):
    round_id: int
    event_date: date
    label: str
    target_total: int
    score: int


class SplitOut(BaseModel):
    key: str
    n_rounds: int
    n_events: int
    avg: float
    median: float
    best: int
    avg_adjusted: float | None


def _profile(session: Session, shooter_id: int) -> dict[str, Any]:
    shooters = frames.load_shooters(session)
    match = shooters.loc[shooters["shooter_id"] == shooter_id]
    if match.empty:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    return rows(match)[0]


def _shooter_rounds(
    session: Session, shooter_id: int, round_types: list[RoundType]
) -> pd.DataFrame:
    rounds = frames.load_rounds(session)
    mine = rounds.loc[rounds["shooter_id"] == shooter_id]
    return frames.apply_round_type_filter(mine, round_types)


def _mean(series: pd.Series) -> float | None:
    clean = series.dropna()
    return None if clean.empty else float(clean.mean())


def shooter_stats(rounds: pd.DataFrame) -> ShooterStatsOut:
    """Stats over one shooter's (already filtered) rounds; ranks are full-field (C7)."""
    best = rounds.loc[rounds["is_best_round"]]
    return ShooterStatsOut(
        n_rounds=len(rounds),
        n_events=int(rounds["event_date"].nunique()),
        avg_score=_mean(rounds["score"]),
        median_score=None if rounds.empty else float(rounds["score"].median()),
        best_score=None if rounds.empty else int(rounds["score"].max()),
        avg_adjusted=_mean(rounds["adjusted"]),
        wins=int((best["event_rank"] == 1).sum()),
        podiums=int((best["event_rank"] <= 3).sum()),
        avg_percentile=_mean(best["percentile"]),
    )


def odometer(
    rounds: pd.DataFrame,
    streak_row: dict[str, Any] | None,
    trophies: int,
    sundays: Collection[date] | None = None,
) -> OdometerOut:
    """Lifetime counters (C12 odometer): clays from the scored rounds; Sundays, years and the
    favourite month from `sundays` (every Sunday shot, special ones included, Plan 17)."""
    thrown = len(rounds) * TARGETS_PER_ROUND
    broken = int(rounds["score"].sum())
    dates = sorted(set(rounds["event_date"]) if sundays is None else set(sundays))
    months = Counter(d.month for d in dates)
    top = max(months.values(), default=0)
    favorite = min((m for m, n in months.items() if n == top), default=None)
    return OdometerOut(
        clays_thrown=thrown,
        clays_broken=broken,
        hit_pct=None if thrown == 0 else broken / thrown,
        rounds=len(rounds),
        events=len(dates),
        years_active=len({d.year for d in dates}),
        current_streak=0 if streak_row is None else int(streak_row["current_streak"]),
        longest_streak=0 if streak_row is None else int(streak_row["longest_streak"]),
        favorite_month=favorite,
        trophies=trophies,
    )


def personal_bests(rounds: pd.DataFrame) -> list[PbOut]:
    """Best score overall and per calendar year, dated when first reached."""
    ordered = rounds.sort_values(["score", "event_date", "ordinal"], ascending=[False, True, True])
    out: list[PbOut] = []
    if ordered.empty:
        return out
    top = rows(ordered.head(1))[0]
    out.append(
        PbOut(
            scope="overall",
            key="all",
            score=int(top["score"]),
            event_date=top["event_date"],
            round_id=int(top["round_id"]),
        )
    )
    by_year = ordered.assign(year=[d.year for d in ordered["event_date"]])
    for r in rows(by_year.drop_duplicates("year").sort_values("year")):
        out.append(
            PbOut(
                scope="year",
                key=str(r["year"]),
                score=int(r["score"]),
                event_date=r["event_date"],
                round_id=int(r["round_id"]),
            )
        )
    return out


def _split_key(by: SplitBy) -> Callable[[dict[str, Any]], str]:
    def band(
        fn: Callable[[float | None], str | None], column: str
    ) -> Callable[[dict[str, Any]], str]:
        return lambda r: fn(opt_float(r[column])) or NO_WEATHER

    keys: dict[SplitBy, Callable[[dict[str, Any]], str]] = {
        SplitBy.SEASON: lambda r: frames.season_label(r["event_date"]),
        SplitBy.MONTH: lambda r: f"{r['event_date'].year:04d}-{r['event_date'].month:02d}",
        SplitBy.YEAR: lambda r: str(r["event_date"].year),
        SplitBy.ROUND_TYPE: lambda r: str(r["round_type"]),
        SplitBy.GAUGE: lambda r: str(r["gauge"]),
        SplitBy.TEMP_BAND: band(frames.temp_band, "temp_f"),
        SplitBy.WIND_BAND: band(frames.wind_band, "gust_mph"),
        SplitBy.PRECIP_BAND: band(frames.precip_band, "precip_in"),
    }
    return keys[by]


def _split_order(by: SplitBy) -> tuple[str, ...]:
    orders: dict[SplitBy, tuple[str, ...]] = {
        SplitBy.SEASON: frames.SEASONS,
        SplitBy.ROUND_TYPE: tuple(rt.value for rt in RoundType),
        SplitBy.TEMP_BAND: (*frames.TEMP_BANDS, NO_WEATHER),
        SplitBy.WIND_BAND: (*frames.WIND_BANDS, NO_WEATHER),
        SplitBy.PRECIP_BAND: (*frames.PRECIP_BANDS, NO_WEATHER),
    }
    return orders.get(by, ())


def splits(rounds: pd.DataFrame, by: SplitBy) -> list[SplitOut]:
    """Per-key aggregates; `best` is the PB for the key. No weather -> "no_data"."""
    key_of = _split_key(by)
    keyed = rounds.assign(key=[key_of(r) for r in rows(rounds)])
    order = _split_order(by)
    out = []
    for key, group in keyed.groupby("key", sort=True):
        out.append(
            SplitOut(
                key=str(key),
                n_rounds=len(group),
                n_events=int(group["event_date"].nunique()),
                avg=float(group["score"].mean()),
                median=float(group["score"].median()),
                best=int(group["score"].max()),
                avg_adjusted=_mean(group["adjusted"]),
            )
        )
    if order:
        out.sort(key=lambda s: order.index(s.key) if s.key in order else len(order))
    return out


@router.get("/api/shooters")
def list_shooters(
    session: SessionDep,
    settings: SettingsDep,
    q: str | None = None,
    active: bool | None = None,
) -> list[ShooterSummaryOut]:
    """`active` counts from the latest scored Sunday: a round in the year to it and 5+ rounds."""
    today = latest_scored_day(session, settings.timezone)
    shooters = frames.load_shooters(session)
    active_ids = active_shooter_ids(frames.load_rounds(session), today)
    history = frames.load_rating_history(session)
    latest_mu = {
        int(r["shooter_id"]): float(r["mu"]) for r in rows(history.groupby("shooter_id").tail(1))
    }
    out = []
    # Alphabetical regardless of case ("de la Cruz" among the Ds), shooter_id breaks ties.
    directory = sorted(
        rows(shooters), key=lambda r: (str(r["display_name"]).casefold(), int(r["shooter_id"]))
    )
    for r in directory:
        sid = int(r["shooter_id"])
        is_active = sid in active_ids
        if q and q.casefold() not in str(r["display_name"]).casefold():
            continue
        if active is not None and is_active != active:
            continue
        out.append(
            ShooterSummaryOut(
                shooter_id=sid,
                display_name=str(r["display_name"]),
                status=str(r["status"]),
                first_event=r["first_event"],
                last_event=r["last_event"],
                n_rounds=int(r["n_rounds"]),
                n_events=int(r["n_events"]),
                active=is_active,
                mu=latest_mu.get(sid),
            )
        )
    return out


@router.get("/api/shooters/{id}")
def get_shooter(
    shooter_id: ShooterId,
    session: SessionDep,
    settings: SettingsDep,
    round_types: list[RoundType] = round_type_param,
    since: date | None = None,
    as_of: date | None = None,
) -> ShooterDetailOut:
    """`stats`, `odometer` and `pbs` are lifetime; `window_stats` covers [since, as_of] if given."""
    check_window(since, as_of)
    today = resolve_as_of(None, settings.timezone)
    profile = _profile(session, shooter_id)
    all_rounds = frames.load_rounds(session)
    lifetime = all_rounds.loc[all_rounds["shooter_id"] == shooter_id]
    filtered = frames.apply_round_type_filter(lifetime, round_types)
    # Streaks are per shooter, so this shooter's Sundays give the same row as streaks over
    # everyone at a fraction of the work. Special Sundays extend runs (Plan 17).
    appearances = frames.load_appearances(session)
    my_sundays = appearances.loc[appearances["shooter_id"] == shooter_id]
    streak_rows = rows(streaks(my_sundays, frames.load_calendar(session), today))
    trophies = int(
        session.execute(
            text("SELECT count(*) FROM achievements_awarded WHERE shooter_id = :s"),
            {"s": shooter_id},
        ).scalar_one()
    )
    history = frames.load_rating_history(session)
    mine = rows(history.loc[history["shooter_id"] == shooter_id].tail(1))
    return ShooterDetailOut(
        shooter_id=shooter_id,
        display_name=str(profile["display_name"]),
        status=str(profile["status"]),
        deceased=profile["status"] == "deceased",
        first_event=profile["first_event"],
        last_event=profile["last_event"],
        left_censored=bool(profile["left_censored"]),
        current_mu=float(mine[0]["mu"]) if mine else None,
        current_var=float(mine[0]["var"]) if mine else None,
        stats=shooter_stats(filtered),
        odometer=odometer(
            lifetime,
            streak_rows[0] if streak_rows else None,
            trophies,
            set(my_sundays["event_date"]),
        ),
        pbs=personal_bests(filtered),
        window_stats=(
            None
            if since is None and as_of is None
            else shooter_stats(in_window(filtered, since, as_of))
        ),
    )


@router.get("/api/shooters/{id}/rounds")
def get_shooter_rounds(
    shooter_id: ShooterId,
    session: SessionDep,
    round_types: list[RoundType] = round_type_param,
) -> list[ShooterRoundOut]:
    _profile(session, shooter_id)
    mine = _shooter_rounds(session, shooter_id, round_types)
    return [
        ShooterRoundOut(
            round_id=int(r["round_id"]),
            event_date=r["event_date"],
            ordinal=int(r["ordinal"]),
            score=int(r["score"]),
            gauge_class=opt_str(r["gauge_class"]),
            status=opt_str(r["status"]),
            round_type=RoundType(str(r["round_type"])),
            is_best_round=bool(r["is_best_round"]),
            event_rank=opt_int(r["event_rank"]),
            percentile=opt_float(r["percentile"]),
            field_median=opt_float(r["field_median"]),
            adjusted=opt_float(r["adjusted"]),
            expected=opt_float(r["expected"]),
            residual=opt_float(r["residual"]),
            mu_before=opt_float(r["mu_before"]),
            mu_after=opt_float(r["mu_after"]),
            condition=opt_str(r["condition"]),
        )
        for r in rows(mine.sort_values(["event_date", "ordinal"]))
    ]


@router.get("/api/shooters/{id}/special")
def get_shooter_special(shooter_id: ShooterId, session: SessionDep) -> list[SpecialRoundOut]:
    """The shooter's special Sundays (Plan 17), oldest first: appearances, never score stats."""
    _profile(session, shooter_id)
    special = frames.load_special_rounds(session)
    mine = special.loc[special["shooter_id"] == shooter_id].sort_values(
        ["event_date", "ordinal"], kind="mergesort"
    )
    return [
        SpecialRoundOut(
            round_id=int(r["round_id"]),
            event_date=r["event_date"],
            label=str(r["label"]),
            target_total=int(r["target_total"]),
            score=int(r["score"]),
        )
        for r in rows(mine)
    ]


@router.get("/api/shooters/{id}/rating")
def get_shooter_rating(shooter_id: ShooterId, session: SessionDep) -> RatingOut:
    _profile(session, shooter_id)
    history = frames.load_rating_history(session)
    mine = rows(history.loc[history["shooter_id"] == shooter_id])
    points = [
        RatingPointOut(
            event_date=r["event_date"],
            mu=float(r["mu"]),
            var=float(r["var"]),
            lo=float(r["mu"]) - BAND_Z * math.sqrt(float(r["var"])),
            hi=float(r["mu"]) + BAND_Z * math.sqrt(float(r["var"])),
        )
        for r in mine
    ]
    peak = max(points, key=lambda p: p.mu, default=None)
    return RatingOut(
        shooter_id=shooter_id,
        points=points,
        current_mu=points[-1].mu if points else None,
        peak_mu=None if peak is None else peak.mu,
        peak_date=None if peak is None else peak.event_date,
    )


@router.get("/api/shooters/{id}/splits")
def get_shooter_splits(
    shooter_id: ShooterId,
    by: SplitBy,
    session: SessionDep,
    round_types: list[RoundType] = round_type_param,
    since: date | None = None,
    as_of: date | None = None,
) -> list[SplitOut]:
    """Splits over rounds in [since, as_of] (both optional; none = every round)."""
    check_window(since, as_of)
    _profile(session, shooter_id)
    return splits(in_window(_shooter_rounds(session, shooter_id, round_types), since, as_of), by)
