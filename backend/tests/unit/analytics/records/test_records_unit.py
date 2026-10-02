from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from sunday_clays.analytics.records import (
    JumpRecord,
    RatingRecord,
    Records,
    RoundRecord,
    ShooterRecord,
    compute_records,
)
from sunday_clays.domain.round_type import RoundType

NAMES = {1: "Ace, Amy", 2: "Bee, Bob", 3: "Cy, Cal"}
ROUND_COLUMNS = [
    "round_id", "event_date", "shooter_id", "name_key", "display_name", "ordinal", "score",
    "gauge_class", "status", "shooter_status", "round_type", "field_median", "adjusted",
    "event_rank", "is_best_round", "percentile", "expected", "residual", "mu_before",
    "mu_after", "temp_f", "apparent_f", "precip_in", "wind_mph", "gust_mph", "wind_dir_deg",
    "cloud_pct", "condition", "gauge",
]  # fmt: skip
EVENT_COLUMNS = [
    "event_date", "round_type", "round_type_source", "head_count", "n_rounds", "n_shooters",
    "has_scores", "has_stations", "results_complete",
]  # fmt: skip
D = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(8)]


@dataclass
class World:
    """Minimal C7-shaped frames for records: rounds, events, rating history."""

    round_rows: list[dict[str, Any]] = field(default_factory=list)
    event_rows: dict[date, dict[str, Any]] = field(default_factory=dict)
    history_rows: list[dict[str, Any]] = field(default_factory=list)

    def event(
        self, day: date, *, round_type: str = "sporting", held: bool = True, scores: bool = True
    ) -> World:
        self.event_rows[day] = dict.fromkeys(EVENT_COLUMNS) | {
            "event_date": day,
            "round_type": round_type,
            "has_scores": scores,
            "results_complete": scores and held,
        }
        return self

    def shot(
        self, day: date, sid: int, score: int, *, ordinal: int = 1, adjusted: float | None = None
    ) -> World:
        if day not in self.event_rows:
            self.event(day)
        self.round_rows.append(
            dict.fromkeys(ROUND_COLUMNS)
            | {
                "round_id": len(self.round_rows) + 1,
                "event_date": day,
                "shooter_id": sid,
                "name_key": NAMES[sid].casefold().replace(",", ""),
                "display_name": NAMES[sid],
                "ordinal": ordinal,
                "score": score,
                "adjusted": adjusted,
                "shooter_status": "member",
                "round_type": self.event_rows[day]["round_type"],
                "gauge": "unspecified",
            }
        )
        return self

    def rating(self, sid: int, day: date, mu: float) -> World:
        self.history_rows.append({"shooter_id": sid, "event_date": day, "mu": mu, "var": 4.0})
        return self

    def records(self, as_of: date = D[-1], **kw: Any) -> Records:
        rounds = pd.DataFrame(self.round_rows, columns=ROUND_COLUMNS)
        rounds["adjusted"] = rounds["adjusted"].astype(float)
        events = pd.DataFrame(
            [self.event_rows[d] for d in sorted(self.event_rows)], columns=EVENT_COLUMNS
        )
        history = pd.DataFrame(self.history_rows, columns=["shooter_id", "event_date", "mu", "var"])
        return compute_records(rounds, events, history, as_of=as_of, **kw)


def test_highest_scores_order_by_value_then_earliest_date() -> None:
    w = World().shot(D[1], 1, 48).shot(D[2], 2, 50).shot(D[0], 3, 48)
    assert w.records().highest_scores == (
        RoundRecord(rank=1, shooter_id=2, display_name="Bee, Bob", event_date=D[2], value=50.0),
        RoundRecord(rank=2, shooter_id=3, display_name="Cy, Cal", event_date=D[0], value=48.0),
        RoundRecord(rank=2, shooter_id=1, display_name="Ace, Amy", event_date=D[1], value=48.0),
    )


