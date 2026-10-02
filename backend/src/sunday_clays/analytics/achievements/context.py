"""AchContext (C12): the frames achievement definitions read, sliceable by date and by shooter."""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Final

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.streaks import held_event_dates, streaks

STATION_COLUMNS: tuple[str, ...] = (
    "event_date",
    "station_no",
    "station_label",
    "target_count",
    "sheet_id",
    "entry_row",
    "shooter_id",
    "round_id",
    "hits",
)
_STATION_INTS: tuple[str, ...] = ("station_no", "target_count", "sheet_id", "entry_row", "hits")
_STATION_NULLABLE_INTS: tuple[str, ...] = ("shooter_id", "round_id")

# pandas 3 infers datetime64[s] from `datetime.date` objects; event_ts is pinned to ns so every
# frame, day series and (empty) value frame shares one datetime unit.
_TS_DTYPE: Final = "datetime64[ns]"

_DAY_DTYPES: dict[str, str] = {
    "shooter_id": "int64",
    "event_ts": _TS_DTYPE,
    "event_date": "object",
    "n_rounds": "int64",
    "day_best": "int64",
    "day_sum": "int64",
    "best_round_id": "int64",
    "n_events": "int64",
    "cum_rounds": "int64",
    "cum_sum": "int64",
    "prior_rounds": "int64",
    "prior_sum": "int64",
    "prior_best": "float64",
    "prev_ts": _TS_DTYPE,
    "prev_day_best": "float64",
}
_VALUE_DTYPES: dict[str, str] = {
    "shooter_id": "int64",
    "event_date": _TS_DTYPE,
    "value": "float64",
}

_STATION_SQL = text(
    """
    SELECT h.event_date, h.station_no, h.station_label, l.target_count, h.sheet_id, h.entry_row,
           h.shooter_id, h.round_id, h.hits
    FROM station_hits h
    JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
    JOIN events e ON e.event_date = h.event_date
    WHERE e.kind = 'regular'
    ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
    """
)


def _empty(dtypes: Mapping[str, str]) -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in dtypes.items()})


def empty_value_frame() -> pd.DataFrame:
    """The empty long frame [shooter_id, event_date, value] a tiered value function returns."""
    return _empty(_VALUE_DTYPES)


