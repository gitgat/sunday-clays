"""Station read endpoints (C8, Plan 10 T4a): overview with era and round-type filters, one station
(incl. wind x station), and a shooter's per-station deltas. All stats use station-sheet hits."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics import stations as st
from sunday_clays.analytics.frames import apply_round_type_filter
from sunday_clays.api.routes import _filters
from sunday_clays.api.routes._convert import opt_float, opt_str, rows
from sunday_clays.api.routes._filters import round_type_param
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.round_type import RoundType
from sunday_clays.station_label import label_number, parse_label

router = APIRouter(prefix="/api", tags=["stations"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


class StationLeaderOut(BaseModel):
    shooter_id: int
    display_name: str
    hits: int
    n_targets: int
    n_rounds: int
    hit_pct: float


class StationStatOut(BaseModel):
    label: str
    station_no: int
    era: int | None
    era_start: date | None
    hits: int
    n_targets: int
    n_rounds: int
    n_events: int
    hit_pct: float | None
    ci_low: float | None
    ci_high: float | None
    deff: float | None
    clean_rate: float | None
    separator: float | None
    leaders: list[StationLeaderOut]


class StationEventPctOut(BaseModel):
    event_date: date
    label: str
    station_no: int
    hits: int
    n_targets: int
    hit_pct: float


class StationShooterCellOut(BaseModel):
    shooter_id: int
    display_name: str
    label: str
    station_no: int
    hits: int
    n_targets: int
    n_rounds: int
    hit_pct: float


class StationResetOut(BaseModel):
    label: str
    station_no: int
    effective_date: date
    note: str | None


class StationCoverageOut(BaseModel):
    """How much of the scored history the station sheets cover (round-type filter applies, the era
    switch does not): Sundays with station hits, their date span, and all scored Sundays."""

    n_station_sundays: int
    first_date: date | None
    last_date: date | None
    n_scored_sundays: int
    # The newest Sunday with a station sheet overall, whatever the date window (round types still
    # apply), so an empty window can say when the last sheet was. For a past window it is later
    # than the window.
    latest_date: date | None


class ShooterStationCoverageOut(BaseModel):
    """The shooter's own station sheets inside the window: rounds, Sundays and their date span."""

    n_rounds: int
    n_sundays: int
    first_date: date | None
    last_date: date | None
    latest_date: date | None


class StationsOut(BaseModel):
    era: Literal["current", "all"]
    n_events: int
    # The newest reset on or before today, for the "Since last reset (date)" setup choice.
    last_reset_date: date | None
    coverage: StationCoverageOut
    stations: list[StationStatOut]
    by_event: list[StationEventPctOut]
    matrix: list[StationShooterCellOut]
    resets: list[StationResetOut]


class StationWindCellOut(BaseModel):
    band: str
    band_order: float
    hit_pct: float
    ci_low: float
    ci_high: float
    n_targets: int
    n_events: int
    sufficient: bool


class StationDetailOut(BaseModel):
    label: str
    station_no: int
    eras: list[StationStatOut]
    by_event: list[StationEventPctOut]
    leaders: list[StationLeaderOut]
    wind: list[StationWindCellOut]
    resets: list[StationResetOut]


class ShooterStationDeltaOut(BaseModel):
    label: str
    station_no: int
    hits: int
    n: int
    n_rounds: int
    hit_pct: float
    field_pct: float
    delta: float


class ShooterStationsOut(BaseModel):
    shooter_id: int
    last_reset_date: date | None
    coverage: ShooterStationCoverageOut
    stations: list[ShooterStationDeltaOut]


def _today(settings: Settings) -> date:
    """Today in the club timezone, through Plan 06's shared helper (tests monkeypatch it)."""
    return _filters.today_local(settings.timezone)


def _last_reset(resets: pd.DataFrame, today: date) -> date | None:
    past = [d for d in resets["effective_date"] if d <= today]
    return max(past) if past else None


