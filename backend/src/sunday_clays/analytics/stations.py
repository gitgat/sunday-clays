"""Station analytics (Plan 10 T4a).

Every statistic reads station-sheet hits (station_hits), never rounds.score. One entry is a
shooter-round: one sheet row (event_date, entry_row) at one station, with its own target_count.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.frames import apply_round_type_filter, wind_band
from sunday_clays.domain.round_type import RoundType
from sunday_clays.station_label import label_number, parse_label

EraSel = Literal["current", "all"]

Z95 = 1.96
EVENT_CLUSTER_MIN_EVENTS = 8
SEPARATOR_MIN_ROUNDS = 30
LEADER_MIN_APPEARANCES = 3
WIND_MIN_EVENTS = 5
# Centering identical floats can leave ~1e-31 of noise; one hit of real spread adds >= 1/(2·t²).
NO_VARIATION = 1e-9

STATION_FRAME_COLUMNS: tuple[str, ...] = (
    "event_date",
    "station_no",
    "station_label",
    "target_count",
    "sheet_id",
    "entry_row",
    "shooter_id",
    "round_id",
    "hits",
    "round_type",
    "display_name",
)
# `label` is the station's text ("7A") and `station_no` its sort integer (7); every stations
# output is keyed by label and sorted by (station_no, label): 4, 5, 6, 7, 7A, 8.
STAT_COLUMNS: tuple[str, ...] = (
    "label",
    "station_no",
    "hits",
    "n_targets",
    "n_rounds",
    "n_events",
    "hit_pct",
    "ci_low",
    "ci_high",
    "deff",
    "clean_rate",
    "separator",
)
WIND_COLUMNS: tuple[str, ...] = (
    "label",
    "station_no",
    "band",
    "band_order",
    "hit_pct",
    "ci_low",
    "ci_high",
    "n_targets",
    "n_events",
    "sufficient",
)

_FRAME_SQL = text(
    """
    SELECT h.event_date, h.station_no, h.station_label, l.target_count, h.sheet_id, h.entry_row,
           h.shooter_id, h.round_id, h.hits, e.round_type, p.display_name
    FROM station_hits h
    JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
    JOIN events e ON e.event_date = h.event_date
    LEFT JOIN shooter_profiles p ON p.shooter_id = h.shooter_id
    WHERE e.kind = 'regular'
    ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
    """
)
_RESETS_SQL = text(
    "SELECT payload FROM rules WHERE rule_type = 'station_reset' AND active ORDER BY id"
)
_WEATHER_SQL = text("SELECT event_date, gust_mph FROM event_weather ORDER BY event_date")


# ---- loaders ----------------------------------------------------------------------------------


def add_sheet_totals(frame: pd.DataFrame) -> pd.DataFrame:
    """`sheet_total` = the entry's recomputed station-sheet total, taken before any filtering."""
    return frame.assign(
        sheet_total=frame.groupby(["event_date", "entry_row"])["hits"].transform("sum")
    )


def load_station_frame(session: Session) -> pd.DataFrame:
    rows = [dict(r) for r in session.execute(_FRAME_SQL).mappings()]
    frame = pd.DataFrame(rows, columns=list(STATION_FRAME_COLUMNS))
    for column in ("shooter_id", "round_id"):
        frame[column] = frame[column].astype("Int64")
    return add_sheet_totals(frame)


def window_frame(frame: pd.DataFrame, since: date | None, as_of: date | None) -> pd.DataFrame:
    """Rows on Sundays from `since` to `as_of`, both inclusive; either bound None = unbounded.

    The header time window is applied before eras, stats, leaders, wind and the matrix, so every
    figure on a page reads the same hits."""
    keep = pd.Series(True, index=frame.index)
    if since is not None:
        keep &= frame["event_date"] >= since
    if as_of is not None:
        keep &= frame["event_date"] <= as_of
    return frame[keep]


