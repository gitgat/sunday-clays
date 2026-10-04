"""Club milestone rules (Plan 19 §3.5.1) on hand-built frames."""

from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import club_milestones as cm

D0 = date(2026, 1, 4)


def sunday(i: int) -> date:
    return D0 + timedelta(weeks=i)


def world(
    regular: dict[int, list[int]],
    special: dict[int, list[int]] | None = None,
    not_held: tuple[int, ...] = (),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """regular/special: Sunday index -> shooter ids with one round each that day."""
    special = special or {}
    rounds = pd.DataFrame(
        [(sunday(i), s) for i, ids in regular.items() for s in ids],
        columns=["event_date", "shooter_id"],
    )
    appearances = pd.DataFrame(
        [(sunday(i), s) for days in (regular, special) for i, ids in days.items() for s in ids],
        columns=["event_date", "shooter_id"],
    )
    days = sorted({*regular, *special})
    calendar = pd.DataFrame(
        [(sunday(i), i not in not_held) for i in days], columns=["event_date", "results_complete"]
    )
    return rounds, appearances, calendar


@pytest.fixture(autouse=True)
def small_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cm,
        "THRESHOLDS",
        {"sundays_held": (2, 3), "clays_thrown": (100, 200), "shooters": (2, 3), "rounds": (3, 5)},
    )


def test_labels() -> None:
    assert cm.milestone_label("clays_thrown", 350_000) == "350,000 clays thrown"
    assert cm.milestone_label("sundays_held", 300) == "300 Sundays held"
    assert cm.milestone_label("shooters", 250) == "250 different shooters"
    assert cm.milestone_label("rounds", 10_000) == "10,000 rounds shot"


def test_crossing_dates_series_and_next() -> None:
    result = cm.compute_milestones(*world({0: [1], 1: [1, 2], 2: [1, 2, 3]}), sunday(2))
    assert [
        (r.event_date, r.rounds, r.clays_thrown, r.shooters, r.sundays_held) for r in result.series
    ] == [
        (sunday(0), 1, 50, 1, 1),
        (sunday(1), 3, 150, 2, 2),
        (sunday(2), 6, 300, 3, 3),
    ]
    crossed = {(c.metric, c.threshold): c.event_date for c in result.milestones}
    assert crossed == {
        ("sundays_held", 2): sunday(1),
        ("sundays_held", 3): sunday(2),
        ("clays_thrown", 100): sunday(1),
        ("clays_thrown", 200): sunday(2),
        ("shooters", 2): sunday(1),
        ("shooters", 3): sunday(2),
        ("rounds", 3): sunday(1),
        ("rounds", 5): sunday(2),
    }
    assert result.next == ()  # every metric is past the (patched) table


def test_newest_first_and_the_latest_tie_order() -> None:
    result = cm.compute_milestones(*world({0: [1], 1: [1, 2], 2: [1, 2, 3]}), sunday(2))
    assert [(c.metric, c.threshold) for c in result.milestones] == [
        ("sundays_held", 3),
        ("clays_thrown", 200),
        ("shooters", 3),
        ("rounds", 5),
        ("sundays_held", 2),
        ("clays_thrown", 100),
        ("shooters", 2),
        ("rounds", 3),
    ]
    assert result.latest == result.milestones[0]


def test_a_partial_results_sunday_dates_its_own_crossing() -> None:
    # Sunday 1 has scores but results_complete is false: clays and rounds still cross there.
    result = cm.compute_milestones(*world({0: [1], 1: [1, 2], 2: [3]}, not_held=(1,)), sunday(2))
    crossed = {(c.metric, c.threshold): c.event_date for c in result.milestones}
    assert crossed[("rounds", 3)] == sunday(1)
    assert crossed[("sundays_held", 2)] == sunday(2)  # held Sundays skip the partial one


def test_special_rows_add_to_held_and_shooters_only() -> None:
    plain = cm.compute_milestones(*world({0: [1], 2: [1]}), sunday(2))
    with_special = cm.compute_milestones(*world({0: [1], 2: [1]}, special={1: [1, 2]}), sunday(2))
    last_plain, last_special = plain.series[-1], with_special.series[-1]
    assert last_special.clays_thrown == last_plain.clays_thrown == 100
    assert last_special.rounds == last_plain.rounds == 2
    assert last_special.sundays_held == last_plain.sundays_held + 1
    assert last_special.shooters == last_plain.shooters + 1


def test_first_on_record() -> None:
    result = cm.compute_milestones(*world({0: [1, 2, 3]}), sunday(0))
    flagged = {(c.metric, c.threshold) for c in result.milestones if c.first_on_record}
    assert ("shooters", 2) in flagged
    assert ("rounds", 3) in flagged
    assert all(c.first_on_record for c in result.milestones)


def test_next_is_the_first_threshold_above_the_current_value() -> None:
    result = cm.compute_milestones(*world({0: [1]}), sunday(0))
    nexts = {n.metric: (n.threshold, n.current, n.remaining) for n in result.next}
    assert nexts == {
        "sundays_held": (2, 1, 1),
        "clays_thrown": (100, 50, 50),
        "shooters": (2, 1, 1),
        "rounds": (3, 1, 2),
    }


def test_a_value_equal_to_a_threshold_has_crossed_it() -> None:
    # Kills `>` in place of `>=`: exactly 100 clays crosses 100.
    result = cm.compute_milestones(*world({0: [1, 2]}), sunday(0))
    assert ("clays_thrown", 100) in {(c.metric, c.threshold) for c in result.milestones}


def test_nothing_on_or_before_as_of() -> None:
    result = cm.compute_milestones(*world({3: [1]}), sunday(1))
    assert result.milestones == ()
    assert result.latest is None
    assert result.series == ()


def test_as_of_cuts_the_data_no_leak() -> None:
    frames = world({0: [1], 1: [1, 2], 2: [1, 2, 3], 3: [4]})
    full = cm.compute_milestones(*frames, sunday(3))
    for i in range(4):
        cut = cm.compute_milestones(*frames, sunday(i))
        assert list(cut.milestones) == [m for m in full.milestones if m.event_date <= sunday(i)]
        assert cut.series == full.series[: i + 1]
        for n in cut.next:
            assert n.current == getattr(full.series[i], n.metric)
