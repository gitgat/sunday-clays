"""Explorer engine (C9): a cached frame loader plus a pure pandas query runner."""

import math
import numbers
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import pandas as pd
from pandas.api.typing import SeriesGroupBy
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames as fr
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.domain.errors import DomainError
from sunday_clays.explorer.spec import (
    Agg,
    Column,
    Dim,
    Filters,
    Metric,
    QueryResult,
    QuerySpec,
)
from sunday_clays.station_label import label_rank

ColumnType = Literal["date", "number", "string", "int"]
Cell = str | int | float | None
# A per-group reducer applied once to the whole SeriesGroupBy, so no Python runs per group.
Reducer = Callable[["SeriesGroupBy[Any, Any]"], "pd.Series[Any]"]


@dataclass(frozen=True)
class ExplorerFrames:
    rounds: pd.DataFrame  # C7 load_rounds columns + temp_band, wind_band, precip_band
    station_hits: pd.DataFrame  # C7 load_station_hits columns (incl. target_count)
    events: pd.DataFrame  # event_date, round_type, head_count, difficulty, WEATHER_COLUMNS, bands


METRIC_LABELS: Final[dict[Metric, str]] = {
    Metric.SCORE: "Score",
    Metric.ADJUSTED: "Adjusted score",
    Metric.RESIDUAL: "Vs expected",
    Metric.RATING: "Rating",
    Metric.ROUNDS: "Rounds",
    Metric.SHOOTERS: "Shooters",
    Metric.ATTENDANCE: "Attendance",
    Metric.WINS: "Wins",
    Metric.HIT_PCT: "Hit %",
    Metric.DIFFICULTY: "How the day played",
}
AGG_LABELS: Final[dict[Agg, str]] = {
    Agg.AVG: "Avg",
    Agg.MEDIAN: "Median",
    Agg.MAX: "Max",
    Agg.MIN: "Min",
    Agg.SUM: "Total",
    Agg.COUNT: "Count of",
    Agg.P90: "P90",
    Agg.STDEV: "Std dev of",
    Agg.P25: "Low end of",
}
DIM_COLUMNS: Final[dict[Dim, tuple[Column, ...]]] = {
    Dim.SHOOTER: (
        Column(key="shooter_id", label="Shooter ID", type="int"),
        Column(key="shooter", label="Shooter", type="string"),
    ),
    Dim.EVENT: (Column(key="event", label="Sunday", type="date"),),
    Dim.MONTH: (Column(key="month", label="Month", type="string"),),
    Dim.YEAR: (Column(key="year", label="Year", type="int"),),
    Dim.SEASON: (Column(key="season", label="Time of year", type="string"),),
    Dim.MONTH_OF_YEAR: (Column(key="month_of_year", label="Month of year", type="int"),),
    Dim.ROUND_TYPE: (Column(key="round_type", label="Round type", type="string"),),
    Dim.GAUGE: (Column(key="gauge", label="Gauge", type="string"),),
    Dim.STATUS: (Column(key="status", label="Status", type="string"),),
    Dim.TEMP_BAND: (Column(key="temp_band", label="Temperature", type="string"),),
    Dim.WIND_BAND: (Column(key="wind_band", label="Wind", type="string"),),
    Dim.PRECIP_BAND: (Column(key="precip_band", label="Precipitation", type="string"),),
    Dim.CONDITION: (Column(key="condition", label="Conditions", type="string"),),
    Dim.STATION: (Column(key="station", label="Station", type="string"),),
}
# Metrics whose per-unit values are combined with spec.agg; the others are fixed counts/rates.
AGGREGATED: Final[dict[Metric, str]] = {
    Metric.SCORE: "score",
    Metric.ADJUSTED: "adjusted",
    Metric.RESIDUAL: "residual",
    Metric.RATING: "mu_after",
    Metric.ATTENDANCE: "head_count",
    Metric.DIFFICULTY: "difficulty",
}
# Each skips missing readings; a group with none gives NaN (null), and COUNT gives 0.
AGG_FUNCS: Final[dict[Agg, Reducer]] = {
    Agg.AVG: lambda g: g.mean(),
    Agg.MEDIAN: lambda g: g.median(),
    Agg.MAX: lambda g: g.max(),
    Agg.MIN: lambda g: g.min(),
    Agg.SUM: lambda g: g.sum(min_count=1),  # no readings -> NaN, not 0
    Agg.COUNT: lambda g: g.count(),
    Agg.P90: lambda g: g.quantile(0.9),  # linear interpolation, like Series.quantile
    Agg.STDEV: lambda g: g.std(),
    Agg.P25: lambda g: g.quantile(0.25),  # the low end; linear interpolation like P90
}
FIXED_REDUCERS: Final[dict[Metric, Reducer]] = {
    Metric.ROUNDS: lambda g: g.sum(),
    Metric.SHOOTERS: lambda g: g.nunique(),
    Metric.WINS: lambda g: g.sum(),
    Metric.HIT_PCT: lambda g: g.sum(),
}
INT_METRICS: Final = frozenset({Metric.ROUNDS, Metric.SHOOTERS, Metric.WINS})
EVENT_DIMS: Final = frozenset(
    {
        Dim.EVENT,
        Dim.MONTH,
        Dim.YEAR,
        Dim.SEASON,
        Dim.MONTH_OF_YEAR,
        Dim.ROUND_TYPE,
        Dim.TEMP_BAND,
        Dim.WIND_BAND,
        Dim.PRECIP_BAND,
        Dim.CONDITION,
    }
)
# C7 sort order winter, spring, summer, fall, from Plan 06's single definition (frames.SEASONS).
SEASON_ORDER: Final[dict[str, int]] = {season: i for i, season in enumerate(fr.SEASONS)}
# D21 weather bands sort in label order (frames.TEMP_BANDS etc., coldest/calmest/driest first).
# The order depends only on the band itself, so key_* then orders a second dim within each band.
BAND_ORDER: Final[dict[Dim, dict[str, int]]] = {
    Dim.TEMP_BAND: {band: i for i, band in enumerate(fr.TEMP_BANDS)},
    Dim.WIND_BAND: {band: i for i, band in enumerate(fr.WIND_BANDS)},
    Dim.PRECIP_BAND: {band: i for i, band in enumerate(fr.PRECIP_BANDS)},
}
PLAIN_DIMS: Final[dict[Dim, str]] = {
    Dim.ROUND_TYPE: "round_type",
    Dim.GAUGE: "gauge",
    Dim.STATUS: "shooter_status",
    Dim.CONDITION: "condition",
    Dim.STATION: "station_label",
}
WEATHER_COLUMNS: Final = ["temp_f", "gust_mph", "precip_in", "condition"]
# Event totals: one value per event, so no shooter, status, gauge, minimum-rounds, best-round or
# minimum-score filter applies, and only event-level dims group them.
EVENT_METRICS: Final = frozenset({Metric.ATTENDANCE, Metric.DIFFICULTY})
ROUND_METRICS_FOR_MIN_SCORE: Final = frozenset(
    {Metric.SCORE, Metric.ADJUSTED, Metric.RESIDUAL, Metric.ROUNDS, Metric.SHOOTERS, Metric.WINS}
)