def test_perfect_rounds_are_newest_first_and_capped_with_a_total() -> None:
    w = World().shot(D[0], 1, 50).shot(D[1], 2, 50).shot(D[1], 3, 49).shot(D[2], 3, 50)
    records = w.records(limit=2)
    assert [(r.shooter_id, r.event_date) for r in records.perfect_rounds] == [(3, D[2]), (2, D[1])]
    assert records.totals["perfect_rounds"] == 3
    everything = w.records(limit=None)
    assert [(r.shooter_id, r.event_date) for r in everything.perfect_rounds] == [
        (3, D[2]),
        (2, D[1]),
        (1, D[0]),
    ]


def test_biggest_adjusted_ignores_rounds_without_adjusted() -> None:
    w = World().shot(D[0], 1, 45, adjusted=9.5).shot(D[0], 2, 30, adjusted=-5.5).shot(D[1], 3, 50)
    assert [(r.shooter_id, r.value) for r in w.records().biggest_adjusted] == [(1, 9.5), (2, -5.5)]


def test_biggest_jump_needs_consecutive_scored_events() -> None:
    w = World()
    w.shot(D[0], 1, 20).shot(D[1], 1, 35).shot(D[3], 1, 49)  # D[1] -> D[3] skips D[2]
    w.shot(D[0], 2, 30).shot(D[1], 2, 31).shot(D[2], 2, 29).shot(D[3], 2, 40)
    w.shot(D[1], 2, 36, ordinal=2)  # the day's best round (36) is what counts
    w.event(D[4], scores=False)  # attendance-only events are not in the sequence
    w.shot(D[5], 2, 45)
    assert w.records().biggest_jumps == (
        JumpRecord(
            rank=1, shooter_id=1, display_name="Ace, Amy", event_date=D[1],
            prev_event_date=D[0], from_score=20, to_score=35, value=15.0,
        ),
        JumpRecord(
            rank=2, shooter_id=2, display_name="Bee, Bob", event_date=D[3],
            prev_event_date=D[2], from_score=29, to_score=40, value=11.0,
        ),
        JumpRecord(
            rank=3, shooter_id=2, display_name="Bee, Bob", event_date=D[1],
            prev_event_date=D[0], from_score=30, to_score=36, value=6.0,
        ),
        JumpRecord(
            rank=4, shooter_id=2, display_name="Bee, Bob", event_date=D[5],
            prev_event_date=D[3], from_score=40, to_score=45, value=5.0,
        ),
    )  # fmt: skip


def test_jump_uses_one_best_round_across_merged_aliases() -> None:
    w = World().shot(D[0], 1, 30).shot(D[1], 1, 33)
    w.shot(D[1], 1, 38)
    w.round_rows[-1]["name_key"] = "amy ace"  # a merged alias shot the day's best round
    assert [(j.prev_event_date, j.from_score, j.to_score) for j in w.records().biggest_jumps] == [
        (D[0], 30, 38)
    ]


def test_rounds_at_non_held_score_dates_still_set_records() -> None:
    w = World().shot(D[0], 1, 30).event(D[1], held=False).shot(D[1], 1, 50)
    records = w.records()
    assert [(r.event_date, r.value) for r in records.perfect_rounds] == [(D[1], 50.0)]
    assert [(j.event_date, j.value) for j in records.biggest_jumps] == [(D[1], 20.0)]
    assert [r.value for r in records.longest_streaks] == [1.0]


def test_most_events_counts_distinct_dates() -> None:
    w = World().shot(D[0], 1, 40).shot(D[0], 1, 30, ordinal=2).shot(D[1], 1, 41).shot(D[0], 2, 45)
    assert w.records().most_events == (
        ShooterRecord(rank=1, shooter_id=1, display_name="Ace, Amy", value=2.0),
        ShooterRecord(rank=2, shooter_id=2, display_name="Bee, Bob", value=1.0),
    )


def test_limit_caps_every_list_and_none_lists_everything() -> None:
    w = World()
    for sid in (1, 2, 3):
        w.shot(D[0], sid, 40 + sid).shot(D[1], sid, 30 + sid)
    default = w.records()
    assert (len(default.most_events), len(default.longest_streaks)) == (3, 3)
    assert len(default.highest_scores) == 6
    capped = w.records(limit=2)
    assert (len(capped.most_events), len(capped.longest_streaks), len(capped.highest_scores)) == (
        2,
        2,
        2,
    )
    assert capped.most_events == default.most_events[:2]
    assert capped.totals["highest_scores"] == 6
    assert capped.totals["most_events"] == 3
    everything = w.records(limit=None)
    assert len(everything.highest_scores) == 6
    assert everything.totals == default.totals


