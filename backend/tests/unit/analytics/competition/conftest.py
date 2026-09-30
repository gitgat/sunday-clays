"""Synthetic C7 frames for the Plan 09 competition unit tests (no DB)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
import pytest

from sunday_clays.analytics.leaderboards import LeaderboardFrames, make_leaderboard_frames

ROUND_COLUMNS = [
    "round_id", "event_date", "shooter_id", "name_key", "display_name", "ordinal", "score",
    "gauge_class", "status", "shooter_status", "round_type", "field_median", "adjusted",
    "event_rank", "is_best_round", "percentile", "expected", "residual", "mu_before",
    "mu_after", "temp_f", "apparent_f", "precip_in", "wind_mph", "gust_mph", "wind_dir_deg",
    "cloud_pct", "condition", "gauge", "held",
]  # fmt: skip
EVENT_COLUMNS = [
    "event_date", "round_type", "round_type_source", "head_count", "n_rounds", "n_shooters",
    "has_scores", "has_stations", "results_complete",
]  # fmt: skip
HISTORY_COLUMNS = ["shooter_id", "event_date", "mu", "var"]


@dataclass
class FrameBuilder:
    """Builds C7-shaped rounds/events/history frames.

    Ranks, best rounds, field medians and adjusted scores are derived per event the way
    C7 defines them (best round = highest score then ordinal; min-rank over best rounds;
    median over all rounds; NULL adjusted at non-held events) unless a round overrides them.
    """

    shooters: dict[int, tuple[str, str, str | None]] = field(default_factory=dict)
    round_rows: list[dict[str, Any]] = field(default_factory=list)
    event_rows: dict[date, dict[str, Any]] = field(default_factory=dict)
    history_rows: list[dict[str, Any]] = field(default_factory=list)

    def shooter(self, shooter_id: int, name: str, status: str | None = "member") -> FrameBuilder:
        key = " ".join(name.casefold().replace(",", " ").split())
        self.shooters[shooter_id] = (name, key, status)
        return self

    def event(
        self,
        event_date: date,
        *,
        round_type: str = "sporting",
        has_scores: bool = True,
        held: bool = True,
    ) -> FrameBuilder:
        self.event_rows[event_date] = {
            "event_date": event_date,
            "round_type": round_type,
            "round_type_source": "none" if round_type == "sporting" else "stations",
            "head_count": None,
            "n_rounds": 0,
            "n_shooters": 0,
            "has_scores": has_scores,
            "has_stations": round_type != "sporting",
            "results_complete": has_scores and held,
        }
        return self

    def round(
        self,
        event_date: date,
        shooter_id: int,
        score: int,
        *,
        ordinal: int = 1,
        row_status: str | None = None,
        gauge_class: str | None = None,
        **overrides: Any,
    ) -> FrameBuilder:
        if event_date not in self.event_rows:
            self.event(event_date)
        name, key, status = self.shooters[shooter_id]
        self.round_rows.append(
            {
                "event_date": event_date,
                "shooter_id": shooter_id,
                "name_key": key,
                "display_name": name,
                "ordinal": ordinal,
                "score": score,
                "gauge_class": gauge_class,
                "status": row_status if row_status is not None else status,
                "shooter_status": status,
                "overrides": overrides,
            }
        )
        return self

    def day(self, event_date: date, scores: dict[int, int], **event_kw: Any) -> FrameBuilder:
        self.event(event_date, **event_kw)
        for shooter_id, score in scores.items():
            self.round(event_date, shooter_id, score)
        return self

    def rating(
        self, shooter_id: int, event_date: date, mu: float, var: float = 4.0
    ) -> FrameBuilder:
        self.history_rows.append(
            {"shooter_id": shooter_id, "event_date": event_date, "mu": mu, "var": var}
        )
        return self

    def rounds(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for round_id, raw in enumerate(self.round_rows, start=1):
            row: dict[str, Any] = dict.fromkeys(ROUND_COLUMNS)
            row.update({k: v for k, v in raw.items() if k != "overrides"})
            row["round_id"] = round_id
            event = self.event_rows[raw["event_date"]]
            row["round_type"] = event["round_type"]
            row["held"] = bool(event["results_complete"])
            rows.append(row)
        self._derive_event_fields(rows)
        for row, raw in zip(rows, self.round_rows, strict=True):
            row.update(raw["overrides"])
        frame = pd.DataFrame(rows, columns=ROUND_COLUMNS)
        frame["event_rank"] = frame["event_rank"].astype(float)
        frame["adjusted"] = frame["adjusted"].astype(float)
        frame["gauge"] = frame["gauge_class"].fillna("unspecified")
        return frame

    def _derive_event_fields(self, rows: list[dict[str, Any]]) -> None:
        by_date: dict[date, list[dict[str, Any]]] = {}
        for row in rows:
            by_date.setdefault(row["event_date"], []).append(row)
        for day, day_rows in by_date.items():
            held = bool(self.event_rows[day]["results_complete"])
            median = float(statistics.median(r["score"] for r in day_rows))
            best: dict[int, dict[str, Any]] = {}
            for r in sorted(day_rows, key=lambda r: (-r["score"], r["name_key"], r["ordinal"])):
                best.setdefault(r["shooter_id"], r)
            best_scores = [r["score"] for r in best.values()]
            for r in day_rows:
                is_best = best[r["shooter_id"]] is r
                r["is_best_round"] = is_best
                r["event_rank"] = 1 + sum(s > r["score"] for s in best_scores) if is_best else None
                r["field_median"] = median if held else None
                r["adjusted"] = r["score"] - median if held else None

    def events(self) -> pd.DataFrame:
        return pd.DataFrame(
            [self.event_rows[d] for d in sorted(self.event_rows)], columns=EVENT_COLUMNS
        )

    def history(self) -> pd.DataFrame:
        return pd.DataFrame(self.history_rows, columns=HISTORY_COLUMNS)

    def frames(self) -> LeaderboardFrames:
        return make_leaderboard_frames(self.rounds(), self.events(), self.history())


@pytest.fixture
def fb() -> FrameBuilder:
    return FrameBuilder()


@pytest.fixture(scope="session")
def make_builder() -> type[FrameBuilder]:
    return FrameBuilder
