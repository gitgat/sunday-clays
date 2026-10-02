"""Synthetic worlds for insight unit tests (no DB).

`make_world()` builds frames shaped exactly like `frames.load_*` output. Field metrics (field
median, vs-the-field, best round, rank) come from the real `metrics.compute_round_metrics`, so a
test states scores and the numbers a kind quotes are derived the same way as in production.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics import frames
from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights.context import AWARD_COLUMNS, InsightFrames
from sunday_clays.analytics.insights.registry import Kind
from sunday_clays.analytics.insights.templates import Int, Shooter, T, named, plain, render
from sunday_clays.analytics.insights.types import (
    ChartLink,
    Fact,
    Family,
    HomeSlot,
    P,
    Polarity,
    Scope,
    SubjectType,
    Window,
    cell,
)
from sunday_clays.analytics.metrics import compute_event_metrics, compute_round_metrics
from sunday_clays.station_label import label_number, parse_label

FIRST_SUNDAY = date(2024, 1, 7)
FILLER = 9000  # filler shooter ids start here


def sunday(i: int) -> date:
    """The i-th weekly Sunday from 2024-01-07."""
    return FIRST_SUNDAY + timedelta(weeks=i)


class World:
    """Fluent builder of an InsightFrames bundle."""

    def __init__(self) -> None:
        self._rounds: list[dict[str, Any]] = []
        self._events: dict[date, dict[str, Any]] = {}
        self._shooters: dict[int, dict[str, Any]] = {}
        self._ratings: list[dict[str, Any]] = []
        self._awards: list[dict[str, Any]] = []
        self._stations: list[dict[str, Any]] = []
        self._filler = FILLER
        self._specials: list[tuple[int, date]] = []
        self._special_heads: dict[date, int] = {}

    def shooter(
        self, sid: int, name: str | None = None, *, status: str = "member", censored: bool = False
    ) -> World:
        self._shooters[sid] = {
            "display_name": name or f"Shooter{sid}, Pat",
            "status": status,
            "left_censored": censored,
        }
        return self

    def sunday(self, day: date, **cols: Any) -> World:
        """Event columns: held (default True), head_count, difficulty, precip_in, temp_f..."""
        self._events.setdefault(day, {}).update(cols)
        return self

    def round(self, sid: int, day: date, score: int, **cols: Any) -> World:
        """A round; optional residual, expected, mu_before, mu_after."""
        self._rounds.append({"shooter_id": sid, "event_date": day, "score": score, **cols})
        self._events.setdefault(day, {})
        self._shooters.setdefault(sid, {})
        return self

    def series(
        self, sid: int, start: int, scores: Sequence[int], *, residuals: Sequence[float] = ()
    ) -> World:
        """Rounds on sunday(start), sunday(start + 1), ...; residuals line up with scores."""
        for j, score in enumerate(scores):
            extra = {"residual": residuals[j]} if j < len(residuals) else {}
            self.round(sid, sunday(start + j), score, **extra)
        return self

    def crowd(self, day: date, scores: Iterable[int]) -> World:
        """Filler shooters (ids from 9000) with these scores on `day`."""
        for score in scores:
            self._filler += 1
            self.round(self._filler, day, score)
        return self

    def rating(self, sid: int, day: date, mu: float) -> World:
        self._ratings.append({"shooter_id": sid, "event_date": day, "mu": mu, "var": 4.0})
        return self

    def award(self, sid: int, code: str, day: date) -> World:
        self._awards.append({"shooter_id": sid, "code": code, "event_date": day})
        return self

    def special(self, sid: int, day: date, *, heads: int | None = None) -> World:
        """A special Sunday shot (Plan 17): an appearance only, never a round. `heads` is the
        Sunday's head count (default: none, as when the weekly workbook has no row for it)."""
        self._specials.append((sid, day))
        self._shooters.setdefault(sid, {})
        if heads is not None:
            self._special_heads[day] = heads
        return self

    def station(
        self, sid: int | None, day: date, station_no: int | str, hits: int, **cols: Any
    ) -> World:
        self._stations.append(
            {
                "event_date": day,
                "station_no": label_number(str(parse_label(station_no))),
                "station_label": parse_label(station_no),
                "target_count": cols.get("target_count", 8),
                "sheet_id": 1,
                "entry_row": cols.get("entry_row", 1),
                "name_key": f"s{sid}",
                "shooter_id": sid,
                "round_id": cols.get("round_id"),
                "hits": hits,
                "round_type": "sporting",
            }
        )
        self._events.setdefault(day, {})
        return self

    # --- frames ---------------------------------------------------------------------------

    def _event_frame(self) -> pd.DataFrame:
        rows = []
        for day in sorted(self._events):
            cols = self._events[day]
            n = [r for r in self._rounds if r["event_date"] == day]
            row: dict[str, Any] = dict.fromkeys(frames.EVENT_COLUMNS, np.nan)
            row.update(
                event_date=day,
                round_type="sporting",
                round_type_source="none",
                n_rounds=len(n),
                n_shooters=len({r["shooter_id"] for r in n}),
                has_scores=bool(n),
                has_stations=any(s["event_date"] == day for s in self._stations),
                results_complete=bool(n) and cols.get("held", True),
                condition=None,
            )
            row.update({k: v for k, v in cols.items() if k != "held"})
            rows.append(row)
        return pd.DataFrame(rows, columns=list(frames.EVENT_COLUMNS))

    def _round_frame(self, events: pd.DataFrame) -> pd.DataFrame:
        held = dict(zip(events["event_date"], events["results_complete"], strict=True))
        base = pd.DataFrame(
            [
                {
                    "round_id": i + 1,
                    "event_date": r["event_date"],
                    "shooter_id": r["shooter_id"],
                    "name_key": f"s{r['shooter_id']}",
                    "score": r["score"],
                    "held": bool(held[r["event_date"]]),
                }
                for i, r in enumerate(self._rounds)
            ],
            columns=["round_id", "event_date", "shooter_id", "name_key", "score", "held"],
        )
        base["ordinal"] = (
            base.sort_values(["score", "round_id"], ascending=[False, True])
            .groupby(["event_date", "shooter_id"])
            .cumcount()
            + 1
        )
        metrics = compute_round_metrics(base) if len(base) else None
        out = base.copy()
        for column in frames.ROUND_COLUMNS:
            if column not in out.columns:
                out[column] = np.nan
        if metrics is not None:
            for column in ("field_median", "adjusted", "event_rank", "is_best_round", "percentile"):
                out[column] = metrics[column].to_numpy()
        out["is_best_round"] = out["is_best_round"].eq(True)
        for i, r in enumerate(self._rounds):
            for key in ("residual", "expected", "mu_before", "mu_after"):
                if key in r:
                    out.loc[i, key] = r[key]
        names = self._names()
        out["display_name"] = out["shooter_id"].map(names)
        out["status"] = "member"
        out["shooter_status"] = out["shooter_id"].map(
            lambda s: self._shooters.get(s, {}).get("status", "member")
        )
        out["round_type"] = "sporting"
        out["gauge_class"] = None
        out["gauge"] = frames.UNSPECIFIED_GAUGE
        weather = events.set_index("event_date")
        for column in ("temp_f", "precip_in", "gust_mph", "wind_mph", "condition"):
            out[column] = out["event_date"].map(weather[column])
        return out[list(frames.ROUND_COLUMNS)]

    def _names(self) -> dict[int, str]:
        return {
            sid: cols.get("display_name", f"Shooter{sid}, Pat")
            for sid, cols in self._shooters.items()
        }

    def _shooter_frame(self, rounds: pd.DataFrame) -> pd.DataFrame:
        rows = []
        names = self._names()
        for sid, cols in sorted(self._shooters.items()):
            own = rounds.loc[rounds["shooter_id"] == sid]
            rows.append(
                {
                    "shooter_id": sid,
                    "display_name": names[sid],
                    "status": cols.get("status", "member"),
                    "first_event": min(own["event_date"]) if len(own) else None,
                    "last_event": max(own["event_date"]) if len(own) else None,
                    "n_rounds": len(own),
                    "n_events": own["event_date"].nunique(),
                    "left_censored": cols.get("left_censored", False),
                }
            )
        return pd.DataFrame(rows, columns=list(frames.SHOOTER_COLUMNS))

    def frames(self) -> InsightFrames:
        events = self._event_frame()
        rounds = self._round_frame(events)
        if len(rounds):
            em = compute_event_metrics(rounds[rounds["held"]])
            events = events.drop(columns=["n", "median", "mean", "stdev", "top_score"]).merge(
                em.drop(columns=["difficulty"]), on="event_date", how="left"
            )[list(frames.EVENT_COLUMNS)]
        appearances = frames.appearances_from_rounds(rounds)
        calendar = frames.calendar_from_events(events)
        if self._specials:
            names = self._names()
            extra = pd.DataFrame(
                [
                    {
                        "shooter_id": sid,
                        "event_date": day,
                        "kind": "special",
                        "round_type": "sporting",
                        "display_name": names[sid],
                        "shooter_status": "member",
                        "name_key": f"s{sid}",
                        "held": True,
                    }
                    for sid, day in self._specials
                ],
                columns=list(frames.APPEARANCE_COLUMNS),
            )
            appearances = (
                pd.concat([appearances, extra], ignore_index=True)
                .sort_values(["event_date", "shooter_id"], kind="mergesort")
                .reset_index(drop=True)
            )
            special_days = pd.DataFrame(
                [
                    {
                        **dict.fromkeys(frames.CALENDAR_COLUMNS, np.nan),
                        "event_date": day,
                        "head_count": self._special_heads.get(day, np.nan),
                        "round_type": "sporting",
                        "round_type_source": "none",
                        "n_rounds": n,
                        "n_shooters": n,
                        "has_scores": True,
                        "has_stations": False,
                        "results_complete": True,
                        "condition": None,
                        "kind": "special",
                        "label": "Three Clay Shoot",
                        "target_total": 60,
                    }
                    for day, n in sorted(Counter(day for _, day in self._specials).items())
                ],
                columns=list(frames.CALENDAR_COLUMNS),
            )
            calendar = (
                pd.concat([calendar, special_days], ignore_index=True)
                .sort_values("event_date", kind="mergesort")
                .reset_index(drop=True)
            )
        return InsightFrames.from_frames(
            rounds=rounds,
            events=events,
            shooters=self._shooter_frame(rounds),
            rating=pd.DataFrame(self._ratings, columns=list(frames.RATING_COLUMNS)),
            stations=pd.DataFrame(self._stations, columns=list(frames.STATION_HIT_COLUMNS)),
            awards=pd.DataFrame(self._awards, columns=list(AWARD_COLUMNS)),
            appearances=appearances,
            calendar=calendar,
        )


