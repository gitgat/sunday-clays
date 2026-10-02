"""Shared fixtures for achievement unit tests (no DB).

CtxBuilder produces frames shaped like frames.load_* output: Plan 06's ROUND_COLUMNS and
EVENT_COLUMNS, event_date as datetime.date. Registry imports are local to the fixtures so context
tests run before registry.py exists.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics.achievements.context import AchContext, station_frame
from sunday_clays.analytics.frames import (
    APPEARANCE_COLUMNS,
    CALENDAR_COLUMNS,
    EVENT_COLUMNS,
    ROUND_COLUMNS,
    appearances_from_rounds,
    calendar_from_events,
)
from sunday_clays.station_label import label_number, parse_label

# Round columns that frames.load_rounds takes from the event's event_weather row.
_WEATHER = (
    "temp_f",
    "apparent_f",
    "precip_in",
    "wind_mph",
    "gust_mph",
    "wind_dir_deg",
    "cloud_pct",
    "condition",
)
_METRICS = (
    "field_median",
    "adjusted",
    "percentile",
    "expected",
    "residual",
    "mu_before",
    "mu_after",
)
_DERIVED = ("ordinal", "is_best_round", "event_rank")


class CtxBuilder:
    """Fluent builder: rounds, events (weather keys ride on events), station entries, ratings."""

    def __init__(self) -> None:
        self._rounds: list[dict[str, Any]] = []
        self._events: dict[date, dict[str, Any]] = {}
        self._stations: list[dict[str, Any]] = []
        self._stations: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []
        self._specials: list[tuple[int, date]] = []
        self._labels: dict[date, str] = {}

    def special(
        self, shooter_id: int, event_date: date, label: str = "Three Clay Shoot"
    ) -> CtxBuilder:
        """A special Sunday shot (Plan 17): an appearance only, never a round or a regular event.
        The Sunday's calendar label is the last one given for that date."""
        self._specials.append((shooter_id, event_date))
        self._labels[event_date] = label
        return self

    def round(self, shooter_id: int, event_date: date, score: int, **cols: Any) -> CtxBuilder:
        self._rounds.append(
            {"shooter_id": shooter_id, "event_date": event_date, "score": score, **cols}
        )
        return self

    def event(self, event_date: date, **cols: Any) -> CtxBuilder:
        self._events.setdefault(event_date, {}).update(cols)
        return self

    def station(
        self,
        shooter_id: int | None,
        event_date: date,
        station_no: int | str,
        hits: int,
        *,
        entry_row: int,
        target_count: int = 7,
        round_id: int | None = None,
    ) -> CtxBuilder:
        self._stations.append(
            {
                "event_date": event_date,
                "station_no": label_number(str(parse_label(station_no))),
                "station_label": parse_label(station_no),
                "target_count": target_count,
                "sheet_id": 1,
                "entry_row": entry_row,
                "shooter_id": shooter_id,
                "round_id": round_id,
                "hits": hits,
            }
        )
        return self

    def rating(self, shooter_id: int, event_date: date, mu: float, var: float = 4.0) -> CtxBuilder:
        self._history.append(
            {"shooter_id": shooter_id, "event_date": event_date, "mu": mu, "var": var}
        )
        return self

    def build(self) -> AchContext:
        events = self._events_frame()
        rounds = self._rounds_frame(events)
        return AchContext.from_frames(
            rounds=rounds,
            events=events,
            station_hits=self._stations_frame(),
            rating_history=pd.DataFrame(
                self._history, columns=["shooter_id", "event_date", "mu", "var"]
            ),
            appearances=self._appearances(rounds),
            calendar=self._calendar(events),
        )

    def _appearances(self, rounds: pd.DataFrame) -> pd.DataFrame:
        regular = appearances_from_rounds(rounds)
        if not self._specials:
            return regular
        special = pd.DataFrame(
            [
                {
                    "shooter_id": sid,
                    "event_date": day,
                    "kind": "special",
                    "round_type": "sporting",
                    "display_name": f"Shooter {sid}",
                    "shooter_status": "member",
                    "name_key": f"shooter {sid}",
                    "held": True,
                }
                for sid, day in self._specials
            ],
            columns=list(APPEARANCE_COLUMNS),
        )
        both = pd.concat([regular, special], ignore_index=True)
        return both.sort_values(["event_date", "shooter_id"], kind="mergesort").reset_index(
            drop=True
        )

    def _calendar(self, events: pd.DataFrame) -> pd.DataFrame:
        calendar = calendar_from_events(events)
        days = sorted({day for _, day in self._specials})
        if not days:
            return calendar
        rows: list[dict[str, Any]] = []
        for day in days:
            row: dict[str, Any] = dict.fromkeys(CALENDAR_COLUMNS, np.nan)
            n = sum(1 for _, d in self._specials if d == day)
            row.update(
                event_date=day,
                round_type="sporting",
                round_type_source="none",
                n_rounds=n,
                n_shooters=n,
                has_scores=True,
                has_stations=False,
                results_complete=True,
                condition=None,
                kind="special",
                label=self._labels[day],
                target_total=60,
            )
            rows.append(row)
        both = pd.concat([calendar, pd.DataFrame(rows, columns=list(CALENDAR_COLUMNS))])
        return both.sort_values("event_date", kind="mergesort").reset_index(drop=True)

    def _events_frame(self) -> pd.DataFrame:
        """Plan 06 EVENT_COLUMNS: event_metrics and event_weather columns start NaN."""
        dates = sorted({r["event_date"] for r in self._rounds} | set(self._events))
        rows: list[dict[str, Any]] = []
        for day in dates:
            same_day = [r for r in self._rounds if r["event_date"] == day]
            row: dict[str, Any] = dict.fromkeys(EVENT_COLUMNS, np.nan)
            row.update(
                {
                    "event_date": day,
                    "round_type": "sporting",
                    "round_type_source": "none",
                    "n_rounds": len(same_day),
                    "n_shooters": len({r["shooter_id"] for r in same_day}),
                    "has_scores": bool(same_day),
                    "has_stations": any(s["event_date"] == day for s in self._stations),
                    "results_complete": bool(same_day),
                    "condition": None,
                }
            )
            row.update(self._events.get(day, {}))
            rows.append(row)
        return pd.DataFrame(rows, columns=list(EVENT_COLUMNS))

    def _rounds_frame(self, events: pd.DataFrame) -> pd.DataFrame:
        """Plan 06 ROUND_COLUMNS: `held` mirrors the event's results_complete; `gauge` derived."""
        by_date = events.set_index("event_date")
        rows: list[dict[str, Any]] = []
        for round_id, given in enumerate(self._rounds, start=1):
            sid, day = given["shooter_id"], given["event_date"]
            row: dict[str, Any] = {
                "round_id": round_id,
                "event_date": day,
                "shooter_id": sid,
                "name_key": f"shooter {sid}",
                "display_name": f"Shooter {sid}",
                "ordinal": np.nan,
                "score": given["score"],
                "gauge_class": None,
                "status": "member",
                "shooter_status": "member",
                "round_type": by_date.at[day, "round_type"],
                "event_rank": np.nan,
                "is_best_round": False,
                "held": bool(by_date.at[day, "results_complete"]),
            }
            row.update(dict.fromkeys(_METRICS, np.nan))
            row.update({key: by_date.at[day, key] for key in _WEATHER})
            row.update({k: v for k, v in given.items() if k not in _DERIVED})
            rows.append(row)
        frame = pd.DataFrame(rows, columns=[c for c in ROUND_COLUMNS if c != "gauge"])
        if frame.empty:
            return frame.assign(gauge=pd.Series(dtype=object))[list(ROUND_COLUMNS)]
        ordered = frame.sort_values(["score", "round_id"], ascending=[False, True])
        frame["ordinal"] = ordered.groupby(["event_date", "shooter_id", "name_key"]).cumcount() + 1
        best = (
            frame.sort_values(["score", "name_key", "ordinal"], ascending=[False, True, True])
            .groupby(["event_date", "shooter_id"])
            .head(1)
            .index
        )
        frame["is_best_round"] = frame.index.isin(best)
        frame["event_rank"] = (
            frame[frame["is_best_round"]]
            .groupby("event_date")["score"]
            .rank(method="min", ascending=False)
        )
        for index, given in zip(frame.index, self._rounds, strict=True):
            for key in _DERIVED:
                if key in given:
                    frame.at[index, key] = given[key]
        frame["gauge"] = frame["gauge_class"].fillna("unspecified")
        return frame[list(ROUND_COLUMNS)]

    def _stations_frame(self) -> pd.DataFrame:
        """Typed exactly as load_station_entries types the SQL rows, empty or not."""
        return station_frame(self._stations)


