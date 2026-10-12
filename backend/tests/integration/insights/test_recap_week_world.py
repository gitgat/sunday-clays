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
EMPTY_MAX = 2  # weeks with no line at all
THREE_PLUS_SHARE = 0.80  # weeks with 3 or more lines
FOUR_PLUS_SHARE = 0.50  # weeks with 4 or more lines: more than this share
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


DIGITS = re.compile(r"\d[\d,.]*")


def wording(x: RecapFact) -> str:
    """How the picker judges a repeat: a stored insight's numbers do not make it new."""
    return x.text if x.type in FACT_TYPES else DIGITS.sub("#", x.text)


def subject(x: RecapFact) -> tuple[str, tuple[int, ...], str] | None:
    return (x.type, x.named_ids, x.key) if x.named_ids or x.key else None


def test_this_week_is_usually_full_and_never_more_than_the_cap(world) -> None:
    """The owner's targets (2026-10-12): 3 or more lines in at least 80% of weeks, 4 or more in a
    majority, and at most 2 empty weeks. Measured on the fixture world's last 52 Sundays, each
    computed on its own the way the route does."""
    days, lines, _ = world
    sizes = collections.Counter(len(lines[d]) for d in days)
    table = ", ".join(f"{n} lines x{sizes[n]}" for n in range(MAX_PICKS + 1))
    print(f"\nline counts over the last {WEEKS} regular Sundays: {table}")
    assert max(sizes) <= MAX_PICKS
    assert sizes[0] <= EMPTY_MAX, sorted(sizes.items())
    assert sum(n for size, n in sizes.items() if size >= 3) >= THREE_PLUS_SHARE * len(days)
    assert sum(n for size, n in sizes.items() if size >= 4) > FOUR_PLUS_SHARE * len(days)


def test_each_week_has_one_line_per_type_and_nobody_twice(world) -> None:
    days, lines, _ = world
    for d in days:
        types = [x.type for x in lines[d]]
        assert len(types) == len(set(types)), (d, types)
        named = [n for x in lines[d] for n in x.named_ids]
        assert len(named) == len(set(named)), (d, named)


def test_rule_1_no_kind_is_on_the_page_two_weeks_running(world) -> None:
    """Each Sunday is replayed on its own, so this is measured over the fixture world (the unit
    tests force it inside one replay)."""
    days, lines, _ = world
    for a, b in pairwise(days):
        assert not {x.type for x in lines[a]} & {x.type for x in lines[b]}, (a, b)


def test_rule_2_no_kind_and_subject_repeats_within_twelve_weeks(world) -> None:
    days, lines, _ = world
    for i, d in enumerate(days):
        recent = {subject(x) for e in days[max(0, i - NO_REPEAT_WEEKS) : i] for x in lines[e]}
        recent.discard(None)
        assert not {subject(x) for x in lines[d]} & recent, d


def test_rule_3_nobody_is_named_in_two_consecutive_weeks(world) -> None:
    days, lines, _ = world
    for a, b in pairwise(days):
        before = {n for x in lines[a] for n in x.named_ids}
        assert not before & {n for x in lines[b] for n in x.named_ids}, (a, b)


def test_an_improvement_line_is_a_high_water_mark_never_a_shrinking_number(world) -> None:
    """Round 2 fix: once a person's step is said, only a higher step is said (the same step, or
    a lower one after the gain fell, would read as a decline). Each date is replayed alone, so this
    is measured across the 52 weeks."""
    days, lines, _ = world
    said: dict[int, list[int]] = collections.defaultdict(list)
    for d in days:
        for x in lines[d]:
            if x.type == "improvement":
                said[x.named_ids[0]].append(int(x.key.removeprefix("step:")))
    assert said, "the fixture world has improvement lines"
    for who, steps in said.items():
        assert steps == sorted(set(steps)), (who, steps)


def test_no_event_fact_is_said_twice_for_the_same_subject(world) -> None:
    """Improvement, coming_up and club_next are news once: not even 13 weeks later."""
    days, lines, _ = world
    seen: set[tuple[str, tuple[int, ...], str]] = set()
    for d in days:
        for x in lines[d]:
            if x.type in {"improvement", "coming_up", "club_next"}:
                assert subject(x) not in seen, (d, x.text)
                seen.add(subject(x))  # type: ignore[arg-type]


def test_no_sentence_repeats_within_twelve_weeks(world) -> None:
    """Exact words for every line; numbers aside for the stored insights, whose template carries
    them. (A recap fact such as 'a year ago this week: N shooters' is new content each week.)"""
    days, lines, _ = world
    for i, d in enumerate(days):
        recent = [x for e in days[max(0, i - NO_REPEAT_WEEKS) : i] for x in lines[e]]
        assert not {x.text for x in lines[d]} & {x.text for x in recent}, d
        assert not {wording(x) for x in lines[d]} & {wording(x) for x in recent}, d


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