@pytest.fixture
def make_world() -> type[World]:
    return World


@pytest.fixture
def sun() -> Callable[[int], date]:
    return sunday


def evaluate(kind_id: str, fr: InsightFrames, sundays: Iterable[date] | None = None) -> list[Fact]:
    """Facts of one kind, every held Sunday in scope (or just `sundays`), as_of = latest."""
    kind = registry.get(kind_id)
    assert fr.as_of is not None
    days = frozenset(sundays) if sundays is not None else frozenset(fr.held_dates())
    return sorted(
        kind.evaluate(fr, Scope(sundays=days, as_of=fr.as_of)),
        key=lambda f: (f.anchor_date or date.min, f.subject_id, f.variant),
    )


@pytest.fixture
def run() -> Callable[..., list[Fact]]:
    return evaluate


def text_of(kind_id: str, fact: Fact, fr: InsightFrames, *, you: bool = False) -> str:
    """The headline of `fact` in the first phrasing (third person or the "you" twin)."""
    kind = registry.get(kind_id)
    template = kind.templates[fact.variant][0]
    return plain(render(template, fact.params, fr.names, you=you))


@pytest.fixture
def headline() -> Callable[..., str]:
    return text_of


@pytest.fixture
def good() -> Callable[..., Kind]:
    """Factory of a well-formed shooter Kind; keyword changes override its fields."""
    label = T(named("A chart"))
    you_label = T(named(Shooter("s"), "'s scores"), you=named("Your scores"))

    def chart(fact: Fact) -> ChartLink:
        return ChartLink(
            type="page", label=label, window=Window(date(2026, 1, 4), date(2026, 1, 4))
        )

    def build(**changes: Any) -> Kind:
        base: dict[str, Any] = {
            "id": "pf.test-kind",
            "family": Family.FORM,
            "home_slot": HomeSlot.PERSON,
            "subject": SubjectType.SHOOTER,
            "pages": frozenset({P.PROFILE}),
            "polarity": Polarity.POSITIVE,
            "care": 3,
            "anchored": False,
            "guard": {"min": 1},
            "params": frozenset({"s", "n"}),
            "templates": {
                "": (
                    T(
                        named(Shooter("s"), " shot ", Int("n"), "."),
                        you=named("You shot ", Int("n"), "."),
                    ),
                )
            },
            "how": {"": (T(named("Counted."), you=named("Your rounds, counted.")),)},
            "labels": (label, you_label),
            "chart": chart,
            "proof": (cell("n"),),
            "evaluate": lambda fr, scope: iter(()),
        }
        base.update(changes)
        return Kind(**base)

    return build