def test_a_cut_tie_reports_how_many_more_share_the_last_value() -> None:
    w = World()
    for sid in (1, 2, 3):
        w.shot(D[0], sid, 49)
    w.shot(D[1], 1, 50)
    cut = w.records(limit=2)
    assert [(r.rank, r.value) for r in cut.highest_scores] == [(1, 50.0), (2, 49.0)]
    assert cut.tied_more["highest_scores"] == 2  # two more 49s did not fit
    assert w.records(limit=4).tied_more["highest_scores"] == 0  # nothing cut
    assert w.records(limit=3).tied_more["highest_scores"] == 1
    assert w.records(limit=None).tied_more["highest_scores"] == 0


def test_the_cut_between_two_values_is_not_a_tie() -> None:
    w = World().shot(D[0], 1, 50).shot(D[0], 2, 49).shot(D[0], 3, 48)
    assert w.records(limit=2).tied_more["highest_scores"] == 0


def test_deceased_shooters_keep_their_records() -> None:
    w = World().shot(D[0], 1, 44).shot(D[0], 2, 50).shot(D[1], 2, 46)
    for row in w.round_rows:
        if row["shooter_id"] == 2:
            row["status"] = row["shooter_status"] = "deceased"
    records = w.records()
    assert records.highest_scores[0] == RoundRecord(
        rank=1, shooter_id=2, display_name="Bee, Bob", event_date=D[0], value=50.0
    )
    assert [(r.shooter_id, r.event_date) for r in records.perfect_rounds] == [(2, D[0])]
    assert records.most_events[0] == ShooterRecord(
        rank=1, shooter_id=2, display_name="Bee, Bob", value=2.0
    )


def test_longest_streaks_skip_non_held_events() -> None:
    w = World().shot(D[0], 1, 40).shot(D[1], 1, 40)
    w.event(D[2], held=False).shot(D[2], 2, 30)  # not held: neither extends nor breaks
    w.shot(D[3], 1, 40).shot(D[4], 2, 41)
    assert [(r.shooter_id, r.value) for r in w.records().longest_streaks] == [(1, 3.0), (2, 1.0)]


def _five_rounds(w: World, sid: int, *, days: list[date] | None = None) -> World:
    for day in days or D[:5]:
        w.shot(day, sid, 40)
    return w


def test_highest_ratings_take_each_shooters_peak() -> None:
    w = _five_rounds(_five_rounds(World(), 1), 2).shot(D[5], 1, 40)
    for day, mu in zip(D[:6], (30.0, 30.0, 30.0, 30.0, 35.004, 33.0), strict=True):
        w.rating(1, day, mu)
    for day, mu in zip(D[:5], (30.0, 30.0, 30.0, 30.0, 31.0), strict=True):
        w.rating(2, day, mu)
    assert w.records().highest_ratings == (
        RatingRecord(rank=1, shooter_id=1, display_name="Ace, Amy", event_date=D[4], value=35.0),
        RatingRecord(rank=2, shooter_id=2, display_name="Bee, Bob", event_date=D[4], value=31.0),
    )


def test_highest_ratings_need_five_rounds_and_only_count_from_the_fifth() -> None:
    w = _five_rounds(World(), 1)
    for day, mu in zip(D[:5], (50.0, 49.0, 48.0, 47.0, 40.0), strict=True):
        w.rating(1, day, mu)
    w.shot(D[0], 2, 45).shot(D[1], 2, 45).shot(D[2], 2, 45).shot(D[3], 2, 45)  # only 4 rounds
    for day in D[:4]:
        w.rating(2, day, 60.0)
    records = w.records()
    assert [(r.shooter_id, r.event_date, r.value) for r in records.highest_ratings] == [
        (1, D[4], 40.0)
    ]


