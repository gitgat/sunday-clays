"""Station kinds (spec §2.2.9). Dormant until 8 Sundays have station sheets (§4.5).

Hit % = 100 x hits / targets over every station entry on record (the stations page and the
Explorer `hit_pct` metric use the same ratio). Layout eras are not split here: the station
resets table is not part of the insight frames, and a later task may add it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pandas as pd

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import InsightFrames, evergreen_days
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import Pct, Shooter, Station, T, field_, named
from sunday_clays.analytics.insights.types import (
    ChartLink,
    Fact,
    Family,
    Highlight,
    P,
    Polarity,
    Requires,
    Scope,
    SubjectType,
    Window,
    cell,
    na,
    p_date,
    p_int,
    p_str,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric
from sunday_clays.station_label import label_sort_key

STATION_SUNDAYS = 8
STATION_ENTRIES = 30
SHOOTER_SUNDAYS = 4
STATION_GAP = 8.0
SPREAD_UNIT = 10.0


def entries_to(fr: InsightFrames, day: date) -> pd.DataFrame:
    s = fr.stations
    return s.loc[[d <= day for d in s["event_date"]]] if len(s) else s


def hit_pct(frame: pd.DataFrame) -> float:
    targets = float(frame["target_count"].sum())
    return 100.0 * float(frame["hits"].sum()) / targets if targets else 0.0


def station_table(frame: pd.DataFrame) -> dict[str, tuple[float, int]]:
    """station label -> (hit %, entries), in station order (7 before 7A)."""
    return {label: (hit_pct(group), len(group)) for label, group in by_station(frame)}


def by_station(frame: pd.DataFrame) -> Iterator[tuple[str, pd.DataFrame]]:
    """Each station of `frame` by label ("7", "7A"), ordered by (number, letter)."""
    labels = {str(x) for x in frame["station_label"]}
    for label in sorted(labels, key=label_sort_key):
        yield label, frame[frame["station_label"] == label]


# --- st.hardest-easiest (field only) -------------------------------------------------------------

STATIONS_LABEL = T(named("Hit % by station"))


def _hardest_easiest(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    frame = entries_to(fr, scope.as_of)
    if not len(frame) or frame["event_date"].nunique() < STATION_SUNDAYS:
        return
    table = {label: pct for label, (pct, n) in station_table(frame).items() if n >= STATION_ENTRIES}
    if len(table) < 2:
        return
    hardest = min(table, key=lambda label: (table[label], label_sort_key(label)))
    spread = max(table.values()) - table[hardest]
    yield Fact(
        subject_id=str(hardest),
        anchor_date=None,
        variant="",
        pages=frozenset({P.STATIONS}),
        params={
            "day": scope.as_of,
            "first": min(frame["event_date"]),
            "station": hardest,
            "pct": round(table[hardest]),
            "overall": round(hit_pct(frame)),
        },
        strength=spread / SPREAD_UNIT,
    )


register(
    Kind(
        id="st.hardest-easiest",
        family=Family.STATION,
        home_slot=None,
        subject=SubjectType.STATION,
        pages=frozenset({P.STATIONS}),
        polarity=Polarity.FIELD_NEGATIVE,
        care=3,
        anchored=False,
        guard={"station_sundays": STATION_SUNDAYS, "entries": STATION_ENTRIES},
        params=frozenset({"day", "first", "station", "pct", "overall"}),
        templates={
            "": (
                T(
                    field_(
                        Station("station"),
                        " is the toughest stand: the field breaks ",
                        Pct("pct"),
                        " there vs ",
                        Pct("overall"),
                        " overall.",
                    )
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Hit % = targets broken out of targets thrown, over every station "
                        "sheet on record. Needs 8 Sundays and 30 entries per station."
                    )
                ),
            )
        },
        labels=(STATIONS_LABEL,),
        chart=lambda fact: charts.page(
            "/stations",
            "sthit",
            label=STATIONS_LABEL,
            window=Window(p_date(fact.params, "first"), p_date(fact.params, "day")),
            hl=Highlight(keys=(p_str(fact.params, "station"),)),
            # Every sheet on record (Decision 11): the page's "All eras" view, not the current era.
            params={"era": "all"},
        ),
        proof=(
            cell("pct", key="station"),
            na("overall", "the stations page summary"),
            na("station", "the highlighted bar"),
        ),
        evaluate=_hardest_easiest,
        requires=Requires(station_sundays=STATION_SUNDAYS),
    )
)


# --- pf.station-best -----------------------------------------------------------------------------

STATION_BEST_LABEL = T(
    named(Shooter("s"), "'s hit % by station, against the field"),
    you=named("Your hit % by station, against the field"),
)


def _station_best(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    frame = entries_to(fr, scope.as_of)
    if not len(frame) or frame["event_date"].nunique() < STATION_SUNDAYS:
        return
    linked = frame[frame["round_id"].notna() & frame["shooter_id"].notna()]
    field = {
        label: pct for label, (pct, n) in station_table(linked).items() if n >= STATION_ENTRIES
    }
    for sid, _days in evergreen_days(fr, scope):
        own = linked[linked["shooter_id"] == sid]
        best: tuple[float, str, float] | None = None
        for station, group in by_station(own):
            if station not in field or group["event_date"].nunique() < SHOOTER_SUNDAYS:
                continue
            mine = hit_pct(group)
            gap = mine - field[station]
            if gap >= STATION_GAP and (best is None or gap > best[0]):
                best = (gap, station, mine)
        if best is None:
            continue
        gap, station, mine = best
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE, P.STATIONS}),
            params={
                "s": sid,
                "station": station,
                "mine": round(mine),
                "field": round(field[station]),
                "first": min(frame["event_date"]),
                "day": scope.as_of,
            },
            strength=gap / STATION_GAP,
            named_shooter_ids=(sid,),
        )


def _station_best_chart(fact: Fact) -> ChartLink:
    window = Window(p_date(fact.params, "first"), p_date(fact.params, "day"))
    mine = charts.spec(
        Metric.HIT_PCT, Agg.AVG, Dim.STATION, window=window, shooters=(p_int(fact.params, "s"),)
    )
    everyone = charts.spec(Metric.HIT_PCT, Agg.AVG, Dim.STATION, window=window)
    return charts.explorer(
        mine,
        label=STATION_BEST_LABEL,
        hl=Highlight(keys=(p_str(fact.params, "station"),)),
        compare=everyone,
    )


register(
    Kind(
        id="pf.station-best",
        family=Family.STATION,
        home_slot=None,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.STATIONS}),
        polarity=Polarity.POSITIVE,
        care=3,
        anchored=False,
        guard={"shooter_sundays": SHOOTER_SUNDAYS, "gap": STATION_GAP},
        params=frozenset({"s", "station", "mine", "field", "first", "day"}),
        templates={
            "": (
                T(
                    named(
                        Station("station"),
                        " is ",
                        Shooter("s"),
                        "'s station: ",
                        Pct("mine"),
                        " vs ",
                        Pct("field"),
                        " for the field.",
                    ),
                    you=named(
                        Station("station"),
                        " is your station: ",
                        Pct("mine"),
                        " vs ",
                        Pct("field"),
                        " for the field.",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "Hit % at each station against everyone's hit % there. Needs 4 Sundays "
                        "at that station and a gap of 8 points or more."
                    ),
                    you=named(
                        "Your hit % at each station against everyone's hit % there. Needs "
                        "4 Sundays at that station and a gap of 8 points or more."
                    ),
                ),
            )
        },
        labels=(STATION_BEST_LABEL,),
        chart=_station_best_chart,
        proof=(
            cell("mine", key="station"),
            na("field", "the comparison bars"),
            na("station", "the highlighted bar"),
        ),
        evaluate=_station_best,
        requires=Requires(station_sundays=STATION_SUNDAYS),
    )
)
