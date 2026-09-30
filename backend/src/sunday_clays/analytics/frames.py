"""DataFrame loaders over the live/analytics tables and shared frame helpers (C7)."""

import math
from collections.abc import Sequence
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.domain.round_type import RoundType

TEMP_BANDS: tuple[str, ...] = ("<40", "40-55", "55-70", "70-85", "85+")
WIND_BANDS: tuple[str, ...] = ("<10", "10-20", "20+")
PRECIP_BANDS: tuple[str, ...] = ("dry", "wet")
SEASONS: tuple[str, ...] = ("winter", "spring", "summer", "fall")
WET_PRECIP_IN = 0.02
UNSPECIFIED_GAUGE = "unspecified"

ROUND_COLUMNS: tuple[str, ...] = (
    "round_id",
    "event_date",
    "shooter_id",
    "name_key",
    "display_name",
    "ordinal",
    "score",
    "gauge_class",
    "status",
    "shooter_status",
    "round_type",
    "field_median",
    "adjusted",
    "event_rank",
    "is_best_round",
    "percentile",
    "expected",
    "residual",
    "mu_before",
    "mu_after",
    "temp_f",
    "apparent_f",
    "precip_in",
    "wind_mph",
    "gust_mph",
    "wind_dir_deg",
    "cloud_pct",
    "condition",
    "gauge",
    "held",
)
EVENT_COLUMNS: tuple[str, ...] = (
    "event_date",
    "round_type",
    "round_type_source",
    "head_count",
    "n_rounds",
    "n_shooters",
    "has_scores",
    "has_stations",
    "results_complete",
    "n",
    "median",
    "mean",
    "stdev",
    "top_score",
    "difficulty",
    "temp_f",
    "apparent_f",
    "precip_in",
    "wind_mph",
    "gust_mph",
    "wind_dir_deg",
    "cloud_pct",
    "humidity_pct",
    "pressure_hpa",
    "condition",
)
STATION_HIT_COLUMNS: tuple[str, ...] = (
    "event_date",
    "station_no",
    "station_label",
    "target_count",
    "sheet_id",
    "entry_row",
    "name_key",
    "shooter_id",
    "round_id",
    "hits",
    "round_type",
)
RATING_COLUMNS: tuple[str, ...] = ("shooter_id", "event_date", "mu", "var")
SHOOTER_COLUMNS: tuple[str, ...] = (
    "shooter_id",
    "display_name",
    "status",
    "first_event",
    "last_event",
    "n_rounds",
    "n_events",
    "left_censored",
)

_ROUNDS_SQL = """
SELECT r.id AS round_id, r.event_date, r.shooter_id, r.name_key, p.display_name,
       r.ordinal, r.score, r.gauge_class, r.status, p.status AS shooter_status,
       e.round_type, m.field_median, m.adjusted, m.event_rank, m.is_best_round,
       m.percentile, m.expected, m.residual, m.mu_before, m.mu_after, w.temp_f,
       w.apparent_f, w.precip_in, w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct,
       w.condition, e.results_complete AS held
FROM rounds r
JOIN events e ON e.event_date = r.event_date
JOIN shooter_profiles p ON p.shooter_id = r.shooter_id
LEFT JOIN round_metrics m ON m.round_id = r.id
LEFT JOIN event_weather w ON w.event_date = r.event_date
ORDER BY r.event_date, r.shooter_id, r.name_key, r.ordinal
"""
_EVENTS_SQL = """
SELECT e.event_date, e.round_type, e.round_type_source, e.head_count, e.n_rounds,
       e.n_shooters, e.has_scores, e.has_stations, e.results_complete, m.n, m.median,
       m.mean, m.stdev, m.top_score, m.difficulty, w.temp_f, w.apparent_f, w.precip_in,
       w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct, w.humidity_pct,
       w.pressure_hpa, w.condition
FROM events e
LEFT JOIN event_metrics m ON m.event_date = e.event_date
LEFT JOIN event_weather w ON w.event_date = e.event_date
ORDER BY e.event_date
"""
_STATION_HITS_SQL = """
SELECT h.event_date, h.station_no, h.station_label, l.target_count, h.sheet_id, h.entry_row,
       h.name_key, h.shooter_id, h.round_id, h.hits, e.round_type
FROM station_hits h
JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
JOIN events e ON e.event_date = h.event_date
ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
"""
_RATING_SQL = """
SELECT shooter_id, event_date, mu, var FROM rating_history
ORDER BY shooter_id, event_date
"""
_SHOOTERS_SQL = """
SELECT shooter_id, display_name, status, first_event, last_event, n_rounds, n_events,
       left_censored
FROM shooter_profiles ORDER BY shooter_id
"""


def _frame(
    session: Session,
    sql: str,
    columns: Sequence[str],
    *,
    ints: Sequence[str] = (),
    nullable_ints: Sequence[str] = (),
    floats: Sequence[str] = (),
    bools: Sequence[str] = (),
) -> pd.DataFrame:
    rows = [dict(r) for r in session.execute(text(sql)).mappings()]
    df = pd.DataFrame(rows, columns=list(columns))
    for c in ints:
        df[c] = df[c].astype("int64")
    for c in nullable_ints:
        df[c] = df[c].astype("Int64")
    for c in floats:
        df[c] = df[c].astype("float64")
    for c in bools:
        df[c] = df[c].eq(True)
    return df


