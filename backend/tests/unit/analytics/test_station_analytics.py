"""Station analytics (Plan 10 T4a) on synthetic multi-event frames."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics.frames import wind_band
from sunday_clays.analytics.stations import (
    add_sheet_totals,
    assign_eras,
    current_eras,
    hit_stats,
    per_event_station_pct,
    shooter_station_deltas,
    shooter_station_matrix,
    station_detail,
    station_leaders,
    station_stats,
    station_wind,
    stations_overview,
    wilson_ci,
)
from sunday_clays.domain.round_type import RoundType
from sunday_clays.station_label import label_number, parse_label

COLUMNS = ["event_date", "entry_row", "station_no", "shooter_id", "hits", "target_count"]
NO_RESETS = pd.DataFrame(columns=["label", "station_no", "effective_date", "note"])
NO_WEATHER = pd.DataFrame(columns=["event_date", "gust_mph"])
D0 = date(2025, 1, 5)


def sun(i: int) -> date:
    return D0 + timedelta(weeks=i)


def frame(rows, *, round_type="sporting"):
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["station_label"] = df["station_no"].map(lambda x: str(parse_label(x)))
    df["station_no"] = df["station_label"].map(label_number)
    df["sheet_id"] = 1
    df["round_id"] = pd.array([pd.NA] * len(df), dtype="Int64")
    df["shooter_id"] = df["shooter_id"].astype("Int64")
    df["round_type"] = round_type
    df["display_name"] = [None if pd.isna(s) else f"Shooter {s}" for s in df["shooter_id"]]
    return add_sheet_totals(df)


def separator_rows(n_per_event):
    rows = []
    for e in range(2):
        for k in range(n_per_event):
            skill = k + e
            for station_no, offset in ((4, 0), (5, 1), (6, 2)):
                hits = min(7, (skill + offset) // 2 + (1 if k % 3 == 0 else 0))
                rows.append((sun(e), k, station_no, 100 * e + k, hits, 7))
    return rows


def test_wilson_ci_matches_textbook_values():
    assert wilson_ci(0.5, 100) == pytest.approx((0.40383, 0.59617), abs=1e-5)
    assert wilson_ci(0.0, 10) == pytest.approx((0.0, 0.27754), abs=1e-5)
    assert wilson_ci(0.5, 0) == (0.0, 1.0)


def test_homogeneous_entries_have_design_effect_one():
    [stats] = station_stats(frame([(D0, r, 4, r, 5, 7) for r in range(10)])).to_dict("records")
    assert stats["deff"] == 1.0
    assert (stats["hits"], stats["n_targets"], stats["n_rounds"], stats["n_events"]) == (
        50,
        70,
        10,
        1,
    )
    assert (stats["ci_low"], stats["ci_high"]) == pytest.approx((0.599496, 0.806779), abs=1e-5)


def test_heterogeneous_entries_widen_the_interval():
    [stats] = station_stats(
        frame([(D0, r, 4, r, 7 if r < 5 else 0, 7) for r in range(10)])
    ).to_dict("records")
    assert stats["deff"] == pytest.approx(7.777778, abs=1e-5)
    assert (stats["ci_low"], stats["ci_high"]) == pytest.approx((0.226526, 0.773474), abs=1e-5)


def test_eight_events_switch_to_event_clusters():
    def rows(n_events):
        out = []
        for e in range(n_events):
            out += [(sun(e), 2 * e, 4, 2 * e, 7, 7), (sun(e), 2 * e + 1, 4, 2 * e + 1, 0, 7)]
        return out

    assert station_stats(frame(rows(7)))["deff"].iloc[0] == pytest.approx(7.538462, abs=1e-5)
    assert station_stats(frame(rows(8)))["deff"].iloc[0] == 1.0


def test_perfect_station_ci_stays_in_unit_interval():
    [stats] = station_stats(frame([(D0, r, 4, r, 7, 7) for r in range(10)])).to_dict("records")
    assert (stats["hit_pct"], stats["deff"], stats["clean_rate"]) == (1.0, 1.0, 1.0)
    assert stats["ci_high"] == pytest.approx(1.0)
    assert stats["ci_low"] == pytest.approx(0.947975, abs=1e-5)


def test_empty_selection_returns_no_stations():
    empty = frame([])
    assert station_stats(empty).empty
    stats = hit_stats(empty)
    assert (stats.hit_pct, stats.ci_low, stats.deff, stats.n_targets) == (None, None, None, 0)


def test_separator_is_item_rest_not_part_whole():
    df = frame(separator_rows(16))
    s4 = df[df["station_no"] == 4]
    total = df.groupby(["event_date", "entry_row"])["hits"].transform("sum")[s4.index]

    def centered(values):
        return values - values.groupby(s4["event_date"]).transform("mean")

    share = s4["hits"] / 7
    item_rest = np.corrcoef(centered(share), centered(total - s4["hits"]))[0, 1]
    part_whole = np.corrcoef(centered(share), centered(total))[0, 1]
    separator = station_stats(df).set_index("label").loc["4", "separator"]
    assert separator == pytest.approx(item_rest)
    assert separator < part_whole


def test_separator_needs_thirty_shooter_rounds():
    # 28 entries per station
    assert station_stats(frame(separator_rows(14)))["separator"].isna().all()


def test_one_round_delta_is_shrunk_toward_zero():
    df = frame([(D0, 1, 4, 1, 7, 7), (D0, 2, 4, 2, 0, 7), (sun(1), 1, 4, 2, 7, 7)])
    [row] = shooter_station_deltas(df, 1).to_dict("records")
    assert (
        row["station_no"],
        row["hits"],
        row["n"],
        row["n_rounds"],
        row["hit_pct"],
        row["field_pct"],
    ) == (
        4,
        7,
        7,
        1,
        1.0,
        0.5,
    )
    # (7 + 14·0.5)/(7 + 14) - 0.5; the raw delta would be 0.5
    assert row["delta"] == pytest.approx(1 / 6)


def test_leaders_need_three_appearances():
    rows = []
    for e in range(3):
        rows += [(sun(e), 1, 4, 1, 7 if e < 2 else 6, 7), (sun(e), 3, 4, 3, 5, 7)]
    rows += [(sun(e), 2, 4, 2, 7, 7) for e in range(2)]
    rows += [(sun(e), 9, 4, None, 7, 7) for e in range(3)]  # unmatched name never leads
    leaders = station_leaders(frame(rows), limit=5)
    assert list(zip(leaders["shooter_id"], leaders["hits"], leaders["n_rounds"], strict=True)) == [
        (1, 20, 3),
        (3, 15, 3),
    ]


def test_leaders_tie_on_hit_pct_break_by_n_targets_then_shooter_id():
    rows = []
    for e in range(3):
        rows += [(sun(e), 1, 4, 1, 7, 7), (sun(e), 2, 4, 2, 7, 7), (sun(e), 3, 4, 3, 7, 7)]
    df = frame(rows)
    df.loc[df["shooter_id"] == 2, ["hits", "target_count"]] = [8, 8]  # 24/24 vs 21/21, all 100%
    leaders = station_leaders(add_sheet_totals(df), limit=5)
    assert list(leaders["shooter_id"]) == [2, 1, 3]
    assert list(leaders["n_targets"]) == [24, 21, 21]


def test_station_wind_bands_flag_insufficient_cells():
    rows = [(sun(e), 1, 4, 1, 5, 7) for e in range(8)]
    weather = pd.DataFrame(
        {"event_date": [sun(e) for e in range(7)], "gust_mph": [5.0] * 5 + [25.0] * 2}
    )
    cells = station_wind(frame(rows), weather, "all")
    assert list(cells["band"]) == [wind_band(5.0), wind_band(25.0)]
    assert list(cells["n_events"]) == [5, 2]
    assert list(cells["n_targets"]) == [35, 14]
    assert list(cells["sufficient"]) == [True, False]
    assert list(cells["hit_pct"]) == pytest.approx([5 / 7, 5 / 7])


def test_station_wind_without_weather_is_empty():
    assert station_wind(frame([(D0, 1, 4, 1, 5, 7)]), NO_WEATHER, "all").empty


def test_round_type_filter_restricts_rounds():
    df = pd.concat(
        [
            frame([(sun(0), 1, 4, 1, 7, 7), (sun(0), 2, 4, None, 3, 7)], round_type="sporting"),
            frame([(sun(1), 1, 4, 1, 3, 7)], round_type="super_sporting"),
        ],
        ignore_index=True,
    )
    sporting = stations_overview(
        df, NO_RESETS, era="all", round_types=[RoundType.SPORTING], today=sun(5)
    )
    assert sporting.n_events == 1
    assert list(sporting.stats["hits"]) == [10]
    assert list(sporting.by_event["hit_pct"]) == pytest.approx([10 / 14])
    assert list(sporting.matrix["shooter_id"]) == [1]  # the unmatched entry is not a matrix row
    everything = stations_overview(df, NO_RESETS, era="all", round_types=[], today=sun(5))
    assert everything.n_events == 2


ERA_ROWS = [
    (date(2025, 2, 2), 1, 4, 1, 3, 7),
    (date(2025, 3, 2), 1, 4, 1, 6, 7),
    (date(2025, 2, 2), 1, 5, 1, 4, 7),
    (date(2025, 3, 2), 1, 5, 1, 5, 7),
]
ERA_RESETS = pd.DataFrame(
    {
        "label": ["4", "4"],
        "effective_date": [date(2025, 3, 1), date(2025, 7, 1)],
        "note": ["new trap", "future"],
    }
)


def test_current_era_starts_at_latest_past_reset():
    today = date(2025, 6, 1)
    assert current_eras(ERA_RESETS, today) == {"4": (1, date(2025, 3, 1))}
    current = stations_overview(
        frame(ERA_ROWS), ERA_RESETS, era="current", round_types=[], today=today
    )
    by_station = current.stats.set_index("label")
    assert by_station.loc["4", "hits"] == 6  # only the post-reset event
    assert by_station.loc["5", "hits"] == 9  # no resets logged: every event
    everything = stations_overview(
        frame(ERA_ROWS), ERA_RESETS, era="all", round_types=[], today=today
    )
    assert everything.stats.set_index("label").loc["4", "hits"] == 9


def test_station_stays_listed_after_a_reset_until_new_data_arrives():
    today = date(2025, 7, 5)  # both resets are past; station 4 has no sheet since the second
    assert current_eras(ERA_RESETS, today) == {"4": (2, date(2025, 7, 1))}
    current = stations_overview(
        frame(ERA_ROWS), ERA_RESETS, era="current", round_types=[], today=today
    )
    by_station = current.stats.set_index("label")
    assert list(by_station.index) == ["4", "5"]
    assert (by_station.loc["4", "hits"], by_station.loc["4", "n_targets"]) == (0, 0)
    assert (by_station.loc["4", "n_rounds"], by_station.loc["4", "n_events"]) == (0, 0)
    assert (
        by_station[["hit_pct", "ci_low", "ci_high", "deff", "clean_rate", "separator"]]
        .loc["4"]
        .isna()
        .all()
    )
    assert by_station.loc["5", "hits"] == 9  # untouched stations keep every event
    assert current.current == {"4": (2, date(2025, 7, 1))}
    assert "4" not in set(current.by_event["label"])
    # era=all never needs the empty row
    everything = stations_overview(
        frame(ERA_ROWS), ERA_RESETS, era="all", round_types=[], today=today
    )
    assert list(everything.stats["label"]) == ["4", "5"]
    assert everything.stats.set_index("label").loc["4", "n_targets"] == 14


def test_same_day_duplicate_resets_are_one_era_boundary():
    resets = pd.DataFrame(
        {
            "label": ["4", "4"],
            "effective_date": [date(2025, 3, 1), date(2025, 3, 1)],
            "note": ["first", "again"],
        }
    )
    assert current_eras(resets, date(2025, 6, 1)) == {"4": (1, date(2025, 3, 1))}
    detail = station_detail(
        frame(ERA_ROWS), resets, NO_WEATHER, label="4", round_types=[], today=date(2025, 6, 1)
    )
    assert list(detail.eras["era"]) == [0, 1]


def test_station_detail_splits_eras():
    detail = station_detail(
        frame(ERA_ROWS),
        ERA_RESETS,
        NO_WEATHER,
        label="4",
        round_types=[],
        today=date(2025, 6, 1),
    )
    assert list(
        zip(detail.eras["era"], detail.eras["era_start"], detail.eras["hits"], strict=True)
    ) == [
        (0, None, 3),
        (1, date(2025, 3, 1), 6),
    ]
    assert list(detail.by_event["hits"]) == [3, 6]
    assert detail.wind.empty
    assert detail.leaders.empty


def test_separator_without_variation_is_none():
    # 30 identical entries: nothing to correlate, no division by zero
    assert station_stats(frame([(D0, r, 4, r, 5, 7) for r in range(30)]))["separator"].isna().all()
    # Centering 39 shares of 3/7 leaves ~1e-31 of float noise, which is still no variation.
    rows = [(D0, r, no, r, 3 if no == 4 else r % 8, 7) for r in range(39) for no in (4, 5)]
    assert station_stats(frame(rows))["separator"].isna().all()


def test_linked_shooter_without_a_profile_is_not_listed():
    """A name linked to a shooter with no shooter_profiles row has no display name to show."""
    rows = [(sun(e), 1, 4, 1, 7, 7) for e in range(3)] + [(sun(e), 2, 4, 2, 6, 7) for e in range(3)]
    df = frame(rows)
    df.loc[df["shooter_id"] == 1, "display_name"] = None
    assert list(station_leaders(df, limit=5)["shooter_id"]) == [2]
    assert list(shooter_station_matrix(df)["shooter_id"]) == [2]


def test_per_event_pct_uses_only_that_days_entries():
    """Task 5 dates station trophies by event: later sheets never change an earlier day."""
    rows = [
        (sun(e), r, no, r, (r + e + no) % 8, 7) for e in range(3) for r in range(4) for no in (4, 5)
    ]
    full = per_event_station_pct(frame(rows))
    cut = per_event_station_pct(frame([row for row in rows if row[0] <= sun(1)]))
    pd.testing.assert_frame_equal(full[full["event_date"] <= sun(1)], cut)


def test_later_resets_never_change_earlier_eras():
    today = date(2025, 12, 1)
    later = pd.concat(
        [
            ERA_RESETS,
            pd.DataFrame({"label": ["4"], "effective_date": [date(2025, 9, 1)], "note": ["later"]}),
        ],
        ignore_index=True,
    )
    before = assign_eras(frame(ERA_ROWS), ERA_RESETS, today)
    after = assign_eras(frame(ERA_ROWS), later, today)
    pd.testing.assert_series_equal(before["era"], after["era"])
    pd.testing.assert_series_equal(before["era_start"], after["era_start"])
    assert (before["current_era"].tolist(), after["current_era"].tolist()) == (
        [2, 2, 0, 0],
        [3, 3, 0, 0],
    )


def test_station_wind_skips_events_with_a_missing_gust():
    rows = [(sun(e), 1, 4, 1, 5, 7) for e in range(2)]
    weather = pd.DataFrame({"event_date": [sun(0), sun(1)], "gust_mph": [np.nan, 15.0]})
    cells = station_wind(frame(rows), weather, "all")
    assert list(zip(cells["band"], cells["n_events"], strict=True)) == [(wind_band(15.0), 1)]


def test_station_detail_leaders_and_wind_follow_the_era_toggle():
    resets = pd.DataFrame(
        {"label": ["4"], "effective_date": [date(2025, 3, 1)], "note": ["new trap"]}
    )
    days = [date(2025, 2, d) for d in (2, 9, 16)] + [date(2025, 3, d) for d in (9, 16, 23)]
    rows = []
    for i, day in enumerate(days):
        rows += [(day, 1, 4, 1, 7 if i < 3 else 3, 7), (day, 2, 4, 2, 6, 7)]
    weather = pd.DataFrame({"event_date": days, "gust_mph": [5.0] * 3 + [25.0] * 3})
    kwargs = {"label": "4", "round_types": [], "today": date(2025, 6, 1)}
    everything = station_detail(frame(rows), resets, weather, era="all", **kwargs)
    assert list(everything.leaders["shooter_id"]) == [2, 1]
    assert list(everything.leaders["n_rounds"]) == [6, 6]
    assert list(everything.wind["band"]) == [wind_band(5.0), wind_band(25.0)]
    current = station_detail(frame(rows), resets, weather, **kwargs)  # default era is current
    assert list(current.leaders["shooter_id"]) == [2, 1]
    assert list(current.leaders["n_rounds"]) == [3, 3]
    assert list(current.leaders["hits"]) == [18, 9]
    assert list(current.wind["band"]) == [wind_band(25.0)]
    assert list(current.eras["era"]) == [0, 1]  # the era chart always shows every setup


def test_station_detail_lists_every_leader_so_the_page_can_offer_show_all():
    days = [sun(i) for i in range(3)]
    rows = [(day, s, 4, s, 5, 7) for day in days for s in range(1, 15)]
    detail = station_detail(
        frame(rows),
        NO_RESETS,
        NO_WEATHER,
        label="4",
        round_types=[],
        today=date(2025, 6, 1),
    )
    assert len(detail.leaders) == 14  # the page shows ten, then "Show all 14"


def test_matrix_counts_each_shooters_rounds_per_station():
    rows = [(sun(e), 1, 4, 1, 7, 7) for e in range(3)] + [(sun(0), 2, 4, 2, 6, 7)]
    matrix = shooter_station_matrix(frame(rows)).set_index("shooter_id")
    assert list(matrix["n_rounds"]) == [3, 1]


def lettered_rows():
    """Stations 7 and 7A (both sort number 7) on three Sundays, with 8 after them."""
    rows = []
    for e in range(3):
        for r in range(4):
            rows += [
                (sun(e), r, "7", r, 5, 7),
                (sun(e), r, "7A", r, 3 + e, 6),
                (sun(e), r, 8, r, 6, 7),
            ]
    return rows


def test_a_lettered_station_is_kept_apart_from_its_number_and_sorted_after_it():
    stats = station_stats(frame(lettered_rows()))
    assert list(stats["label"]) == ["7", "7A", "8"]
    assert list(stats["station_no"]) == [7, 7, 8]
    by = stats.set_index("label")
    assert (by.loc["7", "n_targets"], by.loc["7A", "n_targets"]) == (84, 72)
    assert (by.loc["7", "hits"], by.loc["7A", "hits"]) == (60, 48)


def test_lettered_stations_have_their_own_events_leaders_matrix_and_deltas():
    df = frame(lettered_rows())
    by_event = per_event_station_pct(df)
    assert list(by_event["label"][:3]) == ["7", "7A", "8"]
    assert list(by_event["station_no"][:3]) == [7, 7, 8]
    leaders = station_leaders(df, limit=5)
    assert list(leaders["label"].drop_duplicates()) == ["7", "7A", "8"]
    matrix = shooter_station_matrix(df)
    assert set(matrix["label"]) == {"7", "7A", "8"}
    deltas = shooter_station_deltas(df, 1)
    assert list(deltas["label"]) == ["7", "7A", "8"]
    assert deltas.set_index("label").loc["7A", "n"] == 18


def test_a_reset_on_7a_leaves_7_alone():
    resets = pd.DataFrame(
        {
            "label": ["7A"],
            "station_no": [7],
            "effective_date": [sun(1)],
            "note": ["new trap"],
        }
    )
    today = sun(3)
    assert current_eras(resets, today) == {"7A": (1, sun(1))}
    overview = stations_overview(
        frame(lettered_rows()), resets, era="current", round_types=[], today=today
    )
    by = overview.stats.set_index("label")
    assert by.loc["7", "n_events"] == 3
    assert by.loc["7A", "n_events"] == 2
    detail = station_detail(
        frame(lettered_rows()),
        resets,
        NO_WEATHER,
        label="7A",
        round_types=[],
        today=today,
        era="all",
    )
    assert list(detail.eras["era"]) == [0, 1]
    assert set(detail.eras["label"]) == {"7A"}


def test_station_wind_lists_lettered_stations_in_order():
    df = frame(lettered_rows())
    weather = pd.DataFrame({"event_date": [sun(0), sun(1)], "gust_mph": [5.0, 5.0]})
    wind = station_wind(df, weather, "all")
    assert list(wind["label"]) == ["7", "7A", "8"]