@pytest.fixture
def ctx_builder() -> type[CtxBuilder]:
    return CtxBuilder


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """An empty registry for toy achievements. Real modules are imported first so that a later
    load_all() never re-imports them into the temporary dict."""
    from sunday_clays.analytics.achievements import registry

    registry.load_all()
    fresh: dict[str, Any] = {}
    monkeypatch.setattr(registry, "_REGISTRY", fresh)
    return fresh


def _award_key(award: Any) -> tuple[Any, ...]:
    """Details keyed as s50 stores them, so details s50 cannot serialize fail here too."""
    from sunday_clays.analytics.steps.s50_achievements import details_json

    return (
        award.shooter_id,
        award.code,
        award.event_date,
        award.round_id,
        details_json(award.details),
    )


def _value_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[["shooter_id", "event_date", "value"]].copy()
    out["shooter_id"] = out["shooter_id"].astype("int64")
    out["event_date"] = pd.to_datetime(out["event_date"])
    out["value"] = out["value"].astype(float)
    return out.sort_values(["shooter_id", "event_date"]).reset_index(drop=True)


@pytest.fixture
def no_leak() -> Callable[[str, AchContext, date], tuple[int, int]]:
    """Asserts that `code` awards (and, if tiered, its value series) up to `cut` are identical when
    computed on the full context or on ctx.until(cut). Returns (#awards <= cut, #awards > cut)."""
    from sunday_clays.analytics.achievements import registry

    def check(code: str, ctx: AchContext, cut: date) -> tuple[int, int]:
        achievement = registry.get(code)
        full = registry.evaluate_one(achievement, ctx)
        before = sorted(_award_key(w) for w in full if w.event_date <= cut)
        sliced = sorted(_award_key(w) for w in registry.evaluate_one(achievement, ctx.until(cut)))
        assert before == sliced
        if achievement.value is not None:
            full_values = _value_frame(achievement.value(ctx))
            cut_values = _value_frame(achievement.value(ctx.until(cut)))
            kept = full_values[full_values["event_date"] <= pd.Timestamp(cut)].reset_index(
                drop=True
            )
            pd.testing.assert_frame_equal(kept, cut_values)
        return len(before), len(full) - len(before)

    return check