def test_highest_ratings_count_second_rounds_toward_the_five() -> None:
    w = World()
    for day in D[:3]:
        w.shot(day, 1, 40).shot(day, 1, 41, ordinal=2)
        w.rating(1, day, 33.0)
    assert [(r.shooter_id, r.event_date) for r in w.records().highest_ratings] == [(1, D[2])]


def test_records_round_type_filter_limits_events() -> None:
    w = World().event(D[0], round_type="sporting").event(D[1], round_type="super_sporting")
    w.shot(D[0], 1, 44).shot(D[1], 1, 47).shot(D[1], 2, 40)
    records = w.records(round_types=(RoundType.SPORTING,))
    assert [(r.shooter_id, r.value) for r in records.highest_scores] == [(1, 44.0)]
    assert [(r.shooter_id, r.value) for r in records.most_events] == [(1, 1.0)]


def test_records_no_leak() -> None:
    def build(future: bool) -> World:
        w = World()
        for i, day in enumerate(D[:4]):
            w.shot(day, 1, 35 + i, adjusted=float(i)).shot(day, 2, 40 - i).rating(1, day, 30.0 + i)
        if future:
            for day in D[4:]:
                w.shot(day, 1, 50, adjusted=20.0).shot(day, 3, 49).rating(1, day, 45.0)
        return w

    assert build(False).records(as_of=D[3]) == build(True).records(as_of=D[3])


def test_records_tie_order_ignores_future_aliases() -> None:
    def build(future_alias: bool) -> World:
        w = World().shot(D[0], 1, 40).shot(D[0], 2, 40)
        if future_alias:
            w.shot(D[2], 2, 45)
            w.round_rows[-1]["name_key"] = "aaa bob"  # a merged alias first seen after as_of
        return w

    records = build(True).records(as_of=D[1])
    assert [r.shooter_id for r in records.highest_scores] == [1, 2]
    assert records == build(False).records(as_of=D[1])


def test_jump_and_rating_ties_end_on_shooter_id() -> None:
    w = World().shot(D[0], 3, 20).shot(D[1], 3, 30).shot(D[0], 1, 20).shot(D[1], 1, 30)
    for sid in (3, 1):
        for day in D[2:5]:
            w.shot(day, sid, 30)
        w.rating(sid, D[4], 33.0)
    for row in w.round_rows:
        row["name_key"] = "same"  # identical sort keys: only shooter_id can separate them
    records = w.records()
    assert [r.shooter_id for r in records.biggest_jumps] == [1, 3]
    assert [r.shooter_id for r in records.highest_ratings] == [1, 3]


def test_records_on_empty_frames_are_empty() -> None:
    records = World().records()
    assert set(records.totals) == {
        "highest_scores",
        "perfect_rounds",
        "biggest_adjusted",
        "biggest_jumps",
        "most_events",
        "longest_streaks",
        "highest_ratings",
    }
    assert set(records.totals.values()) == {0}
    assert set(records.tied_more.values()) == {0}
    assert records.highest_scores == ()
    assert records.biggest_jumps == ()
    assert records.longest_streaks == ()
    assert records.highest_ratings == ()


def test_since_defaults_to_none_and_echoes() -> None:
    w = World().shot(D[0], 1, 50).shot(D[1], 2, 48).shot(D[1], 1, 30, adjusted=4.0)
    assert w.records().since is None
    assert w.records(since=D[1]).since == D[1]


def test_since_cuts_round_and_attendance_records_inclusively() -> None:
    w = World().shot(D[0], 1, 50, adjusted=9.0).shot(D[1], 1, 48, adjusted=7.0)
    w.shot(D[2], 1, 46, adjusted=5.0).shot(D[1], 2, 50, adjusted=8.0).shot(D[2], 2, 40)
    records = w.records(since=D[1])
    assert [(r.shooter_id, r.event_date) for r in records.highest_scores] == [
        (2, D[1]),
        (1, D[1]),
        (1, D[2]),
        (2, D[2]),
    ]
    assert [(r.shooter_id, r.event_date) for r in records.perfect_rounds] == [(2, D[1])]
    assert [(r.shooter_id, r.value) for r in records.biggest_adjusted] == [
        (2, 8.0),
        (1, 7.0),
        (1, 5.0),
    ]
    assert [(r.shooter_id, r.value) for r in records.most_events] == [(1, 2.0), (2, 2.0)]
    assert [(r.shooter_id, r.value) for r in w.records().most_events] == [(1, 3.0), (2, 2.0)]
    assert records.since == D[1]


