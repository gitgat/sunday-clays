"""DataFrame loaders over the live/analytics tables and shared frame helpers (C7)."""

import math
from collections.abc import Sequence
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.domain.round_type import RoundType
from sunday_clays.domain.thrown_out import ThrownOut

TEMP_BANDS: tuple[str, ...] = ("<40", "40-55", "55-70", "70-85", "85+")
WIND_BANDS: tuple[str, ...] = ("<10", "10-20", "20+")
PRECIP_BANDS: tuple[str, ...] = ("dry", "wet")
SEASONS: tuple[str, ...] = ("winter", "spring", "summer", "fall")
WET_PRECIP_IN = 0.02
UNSPECIFIED_GAUGE = "unspecified"
EVENT_KIND_REGULAR = "regular"
EVENT_KIND_SPECIAL = "special"  # Plan 17: a special Sunday counts only as an appearance
REGULAR_TARGETS = 50

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
    "stats_excluded",
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
    "stats_excluded",
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
    "dropped",
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

CALENDAR_COLUMNS: tuple[str, ...] = (*EVENT_COLUMNS, "kind", "label", "target_total")
APPEARANCE_COLUMNS: tuple[str, ...] = (
    "shooter_id",
    "event_date",
    "kind",
    "round_type",
    "display_name",
    "shooter_status",
    "name_key",
    "held",
)
SPECIAL_ROUND_COLUMNS: tuple[str, ...] = (
    "round_id",
    "event_date",
    "shooter_id",
    "name_key",
    "display_name",
    "shooter_status",
    "ordinal",
    "score",
    "label",
    "target_total",
)

# Plan 17: every score frame reads regular Sundays only (`WHERE e.kind = 'regular'`); the
# appearance frames below are the only readers that see special Sundays.
_ROUNDS_SQL = """
SELECT r.id AS round_id, r.event_date, r.shooter_id, r.name_key, p.display_name,
       r.ordinal, r.score, r.gauge_class, r.status, p.status AS shooter_status,
       e.round_type, m.field_median, m.adjusted, m.event_rank, m.is_best_round,
       m.percentile, m.expected, m.residual, m.mu_before, m.mu_after, w.temp_f,
       w.apparent_f, w.precip_in, w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct,
       w.condition, e.results_complete AS held, e.stats_excluded
FROM rounds r
JOIN events e ON e.event_date = r.event_date
JOIN shooter_profiles p ON p.shooter_id = r.shooter_id
LEFT JOIN round_metrics m ON m.round_id = r.id
LEFT JOIN event_weather w ON w.event_date = r.event_date
WHERE e.kind = 'regular'
ORDER BY r.event_date, r.shooter_id, r.name_key, r.ordinal
"""
_EVENTS_SQL = """
SELECT e.event_date, e.round_type, e.round_type_source, e.head_count, e.n_rounds,
       e.n_shooters, e.has_scores, e.has_stations, e.results_complete, m.n, m.median,
       m.mean, m.stdev, m.top_score, m.difficulty, w.temp_f, w.apparent_f, w.precip_in,
       w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct, w.humidity_pct,
       w.pressure_hpa, w.condition, e.stats_excluded
FROM events e
LEFT JOIN event_metrics m ON m.event_date = e.event_date
LEFT JOIN event_weather w ON w.event_date = e.event_date
WHERE e.kind = 'regular'
ORDER BY e.event_date
"""
_CALENDAR_SQL = """
SELECT e.event_date, e.round_type, e.round_type_source, e.head_count, e.n_rounds,
       e.n_shooters, e.has_scores, e.has_stations, e.results_complete, m.n, m.median,
       m.mean, m.stdev, m.top_score, m.difficulty, w.temp_f, w.apparent_f, w.precip_in,
       w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct, w.humidity_pct,
       w.pressure_hpa, w.condition, e.stats_excluded, e.kind, e.label, e.target_total
FROM events e
LEFT JOIN event_metrics m ON m.event_date = e.event_date
LEFT JOIN event_weather w ON w.event_date = e.event_date
ORDER BY e.event_date
"""
_STATION_HITS_SQL = """
SELECT h.event_date, h.station_no, h.station_label, l.target_count, h.sheet_id, h.entry_row,
       h.name_key, h.shooter_id, h.round_id, h.hits, e.round_type, l.dropped
FROM station_hits h
JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
JOIN events e ON e.event_date = h.event_date
WHERE e.kind = 'regular'
ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
"""
_SPECIAL_STATION_HITS_SQL = """
SELECT h.event_date, h.station_no, h.station_label, l.target_count, h.sheet_id, h.entry_row,
       h.name_key, h.shooter_id, h.round_id, h.hits, e.round_type, l.dropped
FROM station_hits h
JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
JOIN events e ON e.event_date = h.event_date
WHERE e.kind = 'special'
ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
"""
_APPEARANCES_SQL = """
SELECT r.shooter_id, r.event_date, e.kind, e.round_type, p.display_name,
       p.status AS shooter_status, min(r.name_key) AS name_key, e.results_complete AS held
FROM rounds r
JOIN events e ON e.event_date = r.event_date
JOIN shooter_profiles p ON p.shooter_id = r.shooter_id
GROUP BY r.shooter_id, r.event_date, e.kind, e.round_type, p.display_name, p.status,
         e.results_complete
ORDER BY r.event_date, r.shooter_id
"""
_SPECIAL_ROUNDS_SQL = """
SELECT r.id AS round_id, r.event_date, r.shooter_id, r.name_key, p.display_name,
       p.status AS shooter_status, r.ordinal, r.score, e.label, e.target_total
FROM rounds r
JOIN events e ON e.event_date = r.event_date
JOIN shooter_profiles p ON p.shooter_id = r.shooter_id
WHERE e.kind = 'special'
ORDER BY r.event_date, r.score DESC, p.display_name, r.ordinal
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
    """One row per live round of a regular Sunday, with metrics, weather and derived gauge/held.

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
        bools=("is_best_round", "held", "stats_excluded"),
    )
    df["gauge"] = df["gauge_class"].where(df["gauge_class"].notna(), UNSPECIFIED_GAUGE)
    return df[list(ROUND_COLUMNS)]