def _invalid(message: str) -> DomainError:
    return DomainError("invalid_query", message)


def _validate(frames: ExplorerFrames, spec: QuerySpec) -> None:
    dims = spec.group_by
    if len(set(dims)) != len(dims):
        raise _invalid("Each group-by dimension can be used only once")
    if spec.limit < 1:
        raise _invalid("limit must be at least 1")
    if Dim.STATION in dims and spec.metric is not Metric.HIT_PCT:
        raise _invalid("Grouping by station needs the Hit % metric")
    if spec.metric is Metric.HIT_PCT and not frames.station_hits["round_id"].notna().any():
        raise _invalid("Hit % needs station data, and no station sheet has been imported")
    f = spec.filters
    if spec.metric in EVENT_METRICS:
        name = METRIC_LABELS[spec.metric]
        bad = [d for d in dims if d not in EVENT_DIMS]
        if bad:
            label = DIM_COLUMNS[bad[0]][-1].label.lower()
            raise _invalid(f"{name} is a Sunday total and cannot be grouped by {label}")
        if f.shooter_ids or f.statuses or f.gauges or f.min_rounds > 0 or f.best_round_only:
            raise _invalid(
                f"{name} is a Sunday total; shooter, status, gauge, minimum-rounds and "
                "best-round filters do not apply"
            )
    if f.min_score is not None and spec.metric not in ROUND_METRICS_FOR_MIN_SCORE:
        raise _invalid("A minimum score applies only to round metrics")
    if f.ytd is not None and Dim.YEAR not in dims:
        raise _invalid("A same-date cutoff needs the year grouping")


