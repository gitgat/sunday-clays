"""Proof reading (spec §5) and D4 coverage: each kind proves a headline number on its chart."""

import pandas as pd

from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights.proof import read_value
from sunday_clays.analytics.insights.registry import Kind
from sunday_clays.analytics.insights.types import Highlight, ProofHow, diff, distinct, lead

NO_HL = Highlight()

# Kinds that cannot prove any headline number on their linked chart yet, and why. Every other
# kind must have at least one check that is not `na`, and this list may only shrink (D4).
ALL_NA: dict[str, str] = {
    "cl.originals": "the chart shows rounds by year; the cohort count is on the first Sunday",
    "cl.weather-scoreboard": "the gap is one band against the average of all the other bands",
    "ev.new-faces": "first-timers are marked rows of the Results table, which has no value column",
    "ev.rain-day": "the head count is on the Sunday page, not on the linked chart",
    "ev.second-visit": "the count is of highlighted Results rows, which have no value column",
    "ev.toughest-since": "the headline quotes a month, not a number",
    "lb.new-leader": "the headline quotes no number; the board shows the leader first",
    "pf.charter-shooter": "the headline quotes a date, not a number",
    "pf.first-since": "`level` is the dashed reference line, not a chart value",
    "pf.gaining-on-field": "the gain is a difference of two windows; the yearly bars show the way",
    "pf.next-trophy": "trophy progress is on the achievements page, not on a chart",
    "pf.rating-high": "the rise is the highlighted point against the one 8 points earlier",
    "pf.top-of-club": "the headline quotes no number; the board shows the shooter first",
    "pf.trophy-rare": "the holder count is on the trophy's page, not the timeline",
    "pf.year-wrapped": "a context link: the numbers come from several profile charts",
    "rec.drought-clock": "`wait` counts Sundays with full results; the chart shows every Sunday",
    "rec.streak-chase": "the runs are in the streak tables on the records page",
}


def _proves_something(kind: Kind) -> bool:
    return any(check.how is not ProofHow.NA for check in kind.proof)


def test_every_kind_proves_a_number_or_says_why_not() -> None:
    registry.load_all()
    kinds = {kind.id: kind for kind in registry.all_kinds()}
    unproven = {kid for kid, kind in kinds.items() if not _proves_something(kind)}
    assert unproven <= ALL_NA.keys(), sorted(unproven - ALL_NA.keys())
    assert [kid for kid in ALL_NA if kid in kinds and _proves_something(kinds[kid])] == []


def test_diff_reads_the_gap_between_two_keyed_bars() -> None:
    table = pd.DataFrame({"precip_band": ["dry", "wet"], "value": [24.5, 18.0]})
    params = {"dry_key": "dry", "wet_key": "wet"}
    dry_minus_wet = diff("gap", key="dry_key", other="wet_key")
    assert read_value(dry_minus_wet, table, NO_HL, params) == 6.5
    flipped = diff("gap", key="wet_key", other="dry_key", absolute=True)
    assert read_value(flipped, table, NO_HL, params) == 6.5
    assert read_value(dry_minus_wet, table.head(1), NO_HL, params) is None


def test_lead_is_the_top_value_minus_the_next() -> None:
    table = pd.DataFrame({"shooter_id": [1, 2, 3], "value": [40, 52, 47]})
    assert read_value(lead("lead"), table, NO_HL, {}) == 5.0
    assert read_value(lead("lead"), table.head(1), NO_HL, {}) is None


def test_distinct_counts_the_highlighted_months() -> None:
    table = pd.DataFrame(
        {
            "event": ["2026-06-07", "2026-06-14", "2026-07-05", "2026-08-02"],
            "value": [40, 41, 42, 43],
            "month": ["2026-06", "2026-06", "2026-07", "2026-08"],
        }
    )
    hl = Highlight(keys=("2026-06", "2026-07"))
    assert read_value(distinct("months", "month"), table, hl, {}) == 2.0
