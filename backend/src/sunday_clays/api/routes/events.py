"""GET /api/events and /api/events/{date}: calendar list and event detail."""

from datetime import date
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, ConfigDict

from sunday_clays.analytics import frames
from sunday_clays.api.routes._convert import opt_float, opt_int, opt_str, rows
from sunday_clays.api.routes._filters import round_type_param
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()

PB_MIN_PRIOR_ROUNDS = 5
EventKind = Literal["regular", "special"]


class WinnerOut(BaseModel):
    shooter_id: int
    display_name: str
    score: int


class EventSummaryOut(BaseModel):
    # Plan 17: kind, label and target_total are always sent, so the schema requires them
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    event_date: date
    round_type: RoundType
    round_type_source: str
    head_count: int | None
    n_rounds: int
    n_shooters: int
    has_scores: bool
    has_stations: bool
    results_complete: bool
    median: float | None
    top_score: int | None
    difficulty: float | None
    condition: str | None
    winners: list[WinnerOut]
    # Plan 17: a special Sunday counts only as an appearance; its own name and target total
    kind: EventKind = "regular"
    label: str | None = None
    target_total: int = frames.REGULAR_TARGETS


class EventResultOut(BaseModel):
    round_id: int
    shooter_id: int
    display_name: str
    name_key: str  # C4 identity key; with event_date + ordinal it targets C5 round rules
    shooter_status: str
    ordinal: int
    score: int
    gauge_class: str | None
    is_best_round: bool
    event_rank: int | None
    percentile: float | None
    adjusted: float | None
    expected: float | None
    residual: float | None
    mu_before: float | None
    mu_after: float | None
    rating_delta: float | None


class EventWeatherOut(BaseModel):
    temp_f: float | None
    apparent_f: float | None
    precip_in: float | None
    wind_mph: float | None
    gust_mph: float | None
    wind_dir_deg: float | None
    cloud_pct: float | None
    humidity_pct: float | None
    pressure_hpa: float | None
    condition: str | None


class StationLayoutOut(BaseModel):
    label: str
    station_no: int
    target_count: int


class StationCellOut(BaseModel):
    label: str
    station_no: int
    hits: int


class StationEntryOut(BaseModel):
    entry_row: int
    name_key: str
    shooter_id: int | None
    display_name: str | None
    round_id: int | None
    hits: list[StationCellOut]
    total: int


class StationMatrixOut(BaseModel):
    layout: list[StationLayoutOut]
    entries: list[StationEntryOut]


class NotableOut(BaseModel):
    kind: Literal["pb", "first_timer"]
    shooter_id: int
    display_name: str
    detail: str
    value: float | None


class VsPrevOut(BaseModel):
    prev_date: date
    head_count_delta: int | None
    median_delta: float | None
    top_score_delta: int | None
    difficulty_delta: float | None


class EventDetailOut(BaseModel):
    # Plan 17: kind, label and target_total are always sent, so the schema requires them
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    event_date: date
    round_type: RoundType
    round_type_source: str
    head_count: int | None
    has_scores: bool
    has_stations: bool
    results_complete: bool
    n_rounds: int
    n_shooters: int
    median: float | None
    mean: float | None
    stdev: float | None
    top_score: int | None
    difficulty: float | None
    results: list[EventResultOut]
    weather: EventWeatherOut | None
    stations: StationMatrixOut | None
    notables: list[NotableOut]
    vs_prev: VsPrevOut | None
    # Plan 17: a special Sunday counts only as an appearance; its own name and target total
    kind: EventKind = "regular"
    label: str | None = None
    target_total: int = frames.REGULAR_TARGETS


def _kind(row: dict[str, Any]) -> EventKind:
    return "special" if row["kind"] == frames.EVENT_KIND_SPECIAL else "regular"


def _winners(rounds: pd.DataFrame) -> dict[date, list[WinnerOut]]:
    top = rounds.loc[rounds["event_rank"] == 1].sort_values(["event_date", "display_name"])
    out: dict[date, list[WinnerOut]] = {}
    for row in rows(top):
        winner = WinnerOut(
            shooter_id=int(row["shooter_id"]),
            display_name=str(row["display_name"]),
            score=int(row["score"]),
        )
        out.setdefault(row["event_date"], []).append(winner)
    return out


