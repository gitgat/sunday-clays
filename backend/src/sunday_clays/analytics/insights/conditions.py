"""Conditions kinds (spec §2.2.4): how a shooter does in the rain, cold or on tough days.

At most one of these shows on a profile (select.PROFILE_CONDITIONS). Each compares the shooter
with the field on their own rounds only, and a shuffle test keeps chance gaps out.
"""

from __future__ import annotations

import random
from collections.abc import Iterator, Sequence
from datetime import date

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    Day,
    InsightFrames,
    evergreen_days,
    held_only,
    mean,
    shuffle_share,
    split_by_rain,
    stable_seed,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import Shooter, Signed, T, Word, named
from sunday_clays.analytics.insights.types import (
    ChartLink,
    Fact,
    Family,
    Highlight,
    HomeSlot,
    P,
    Polarity,
    Scope,
    SubjectType,
    Window,
    cell,
    mean_of,
    p_date,
    p_int,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric

WET_MIN, DRY_MIN = 6, 12
WET_GAP = 1.5
WET_SHUFFLE = 0.90
STEADY_GAP = 0.75


RAIN_LABEL = T(
    named(Shooter("s"), " vs the field's middle score, wet and dry Sundays"),
    you=named("You vs the field's middle score, wet and dry Sundays"),
)


def rain_chart(fact: Fact, hl: Highlight) -> ChartLink:
    sid = p_int(fact.params, "s")
    window = Window(p_date(fact.params, "first"), p_date(fact.params, "day"))
    query = charts.spec(
        Metric.ADJUSTED, Agg.AVG, Dim.PRECIP_BAND, window=window, shooters=(sid,), best=True
    )
    return charts.explorer(query, label=RAIN_LABEL, hl=hl, ref=0)


def _rain_params(
    sid: int, days: Sequence[Day], wet: list[float], dry: list[float]
) -> dict[str, object]:
    return {
        "s": sid,
        "wet": round(mean(wet), 1),
        "dry": round(mean(dry), 1),
        "n_wet": len(wet),
        "n_dry": len(dry),
        "wet_key": "wet",
        "dry_key": "dry",
        "first": days[0].date,
        "day": days[-1].date,
    }


# --- pf.wet-strength -----------------------------------------------------------------------------


def _wet_strength(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        wet, dry = split_by_rain(days)
        if len(wet) < WET_MIN or len(dry) < DRY_MIN:
            continue
        gap = mean(wet) - mean(dry)
        if gap < WET_GAP or mean(wet) < 0:
            continue
        if shuffle_share(wet, dry, seed=stable_seed("pf.wet-strength", sid)) < WET_SHUFFLE:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params=_rain_params(sid, days, wet, dry),
            strength=gap / WET_GAP,
            named_shooter_ids=(sid,),
        )


_RAIN_HOW_SPLIT = T(
    named(
        "Each Sunday: the best round minus the middle score of everyone who shot. Wet = 0.02 "
        "in of rain or more between 10:00 and 12:00."
    ),
    you=named(
        "Each Sunday: your best round minus the middle score of everyone who shot. Wet = "
        "0.02 in of rain or more between 10:00 and 12:00."
    ),
)

register(
    Kind(
        id="pf.wet-strength",
        family=Family.WEATHER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=False,
        guard={"wet": WET_MIN, "dry": DRY_MIN, "gap": WET_GAP, "shuffle": WET_SHUFFLE},
        params=frozenset(
            {"s", "wet", "dry", "n_wet", "n_dry", "wet_key", "dry_key", "first", "day"}
        ),
        templates={
            "": (
                T(
                    named(
                        "Rain suits ",
                        Shooter("s"),
                        ": ",
                        Signed("wet"),
                        " against the field's middle score on wet Sundays, ",
                        Signed("dry"),
                        " on dry.",
                    ),
                    you=named(
                        "Rain suits you: ",
                        Signed("wet"),
                        " against the field's middle score on wet Sundays, ",
                        Signed("dry"),
                        " on dry.",
                    ),
                ),
            )
        },
        how={
            "": (
                _RAIN_HOW_SPLIT,
                T(
                    named(
                        "Needs 6 wet and 12 dry Sundays, a gap of 1.5 or more, and a gap "
                        "bigger than 90% of 1,000 random reshuffles of wet and dry."
                    ),
                    you=named(
                        "Needs 6 wet and 12 dry Sundays of yours, a gap of 1.5 or more, "
                        "and a gap bigger than 90% of 1,000 random reshuffles."
                    ),
                ),
            )
        },
        labels=(RAIN_LABEL,),
        chart=lambda fact: rain_chart(fact, Highlight(keys=("wet",))),
        proof=(cell("wet", key="wet_key"), cell("dry", key="dry_key")),
        evaluate=_wet_strength,
    )
)


# --- pf.weather-steady ---------------------------------------------------------------------------


def _weather_steady(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        wet, dry = split_by_rain(days)
        if len(wet) < WET_MIN or len(dry) < DRY_MIN:
            continue
        gap = abs(mean(wet) - mean(dry))
        if gap > STEADY_GAP or min(mean(wet), mean(dry)) < 0:
            continue  # never quote a below-the-field number about a named shooter (D1)
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params=_rain_params(sid, days, wet, dry),
            strength=min(2.0, STEADY_GAP / max(gap, 0.25)),
            named_shooter_ids=(sid,),
        )


register(
    Kind(
        id="pf.weather-steady",
        family=Family.WEATHER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.NEUTRAL,
        care=2,
        anchored=False,
        guard={"wet": WET_MIN, "dry": DRY_MIN, "max_gap": STEADY_GAP},
        params=frozenset(
            {"s", "wet", "dry", "n_wet", "n_dry", "wet_key", "dry_key", "first", "day"}
        ),
        templates={
            "": (
                T(
                    named(
                        "Rain doesn't change ",
                        Shooter("s"),
                        "'s game: ",
                        Signed("wet"),
                        " against the field's middle score on wet Sundays, ",
                        Signed("dry"),
                        " on dry.",
                    ),
                    you=named(
                        "Rain doesn't change your game: ",
                        Signed("wet"),
                        " against the field's middle score on wet Sundays, ",
                        Signed("dry"),
                        " on dry.",
                    ),
                ),
            )
        },
        how={
            "": (
                _RAIN_HOW_SPLIT,
                T(
                    named(
                        "Shown when wet and dry are within 0.75 of each other and both at or "
                        "over the field, with 6 wet and 12 dry Sundays."
                    ),
                    you=named(
                        "Shown when your wet and dry are within 0.75 of each other and both "
                        "at or over the field, with 6 wet and 12 dry Sundays."
                    ),
                ),
            )
        },
        labels=(RAIN_LABEL,),
        chart=lambda fact: rain_chart(fact, Highlight()),
        proof=(cell("wet", key="wet_key"), cell("dry", key="dry_key")),
        evaluate=_weather_steady,
    )
)


# --- pf.best-temp --------------------------------------------------------------------------------

TEMP_GAP = 2.0
TEMP_MIN = 6
TEMP_SHUFFLE = 0.95
TEMP_LEAD = (
    ("<40", "Cold suits "),
    ("40-55", "Cool mornings suit "),
    ("55-70", "Mild mornings suit "),
    ("70-85", "Warm mornings suit "),
    ("85+", "Heat suits "),
)
TEMP_LEAD_YOU = (
    ("<40", "Cold suits you"),
    ("40-55", "Cool mornings suit you"),
    ("55-70", "Mild mornings suit you"),
    ("70-85", "Warm mornings suit you"),
    ("85+", "Heat suits you"),
)
TEMP_WHEN = (
    ("<40", "under 40°F"),
    ("40-55", "from 40 to 55°F"),
    ("55-70", "from 55 to 70°F"),
    ("70-85", "from 70 to 85°F"),
    ("85+", "at 85°F and up"),
)


def band_gaps(groups: dict[str, list[float]], min_n: int) -> dict[str, float]:
    """Each band with >= min_n values: its mean minus the mean of every other value."""
    out: dict[str, float] = {}
    for band, values in groups.items():
        rest = [v for other, vs in groups.items() if other != band for v in vs]
        if len(values) >= min_n and rest:
            out[band] = mean(values) - mean(rest)
    return out


def shuffle_max_share(
    groups: dict[str, list[float]], real: float, *, min_n: int, seed: int, n: int = 1000
) -> float:
    """Share of `n` shuffles of the band labels whose biggest band gap the real gap beats: the
    search over five bands is part of the test, so a lucky band does not pass."""
    # The labels run band by band, so each shuffled band is a contiguous slice of `values` and its
    # "everyone else" is the rest of the list in order (the sums add in the same order as before).
    values = [v for vs in groups.values() for v in vs]
    total = len(values)
    spans: list[tuple[int, int]] = []
    start = 0
    for vs in groups.values():
        end = start + len(vs)
        if len(vs) >= min_n and total > len(vs):
            spans.append((start, end))
        start = end
    rng = random.Random(seed)  # noqa: S311 - a reproducible shuffle, not a secret
    beaten = 0
    for _ in range(n):
        rng.shuffle(values)
        if not spans or real > max(
            sum(values[a:b]) / (b - a) - sum(values[:a] + values[b:]) / (total - b + a)
            for a, b in spans
        ):
            beaten += 1
    return beaten / n


def _best_temp(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        groups: dict[str, list[float]] = {}
        for d in held_only(days):
            if d.adjusted is not None and d.temp_band is not None:
                groups.setdefault(d.temp_band, []).append(float(d.adjusted))
        gaps = band_gaps(groups, TEMP_MIN)
        if not gaps:
            continue
        band = max(gaps, key=lambda b: (gaps[b], b))
        gap = gaps[band]
        if gap < TEMP_GAP or round(mean(groups[band]), 1) <= 0:
            continue
        seed = stable_seed("pf.best-temp", sid)
        if shuffle_max_share(groups, gap, min_n=TEMP_MIN, seed=seed) < TEMP_SHUFFLE:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={
                "s": sid,
                "band": band,
                "avg": round(mean(groups[band]), 1),
                "first": days[0].date,
                "day": days[-1].date,
            },
            strength=gap / TEMP_GAP,
            named_shooter_ids=(sid,),
        )


TEMP_LABEL = T(
    named(Shooter("s"), " vs the field's middle score, by temperature"),
    you=named("You vs the field's middle score, by temperature"),
)


def _temp_chart(fact: Fact) -> ChartLink:
    window = Window(p_date(fact.params, "first"), p_date(fact.params, "day"))
    query = charts.spec(
        Metric.ADJUSTED,
        Agg.AVG,
        Dim.TEMP_BAND,
        window=window,
        shooters=(p_int(fact.params, "s"),),
        best=True,
    )
    hl = Highlight(keys=(str(fact.params["band"]),))
    return charts.explorer(query, label=TEMP_LABEL, hl=hl, ref=0)


register(
    Kind(
        id="pf.best-temp",
        family=Family.WEATHER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"gap": TEMP_GAP, "band_rounds": TEMP_MIN, "shuffle": TEMP_SHUFFLE},
        params=frozenset({"s", "band", "avg", "first", "day"}),
        templates={
            "": (
                T(
                    named(
                        Word("band", TEMP_LEAD),
                        Shooter("s"),
                        ": ",
                        Signed("avg"),
                        " against the field's middle score ",
                        Word("band", TEMP_WHEN),
                        ".",
                    ),
                    you=named(
                        Word("band", TEMP_LEAD_YOU),
                        ": ",
                        Signed("avg"),
                        " against the field's middle score ",
                        Word("band", TEMP_WHEN),
                        ".",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Each Sunday: the best round minus the middle score of everyone who "
                        "shot, grouped by the temperature between 10:00 and 12:00."
                    ),
                    you=named(
                        "Each Sunday: your best round minus the middle score of everyone "
                        "who shot, grouped by the temperature between 10:00 and 12:00."
                    ),
                ),
                T(
                    named(
                        "The band must beat their other Sundays by 2 or more, with 6 Sundays "
                        "in it, and beat 95% of 1,000 random reshuffles of all five bands."
                    ),
                    you=named(
                        "The band must beat your other Sundays by 2 or more, with 6 "
                        "Sundays in it, and beat 95% of 1,000 random reshuffles."
                    ),
                ),
            )
        },
        labels=(TEMP_LABEL,),
        chart=_temp_chart,
        proof=(cell("avg", key="band"),),
        evaluate=_best_temp,
    )
)