def load_station_resets(session: Session) -> pd.DataFrame:
    """Active station_reset rules, C5 payload {station | station_no, effective_date, note}.

    `station` is a number or a label such as "7A"; the older `station_no` is a number. Either
    way the frame has the station's `label`, and `station_no` its sort integer."""
    rows: list[dict[str, Any]] = []
    for (payload,) in session.execute(_RESETS_SQL).all():
        label = parse_label(payload.get("station", payload.get("station_no")))
        if label is None:  # not a station the rebuild could ever have; nothing to split
            continue
        rows.append(
            {
                "label": label,
                "station_no": label_number(label),
                "effective_date": date.fromisoformat(str(payload["effective_date"])),
                "note": payload.get("note"),
            }
        )
    return pd.DataFrame(rows, columns=["label", "station_no", "effective_date", "note"])


def load_event_weather(session: Session) -> pd.DataFrame:
    rows = [dict(r) for r in session.execute(_WEATHER_SQL).mappings()]
    return pd.DataFrame(rows, columns=["event_date", "gust_mph"])


# ---- hit % with a clustered Wilson interval --------------------------------------------------


def wilson_ci(p: float, n_eff: float, z: float = Z95) -> tuple[float, float]:
    if n_eff <= 0:
        return (0.0, 1.0)
    z2 = z * z
    denom = 1.0 + z2 / n_eff
    center = (p + z2 / (2.0 * n_eff)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n_eff + z2 / (4.0 * n_eff * n_eff)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def design_effect(hits: npt.NDArray[np.float64], targets: npt.NDArray[np.float64]) -> float:
    """deff = max(1, V_cluster / V_binomial) with V_cluster = k/(k-1)·Σ(h_i - p·m_i)²/(Σm_i)²."""
    total = float(targets.sum())
    k = len(hits)
    if k < 2 or total <= 0.0:
        return 1.0
    p = float(hits.sum()) / total
    v_binomial = p * (1.0 - p) / total
    if v_binomial <= 0.0:
        return 1.0
    v_cluster = k / (k - 1) * float(((hits - p * targets) ** 2).sum()) / total**2
    return max(1.0, v_cluster / v_binomial)


@dataclass(frozen=True)
class HitStats:
    hits: int
    n_targets: int
    n_rounds: int
    n_events: int
    hit_pct: float | None
    ci_low: float | None
    ci_high: float | None
    deff: float | None


def hit_stats(entries: pd.DataFrame) -> HitStats:
    """p = Σhits/Σtargets; 95% Wilson CI on n_eff = Σtargets/deff. Clusters are shooter-rounds, or
    events once the selection spans >= 8 events."""
    n_targets = int(entries["target_count"].sum())
    n_events = int(entries["event_date"].nunique())
    hits = int(entries["hits"].sum())
    if n_targets == 0:
        return HitStats(hits, 0, len(entries), n_events, None, None, None, None)
    if n_events >= EVENT_CLUSTER_MIN_EVENTS:
        clusters = entries.groupby("event_date")[["hits", "target_count"]].sum()
    else:
        clusters = entries[["hits", "target_count"]]
    deff = design_effect(
        clusters["hits"].to_numpy(dtype=np.float64),
        clusters["target_count"].to_numpy(dtype=np.float64),
    )
    p = hits / n_targets
    low, high = wilson_ci(p, n_targets / deff)
    return HitStats(hits, n_targets, len(entries), n_events, p, low, high, deff)


def separator(entries: pd.DataFrame) -> float | None:
    """Pearson corr of hits/target vs (sheet total - hits), both centered within each event."""
    if len(entries) < SEPARATOR_MIN_ROUNDS:
        return None
    share = entries["hits"] / entries["target_count"]
    rest = entries["sheet_total"] - entries["hits"]
    x = share - share.groupby(entries["event_date"]).transform("mean")
    y = rest - rest.groupby(entries["event_date"]).transform("mean")
    sxx, syy = float((x * x).sum()), float((y * y).sum())
    if sxx < NO_VARIATION or syy < NO_VARIATION:
        return None
    return float((x * y).sum()) / math.sqrt(sxx * syy)


def station_order(frame: pd.DataFrame) -> list[tuple[int, str]]:
    """The (sort number, label) of every station in `frame`, in station order (7 before 7A)."""
    return sorted(
        {
            (int(no), str(label))
            for no, label in zip(frame["station_no"], frame["station_label"], strict=True)
        }
    )


def _stat_row(station: tuple[int, str], entries: pd.DataFrame) -> dict[str, Any]:
    clean = float((entries["hits"] == entries["target_count"]).mean()) if len(entries) else None
    return {
        "label": station[1],
        "station_no": station[0],
        **asdict(hit_stats(entries)),
        "clean_rate": clean,
        "separator": separator(entries),
    }


def station_stats(frame: pd.DataFrame, stations: Sequence[tuple[int, str]] = ()) -> pd.DataFrame:
    """One row per station in `frame`, plus one empty row (zero counts, null stats) for each of
    `stations` ((number, label) pairs) that has no entries in it."""
    keys = sorted({*station_order(frame), *stations})
    rows = [_stat_row(key, frame[frame["station_label"] == key[1]]) for key in keys]
    return pd.DataFrame(rows, columns=list(STAT_COLUMNS))


def per_event_station_pct(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        frame.groupby(["event_date", "station_no", "station_label"], sort=True)[
            ["hits", "target_count"]
        ]
        .sum()
        .reset_index()
        .rename(columns={"target_count": "n_targets"})
    )
    grouped["hit_pct"] = grouped["hits"] / grouped["n_targets"]
    grouped = grouped.rename(columns={"station_label": "label"})
    return grouped[["event_date", "label", "station_no", "hits", "n_targets", "hit_pct"]]


# ---- shooters at stations ---------------------------------------------------------------------


def _linked(frame: pd.DataFrame) -> pd.DataFrame:
    """Entries of a shooter who has a profile: an unmatched name, or a shooter left without
    shooter_profiles (no live rounds), has no display name and is never listed."""
    return frame[frame["shooter_id"].notna() & frame["display_name"].notna()]


def station_leaders(frame: pd.DataFrame, *, limit: int | None) -> pd.DataFrame:
    columns = [
        "label",
        "station_no",
        "shooter_id",
        "display_name",
        "hits",
        "n_targets",
        "n_rounds",
        "hit_pct",
    ]
    linked = _linked(frame)
    if linked.empty:
        return pd.DataFrame(columns=columns)
    grouped = (
        linked.groupby(["station_no", "station_label", "shooter_id"], sort=True)
        .agg(
            display_name=("display_name", "first"),
            hits=("hits", "sum"),
            n_targets=("target_count", "sum"),
            n_rounds=("hits", "size"),
        )
        .reset_index()
    )
    grouped = grouped[grouped["n_rounds"] >= LEADER_MIN_APPEARANCES].copy()
    grouped["hit_pct"] = grouped["hits"] / grouped["n_targets"]
    grouped = grouped.rename(columns={"station_label": "label"})
    grouped = grouped.sort_values(
        ["station_no", "label", "hit_pct", "n_targets", "shooter_id"],
        ascending=[True, True, False, False, True],
        kind="stable",
    )
    if limit is not None:
        grouped = grouped.groupby(["station_no", "label"], sort=True).head(limit)
    return grouped.reset_index(drop=True)[columns]


def shooter_station_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "shooter_id",
        "display_name",
        "label",
        "station_no",
        "hits",
        "n_targets",
        "n_rounds",
        "hit_pct",
    ]
    linked = _linked(frame)
    if linked.empty:
        return pd.DataFrame(columns=columns)
    grouped = (
        linked.groupby(["shooter_id", "station_no", "station_label"], sort=True)
        .agg(
            display_name=("display_name", "first"),
            hits=("hits", "sum"),
            n_targets=("target_count", "sum"),
            n_rounds=("hits", "size"),
        )
        .reset_index()
    )
    grouped["hit_pct"] = grouped["hits"] / grouped["n_targets"]
    return grouped.rename(columns={"station_label": "label"})[columns]