@router.get("/api/events")
def list_events(
    session: SessionDep,
    year: int | None = None,
    round_types: list[RoundType] = round_type_param,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> list[EventSummaryOut]:
    """Events in date order; `year` and the inclusive `from`/`to` window each narrow the list."""
    events = frames.apply_round_type_filter(frames.load_calendar(session), round_types)
    if year is not None:
        events = events.loc[[d.year == year for d in events["event_date"]]]
    if date_from is not None:
        events = events.loc[[d >= date_from for d in events["event_date"]]]
    if date_to is not None:
        events = events.loc[[d <= date_to for d in events["event_date"]]]
    events = events.sort_values("event_date")  # D16 date order is the route's, not the loader's
    winners = _winners(frames.load_rounds(session))
    return [
        EventSummaryOut(
            event_date=row["event_date"],
            round_type=RoundType(row["round_type"]),
            round_type_source=str(row["round_type_source"]),
            head_count=opt_int(row["head_count"]),
            n_rounds=int(row["n_rounds"]),
            n_shooters=int(row["n_shooters"]),
            has_scores=bool(row["has_scores"]),
            has_stations=bool(row["has_stations"]),
            results_complete=bool(row["results_complete"]),
            median=opt_float(row["median"]),
            top_score=opt_int(row["top_score"]),
            difficulty=opt_float(row["difficulty"]),
            condition=opt_str(row["condition"]),
            winners=winners.get(row["event_date"], []),
            kind=_kind(row),
            label=opt_str(row["label"]),
            target_total=int(row["target_total"]),
        )
        for row in rows(events)
    ]


def _special_results(special: pd.DataFrame, event_date: date) -> list[EventResultOut]:
    """A special Sunday's rounds, best first: as entered, never ranked or rated (Decision 18)."""
    day = special.loc[special["event_date"] == event_date]
    ordered = day.sort_values(["score", "display_name", "ordinal"], ascending=[False, True, True])
    return [
        EventResultOut(
            round_id=int(r["round_id"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            name_key=str(r["name_key"]),
            shooter_status=str(r["shooter_status"]),
            ordinal=int(r["ordinal"]),
            score=int(r["score"]),
            gauge_class=None,
            is_best_round=True,
            event_rank=None,
            percentile=None,
            adjusted=None,
            expected=None,
            residual=None,
            mu_before=None,
            mu_after=None,
            rating_delta=None,
        )
        for r in rows(ordered)
    ]


def _results(day: pd.DataFrame) -> list[EventResultOut]:
    ordered = day.sort_values(["score", "display_name", "ordinal"], ascending=[False, True, True])
    return [
        EventResultOut(
            round_id=int(r["round_id"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            name_key=str(r["name_key"]),
            shooter_status=str(r["shooter_status"]),
            ordinal=int(r["ordinal"]),
            score=int(r["score"]),
            gauge_class=opt_str(r["gauge_class"]),
            is_best_round=bool(r["is_best_round"]),
            event_rank=opt_int(r["event_rank"]),
            percentile=opt_float(r["percentile"]),
            adjusted=opt_float(r["adjusted"]),
            expected=opt_float(r["expected"]),
            residual=opt_float(r["residual"]),
            mu_before=opt_float(r["mu_before"]),
            mu_after=opt_float(r["mu_after"]),
            rating_delta=opt_float(r["mu_after"] - r["mu_before"]),
        )
        for r in rows(ordered)
    ]


def _weather(event: dict[str, Any]) -> EventWeatherOut | None:
    if opt_str(event["condition"]) is None and opt_float(event["temp_f"]) is None:
        return None
    return EventWeatherOut(
        temp_f=opt_float(event["temp_f"]),
        apparent_f=opt_float(event["apparent_f"]),
        precip_in=opt_float(event["precip_in"]),
        wind_mph=opt_float(event["wind_mph"]),
        gust_mph=opt_float(event["gust_mph"]),
        wind_dir_deg=opt_float(event["wind_dir_deg"]),
        cloud_pct=opt_float(event["cloud_pct"]),
        humidity_pct=opt_float(event["humidity_pct"]),
        pressure_hpa=opt_float(event["pressure_hpa"]),
        condition=opt_str(event["condition"]),
    )


def _stations(hits: pd.DataFrame, names: dict[int, str]) -> StationMatrixOut | None:
    if hits.empty:
        return None
    layout = (
        hits[["station_no", "station_label", "target_count"]]
        .drop_duplicates()
        .sort_values(["station_no", "station_label"])
    )
    entries: dict[int, StationEntryOut] = {}
    for cell in rows(hits.sort_values(["entry_row", "station_no", "station_label"])):
        entry_row = int(cell["entry_row"])
        if entry_row not in entries:
            shooter_id = opt_int(cell["shooter_id"])
            entries[entry_row] = StationEntryOut(
                entry_row=entry_row,
                name_key=str(cell["name_key"]),
                shooter_id=shooter_id,
                display_name=None if shooter_id is None else names.get(shooter_id),
                round_id=opt_int(cell["round_id"]),
                hits=[],
                total=0,
            )
        entry = entries[entry_row]
        entry.hits.append(
            StationCellOut(
                label=str(cell["station_label"]),
                station_no=int(cell["station_no"]),
                hits=int(cell["hits"]),
            )
        )
        entry.total += int(cell["hits"])
    return StationMatrixOut(
        layout=[
            StationLayoutOut(
                label=str(r["station_label"]),
                station_no=int(r["station_no"]),
                target_count=int(r["target_count"]),
            )
            for r in rows(layout)
        ],
        entries=list(entries.values()),
    )


def event_notables(
    rounds: pd.DataFrame, shooters: pd.DataFrame, event_date: date
) -> list[NotableOut]:
    """PBs (C12 personal_bests rule), and first-timers (not left_censored)."""
    day = rounds.loc[rounds["event_date"] == event_date]
    earlier = rounds.loc[rounds["event_date"] < event_date]
    notables: list[NotableOut] = []
    best = day.loc[day["is_best_round"]].sort_values("display_name")
    prior = {
        int(r["shooter_id"]): (int(r["max"]), int(r["size"]))
        for r in rows(earlier.groupby("shooter_id")["score"].agg(["max", "size"]).reset_index())
    }
    for r in rows(best):
        previous, n_prior = prior.get(int(r["shooter_id"]), (0, 0))
        if n_prior >= PB_MIN_PRIOR_ROUNDS and int(r["score"]) > previous:
            notables.append(
                NotableOut(
                    kind="pb",
                    shooter_id=int(r["shooter_id"]),
                    display_name=str(r["display_name"]),
                    detail=f"New personal best {int(r['score'])} (was {previous})",
                    value=float(r["score"]),
                )
            )
    firsts = shooters.loc[(shooters["first_event"] == event_date) & ~shooters["left_censored"]]
    for s in rows(firsts.sort_values("display_name")):
        notables.append(
            NotableOut(
                kind="first_timer",
                shooter_id=int(s["shooter_id"]),
                display_name=str(s["display_name"]),
                detail="First Sunday Clays",
                value=None,
            )
        )
    return notables


def _vs_prev(events: pd.DataFrame, event: dict[str, Any]) -> VsPrevOut | None:
    earlier = events.loc[events["results_complete"] & (events["event_date"] < event["event_date"])]
    if earlier.empty:
        return None
    prev = rows(earlier.sort_values("event_date").tail(1))[0]

    def delta(column: str) -> float | None:
        a, b = opt_float(event[column]), opt_float(prev[column])
        return None if a is None or b is None else a - b

    head, top = delta("head_count"), delta("top_score")
    return VsPrevOut(
        prev_date=prev["event_date"],
        head_count_delta=None if head is None else int(head),
        median_delta=delta("median"),
        top_score_delta=None if top is None else int(top),
        difficulty_delta=delta("difficulty"),
    )


@router.get("/api/events/{date}")
def get_event(
    event_date: Annotated[date, Path(alias="date")],
    session: SessionDep,
) -> EventDetailOut:
    events = frames.load_calendar(session)
    match = events.loc[events["event_date"] == event_date]
    if match.empty:
        raise NotFoundError("event_not_found", f"No event on {event_date.isoformat()}")
    event = rows(match)[0]
    special = _kind(event) == "special"
    rounds = frames.load_rounds(session)
    shooters = frames.load_shooters(session)
    hits = (
        frames.load_special_station_hits(session) if special else frames.load_station_hits(session)
    )
    names = {int(r["shooter_id"]): str(r["display_name"]) for r in rows(shooters)}
    results = (
        _special_results(frames.load_special_rounds(session), event_date)
        if special
        else _results(rounds.loc[rounds["event_date"] == event_date])
    )
    regular = events.loc[events["kind"] == frames.EVENT_KIND_REGULAR]
    return EventDetailOut(
        event_date=event_date,
        round_type=RoundType(str(event["round_type"])),
        round_type_source=str(event["round_type_source"]),
        head_count=opt_int(event["head_count"]),
        has_scores=bool(event["has_scores"]),
        has_stations=bool(event["has_stations"]),
        results_complete=bool(event["results_complete"]),
        n_rounds=int(event["n_rounds"]),
        n_shooters=int(event["n_shooters"]),
        median=opt_float(event["median"]),
        mean=opt_float(event["mean"]),
        stdev=opt_float(event["stdev"]),
        top_score=opt_int(event["top_score"]),
        difficulty=opt_float(event["difficulty"]),
        results=results,
        weather=_weather(event),
        stations=_stations(hits.loc[hits["event_date"] == event_date], names),
        notables=event_notables(rounds, shooters, event_date),
        vs_prev=None if special else _vs_prev(regular, event),
        kind=_kind(event),
        label=opt_str(event["label"]),
        target_total=int(event["target_total"]),
    )
