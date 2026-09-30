"""Conditions trophies (Plan 10 T3): sub_gauge, rain/cold/heat/wind, all_weather, mudder."""

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


def gauge_ctx(b):
    return (
        b()
        .round(1, sun(0), 30, gauge_class="20 Gauge")
        .round(2, sun(0), 30, gauge_class="SxS")
        .round(3, sun(0), 30, gauge_class="12 Gauge")
        .round(4, sun(0), 30, gauge_class="Pump")  # an unknown_gauge_class value kept verbatim
        .round(5, sun(0), 30)  # not recorded
        .round(6, sun(1), 30, gauge_class=".410")
        .round(6, sun(2), 30, gauge_class="Sub-Gauge")
        .round(7, sun(3), 30, gauge_class="28 Gauge")
        .build()
    )


def weather_ctx(b):
    return (
        b()
        .event(sun(0), precip_in=0.02, temp_f=50.0, gust_mph=5.0)
        .event(sun(1), precip_in=0.019, temp_f=34.9, gust_mph=19.9)
        .event(sun(2), precip_in=0.0, temp_f=35.0, gust_mph=20.0)
        .event(sun(3), precip_in=0.0, temp_f=85.0, gust_mph=5.0)
        .event(sun(4), precip_in=0.0, temp_f=84.9, gust_mph=5.0)
        .event(sun(6), precip_in=0.5, temp_f=55.0, gust_mph=8.0)
        .round(1, sun(0), 30)
        .round(1, sun(1), 30)
        .round(1, sun(2), 30)
        .round(1, sun(3), 30)
        .round(2, sun(2), 30)
        .round(2, sun(4), 30)
        .round(2, sun(6), 42)
        .round(3, sun(5), 45)  # sun(5) has no event_weather row
        .build()
    )


def test_sub_gauge_accepts_only_sub_gauges(ctx_builder):
    assert awards("sub_gauge", gauge_ctx(ctx_builder)) == [
        (1, "sub_gauge", sun(0)),
        (6, "sub_gauge", sun(1)),
        (7, "sub_gauge", sun(3)),
    ]


def test_sxs_does_not_earn_sub_gauge(ctx_builder):
    assert awards("sub_gauge", ctx_builder().round(2, sun(0), 30, gauge_class="SxS").build()) == []


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("rain", [(1, "rain", sun(0)), (2, "rain", sun(6))]),
        ("cold", [(1, "cold", sun(1))]),
        ("heat", [(1, "heat", sun(3))]),
        ("wind", [(1, "wind", sun(2)), (2, "wind", sun(2))]),
        ("all_weather", [(1, "all_weather", sun(3))]),
        ("mudder", [(2, "mudder", sun(6))]),
    ],
)
def test_weather_trophy_thresholds(ctx_builder, code, expected):
    assert awards(code, weather_ctx(ctx_builder)) == expected


def test_weather_details_record_the_measurement(ctx_builder):
    [rain] = [
        w
        for w in registry.evaluate_one(registry.get("rain"), weather_ctx(ctx_builder))
        if w.shooter_id == 2
    ]
    assert (rain.round_id, dict(rain.details)) == (7, {"precip_in": 0.5})


def test_mudder_needs_forty_in_the_rain(ctx_builder):
    ctx = (
        ctx_builder()
        .event(sun(0), precip_in=0.02)
        .event(sun(1), precip_in=0.0)
        .round(1, sun(0), 40)
        .round(2, sun(0), 39)
        .round(3, sun(1), 45)
        .build()
    )
    got = [
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_one(registry.get("mudder"), ctx)
    ]
    assert got == [(1, sun(0), 1)]


def test_weather_trophies_skip_events_without_weather(ctx_builder):
    ctx = weather_ctx(ctx_builder)
    for code in ("rain", "cold", "heat", "wind", "all_weather", "mudder"):
        assert all(w.shooter_id != 3 for w in registry.evaluate_one(registry.get(code), ctx))


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("sub_gauge", gauge_ctx, sun(1)),
        ("rain", weather_ctx, sun(2)),
        ("cold", weather_ctx, sun(0)),
        ("heat", weather_ctx, sun(2)),
        ("wind", weather_ctx, sun(1)),
        ("all_weather", weather_ctx, sun(2)),
        ("mudder", weather_ctx, sun(2)),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0