# --- pf.tough-days -------------------------------------------------------------------------------

TOUGH_DIFFICULTY = 1.0
TOUGH_GAP = 1.5
TOUGH_MIN = 6


def _tough_days(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sid, days in evergreen_days(fr, scope):
        rated = [d for d in held_only(days) if d.adjusted is not None and d.difficulty is not None]
        hard: list[Day] = []
        rest: list[float] = []
        for d in rated:
            if (d.difficulty or 0.0) >= TOUGH_DIFFICULTY:
                hard.append(d)
            else:
                rest.append(float(d.adjusted or 0.0))
        hard_values = [float(d.adjusted or 0.0) for d in hard]
        if len(hard) < TOUGH_MIN or not rest:
            continue
        gap = mean(hard_values) - mean(rest)
        if gap < TOUGH_GAP or round(mean(hard_values), 1) <= 0:
            continue
        if shuffle_share(hard_values, rest, seed=stable_seed("pf.tough-days", sid)) < TEMP_SHUFFLE:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={
                "s": sid,
                "hard": round(mean(hard_values), 1),
                "hard_days": [d.date for d in hard],
                "first": days[0].date,
                "day": days[-1].date,
            },
            strength=gap / TOUGH_GAP,
            named_shooter_ids=(sid,),
        )


TOUGH_LABEL = T(
    named(Shooter("s"), " vs the field, by how the Sunday played"),
    you=named("You vs the field, by how the Sunday played"),
)


