"""Row sources of the page anchors (spec §3.6.4) and the proof harness's reading of them."""

from datetime import date

import pandas as pd
import pytest

from sunday_clays.analytics.insights import anchors
from sunday_clays.analytics.insights.proof import (
    TENTH,
    WHOLE,
    _tolerance,
    chart_table,
    highlighted,
    proof_problems,
    read_value,
)
from sunday_clays.analytics.insights.templates import Dec1, Int, Shooter, Signed, T, named
from sunday_clays.analytics.insights.types import (
    ChartLink,
    Fact,
    Highlight,
    ProofCheck,
    ProofHow,
    Window,
    cell,
    count_rows,
    diff,
    max_before,
    mean_of,
    na,
    rank_of,
    rows_total,
    run_length,
    share,
    total,
)

LABEL = T()
NO_HL = Highlight()


def link(route: str, anchor: str, start: date, end: date, **params: str) -> ChartLink:
    return ChartLink(
        type="page",
        label=LABEL,
        window=Window(start, end),
        route=route,
        anchor=anchor,
        params=params,
    )


def world(make_world, sun):
    w = make_world()
    for i, (a, b) in enumerate([(30, 40), (35, 45), (44, 50), (41, 38)]):
        w.round(1, sun(i), a).round(2, sun(i), b)
    for i in range(12):
        w.round(1, sun(4 + i), 30 + i)
    w.rating(1, sun(1), 24.0).rating(1, sun(3), 25.5)
    w.station(1, sun(0), 1, 6).station(2, sun(0), 1, 7).station(1, sun(1), 2, 8)
    return w.frames()


def test_profile_anchors_read_the_shooters_history(make_world, sun):
    fr = world(make_world, sun)
    start, end = sun(0), sun(20)
    profile = "/shooters/1"
    trend = anchors.trend_rows(fr, link(profile, "trend", start, end))
    assert list(trend["score"][:4]) == [30, 35, 44, 41]
    assert trend["pb"].iloc[3] == 44
    assert trend["roll10"].notna().sum() >= 1
    assert anchors.trend_rows(fr, link("/shooters/999", "trend", start, end)).empty
    assert anchors.rating_rows(fr, link(profile, "rating", start, end))["value"].tolist() == [
        24.0,
        25.5,
    ]
    cal = anchors.calendar_rows(fr, link(profile, "cal", start, end))
    assert cal["month"].iloc[0] == "2024-01"
    assert len(anchors.finishes_rows(fr, link(profile, "finishes", start, end))) == 16
    assert len(anchors.tough_days_rows(fr, link(profile, "tough-days", start, end))) <= 4
    learn = anchors.learning_rows(fr, link(profile, "learn", start, end))
    assert list(learn.columns) == ["key", "value", "club"]


def test_sunday_records_and_leaderboard_anchors(make_world, sun):
    fr = world(make_world, sun)
    start, end = sun(0), sun(20)
    results = anchors.results_rows(fr, link(f"/events/{sun(2).isoformat()}", "results", start, end))
    assert results["score"].tolist() == [50, 44]
    highest = anchors.highest_rows(fr, link("/records", "rec-highest", start, end))
    assert set(highest["value"]) == {50}
    assert highest["perfect"].tolist() == [50]
    streaks = anchors.streak_rows(fr, link("/records", "rec-streaks", start, end))
    assert set(streaks["shooter_id"]) == {1, 2}
    points = anchors.season_points_rows(
        fr, link("/race", "race-bars", start, end, at=sun(3).isoformat())
    )
    assert points["rank"].iloc[0] == 1
    assert anchors.season_points_rows(fr, link("/race", "race-bars", start, end)).shape[1] == 3
    newcomers = anchors.newcomer_rows(fr, link("/club", "new", start, end))
    assert list(newcomers.columns) == ["year", "value", "returned"]
    board = anchors.board_rows(fr, link("/leaderboards", "lb-board", start, end))
    assert list(board.columns) == ["shooter_id", "value", "rank"]
    stations = anchors.station_rows(fr, link("/stations", "sthit", start, end))
    assert stations["station"].tolist() == ["1", "2"]
    firsts = anchors.first_round_rows(fr, link("/club", "first-rounds", start, end))
    assert list(firsts.columns) == ["score", "value"]
    assert not firsts.empty
    assert anchors.page_rows_unavailable(fr, link("/club", "first-rounds", start, end)).empty


def test_chart_table_uses_the_anchor_source(make_world, sun):
    fr = world(make_world, sun)
    table = chart_table(link("/stations", "sthit", sun(0), sun(20)), fr, None)
    assert table["station"].tolist() == ["1", "2"]


