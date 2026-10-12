"""The recap's "This week" over the fixture world (2026-10-11): how full and how fresh it is.

The route gives each Sunday its lines from a stateless replay over the 36 held Sundays before it.
These tests do the same for the last 52 regular Sundays of the fixture world and check the
promises the email makes across the weeks.
"""

import collections
import re
from datetime import date
from itertools import pairwise

import pytest
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.store import insights_table, load_rows
from sunday_clays.analytics.recap_facts import FACT_TYPES, FactSource, RecapFact
from sunday_clays.analytics.recap_insights import (
    HORIZON,
    MAX_PICKS,
    MIN_PICKS,
    NO_REPEAT_WEEKS,
    recap_text_problems,
    week_picks,
)
from sunday_clays.analytics.steps.s60_insights import build_frames
from sunday_clays.api.routes.insights import held_dates, supersedes_of

WEEKS = 52
FULL_SHARE = 0.85  # the large majority of weeks carry at least MIN_PICKS lines
PRONOUNS = re.compile(r"\b(he|she|his|her|hers|him)\b|\bclass(es)?\b", re.IGNORECASE)


_BUILT: list[tuple[list[date], dict[date, list[RecapFact]], FactSource]] = []


@pytest.fixture
def world(fx_session: Session) -> tuple[list[date], dict[date, list[RecapFact]], FactSource]:
    """The last 52 regular Sundays and the lines the route would give each (club lines on).

    The fixture world never changes during a run, so the (slow) replay is done once.
    """
    if not _BUILT:
        _BUILT.append(_build(fx_session))
    return _BUILT[0]


def _build(
    fx_session: Session,
) -> tuple[list[date], dict[date, list[RecapFact]], FactSource]:
    held = held_dates(fx_session)
    t = insights_table()
    rows = load_rows(fx_session, t.c.pages.contains(["sunday"]))
    source = FactSource(build_frames(fx_session))
    memo: dict[date, list[RecapFact]] = {}

    def facts_for(d: date) -> list[RecapFact]:
        if d not in memo:
            memo[d] = source.on(d)
        return memo[d]

    lines: dict[date, list[RecapFact]] = {}
    for day in held[-WEEKS:]:
        window = set(held[: held.index(day) + 1][-HORIZON:])  # what the route loads
        lines[day] = week_picks(
            [r for r in rows if r.anchor_date in window], held, day, supersedes_of, facts_for
        )
    return held[-WEEKS:], lines, source


def test_this_week_is_full_on_the_large_majority_of_sundays(world) -> None:
    days, lines, _ = world
    sizes = collections.Counter(len(lines[d]) for d in days)
    print(f"\nline counts over the last {WEEKS} regular Sundays: {sorted(sizes.items())}")
    assert max(sizes) <= MAX_PICKS
    full = sum(n for size, n in sizes.items() if size >= MIN_PICKS)
    assert full >= FULL_SHARE * len(days), sorted(sizes.items())
    assert min(sizes) >= 2, sorted(sizes.items())  # a thin week still says something


def test_each_week_has_one_line_per_type_and_nobody_twice(world) -> None:
    days, lines, _ = world
    for d in days:
        types = [x.type for x in lines[d]]
        assert len(types) == len(set(types)), (d, types)
        named = [n for x in lines[d] for n in x.named_ids]
        assert len(named) == len(set(named)), (d, named)


def test_nobody_is_named_in_two_consecutive_weeks(world) -> None:
    days, lines, _ = world
    for a, b in pairwise(days):
        before = {n for x in lines[a] for n in x.named_ids}
        assert not before & {n for x in lines[b] for n in x.named_ids}, (a, b)


def test_no_sentence_repeats_within_twelve_weeks(world) -> None:
    days, lines, _ = world
    for i, d in enumerate(days):
        recent = {x.text for e in days[max(0, i - NO_REPEAT_WEEKS) : i] for x in lines[e]}
        assert not {x.text for x in lines[d]} & recent, d


def test_a_type_comes_back_inside_twelve_weeks_only_to_fill_the_week(world) -> None:
    """Fresh types come first: a recent type is on the page only when fewer than four fresh
    lines were left (so every week with a recent type has fewer than four fresh ones)."""
    days, lines, _ = world
    reused = 0
    for i, d in enumerate(days):
        recent = {x.type for e in days[max(0, i - NO_REPEAT_WEEKS) : i] for x in lines[e]}
        fresh = [x for x in lines[d] if x.type not in recent]
        if len(fresh) < len(lines[d]):
            reused += 1
            assert len(fresh) < MIN_PICKS, (d, [x.type for x in lines[d]])
    assert reused > 0, "the fixture world is rich enough to need the fill somewhere"


def test_the_fixture_world_uses_the_new_facts_and_every_line_reads_to_an_outsider(world) -> None:
    days, lines, source = world
    used = {x.type for d in days for x in lines[d]}
    available = {f.type for d in days for f in source.on(d)}
    assert available <= set(FACT_TYPES)
    assert len(available) >= 8, sorted(available)
    assert len(used & set(FACT_TYPES)) >= 6, sorted(used)
    names = source.fr.names
    for d in days:
        for x in lines[d]:
            prose = x.text
            for sid in x.named_ids:
                prose = prose.replace(names[sid], "")
            assert recap_text_problems(prose) == [], x.text
            assert not PRONOUNS.search(x.text), x.text