_EVENT_FLOATS: tuple[str, ...] = (
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
)
_EVENT_BOOLS: tuple[str, ...] = (
    "has_scores",
    "has_stations",
    "results_complete",
    "stats_excluded",
)


@cached_by_data_version
def load_events(session: Session) -> pd.DataFrame:
    """Each regular `events` row plus event_metrics/event_weather columns (NaN if absent)."""
    return _frame(
        session,
        _EVENTS_SQL,
        EVENT_COLUMNS,
        ints=("n_rounds", "n_shooters"),
        floats=_EVENT_FLOATS,
        bools=_EVENT_BOOLS,
    )


@cached_by_data_version
def load_calendar(session: Session) -> pd.DataFrame:
    """Every Sunday, special ones included (Plan 17): load_events' columns plus kind, label and
    target_total. For appearance consumers (turnout, calendars, streaks); a special row has no
    metrics."""
    df = _frame(
        session,
        _CALENDAR_SQL,
        CALENDAR_COLUMNS,
        ints=("n_rounds", "n_shooters", "target_total"),
        floats=_EVENT_FLOATS,
        bools=_EVENT_BOOLS,
    )
    # a regular Sunday has no label: None, whatever dtype pandas infers for the column
    df["label"] = df["label"].astype(object).where(df["label"].notna(), None)
    return df


@cached_by_data_version
def load_appearances(session: Session) -> pd.DataFrame:
    """One row per shooter per Sunday shot, special Sundays included (Plan 17)."""
    return _frame(
        session, _APPEARANCES_SQL, APPEARANCE_COLUMNS, ints=("shooter_id",), bools=("held",)
    )


@cached_by_data_version
def load_special_rounds(session: Session) -> pd.DataFrame:
    """The rounds of special Sundays only (Plan 17), best first: for display, never for stats."""
    return _frame(
        session,
        _SPECIAL_ROUNDS_SQL,
        SPECIAL_ROUND_COLUMNS,
        ints=("round_id", "shooter_id", "ordinal", "score", "target_total"),
    )


def _station_frame(session: Session, sql: str) -> pd.DataFrame:
    df = _frame(
        session,
        sql,
        STATION_HIT_COLUMNS,
        ints=("station_no", "target_count", "sheet_id", "entry_row", "hits"),
        nullable_ints=("shooter_id", "round_id"),
        bools=("dropped",),
    )
    df["station_label"] = df["station_label"].astype(str)  # text dtype, empty or not
    return df


@cached_by_data_version
def load_station_hits(session: Session) -> pd.DataFrame:
    """Regular Sundays' station_hits with the station's target_count and the round_type."""
    return _station_frame(session, _STATION_HITS_SQL)


