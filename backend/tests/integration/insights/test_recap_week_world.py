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
    NO_REPEAT_WEEKS,
    recap_text_problems,
    week_picks,
)
from sunday_clays.analytics.steps.s60_insights import build_frames
from sunday_clays.api.routes.insights import held_dates, supersedes_of

WEEKS = 52
EMPTY_MAX = 0.20  # a week with no line at all stays rare (measured 8 of 52)
TWO_PLUS_SHARE = 0.5  # and most weeks carry at least two (measured 31 of 52)
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


def test_this_week_is_rarely_empty_and_usually_has_a_few_lines(world) -> None:
    """The fresh-types-only rules (no kind two weeks running) leave a thin week thin: with about
    two dozen types and twelve weeks of memory, four lines every week cannot hold."""
    days, lines, _ = world
    sizes = collections.Counter(len(lines[d]) for d in days)
    print(f"\nline counts over the last {WEEKS} regular Sundays: {sorted(sizes.items())}")
    assert max(sizes) <= MAX_PICKS
    assert sizes[0] <= EMPTY_MAX * len(days), sorted(sizes.items())
    assert sum(n for size, n in sizes.items() if size >= 2) >= TWO_PLUS_SHARE * len(days)


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


def test_no_type_is_on_the_page_two_weeks_running(world) -> None:
    """The owner's complaint was 'basically the same as last week': a kind (or a person) twice in
    a row. Each Sunday is replayed on its own, so this is measured over the fixture world, not
    forced for any data (the unit tests force it inside one replay)."""
    days, lines, _ = world
    for a, b in pairwise(days):
        assert not {x.type for x in lines[a]} & {x.type for x in lines[b]}, (a, b)