def shooter_station_deltas(frame: pd.DataFrame, shooter_id: int) -> pd.DataFrame:
    """Shrunken delta (h + κ·p_f)/(n + κ) - p_f; p_f = field hit % at s on the days the shooter
    shot s (the shooter included); κ = 2 x median target_count of those field entries."""
    columns = ["label", "station_no", "hits", "n", "n_rounds", "hit_pct", "field_pct", "delta"]
    mine = frame[frame["shooter_id"].eq(shooter_id).fillna(False).astype(bool)]
    rows: list[dict[str, Any]] = []
    for no, label in station_order(mine):
        own = mine[mine["station_label"] == label]
        field = frame[
            (frame["station_label"] == label) & frame["event_date"].isin(set(own["event_date"]))
        ]
        field_pct = float(field["hits"].sum()) / float(field["target_count"].sum())
        kappa = 2.0 * float(field["target_count"].median())
        hits = int(own["hits"].sum())
        n = int(own["target_count"].sum())
        rows.append(
            {
                "label": label,
                "station_no": no,
                "hits": hits,
                "n": n,
                "n_rounds": len(own),
                "hit_pct": hits / n,
                "field_pct": field_pct,
                "delta": (hits + kappa * field_pct) / (n + kappa) - field_pct,
            }
        )
    return pd.DataFrame(rows, columns=columns)