def _with_ts(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["event_ts"] = pd.to_datetime(out["event_date"]).astype(_TS_DTYPE)
    return out


def _cut(frame: pd.DataFrame, as_of: date) -> pd.DataFrame:
    return frame[frame["event_ts"] <= pd.Timestamp(as_of)]


def _shooter_days(rounds: pd.DataFrame) -> pd.DataFrame:
    if rounds.empty:
        return _empty(_DAY_DTYPES)
    ordered = rounds.sort_values(
        ["shooter_id", "event_ts", "score", "name_key", "ordinal"],
        ascending=[True, True, False, True, True],
        kind="stable",
    )
    days = (
        ordered.groupby(["shooter_id", "event_ts"], sort=True)
        .agg(
            n_rounds=("score", "size"),
            day_best=("score", "max"),
            day_sum=("score", "sum"),
            best_round_id=("round_id", "first"),
        )
        .reset_index()
    )
    days["event_date"] = days["event_ts"].dt.date
    by_shooter = days.groupby("shooter_id", sort=False)
    days["n_events"] = by_shooter.cumcount() + 1
    days["cum_rounds"] = by_shooter["n_rounds"].cumsum()
    days["cum_sum"] = by_shooter["day_sum"].cumsum()
    days["prior_rounds"] = days["cum_rounds"] - days["n_rounds"]
    days["prior_sum"] = days["cum_sum"] - days["day_sum"]
    days["prior_best"] = by_shooter["day_best"].transform(lambda s: s.cummax().shift(1))
    days["prev_ts"] = by_shooter["event_ts"].shift(1)
    days["prev_day_best"] = by_shooter["day_best"].shift(1).astype(float)
    return days[list(_DAY_DTYPES)]


@dataclass(frozen=True, eq=False)
class AchContext:
    """Frames as frames.load_* return them, each with an extra `event_ts` (datetime64) column."""

    rounds: pd.DataFrame
    events: pd.DataFrame
    station_hits: pd.DataFrame
    rating_history: pd.DataFrame
    as_of: date | None = None
    _memo: dict[Any, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_frames(
        cls,
        *,
        rounds: pd.DataFrame,
        events: pd.DataFrame,
        station_hits: pd.DataFrame,
        rating_history: pd.DataFrame,
        as_of: date | None = None,
    ) -> AchContext:
        return cls(
            rounds=_with_ts(rounds),
            events=_with_ts(events),
            station_hits=_with_ts(station_hits),
            rating_history=_with_ts(rating_history),
            as_of=as_of,
        )

    def until(self, as_of: date | None) -> AchContext:
        """Only data dated <= as_of (None → this context unchanged)."""
        if as_of is None:
            return self
        return AchContext(
            rounds=_cut(self.rounds, as_of),
            events=_cut(self.events, as_of),
            station_hits=_cut(self.station_hits, as_of),
            rating_history=_cut(self.rating_history, as_of),
            as_of=as_of,
        )

    def for_shooter(self, shooter_id: int) -> AchContext:
        """One shooter's rows; events stay whole (held events are club-wide)."""
        linked = self.station_hits["shooter_id"].eq(shooter_id).fillna(False).astype(bool)
        return AchContext(
            rounds=self.rounds[self.rounds["shooter_id"] == shooter_id],
            events=self.events,
            station_hits=self.station_hits[linked],
            rating_history=self.rating_history[self.rating_history["shooter_id"] == shooter_id],
            as_of=self.as_of,
        )

    @property
    def shooter_days(self) -> pd.DataFrame:
        cached: pd.DataFrame | None = self._memo.get("shooter_days")
        if cached is None:
            cached = _shooter_days(self.rounds)
            self._memo["shooter_days"] = cached
        return cached

    def held_dates(self) -> list[date]:
        return sorted(held_event_dates(self.events, self.as_of))

    def streaks_at(self, day: date) -> pd.DataFrame:
        key = ("streaks", day)
        if key not in self._memo:
            self._memo[key] = streaks(self.rounds, self.events, day)
        result: pd.DataFrame = self._memo[key]
        return result


def station_frame(rows: Iterable[Mapping[Any, Any]]) -> pd.DataFrame:
    """STATION_COLUMNS rows as a frame: int64 counts and ids, nullable Int64 shooter/round ids.

    Dtypes match Plan 06's frames.load_station_hits for the shared columns, empty or not.
    """
    frame = pd.DataFrame([dict(r) for r in rows], columns=list(STATION_COLUMNS))
    for column in _STATION_INTS:
        frame[column] = frame[column].astype("int64")
    for column in _STATION_NULLABLE_INTS:
        frame[column] = frame[column].astype("Int64")
    frame["station_label"] = frame["station_label"].astype(str)
    return frame


def load_station_entries(session: Session) -> pd.DataFrame:
    """station_hits joined to its layout's target_count, typed by station_frame."""
    return station_frame(session.execute(_STATION_SQL).mappings())


def build_context(session: Session) -> AchContext:
    """Fresh frames for s50. Loaders are unwrapped so a @cached_by_data_version memo can never
    return frames from before s10/s30 wrote this pipeline run's metrics (data_version is bumped
    only after the last step)."""
    return AchContext.from_frames(
        rounds=inspect.unwrap(frames.load_rounds)(session),
        events=inspect.unwrap(frames.load_events)(session),
        station_hits=load_station_entries(session),
        rating_history=inspect.unwrap(frames.load_rating_history)(session),
    )


@cached_by_data_version
def cached_context(session: Session) -> AchContext:
    """The context the read routes use; rebuilt once per data_version."""
    return build_context(session)