def _common_mask(df: pd.DataFrame, f: Filters) -> "pd.Series[bool]":
    ts = pd.to_datetime(df["event_date"])
    mask = pd.Series(True, index=df.index)
    if f.date_from is not None:
        mask &= ts >= pd.Timestamp(f.date_from)
    if f.date_to is not None:
        mask &= ts <= pd.Timestamp(f.date_to)
    for column, bounds in (
        ("temp_f", f.temp_f),
        ("gust_mph", f.gust_mph),
        ("precip_in", f.precip_in),
    ):
        if bounds is not None:
            mask &= df[column].between(bounds[0], bounds[1])
    return mask & _ytd_mask(df, f.ytd)


def _ytd_mask(df: pd.DataFrame, ytd: str | None) -> "pd.Series[bool]":
    """Rows on or before month-day `ytd` of their own year (same-date cutoff per year)."""
    if ytd is None:
        return pd.Series(True, index=df.index)
    month, day = (int(part) for part in ytd.split("-"))
    ts = pd.to_datetime(df["event_date"])
    return (ts.dt.month < month) | ((ts.dt.month == month) & (ts.dt.day <= day))


def _filter_events(events: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = _common_mask(events, f)
    return fr.apply_round_type_filter(events[mask], f.round_types)


def _filter_rounds(rounds: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = _common_mask(rounds, f)
    if f.shooter_ids:
        mask &= rounds["shooter_id"].isin(f.shooter_ids)
    if f.statuses:
        mask &= rounds["shooter_status"].isin(f.statuses)
    if f.gauges:
        mask &= rounds["gauge"].isin(f.gauges)
    if f.min_score is not None:
        # Applied before min_rounds on purpose: "3+ rounds" then counts only rounds at the score.
        mask &= rounds["score"] >= f.min_score
    out = fr.apply_round_type_filter(rounds[mask], f.round_types)
    if f.min_rounds > 0:
        per_shooter = out.groupby("shooter_id")["round_id"].transform("size")
        out = out[per_shooter >= f.min_rounds]
    if f.best_round_only:
        out = out[out["is_best_round"].eq(True)]
    return out


def _keys(df: pd.DataFrame, dims: Sequence[Dim]) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Output key columns plus one hidden sort column per dim, aligned with df's index."""
    ts = pd.to_datetime(df["event_date"])
    out = pd.DataFrame(index=df.index)
    key_cols: list[str] = []
    sort_cols: list[str] = []
    for i, dim in enumerate(dims):
        sort = f"_sort{i}"
        if dim is Dim.SHOOTER:
            out["shooter_id"] = df["shooter_id"].astype("int64")
            out["shooter"] = df["display_name"].astype(str)
            out[sort] = out["shooter"].str.casefold()
        elif dim is Dim.EVENT:
            out["event"] = ts.dt.strftime("%Y-%m-%d")
            out[sort] = out["event"]
        elif dim is Dim.MONTH:
            out["month"] = ts.dt.strftime("%Y-%m")
            out[sort] = out["month"]
        elif dim is Dim.YEAR:
            out["year"] = ts.dt.year.astype("int64")
            out[sort] = out["year"]
        elif dim is Dim.SEASON:
            out["season"] = ts.dt.date.map(fr.season_label)
            out[sort] = out["season"].map(SEASON_ORDER)
        elif dim is Dim.MONTH_OF_YEAR:
            out["month_of_year"] = ts.dt.month.astype("int64")
            out[sort] = out["month_of_year"]
        elif dim is Dim.STATION:
            out["station"] = df["station_label"]
            out[sort] = df["station_label"].map(label_rank).astype("int64")
        elif dim in BAND_ORDER:
            out[dim.value] = df[dim.value]
            out[sort] = out[dim.value].map(BAND_ORDER[dim]).astype(float)  # None -> NaN, last
        else:
            key = DIM_COLUMNS[dim][-1].key
            out[key] = df[PLAIN_DIMS[dim]]
            out[sort] = out[key]
        key_cols.extend(c.key for c in DIM_COLUMNS[dim])
        sort_cols.append(sort)
    return out, key_cols, sort_cols


def _units(
    frames: ExplorerFrames, spec: QuerySpec
) -> tuple[pd.DataFrame, list[str], list[str], int]:
    """One row per counted unit (round, shooter-event, station entry or event) with a 'value'."""
    metric = spec.metric
    if metric in EVENT_METRICS:
        events = _filter_events(frames.events, spec.filters)
        units, key_cols, sort_cols = _keys(events, spec.group_by)
        units["value"] = events[AGGREGATED[metric]].astype(float)
        return units, key_cols, sort_cols, 0
    rounds = _filter_rounds(frames.rounds, spec.filters)
    if metric is Metric.HIT_PCT:
        hits = frames.station_hits
        hits = hits[hits["round_id"].notna()].astype({"round_id": "int64"})
        joined = hits[["round_id", "station_no", "station_label", "hits", "target_count"]].merge(
            rounds, on="round_id", how="inner"
        )
        units, key_cols, sort_cols = _keys(joined, spec.group_by)
        units["value"] = joined["hits"].astype(float)
        units["weight"] = joined["target_count"].astype(float)
        return units, key_cols, sort_cols, int(joined["round_id"].nunique())
    if metric in (Metric.RATING, Metric.WINS):
        rounds = rounds[rounds["is_best_round"].eq(True)]
    units, key_cols, sort_cols = _keys(rounds, spec.group_by)
    if metric is Metric.ROUNDS:
        units["value"] = 1
    elif metric is Metric.SHOOTERS:
        units["value"] = rounds["shooter_id"].astype("int64")
    elif metric is Metric.WINS:
        units["value"] = rounds["event_rank"].eq(1).astype("int64")
    else:
        units["value"] = rounds[AGGREGATED[metric]].astype(float)
    return units, key_cols, sort_cols, int(rounds["round_id"].nunique())


def _cell(value: object) -> Cell:
    """JSON-safe cell: numpy scalars become int/float; NaN, None and NA become None."""
    if isinstance(value, str):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real) and not math.isnan(float(value)):
        return float(value)
    return None


def run_query(frames: ExplorerFrames, spec: QuerySpec) -> QueryResult:
    _validate(frames, spec)
    units, key_cols, sort_cols, n_rounds = _units(frames, spec)
    group_cols = key_cols or ["_all"]
    if not key_cols:
        units["_all"] = 0
    grouper = units.groupby(group_cols, dropna=False, sort=False)
    named: dict[str, tuple[str, str]] = {c: (c, "min") for c in sort_cols}
    named["n"] = ("value", "count")
    if spec.metric is Metric.HIT_PCT:
        named["weight"] = ("weight", "sum")
    grouped = grouper.agg(**named)
    reducer = AGG_FUNCS[spec.agg] if spec.metric in AGGREGATED else FIXED_REDUCERS[spec.metric]
    grouped["value"] = reducer(grouper["value"])  # same grouper, so the same group index
    grouped = grouped.reset_index()
    if spec.metric is Metric.HIT_PCT:
        grouped["value"] = 100.0 * grouped["value"] / grouped["weight"]
    if spec.sort in ("key_asc", "key_desc"):
        by = [*sort_cols, *key_cols, "n"]
        ascending = spec.sort == "key_asc"
        grouped = grouped.sort_values(by, ascending=ascending, na_position="last", kind="stable")
    else:
        by = ["value", *sort_cols, *key_cols]
        flags = [spec.sort == "value_asc", *([True] * (len(by) - 1))]
        grouped = grouped.sort_values(by, ascending=flags, na_position="last", kind="stable")
    truncated = len(grouped) > spec.limit
    grouped = grouped.head(spec.limit)

    if spec.metric in AGGREGATED:
        value_label = f"{AGG_LABELS[spec.agg]} {METRIC_LABELS[spec.metric].lower()}"
    else:
        value_label = METRIC_LABELS[spec.metric]
    value_type: ColumnType = "int" if spec.metric in INT_METRICS else "number"
    columns = [c for d in spec.group_by for c in DIM_COLUMNS[d]]
    columns += [
        Column(key="value", label=value_label, type=value_type),
        Column(key="n", label="n", type="int"),
    ]
    keys = [c.key for c in columns]
    rows = [
        {k: _cell(v) for k, v in zip(keys, record, strict=True)}
        for record in grouped[keys].itertuples(index=False, name=None)
    ]
    return QueryResult(columns=columns, rows=rows, n_rounds=n_rounds, truncated=truncated)


def _add_bands(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(
        temp_band=df["temp_f"].map(fr.temp_band),
        wind_band=df["gust_mph"].map(fr.wind_band),
        precip_band=df["precip_in"].map(fr.precip_band),
    )


@cached_by_data_version
def load_explorer_frames(session: Session) -> ExplorerFrames:
    """Plan 06 frames plus weather bands (rounds and events)."""
    rounds = _add_bands(fr.load_rounds(session))
    events = fr.load_events(session)[
        ["event_date", "round_type", "head_count", "difficulty", *WEATHER_COLUMNS]
    ]
    return ExplorerFrames(
        rounds=rounds, station_hits=fr.load_station_hits(session), events=_add_bands(events)
    )