def test_since_counts_only_the_streak_inside_the_range() -> None:
    w = World()
    for day in D[:6]:
        w.shot(day, 1, 40)
    assert [r.value for r in w.records().longest_streaks] == [6.0]
    assert [r.value for r in w.records(since=D[3]).longest_streaks] == [3.0]


def test_since_needs_both_jump_sundays_inside_the_range() -> None:
    w = World().shot(D[1], 1, 20).shot(D[2], 1, 30).shot(D[3], 1, 45)
    assert [(j.prev_event_date, j.event_date) for j in w.records(since=D[2]).biggest_jumps] == [
        (D[2], D[3])
    ]
    assert [(j.prev_event_date, j.event_date) for j in w.records(since=D[3]).biggest_jumps] == []
    assert [j.event_date for j in w.records().biggest_jumps] == [D[3], D[2]]


def test_since_ratings_use_peaks_inside_the_range_with_lifetime_round_counts() -> None:
    w = World()
    for day, mu in zip(D[:6], (50.0, 49.0, 48.0, 40.0, 35.0, 30.0), strict=True):
        w.shot(day, 1, 40).rating(1, day, mu)  # 5th round ever falls before since
    for day in D[:4]:  # only 4 rounds ever up to as_of
        w.shot(day, 2, 40).rating(2, day, 60.0)
    early = w.records()
    assert [(r.shooter_id, r.event_date, r.value) for r in early.highest_ratings] == [
        (1, D[4], 35.0)
    ]
    records = w.records(since=D[5])
    assert [(r.shooter_id, r.event_date, r.value) for r in records.highest_ratings] == [
        (1, D[5], 30.0)
    ]
    mid = w.records(since=D[2], as_of=D[5])
    assert [(r.event_date, r.value) for r in mid.highest_ratings] == [(D[4], 35.0)]


def _seen(day: date, sid: int, kind: str) -> dict[str, Any]:
    return {
        "shooter_id": sid,
        "event_date": day,
        "kind": kind,
        "round_type": "sporting",
        "display_name": NAMES[sid],
        "shooter_status": "member",
        "name_key": NAMES[sid].casefold().replace(",", ""),
        "held": True,
    }


def test_most_sundays_and_longest_runs_count_special_sundays_but_scores_do_not() -> None:
    w = World().shot(D[0], 1, 40).shot(D[2], 1, 41).shot(D[0], 2, 30).shot(D[2], 2, 31)
    seen = pd.DataFrame(
        [
            _seen(D[0], 1, "regular"),
            _seen(D[0], 2, "regular"),
            _seen(D[1], 1, "special"),
            _seen(D[1], 3, "special"),
            _seen(D[2], 1, "regular"),
            _seen(D[2], 2, "regular"),
        ]
    )
    calendar = pd.DataFrame(
        [
            dict.fromkeys(EVENT_COLUMNS)
            | {
                "event_date": day,
                "round_type": "sporting",
                "has_scores": True,
                "results_complete": True,
                "kind": kind,
            }
            for day, kind in [(D[0], "regular"), (D[1], "special"), (D[2], "regular")]
        ]
    )
    base = w.records(as_of=D[2])

    records = w.records(as_of=D[2], appearances=seen, calendar=calendar)

    assert {(r.shooter_id, r.value) for r in records.most_events} == {(1, 3.0), (2, 2.0), (3, 1.0)}
    assert {(r.shooter_id, r.value) for r in records.longest_streaks} == {
        (1, 3.0),
        (2, 2.0),
        (3, 1.0),
    }
    assert records.highest_scores == base.highest_scores
    assert records.biggest_jumps == base.biggest_jumps
    assert records.perfect_rounds == base.perfect_rounds