# ---- eras -------------------------------------------------------------------------------------


def _reset_dates(resets: pd.DataFrame) -> dict[str, list[date]]:
    out: dict[str, list[date]] = {}
    for label, day in zip(resets["label"], resets["effective_date"], strict=True):
        out.setdefault(str(label), []).append(day)
    # Two resets on one day are one era boundary: no empty era between them.
    return {label: sorted(set(days)) for label, days in out.items()}


def current_eras(resets: pd.DataFrame, today: date) -> dict[str, tuple[int, date | None]]:
    """label → (current era index, its start) for stations with at least one logged reset."""
    out: dict[str, tuple[int, date | None]] = {}
    for label, days in _reset_dates(resets).items():
        past = [day for day in days if day <= today]
        out[label] = (len(past), past[-1] if past else None)
    return out


def assign_eras(frame: pd.DataFrame, resets: pd.DataFrame, today: date) -> pd.DataFrame:
    by_station = _reset_dates(resets)
    current = current_eras(resets, today)
    eras: list[int] = []
    starts: list[date | None] = []
    currents: list[int] = []
    for label, day in zip(frame["station_label"], frame["event_date"], strict=True):
        past = [reset for reset in by_station.get(str(label), []) if reset <= day]
        eras.append(len(past))
        starts.append(past[-1] if past else None)
        currents.append(current.get(str(label), (0, None))[0])
    return frame.assign(
        era=eras,
        era_start=pd.Series(starts, index=frame.index, dtype=object),
        current_era=currents,
    )


def select_era(frame: pd.DataFrame, era: EraSel) -> pd.DataFrame:
    """`all` keeps every row; `current` keeps each station's current era.

    `current` needs the assign_eras columns."""
    if era == "all":
        return frame
    return frame[frame["era"] == frame["current_era"]]