def test_highlight_masks_and_readers():
    table = pd.DataFrame(
        {
            "event": ["2026-06-07", "2026-06-14", "2026-06-21", "2026-06-28"],
            "shooter_id": [1, 1, 2, 2],
            "key": ["a", "b", "c", "d"],
            "value": [10.0, 20.0, 30.0, 40.0],
        }
    )
    both = Highlight(dates=(date(2026, 6, 21), date(2026, 6, 28)), shooter_ids=(2,))
    assert highlighted(table, both).tolist() == [False, False, True, True]
    span = Highlight(span=(date(2026, 6, 14), date(2026, 6, 21)))
    assert highlighted(table, span).tolist() == [False, True, True, False]
    assert highlighted(table, Highlight(shooter_ids=(1,))).tolist() == [True, True, False, False]
    keyed = Highlight(keys=("b", "c"))
    assert highlighted(table, keyed).tolist() == [False, True, True, False]
    assert highlighted(table.drop(columns="key"), keyed).tolist() == [False] * 4

    params = {"day": date(2026, 6, 14), "who": 2}
    assert read_value(count_rows("n"), table, keyed, {}) == 2.0
    assert read_value(rows_total("n"), table, keyed, {}) == 4.0
    assert read_value(total("v"), table, keyed, {}) == 50.0
    assert read_value(mean_of("v"), table, keyed, {}) == 25.0
    assert read_value(mean_of("v"), table, Highlight(keys=("zzz",)), {}) is None
    two_in_a_row = Highlight(dates=(date(2026, 6, 14), date(2026, 6, 21)))
    assert read_value(run_length("v"), table, two_in_a_row, {}) == 2.0
    assert read_value(max_before("v"), table, two_in_a_row, {}) == 10.0
    assert read_value(max_before("v"), table, Highlight(dates=(date(2026, 6, 7),)), {}) is None
    assert read_value(rank_of("v", key="day"), table, keyed, params) == 3.0
    assert read_value(rank_of("v", key="who"), table, keyed, params) == 2.0
    assert read_value(rank_of("v", key="day"), table.head(1), keyed, params) is None
    assert read_value(share("v", threshold=25.0), table, keyed, {}) == 50.0


def fact_of(params):
    return Fact(
        subject_id="1", anchor_date=None, variant="", pages=frozenset(), params=params, strength=1.0
    )


def test_read_value_edge_cases():
    table = pd.DataFrame({"shooter_id": [1, 2], "value": [-3.0, None], "key": ["a", "b"]})
    assert read_value(cell("n"), table, Highlight(shooter_ids=(1,)), {}) == -3.0
    assert read_value(cell("n", absolute=True), table, Highlight(shooter_ids=(1,)), {}) == 3.0
    assert read_value(cell("n"), table, Highlight(shooter_ids=(2,)), {}) is None
    assert read_value(diff("n", key="a", other="b"), table, NO_HL, {"a": "a", "b": "b"}) is None
    assert read_value(na("n", "why"), table, NO_HL, {}) is None
    open_diff = ProofCheck("n", ProofHow.DIFF, "value")
    assert read_value(open_diff, table, NO_HL, {}) is None
    no_key = pd.DataFrame({"value": [1.0, 2.0]})
    assert read_value(cell("n", key="k"), no_key, NO_HL, {"k": "x"}) == 2.0
    assert read_value(rank_of("n", key="k"), table.head(0), NO_HL, {"k": 1}) is None


def test_chart_table_needs_a_spec_for_an_explorer_link(make_world, sun):
    fr = world(make_world, sun)
    bad = ChartLink(type="explorer", label=LABEL, window=Window(sun(0), sun(1)))
    with pytest.raises(ValueError, match="needs a spec"):
        chart_table(bad, fr, None)


def test_slot_tolerance_follows_the_slot_kind(good):
    kind = good(
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        " ",
                        Int("n"),
                        " ",
                        Signed("a", 0),
                        " ",
                        Signed("b"),
                        " ",
                        Dec1("d"),
                        ".",
                    ),
                    you=named(
                        "You ", Int("n"), " ", Signed("a", 0), " ", Signed("b"), " ", Dec1("d"), "."
                    ),
                ),
            )
        },
    )
    assert _tolerance(kind, "n") == WHOLE
    assert _tolerance(kind, "a") == WHOLE
    assert _tolerance(kind, "b") == TENTH
    assert _tolerance(kind, "d") == TENTH
    assert _tolerance(kind, "unknown") == TENTH