def _leaders(frame: pd.DataFrame) -> dict[str, list[StationLeaderOut]]:
    out: dict[str, list[StationLeaderOut]] = {}
    for r in rows(frame):
        out.setdefault(str(r["label"]), []).append(
            StationLeaderOut(
                shooter_id=int(r["shooter_id"]),
                display_name=str(r["display_name"]),
                hits=int(r["hits"]),
                n_targets=int(r["n_targets"]),
                n_rounds=int(r["n_rounds"]),
                hit_pct=float(r["hit_pct"]),
            )
        )
    return out


def _stat_out(
    r: Mapping[str, Any],
    *,
    era: int | None,
    era_start: date | None,
    leaders: list[StationLeaderOut],
) -> StationStatOut:
    return StationStatOut(
        label=str(r["label"]),
        station_no=int(r["station_no"]),
        era=era,
        era_start=era_start,
        hits=int(r["hits"]),
        n_targets=int(r["n_targets"]),
        n_rounds=int(r["n_rounds"]),
        n_events=int(r["n_events"]),
        hit_pct=opt_float(r["hit_pct"]),
        ci_low=opt_float(r["ci_low"]),
        ci_high=opt_float(r["ci_high"]),
        deff=opt_float(r["deff"]),
        clean_rate=opt_float(r["clean_rate"]),
        separator=opt_float(r["separator"]),
        leaders=leaders,
    )


def _events_out(frame: pd.DataFrame) -> list[StationEventPctOut]:
    return [
        StationEventPctOut(
            event_date=r["event_date"],
            label=str(r["label"]),
            station_no=int(r["station_no"]),
            hits=int(r["hits"]),
            n_targets=int(r["n_targets"]),
            hit_pct=float(r["hit_pct"]),
        )
        for r in rows(frame)
    ]


def _resets_out(resets: pd.DataFrame, label: str | None = None) -> list[StationResetOut]:
    return [
        StationResetOut(
            label=str(r["label"]),
            station_no=int(r["station_no"]),
            effective_date=r["effective_date"],
            note=opt_str(r["note"]),
        )
        for r in rows(resets)
        if label is None or str(r["label"]) == label
    ]


def _coverage(
    session: Session,
    station_frame: pd.DataFrame,
    round_types: list[RoundType],
    since: date | None,
    as_of: date | None,
) -> StationCoverageOut:
    """Counted inside the window: station Sundays and scored Sundays; `latest_date` ignores it."""
    typed = apply_round_type_filter(station_frame, round_types)
    every = typed["event_date"]
    days = st.window_frame(typed, since, as_of)["event_date"]
    events = st.window_frame(
        apply_round_type_filter(frames.load_events(session), round_types), since, as_of
    )
    return StationCoverageOut(
        n_station_sundays=int(days.nunique()),
        first_date=days.min() if len(days) else None,
        last_date=days.max() if len(days) else None,
        n_scored_sundays=int(events["has_scores"].sum()),
        latest_date=every.max() if len(every) else None,
    )


@router.get("/stations", response_model=StationsOut)
def get_stations(
    session: SessionDep,
    settings: SettingsDep,
    era: Literal["current", "all"] = "current",
    since: date | None = None,
    as_of: date | None = None,
    round_types: list[RoundType] = round_type_param,
) -> StationsOut:
    today = _today(settings)
    resets = st.load_station_resets(session)
    station_frame = st.load_station_frame(session)
    overview = st.stations_overview(
        st.window_frame(station_frame, since, as_of),
        resets,
        era=era,
        round_types=round_types,
        today=today,
    )
    current = overview.current
    leaders = _leaders(overview.leaders)
    stations: list[StationStatOut] = []
    for r in rows(overview.stats):
        no = str(r["label"])
        era_index: int | None = None
        era_start: date | None = None
        if era == "current":
            era_index, era_start = current.get(no, (0, None))
        stations.append(
            _stat_out(r, era=era_index, era_start=era_start, leaders=leaders.get(no, []))
        )
    matrix = [
        StationShooterCellOut(
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            label=str(r["label"]),
            station_no=int(r["station_no"]),
            hits=int(r["hits"]),
            n_targets=int(r["n_targets"]),
            n_rounds=int(r["n_rounds"]),
            hit_pct=float(r["hit_pct"]),
        )
        for r in rows(overview.matrix)
    ]
    return StationsOut(
        era=era,
        n_events=overview.n_events,
        last_reset_date=_last_reset(resets, today),
        coverage=_coverage(session, station_frame, round_types, since, as_of),
        stations=stations,
        by_event=_events_out(overview.by_event),
        matrix=matrix,
        resets=_resets_out(resets),
    )


