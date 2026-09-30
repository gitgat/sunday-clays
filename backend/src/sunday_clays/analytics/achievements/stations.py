"""Station trophies (C12, Plan 10 T4b), from station-sheet entries (AchContext.station_hits).

Only entries linked to a shooter earn awards; unmatched names still count toward a day's station
hit % and the number of entries on the sheet."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from fractions import Fraction

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext, empty_value_frame
from sunday_clays.analytics.achievements.registry import (
    Achievement,
    Award,
    Category,
    make_tiers,
    register,
)
from sunday_clays.analytics.stations import per_event_station_pct
from sunday_clays.station_label import label_sort_key

TOP_GUN_MIN_ENTRIES = 5


def _as_date(value: object) -> date:
    return pd.Timestamp(str(value)).date()


def _linked(ctx: AchContext) -> pd.DataFrame:
    hits = ctx.station_hits
    return hits[hits["shooter_id"].notna()]


def station_cleaner_value(ctx: AchContext) -> pd.DataFrame:
    linked = _linked(ctx)
    if linked.empty:
        return empty_value_frame()
    cleaned = linked.assign(clean=(linked["hits"] == linked["target_count"]).astype(int))
    per_day = cleaned.groupby(["shooter_id", "event_ts"], sort=True)["clean"].sum().reset_index()
    per_day["value"] = per_day.groupby("shooter_id")["clean"].cumsum()
    return pd.DataFrame(
        {
            "shooter_id": per_day["shooter_id"].astype("int64").to_numpy(),
            "event_date": per_day["event_ts"].to_numpy(),
            "value": per_day["value"].to_numpy(dtype=float),
        }
    )


def _hardest_station_clean(ctx: AchContext) -> Iterator[Award]:
    hits = ctx.station_hits
    if hits.empty:
        return
    pct = per_event_station_pct(hits)
    for day in sorted(set(pct["event_date"])):
        today = pct[pct["event_date"] == day]
        rates = {
            str(label): Fraction(int(h), int(n))
            for label, h, n in zip(today["label"], today["hits"], today["n_targets"], strict=True)
        }
        lowest = min(rates.values())
        hardest = {label for label, rate in rates.items() if rate == lowest}
        cleaners = hits[
            (hits["event_date"] == day)
            & hits["station_label"].isin(hardest)
            & (hits["hits"] == hits["target_count"])
            & hits["shooter_id"].notna()
        ]
        for sid in sorted(set(cleaners["shooter_id"])):
            mine = cleaners[cleaners["shooter_id"] == sid]
            yield Award(
                int(sid),
                "hardest_station_clean",
                _as_date(day),
                None,
                {"stations": sorted({str(s) for s in mine["station_label"]}, key=label_sort_key)},
            )


def _station_top_gun(ctx: AchContext) -> Iterator[Award]:
    hits = ctx.station_hits
    won: dict[tuple[int, date], list[str]] = {}
    for day in sorted(set(hits["event_date"])):
        sheet = hits[hits["event_date"] == day]
        if sheet["entry_row"].nunique() < TOP_GUN_MIN_ENTRIES:
            continue
        for label in sorted({str(x) for x in sheet["station_label"]}, key=label_sort_key):
            station = sheet[sheet["station_label"] == label]
            who = (
                station["shooter_id"]
                .astype("Float64")
                .fillna(-(station["entry_row"].astype("Float64") + 1))
            )
            best = station["hits"].groupby(who).max()
            leaders = best[best == best.max()]
            if len(leaders) != 1 or float(leaders.index[0]) < 0:
                continue  # a tie, or an unmatched name on top
            won.setdefault((int(leaders.index[0]), _as_date(day)), []).append(label)
    for (sid, day), stations in sorted(won.items()):
        yield Award(
            sid, "station_top_gun", day, None, {"stations": sorted(stations, key=label_sort_key)}
        )


register(
    Achievement(
        code="station_cleaner",
        name="Station Cleaner",
        description="Stations cleaned: every target at the station broken.",
        category=Category.STATIONS,
        art_key="station_cleaner",
        tiers=make_tiers((1, 5, 10, 25), "stations cleaned", singular="station cleaned"),
        value=station_cleaner_value,
    )
)
register(
    Achievement(
        code="hardest_station_clean",
        name="Hardest Station Clean",
        description="Cleaned the day's hardest station.",
        category=Category.STATIONS,
        art_key="hardest_station_clean",
        evaluate=_hardest_station_clean,
        repeatable=True,
    )
)
register(
    Achievement(
        code="station_top_gun",
        name="Station Top Gun",
        description="Sole top score at a station on a sheet with at least 5 shooters.",
        category=Category.STATIONS,
        art_key="station_top_gun",
        evaluate=_station_top_gun,
        repeatable=True,
    )
)
