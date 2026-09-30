"""Conditions trophies (C12, Plan 10 T3): sub-gauge and weather.

Weather comes from the event's 10:00-12:00 event_weather aggregate (C7) via frames.load_rounds;
an event without it earns nothing."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext
from sunday_clays.analytics.achievements.registry import Achievement, Award, Category, register

# SxS is an action, not a gauge.
SUB_GAUGES = frozenset({"Sub-Gauge", "20 Gauge", "28 Gauge", ".410"})
RAIN_IN = 0.02
COLD_BELOW_F = 35.0
HEAT_AT_F = 85.0
WIND_GUST_MPH = 20.0
MUDDER_SCORE = 40
_MEASURE = {"rain": "precip_in", "cold": "temp_f", "heat": "temp_f", "wind": "gust_mph"}


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _masks(rounds: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "rain": _num(rounds["precip_in"]) >= RAIN_IN,
        "cold": _num(rounds["temp_f"]) < COLD_BELOW_F,
        "heat": _num(rounds["temp_f"]) >= HEAT_AT_F,
        "wind": _num(rounds["gust_mph"]) >= WIND_GUST_MPH,
    }


def _first_rounds(rounds: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """Each shooter's first qualifying round: earliest date, then highest score, then ordinal."""
    hits = rounds[mask].sort_values(
        ["shooter_id", "event_ts", "score", "ordinal"],
        ascending=[True, True, False, True],
        kind="stable",
    )
    return hits.groupby("shooter_id", sort=True).head(1)


def _weather(code: str) -> Callable[[AchContext], Iterator[Award]]:
    measure = _MEASURE[code]

    def evaluate(ctx: AchContext) -> Iterator[Award]:
        first = _first_rounds(ctx.rounds, _masks(ctx.rounds)[code])
        for sid, ts, rid, value in zip(
            first["shooter_id"], first["event_ts"], first["round_id"], first[measure], strict=True
        ):
            yield Award(int(sid), code, ts.date(), int(rid), {measure: round(float(value), 2)})

    return evaluate


def _all_weather(ctx: AchContext) -> Iterator[Award]:
    masks = _masks(ctx.rounds)
    earned: dict[int, list[date]] = {}
    for code in ("rain", "cold", "heat", "wind"):
        first = _first_rounds(ctx.rounds, masks[code])
        for sid, ts in zip(first["shooter_id"], first["event_ts"], strict=True):
            earned.setdefault(int(sid), []).append(ts.date())
    for sid, days in sorted(earned.items()):
        if len(days) == 4:
            yield Award(sid, "all_weather", max(days), None, {})


def _mudder(ctx: AchContext) -> Iterator[Award]:
    rounds = ctx.rounds
    first = _first_rounds(
        rounds, (rounds["score"] >= MUDDER_SCORE) & (_num(rounds["precip_in"]) >= RAIN_IN)
    )
    for sid, ts, rid, score, precip in zip(
        first["shooter_id"],
        first["event_ts"],
        first["round_id"],
        first["score"],
        first["precip_in"],
        strict=True,
    ):
        yield Award(
            int(sid),
            "mudder",
            ts.date(),
            int(rid),
            {"score": int(score), "precip_in": round(float(precip), 2)},
        )


def _sub_gauge(ctx: AchContext) -> Iterator[Award]:
    rounds = ctx.rounds
    first = _first_rounds(rounds, rounds["gauge_class"].isin(SUB_GAUGES))
    for sid, ts, rid, gauge in zip(
        first["shooter_id"], first["event_ts"], first["round_id"], first["gauge_class"], strict=True
    ):
        yield Award(int(sid), "sub_gauge", ts.date(), int(rid), {"gauge_class": str(gauge)})


register(
    Achievement(
        code="sub_gauge",
        name="Sub-Gauge",
        description="Shot a round with a 20, 28 or .410 gauge.",
        category=Category.CONDITIONS,
        art_key="sub_gauge",
        evaluate=_sub_gauge,
    )
)
register(
    Achievement(
        code="rain",
        name="Rain Shooter",
        description="Shot on a day with 0.02 in or more of rain between 10:00 and 12:00.",
        category=Category.CONDITIONS,
        art_key="rain",
        evaluate=_weather("rain"),
    )
)
register(
    Achievement(
        code="cold",
        name="Cold Shooter",
        description="Shot on a day colder than 35 °F.",
        category=Category.CONDITIONS,
        art_key="cold",
        evaluate=_weather("cold"),
    )
)
register(
    Achievement(
        code="heat",
        name="Heat Shooter",
        description="Shot on a day at 85 °F or hotter.",
        category=Category.CONDITIONS,
        art_key="heat",
        evaluate=_weather("heat"),
    )
)
register(
    Achievement(
        code="wind",
        name="Wind Shooter",
        description="Shot on a day with gusts of 20 mph or more.",
        category=Category.CONDITIONS,
        art_key="wind",
        evaluate=_weather("wind"),
    )
)
register(
    Achievement(
        code="all_weather",
        name="All-Weather",
        description="Earned Rain, Cold, Heat and Wind Shooter.",
        category=Category.CONDITIONS,
        art_key="all_weather",
        evaluate=_all_weather,
    )
)
register(
    Achievement(
        code="mudder",
        name="Mudder",
        description="Broke 40 or more in the rain.",
        category=Category.CONDITIONS,
        art_key="mudder",
        evaluate=_mudder,
    )
)