def era_stats(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key in station_order(frame):
        station = frame[frame["station_label"] == key[1]]
        for era in sorted(station["era"].unique()):
            entries = station[station["era"] == era]
            rows.append(
                {
                    "era": int(era),
                    "era_start": entries["era_start"].iloc[0],
                    **_stat_row(key, entries),
                }
            )
    return pd.DataFrame(rows, columns=["era", "era_start", *STAT_COLUMNS])


# ---- wind x station ---------------------------------------------------------------------------


def station_wind(
    station_hits: pd.DataFrame, event_weather: pd.DataFrame, era: EraSel
) -> pd.DataFrame:
    """Hit % per station x C7 gust band (frames.wind_band); events without weather are excluded;
    `sufficient` = n_events >= 5."""
    frame = select_era(station_hits, era)
    gusts = {
        day: float(gust)
        for day, gust in zip(event_weather["event_date"], event_weather["gust_mph"], strict=True)
        if pd.notna(gust)
    }
    frame = frame[frame["event_date"].isin(set(gusts))]
    rows: list[dict[str, Any]] = []
    for no, label in station_order(frame):
        station = frame[frame["station_label"] == label]
        bands = pd.Series(
            [wind_band(gusts[day]) for day in station["event_date"]], index=station.index
        )
        for band in bands.unique():
            entries = station[bands == band]
            stats = hit_stats(entries)
            rows.append(
                {
                    "label": label,
                    "station_no": no,
                    "band": str(band),
                    "band_order": min(gusts[day] for day in entries["event_date"]),
                    "hit_pct": stats.hit_pct,
                    "ci_low": stats.ci_low,
                    "ci_high": stats.ci_high,
                    "n_targets": stats.n_targets,
                    "n_events": stats.n_events,
                    "sufficient": stats.n_events >= WIND_MIN_EVENTS,
                }
            )
    out = pd.DataFrame(rows, columns=list(WIND_COLUMNS))
    return out.sort_values(["station_no", "label", "band_order"], kind="stable").reset_index(
        drop=True
    )


# ---- compositions used by the routes ----------------------------------------------------------


@dataclass(frozen=True)
class StationsOverview:
    stats: pd.DataFrame
    by_event: pd.DataFrame
    matrix: pd.DataFrame
    leaders: pd.DataFrame
    n_events: int
    current: dict[str, tuple[int, date | None]]


def stations_overview(
    frame: pd.DataFrame,
    resets: pd.DataFrame,
    *,
    era: EraSel,
    round_types: Sequence[RoundType],
    today: date,
    leader_limit: int = 5,
) -> StationsOverview:
    """era="current" keeps each station's current era. A station that has entries in some era but
    none yet in its current one (a reset with no sheet since) stays listed with empty stats."""
    assigned = assign_eras(apply_round_type_filter(frame, round_types), resets, today)
    selected = select_era(assigned, era)
    return StationsOverview(
        stats=station_stats(selected, station_order(assigned)),
        by_event=per_event_station_pct(selected),
        matrix=shooter_station_matrix(selected),
        leaders=station_leaders(selected, limit=leader_limit),
        n_events=int(selected["event_date"].nunique()),
        current=current_eras(resets, today),
    )


@dataclass(frozen=True)
class StationDetail:
    eras: pd.DataFrame
    by_event: pd.DataFrame
    leaders: pd.DataFrame
    wind: pd.DataFrame


def station_detail(
    frame: pd.DataFrame,
    resets: pd.DataFrame,
    weather: pd.DataFrame,
    *,
    label: str,
    round_types: Sequence[RoundType],
    today: date,
    era: EraSel = "current",
    leader_limit: int | None = None,
) -> StationDetail:
    """Eras always cover every setup; leaders and wind follow `era` like the overview. Every leader
    is returned (no limit): the page lists ten, then offers "Show all N"."""
    with_eras = assign_eras(apply_round_type_filter(frame, round_types), resets, today)
    mine = with_eras[with_eras["station_label"] == label]
    return StationDetail(
        eras=era_stats(mine),
        by_event=per_event_station_pct(mine),
        leaders=station_leaders(select_era(mine, era), limit=leader_limit),
        wind=station_wind(mine, weather, era),
    )
