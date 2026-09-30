"""Station trophies (Plan 10 T4b): station_cleaner, hardest_station_clean, station_top_gun."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.achievements import registry


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def awards(code, ctx):
    return sorted(
        (w.shooter_id, w.code, w.event_date) for w in registry.evaluate_one(registry.get(code), ctx)
    )


def with_stations(code, ctx):
    return sorted(
        (w.shooter_id, w.event_date, tuple(w.details["stations"]))
        for w in registry.evaluate_one(registry.get(code), ctx)
    )


def sheet(builder, day, entries):
    """entries: [(shooter_id or None, {station_no: hits})]; every station has 7 targets."""
    for entry_row, (shooter_id, hits_by_station) in enumerate(entries, start=10):
        for station_no, hits in hits_by_station.items():
            builder.station(shooter_id, day, station_no, hits, entry_row=entry_row)
    return builder


def cleaner_ctx(b):
    builder = b()
    sheet(builder, sun(0), [(1, {4: 7, 5: 7, 6: 3})])
    sheet(builder, sun(1), [(1, {4: 7, 5: 7, 6: 7}), (None, {4: 7}), (2, {4: 6})])
    return builder.build()


def hardest_ctx(b):
    builder = b()
    sheet(
        builder, sun(0), [(1, {4: 7, 5: 0, 6: 7}), (2, {4: 0, 5: 7, 6: 7}), (3, {4: 0, 5: 0, 6: 6})]
    )
    sheet(builder, sun(1), [(1, {4: 7, 5: 7, 6: 0}), (2, {4: 7, 5: 7, 6: 7})])
    return builder.build()


def top_gun_ctx(b):
    builder = b()
    sheet(
        builder,
        sun(0),
        [
            (1, {4: 7, 5: 6}),
            (2, {4: 6, 5: 6}),
            (3, {4: 6, 5: 5}),
            (4, {4: 5, 5: 4}),
            (5, {4: 5, 5: 3}),
        ],
    )
    # sun(1): only 4 entries on the sheet
    sheet(builder, sun(1), [(1, {4: 7}), (2, {4: 3}), (3, {4: 3}), (4, {4: 3})])
    # sun(2): the sole top score belongs to an unmatched entry
    sheet(builder, sun(2), [(None, {4: 7}), (2, {4: 6}), (3, {4: 5}), (4, {4: 5}), (5, {4: 5})])
    sheet(
        builder,
        sun(3),
        [
            (1, {4: 7, 6: 7}),
            (2, {4: 6, 6: 6}),
            (3, {4: 6, 6: 6}),
            (4, {4: 5, 6: 5}),
            (5, {4: 5, 6: 5}),
        ],
    )
    return builder.build()


def test_station_cleaner_counts_cleaned_stations(ctx_builder):
    assert awards("station_cleaner", cleaner_ctx(ctx_builder)) == [
        (1, "station_cleaner:1", sun(0)),
        (1, "station_cleaner:2", sun(1)),
    ]


def test_tied_hardest_stations_award_both(ctx_builder):
    assert with_stations("hardest_station_clean", hardest_ctx(ctx_builder)) == [
        (1, sun(0), ("4",)),
        (2, sun(0), ("5",)),
        (2, sun(1), ("6",)),
    ]


def test_tied_top_gun_gets_no_award(ctx_builder):
    ctx = top_gun_ctx(ctx_builder)
    assert all(
        "5" not in stations
        for _, day, stations in with_stations("station_top_gun", ctx)
        if day == sun(0)
    )


def test_top_gun_needs_five_on_the_sheet_and_a_matched_winner(ctx_builder):
    days = [day for _, day, _ in with_stations("station_top_gun", top_gun_ctx(ctx_builder))]
    assert sun(1) not in days
    assert sun(2) not in days


def test_top_gun_lists_every_station_won_that_day(ctx_builder):
    assert with_stations("station_top_gun", top_gun_ctx(ctx_builder)) == [
        (1, sun(0), ("4",)),
        (1, sun(3), ("4", "6")),
    ]


def test_unmatched_station_entries_earn_nothing(ctx_builder):
    # An unmatched entry (shooter_id NULL) cleans station 4 on cleaner_ctx's sun(1) and has the
    # sole top score on top_gun_ctx's sun(2); every award must still go to a linked shooter.
    cleaner = cleaner_ctx(ctx_builder)
    assert awards("station_cleaner", cleaner) == [
        (1, "station_cleaner:1", sun(0)),
        (1, "station_cleaner:2", sun(1)),
    ]
    assert awards("hardest_station_clean", cleaner) == [(1, "hardest_station_clean", sun(1))]
    assert with_stations("station_top_gun", top_gun_ctx(ctx_builder)) == [
        (1, sun(0), ("4",)),
        (1, sun(3), ("4", "6")),
    ]


def test_unmatched_entries_count_toward_the_field_size(ctx_builder):
    # Only 4 linked entries; the 5th (unmatched, not the leader) still makes the sheet a field.
    builder = ctx_builder()
    sheet(builder, sun(0), [(1, {4: 7}), (2, {4: 5}), (3, {4: 5}), (4, {4: 5}), (None, {4: 2})])
    assert with_stations("station_top_gun", builder.build()) == [(1, sun(0), ("4",))]


def test_unmatched_misses_make_a_station_the_hardest(ctx_builder):
    # Linked shooters clean both stations (100% each); only the unmatched entry's misses make
    # station 4 the day's hardest, so the award lists station 4 alone.
    builder = ctx_builder()
    sheet(builder, sun(0), [(1, {4: 7, 5: 7}), (2, {4: 7, 5: 7}), (None, {4: 0, 5: 7})])
    assert with_stations("hardest_station_clean", builder.build()) == [
        (1, sun(0), ("4",)),
        (2, sun(0), ("4",)),
    ]


def test_a_shooter_with_two_entries_competes_with_their_best(ctx_builder):
    builder = ctx_builder()
    sheet(
        builder,
        sun(0),
        [(1, {4: 7}), (1, {4: 7}), (2, {4: 6}), (3, {4: 5}), (4, {4: 5}), (5, {4: 4})],
    )
    ctx = builder.build()
    assert with_stations("station_top_gun", ctx) == [(1, sun(0), ("4",))]
    # Both entries clean station 4, so the cumulative count is 2 (tier 1 only).
    values = registry.get("station_cleaner").value(ctx)
    assert values[values["shooter_id"] == 1]["value"].tolist() == [2.0]
    assert awards("station_cleaner", ctx) == [(1, "station_cleaner:1", sun(0))]


def test_an_unmatched_leader_at_entry_row_zero_earns_nothing(ctx_builder):
    builder = ctx_builder()
    builder.station(None, sun(0), 4, 7, entry_row=0)
    for row, (sid, hits) in enumerate([(2, 6), (3, 5), (4, 5), (5, 5)], start=1):
        builder.station(sid, sun(0), 4, hits, entry_row=row)
    assert with_stations("station_top_gun", builder.build()) == []


def test_station_trophies_handle_contexts_without_station_data(ctx_builder):
    ctx = ctx_builder().round(1, sun(0), 30).build()
    assert registry.get("station_cleaner").value(ctx).empty
    assert awards("hardest_station_clean", ctx) == []
    assert awards("station_top_gun", ctx) == []


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("station_cleaner", cleaner_ctx, sun(0)),
        ("hardest_station_clean", hardest_ctx, sun(0)),
        ("station_top_gun", top_gun_ctx, sun(1)),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0


def test_a_lettered_station_is_cleaned_and_won_on_its_own(ctx_builder):
    builder = ctx_builder()
    # 7 and 7A share a sort number; 7A is the day's hardest station and one shooter cleans it
    sheet(
        builder,
        sun(0),
        [
            (1, {"7": 7, "7A": 7, 8: 7}),
            (2, {"7": 6, "7A": 2, 8: 6}),
            (3, {"7": 6, "7A": 3, 8: 6}),
            (4, {"7": 6, "7A": 3, 8: 6}),
            (5, {"7": 5, "7A": 3, 8: 6}),
        ],
    )
    ctx = builder.build()
    assert with_stations("hardest_station_clean", ctx) == [(1, sun(0), ("7A",))]
    assert with_stations("station_top_gun", ctx) == [(1, sun(0), ("7", "7A", "8"))]
    assert awards("station_cleaner", ctx)[0][:2] == (1, "station_cleaner:1")