def _tough_chart(fact: Fact) -> ChartLink:
    hard = fact.params["hard_days"]
    dates = tuple(d for d in hard if isinstance(d, date)) if isinstance(hard, list) else ()
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "tough-days",
        label=TOUGH_LABEL,
        window=Window(p_date(fact.params, "first"), p_date(fact.params, "day")),
        hl=Highlight(dates=dates),
    )


register(
    Kind(
        id="pf.tough-days",
        family=Family.WEATHER,
        home_slot=HomeSlot.FIELD,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"difficulty": TOUGH_DIFFICULTY, "gap": TOUGH_GAP, "hard_sundays": TOUGH_MIN},
        params=frozenset({"s", "hard", "hard_days", "first", "day"}),
        templates={
            "": (
                T(
                    named(
                        "The tougher the Sunday, the better ",
                        Shooter("s"),
                        " does: ",
                        Signed("hard"),
                        " against the field's middle score on the hardest days.",
                    ),
                    you=named(
                        "The tougher the Sunday, the better you do: ",
                        Signed("hard"),
                        " against the field's middle score on the hardest days.",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Hardest days = Sundays that played 1 target or more tougher than "
                        "typical, from the skill model."
                    ),
                    you=named(
                        "Hardest days = Sundays that played 1 target or more tougher than "
                        "typical, from the skill model."
                    ),
                ),
                T(
                    named(
                        "Needs 6 such Sundays, a gap of 1.5 or more over their other Sundays, "
                        "and a gap bigger than 95% of 1,000 random reshuffles."
                    ),
                    you=named(
                        "Needs 6 such Sundays, a gap of 1.5 or more over your other "
                        "Sundays, and a gap bigger than 95% of 1,000 random reshuffles."
                    ),
                ),
            )
        },
        labels=(TOUGH_LABEL,),
        chart=_tough_chart,
        proof=(mean_of("hard"),),
        evaluate=_tough_days,
    )
)