@router.get("/stations/{label}", response_model=StationDetailOut)
def get_station(
    raw_label: Annotated[str, Path(alias="label")],
    session: SessionDep,
    settings: SettingsDep,
    era: Literal["current", "all"] = "current",
    since: date | None = None,
    as_of: date | None = None,
    round_types: list[RoundType] = round_type_param,
) -> StationDetailOut:
    frame = st.load_station_frame(session)
    label = parse_label(raw_label)
    if label is None or not bool((frame["station_label"] == label).any()):
        raise NotFoundError("station_not_found", f"No station {raw_label}")
    resets = st.load_station_resets(session)
    detail = st.station_detail(
        st.window_frame(frame, since, as_of),
        resets,
        st.load_event_weather(session),
        label=label,
        round_types=round_types,
        today=_today(settings),
        era=era,
    )
    eras = [
        _stat_out(
            r,
            era=int(r["era"]),
            era_start=r["era_start"] if isinstance(r["era_start"], date) else None,
            leaders=[],
        )
        for r in rows(detail.eras)
    ]
    wind = [
        StationWindCellOut(
            band=str(r["band"]),
            band_order=float(r["band_order"]),
            hit_pct=float(r["hit_pct"]),
            ci_low=float(r["ci_low"]),
            ci_high=float(r["ci_high"]),
            n_targets=int(r["n_targets"]),
            n_events=int(r["n_events"]),
            sufficient=bool(r["sufficient"]),
        )
        for r in rows(detail.wind)
    ]
    return StationDetailOut(
        label=label,
        station_no=label_number(label),
        eras=eras,
        by_event=_events_out(detail.by_event),
        leaders=_leaders(detail.leaders).get(label, []),
        wind=wind,
        resets=_resets_out(resets, label),
    )


@router.get("/shooters/{id}/stations", response_model=ShooterStationsOut)
def get_shooter_stations(
    shooter_id: Annotated[int, Path(alias="id")],
    session: SessionDep,
    settings: SettingsDep,
    era: Literal["current", "all"] = "current",
    since: date | None = None,
    as_of: date | None = None,
    round_types: list[RoundType] = round_type_param,
) -> ShooterStationsOut:
    found = session.execute(
        text("SELECT 1 FROM shooter_profiles WHERE shooter_id = :id"), {"id": shooter_id}
    ).first()
    if found is None:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    every = apply_round_type_filter(st.load_station_frame(session), round_types)
    windowed = st.window_frame(every, since, as_of)
    resets = st.load_station_resets(session)
    today = _today(settings)
    frame = st.select_era(st.assign_eras(windowed, resets, today), era)
    mine = frame[frame["shooter_id"].eq(shooter_id).fillna(False).astype(bool)]
    my_days = mine["event_date"]
    my_latest = every[every["shooter_id"].eq(shooter_id).fillna(False).astype(bool)]["event_date"]
    return ShooterStationsOut(
        shooter_id=shooter_id,
        last_reset_date=_last_reset(resets, today),
        coverage=ShooterStationCoverageOut(
            n_rounds=len(mine.drop_duplicates(["event_date", "entry_row"])),
            n_sundays=int(my_days.nunique()),
            first_date=my_days.min() if len(my_days) else None,
            last_date=my_days.max() if len(my_days) else None,
            latest_date=my_latest.max() if len(my_latest) else None,
        ),
        stations=[
            ShooterStationDeltaOut(
                label=str(r["label"]),
                station_no=int(r["station_no"]),
                hits=int(r["hits"]),
                n=int(r["n"]),
                n_rounds=int(r["n_rounds"]),
                hit_pct=float(r["hit_pct"]),
                field_pct=float(r["field_pct"]),
                delta=float(r["delta"]),
            )
            for r in rows(st.shooter_station_deltas(frame, shooter_id))
        ],
    )