def test_proof_problems_reports_each_kind_of_miss(good, make_world, sun):
    fr = world(make_world, sun)
    hit = ChartLink(
        type="page",
        label=LABEL,
        window=Window(sun(0), sun(20)),
        route="/stations",
        anchor="sthit",
        highlight=Highlight(keys=("1",)),
    )
    kind = good(chart=lambda fact: hit, proof=(cell("n"), cell("m"), cell("q"), na("z", "why")))
    fact = fact_of({"n": 75.0, "m": 81.25})
    problems = proof_problems(kind, fact, fr, None)
    assert len(problems) == 1
    assert problems[0].startswith("n: headline 75.0 vs chart")
    text = fact_of({"n": "x"})
    assert proof_problems(kind, text, fr, None) == ["n: not a number ('x')"]
    empty = ChartLink(
        type="page",
        label=LABEL,
        window=Window(sun(0), sun(20)),
        route="/stations",
        anchor="sthit",
        highlight=Highlight(keys=("9",)),
    )
    kind2 = good(chart=lambda fact: empty, proof=(cell("n"),))
    missing = fact_of({"n": 1.0})
    assert proof_problems(kind2, missing, fr, None) == ["n: the chart has no value for it"]


def test_empty_windows_keep_their_columns(make_world, sun):
    fr = world(make_world, sun)
    far = date(2031, 1, 6)
    profile = "/shooters/1"
    cases = [
        (anchors.rating_rows, profile, "rating", "value"),
        (anchors.calendar_rows, profile, "cal", "value"),
        (anchors.finishes_rows, profile, "finishes", "value"),
        (anchors.tough_days_rows, profile, "tough-days", "value"),
        (anchors.results_rows, f"/events/{far.isoformat()}", "results", "score"),
    ]
    for fn, route, anchor, column in cases:
        table = fn(fr, link(route, anchor, far, far))
        assert table.empty
        assert column in table.columns
        assert read_value(cell("p", column), table, NO_HL, {}) is None


def test_span_highlight_with_shooters_is_an_and():
    table = pd.DataFrame(
        {
            "event": ["2026-06-07", "2026-06-14", "2026-06-21"],
            "shooter_id": [1, 2, 1],
            "value": [1.0, 2.0, 3.0],
        }
    )
    hl = Highlight(span=(date(2026, 6, 7), date(2026, 6, 14)), shooter_ids=(1,))
    assert highlighted(table, hl).tolist() == [True, False, False]


def test_rank_of_a_missing_value_is_unknown():
    table = pd.DataFrame({"shooter_id": [1, 2], "value": [None, 5.0]})
    assert read_value(rank_of("who", "value", key="who"), table, NO_HL, {"who": 1}) is None


def test_tough_days_and_rolling_values_are_exact(make_world, sun):
    fr = world(make_world, sun)
    profile = "/shooters/1"
    trend = anchors.trend_rows(fr, link(profile, "trend", sun(0), sun(20)))
    assert trend["roll10"].iloc[9] == pytest.approx(34.5)
    assert len(anchors.tough_days_rows(fr, link(profile, "tough-days", sun(0), sun(20)))) == 0


def test_race_points_follow_the_links_period(make_world, sun):
    fr = world(make_world, sun)
    start, end = sun(0), sun(20)

    def points(**params: str) -> dict[int, int]:
        rows = anchors.season_points_rows(fr, link("/race", "race-bars", start, end, **params))
        return dict(zip(rows["shooter_id"], rows["value"], strict=True))

    everything = points(period="all_time", at=sun(15).isoformat())
    last_8 = points(period="season", at=sun(15).isoformat())
    assert sum(last_8.values()) < sum(everything.values())  # the first Sundays aged out
    assert points(at=sun(15).isoformat()) == points(period="rolling_12", at=sun(15).isoformat())
    assert set(points(period="ytd", at=sun(15).isoformat())) <= set(everything)


def test_station_rows_list_a_lettered_station_after_its_number(make_world, sun):
    w = make_world()
    w.round(1, sun(0), 30)
    w.station(1, sun(0), 10, 8).station(1, sun(0), "7A", 6).station(1, sun(0), 7, 4)
    w.station(1, sun(0), 8, 8)
    fr = w.frames()
    rows = anchors.station_rows(fr, link("/stations", "sthit", sun(0), sun(20)))
    assert rows["station"].tolist() == ["7", "7A", "8", "10"]
    assert rows["value"].tolist() == [50.0, 75.0, 100.0, 100.0]