@cached_by_data_version
def load_special_station_hits(session: Session) -> pd.DataFrame:
    """Special Sundays' station grids (Plan 17): for the Sunday page only."""
    return _station_frame(session, _SPECIAL_STATION_HITS_SQL)


def appearances_from_rounds(rounds: pd.DataFrame) -> pd.DataFrame:
    """The appearance frame a rounds frame implies: its Sundays shot, all regular (Plan 17).

    Equal to load_appearances when no special Sunday exists; callers and unit-test worlds that
    hold only rounds use it.
    """
    if rounds.empty:
        return pd.DataFrame(
            {
                c: pd.Series(
                    dtype="int64" if c == "shooter_id" else "bool" if c == "held" else object
                )
                for c in APPEARANCE_COLUMNS
            }
        )
    days = rounds.groupby(["shooter_id", "event_date"], as_index=False, sort=False).agg(
        round_type=("round_type", "first"),
        display_name=("display_name", "first"),
        shooter_status=("shooter_status", "first"),
        name_key=("name_key", "min"),
        held=("held", "first"),
    )
    days["kind"] = EVENT_KIND_REGULAR
    days["shooter_id"] = days["shooter_id"].astype("int64")
    days["held"] = days["held"].eq(True)
    ordered = days.sort_values(["event_date", "shooter_id"], kind="mergesort")
    return ordered.reset_index(drop=True)[list(APPEARANCE_COLUMNS)]


def calendar_from_events(events: pd.DataFrame) -> pd.DataFrame:
    """The calendar an events frame implies: every Sunday regular, 50 targets (Plan 17)."""
    out = events.copy()
    if "stats_excluded" not in out.columns:
        out["stats_excluded"] = False
    out["kind"] = EVENT_KIND_REGULAR
    out["label"] = None
    out["target_total"] = REGULAR_TARGETS
    return out


def _without(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """`df` minus the rows whose `column` is True; NaN counts as kept, no column means no-op."""
    if column not in df.columns:
        return df
    return df[~df[column].eq(True)]


def stat_rounds(rounds: pd.DataFrame) -> pd.DataFrame:
    """The rounds that feed score statistics: those of a Sunday with a station thrown out stay
    on the page but out of every average, PB and record."""
    return _without(rounds, "stats_excluded")


def stat_events(events: pd.DataFrame) -> pd.DataFrame:
    """The Sundays that feed score statistics (a thrown-out Sunday is left out)."""
    return _without(events, "stats_excluded")


def live_station_hits(hits: pd.DataFrame) -> pd.DataFrame:
    """Station hits without the stations thrown out."""
    return _without(hits, "dropped")


_THROWN_OUT_STATIONS_SQL = """
SELECT l.event_date, l.station_label, l.target_count, l.dropped_source,
       count(h.hits) AS n_hits, coalesce(bool_and(h.hits = l.target_count), false) AS all_full
FROM station_layouts l
JOIN events e ON e.event_date = l.event_date
LEFT JOIN station_hits h
       ON h.event_date = l.event_date AND h.station_label = l.station_label
WHERE l.dropped AND e.kind = 'regular'
GROUP BY l.event_date, l.station_no, l.station_label, l.target_count, l.dropped_source
ORDER BY l.event_date, l.station_no, l.station_label
"""
_THROWN_OUT_SUNDAYS_SQL = """
SELECT e.event_date FROM events e
WHERE e.stats_excluded AND e.kind = 'regular'
  AND NOT EXISTS (
    SELECT 1 FROM station_layouts l WHERE l.event_date = e.event_date AND l.dropped
  )
"""


@cached_by_data_version
def load_thrown_out(session: Session) -> dict[date, tuple[ThrownOut, ...]]:
    """What was thrown out on each regular Sunday, dates ascending.

    A station item per dropped layout (layout order); a Sunday-level item only for a flagged
    Sunday with no dropped layout.
    """
    out: dict[date, list[ThrownOut]] = {}
    for r in session.execute(text(_THROWN_OUT_STATIONS_SQL)).mappings():
        source = r["dropped_source"]
        out.setdefault(r["event_date"], []).append(
            ThrownOut(
                station_label=str(r["station_label"]),
                target_count=int(r["target_count"]),
                credited=int(r["n_hits"]) > 0 and bool(r["all_full"]),
                source="override" if source == "override" else "auto",
            )
        )
    for r in session.execute(text(_THROWN_OUT_SUNDAYS_SQL)).mappings():
        out[r["event_date"]] = [ThrownOut(None, None, False, "override")]
    return {d: tuple(out[d]) for d in sorted(out)}


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