@cached_by_data_version
def load_rounds(session: Session) -> pd.DataFrame:
    """One row per live round with metrics, weather and derived `gauge`/`held`.

    Dates are `datetime.date` objects. Metric/weather columns are NaN until computed;
    `is_best_round` is False until s10 has run; `held` = the event's `results_complete`.
    """
    df = _frame(
        session,
        _ROUNDS_SQL,
        [c for c in ROUND_COLUMNS if c != "gauge"],
        ints=("round_id", "shooter_id", "ordinal", "score"),
        floats=(
            "field_median",
            "adjusted",
            "event_rank",
            "percentile",
            "expected",
            "residual",
            "mu_before",
            "mu_after",
            "temp_f",
            "apparent_f",
            "precip_in",
            "wind_mph",
            "gust_mph",
            "wind_dir_deg",
            "cloud_pct",
        ),
        bools=("is_best_round", "held"),
    )
    df["gauge"] = df["gauge_class"].where(df["gauge_class"].notna(), UNSPECIFIED_GAUGE)
    return df[list(ROUND_COLUMNS)]


@cached_by_data_version
def load_events(session: Session) -> pd.DataFrame:
    """Each `events` row plus event_metrics/event_weather columns (NaN if absent)."""
    return _frame(
        session,
        _EVENTS_SQL,
        EVENT_COLUMNS,
        ints=("n_rounds", "n_shooters"),
        floats=(
            "head_count",
            "n",
            "median",
            "mean",
            "stdev",
            "top_score",
            "difficulty",
            "temp_f",
            "apparent_f",
            "precip_in",
            "wind_mph",
            "gust_mph",
            "wind_dir_deg",
            "cloud_pct",
            "humidity_pct",
            "pressure_hpa",
        ),
        bools=("has_scores", "has_stations", "results_complete"),
    )


@cached_by_data_version
def load_station_hits(session: Session) -> pd.DataFrame:
    """station_hits rows with the station's target_count and the event round_type."""
    df = _frame(
        session,
        _STATION_HITS_SQL,
        STATION_HIT_COLUMNS,
        ints=("station_no", "target_count", "sheet_id", "entry_row", "hits"),
        nullable_ints=("shooter_id", "round_id"),
    )
    df["station_label"] = df["station_label"].astype(str)  # text dtype, empty or not
    return df


@cached_by_data_version
def load_rating_history(session: Session) -> pd.DataFrame:
    """rating_history by (shooter_id, event_date); `mu` on the published scale."""
    return _frame(session, _RATING_SQL, RATING_COLUMNS, ints=("shooter_id",), floats=("mu", "var"))


@cached_by_data_version
def load_shooters(session: Session) -> pd.DataFrame:
    """shooter_profiles as a frame (current status incl. overrides, left_censored)."""
    return _frame(
        session,
        _SHOOTERS_SQL,
        SHOOTER_COLUMNS,
        ints=("shooter_id", "n_rounds", "n_events"),
        bools=("left_censored",),
    )


def _is_missing(value: float | None) -> bool:
    return value is None or math.isnan(value)


def temp_band(temp_f: float | None) -> str | None:
    """C7 temperature band, half-open [lo, hi): <40, 40-55, 55-70, 70-85, 85+ (°F)."""
    if temp_f is None or _is_missing(temp_f):
        return None
    if temp_f < 40:
        return "<40"
    if temp_f < 55:
        return "40-55"
    if temp_f < 70:
        return "55-70"
    if temp_f < 85:
        return "70-85"
    return "85+"


def wind_band(gust_mph: float | None) -> str | None:
    """C7 wind band by gust: <10, 10-20, 20+ (mph)."""
    if gust_mph is None or _is_missing(gust_mph):
        return None
    if gust_mph < 10:
        return "<10"
    if gust_mph < 20:
        return "10-20"
    return "20+"


def precip_band(precip_in: float | None) -> str | None:
    """C7 precipitation band: dry (< 0.02 in) or wet (>= 0.02 in).

    Plan 05 writes `event_weather.precip_in` rounded to 3 dp. Rounding again before the
    comparison keeps a value that passed through float4 (0.02 -> 0.019999999552965164)
    on the same side as the `rain` condition label (Plan 05 T3 Produces).
    """
    if precip_in is None or _is_missing(precip_in):
        return None
    return "wet" if round(precip_in, 3) >= WET_PRECIP_IN else "dry"


def season_label(event_date: date) -> str:
    """Month season: winter Dec-Feb, spring Mar-May, summer Jun-Aug, fall Sep-Nov."""
    return SEASONS[(event_date.month % 12) // 3]


def apply_round_type_filter(df: pd.DataFrame, round_types: Sequence[RoundType]) -> pd.DataFrame:
    """Keep rows whose event `round_type` is in `round_types`; empty = no filter."""
    if not round_types:
        return df
    return df.loc[df["round_type"].isin([rt.value for rt in round_types])]


def db_records(df: pd.DataFrame) -> list[dict[str, object]]:
    """Rows as dicts with NaN/NA mapped to None (for SQL parameters).

    `DataFrame.to_dict(orient="records")` already unboxes numpy scalars.
    """
    return [{str(k): _plain(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _plain(value: object) -> object:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value
