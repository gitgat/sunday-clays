"""The weekly club email's "This week" lines (owner, 2026-10-04; amended 2026-10-11 and 2026-10-12).

The email goes to people who never open the site, so only a vetted subset of the Sunday page's
stored insight rows is eligible (rendered with the named headline), and they share the pool with
the recap-only facts of `recap_facts`. Up to five lines a Sunday (MAX_PICKS), strongest first, one
per type, nobody named twice. Repeats are judged by content, not by kind (owner, 2026-10-12):

1. a type used in the previous held Sunday's recap is not used (a type may return after one week);
2. a (type, who or what it is about) used in any of the previous 12 held Sundays is skipped;
3. nobody named in the previous held Sunday's recap is named;
4. a sentence sent in the previous 12 weeks is not sent again, where a stored insight's sentence
   is compared with its numbers blanked ("20 Sundays since" is "21 Sundays since") and a recap
   fact's exactly, because its key already says what it is about. (Owner-approved, 2026-10-12:
   recurring recap facts may repeat with new numbers; see the spec amendment.)

Event facts are news once: coming_up and club_next rest for the whole replay (not the 12 weeks),
improvement is a high-water mark (only a step above the highest already said for that person), and
a streak line rests that person for 26 weeks. on_this_day, which has no subject to tell one
week from the next, rests 4 held Sundays after each use (ON_THIS_DAY_REST_WEEKS).

There is no fill: a week the rules leave short stays short. Stateless: earlier weeks' picks are
recomputed by replaying the held regular Sundays in date order over a bounded horizon, so the same
date always gives the same picks. Inside one date's replay the rules hold exactly; across dates
(each replayed alone from empty history) they hold as measured on the fixture world, see the
world test and the spec amendment.
"""

import functools
import re
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, Final

from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights import select as sel
from sunday_clays.analytics.insights.context import InsightFrames
from sunday_clays.analytics.insights.rank import RECENCY_TOP
from sunday_clays.analytics.insights.store import InsightRow
from sunday_clays.analytics.insights.templates import Segment, plain, render
from sunday_clays.analytics.insights.types import Scope
from sunday_clays.analytics.recap_facts import FACT_TYPES, RecapFact

TARGETS_KIND: Final = "pf.targets-milestone"
MAX_PICKS: Final = 5
NO_REPEAT_WEEKS: Final = 12
#: on_this_day is a weekly club fact with nothing to tell it from last week's, so after each use
#: it rests this many held regular Sundays (owner, 2026-10-12): used in week 0, back in week 5.
ON_THIS_DAY_REST_WEEKS: Final = 4
HORIZON: Final = 36  # held regular Sundays replayed, ending at the requested date
#: Event facts are news once: they rest for the whole replay, not just the 12-week window (a
#: milestone said 13 weeks ago is still said). Improvement is judged by its high-water mark
#: instead. A streak is news about a person, not a number, so it rests that person for half a year
#: whatever the count.
REST_WEEKS: Final[dict[str, int]] = {
    "coming_up": HORIZON,
    "club_next": HORIZON,
    "attendance_streak": 26,
}
HIGH_WATER_TYPES: Final = frozenset({"improvement"})  # only a higher step than ever said is news

#: Kinds (and variants) a reader who never visits the site can follow from the sentence alone.
#: Where a kind has a vague roll-up ("a mark", "their own high mark") only the single-shooter
#: variants are listed. Every Sunday-page kind appears here or in EXCLUDED (a test enforces it, so
#: a new kind forces a decision).
ELIGIBLE: Final[dict[str, frozenset[str]]] = {
    # Says the wait in Sundays and the score ("a round of 49 or better").
    "ev.drought-ended": frozenset({"one", "many"}),
    # Club level, names nobody; the sentence defines "typical" and gives the middle score.
    "ev.how-it-played": frozenset({"tough", "easy"}),
    # Only the field line: the "better in the rain" variants name shooters on a mixed kind.
    "ev.rain-day": frozenset({"field"}),
    # Club record, with the old record or the gap in the sentence. Not "tie": it says "level with".
    "ev.record-watch": frozenset({"new", "near"}),
    # Club level, names nobody; states the month it was last this way.
    "ev.toughest-since": frozenset({"tough", "easy"}),
    # Roll-ups name people with no number or length, so only single-shooter variants stay for
    # above-own-avg-streak, beat-field-streak, best-stretch and three-rising (the same rule as
    # average-milestone). The roll-up that remains below carries the fact itself.
    "pf.above-own-avg-streak": frozenset({""}),
    # The average and the mark are both in the sentence; the roll-up is too vague.
    "pf.average-milestone": frozenset({""}),
    "pf.beat-field-streak": frozenset({""}),
    "pf.best-stretch": frozenset({""}),
    # Only the score variant: the win and podium variants are the club newsletter's story.
    "pf.first-since": frozenset({"score"}),
    "pf.more-high-rounds": frozenset({""}),
    "pf.shooter-anniversary": frozenset({"", "rollup"}),
    # Only the look-ahead: the reached Sunday counts are the Events Attended milestone already.
    "pf.sunday-milestone": frozenset({"to_go"}),
    # The roll-up ("Up 3 Sundays straight: A and B.") never says what went up.
    "pf.three-rising": frozenset({""}),
    "pf.tier-run": frozenset({""}),
    # Club level, names nobody; says the Sundays and the score.
    "rec.drought-clock": frozenset({""}),
}

#: Sunday-page kinds left out of the email, with the reason.
EXCLUDED: Final[dict[str, str]] = {
    "ev.close-finish": "the club newsletter already shows the podium",
    "ev.new-faces": "the club newsletter already welcomes new shooters",
    "ev.top-score": "the club newsletter already shows the podium and top score",
    "ev.spotlight": "says 'their usual for a day like this', which only makes sense on the site",
    "ev.week-jump": "'Biggest jump: <Name>' ranks one shooter and never says how big the jump was",
    "pf.high-round-count": "opens with 'That was', which needs the score shown before it",
    "pf.beat-own-usual": "says 'their usual for a day like that': meaningless without the site",
    "pf.back-strong": "welcome-backs are the club newsletter's story (owner, 2026-10-05)",
    "ev.second-visit": "a second visit is a welcome-back, the club newsletter's new-shooter story",
    "pf.podium-run": "the club newsletter already shows the podium",
    "pf.career-first": "its only variant is a first podium, which the newsletter already shows",
    "pf.tied-best": "the club newsletter already lists personal bests, a tied one included",
    "pf.pb": "the club newsletter already lists personal bests",
    "pf.wins": "wins are the podium's story (the club newsletter's), and a ranking beyond it",
}

#: Kinds the email's Milestones section carries instead of "This week" (owner, 2026-10-05). The
#: sentences come from the engine's facts before roll-up (`milestone_sentences`), so every
#: crossing keeps its own single-shooter sentence with the number; this map classifies the kind
#: for the partition tests.
MILESTONE_KINDS: Final[dict[str, frozenset[str]]] = {
    TARGETS_KIND: frozenset({""}),
}

_BANNED: Final = re.compile(
    r"\b(you|your|yours|rating|skill|model|tier|level|chart|tap|see the"
    r"|bronze|silver|gold|platinum|diamond)s?\b|usual for a day like",
    re.IGNORECASE,
)
_ALLOWED_POLARITY: Final = frozenset({"positive", "neutral"})


def recap_text_problems(text: str) -> list[str]:
    """Words and phrases that only make sense for a reader of the site (R3)."""
    return [m.group(0) for m in _BANNED.finditer(text)]


def _prose(segments: Sequence[Segment]) -> str:
    """The sentence's own words: names are left out so a shooter surnamed Gold is not flagged."""
    return plain([s for s in segments if s["t"] != "shooter"])


def _eligible(r: InsightRow) -> bool:
    if r.variant not in ELIGIBLE.get(r.kind, frozenset()):
        return False
    if r.polarity not in _ALLOWED_POLARITY and r.named_shooter_ids:
        return False
    return not recap_text_problems(_prose(r.headline))


def candidates(
    rows: Sequence[InsightRow], day: date, supersedes: Callable[[str], frozenset[str]]
) -> list[InsightRow]:
    """The Sunday page's pool, ranked as it ranks them, narrowed to what the email can use."""
    pool = [r for r in rows if r.anchor_date == day and "sunday" in r.pages]
    ordered = sel.ranked(sel.supersede(pool, supersedes), lambda r: r.base_score * RECENCY_TOP)
    return [r for r in ordered if _eligible(r)]


def row_line(r: InsightRow) -> RecapFact:
    """A stored Sunday insight as a candidate line: its kind is its type, its rank its strength."""
    return RecapFact(
        r.kind, plain(r.headline), tuple(r.named_shooter_ids), r.base_score * RECENCY_TOP
    )


def _order(line: RecapFact) -> tuple[float, str, str]:
    return (-line.strength, line.type, line.text)


_DIGITS: Final = re.compile(r"\d[\d,.]*")


def _wording(line: RecapFact) -> str:
    """The sentence a repeat is judged by. A stored insight's template carries its numbers, so
    '19 Sundays since' and '20 Sundays since' are one sentence there. A recap fact says what it is
    about in its key, so only its exact words count."""
    return line.text if line.type in FACT_TYPES else _DIGITS.sub("#", line.text)


def _subject(line: RecapFact) -> tuple[str, tuple[int, ...], str] | None:
    """Who or what a line is about (its type with the shooters and milestone), or None if it
    is about nobody in particular (those are held back by their type alone)."""
    return (line.type, line.named_ids, line.key) if line.named_ids or line.key else None


def _step(line: RecapFact) -> int | None:
    """The whole-target step of an improvement line (key 'step:N')."""
    head, _, tail = line.key.partition(":")
    return int(tail) if head == "step" and tail.isdigit() else None


def _rested(line: RecapFact, resting: dict[str, set[Any]]) -> bool:
    """Event facts rest longer than the 12-week subject window (REST_WEEKS). A streak rests the
    person whatever the count: its key is ignored."""
    if line.type == "attendance_streak":
        return any(x[:2] == (line.type, line.named_ids) for x in resting[line.type])
    return _subject(line) in resting.get(line.type, ())


def _below_high_water(line: RecapFact, top: dict[tuple[str, tuple[int, ...]], int]) -> bool:
    step = _step(line)
    return (
        line.type in HIGH_WATER_TYPES
        and step is not None
        and step <= top.get((line.type, line.named_ids), 0)
    )


def _pick(pool: Sequence[RecapFact], history: Sequence[Sequence[RecapFact]]) -> list[RecapFact]:
    """Up to MAX_PICKS lines, strongest first, one per type, nobody twice (owner, 2026-10-12).

    A line is skipped when its type was in the previous held Sunday's recap, when anyone it names
    was named there, when its (type, who and what it is about) was used in the previous 12 held
    Sundays, or when its words (numbers aside) were. There is no fill: a thin week stays thin.
    """
    window = history[-NO_REPEAT_WEEKS:]
    last = history[-1] if history else []
    last_types = {x.type for x in last}
    rested_types = {x.type for week in history[-ON_THIS_DAY_REST_WEEKS:] for x in week} & {
        "on_this_day"
    }
    last_names = {n for x in last for n in x.named_ids}
    recent_subjects = {_subject(x) for week in window for x in week} - {None}
    resting = {
        t: {_subject(x) for week in history[-n:] for x in week if x.type == t} - {None}
        for t, n in REST_WEEKS.items()
    }
    top_step: dict[tuple[str, tuple[int, ...]], int] = {}
    for week in history:
        for x in week:
            step = _step(x)
            if x.type in HIGH_WATER_TYPES and step is not None:
                top_step[x.type, x.named_ids] = max(step, top_step.get((x.type, x.named_ids), 0))
    recent_texts = {_wording(x) for week in window for x in week}
    chosen: list[RecapFact] = []
    types: set[str] = set()
    named: set[int] = set()
    for line in sorted(pool, key=_order):
        names = set(line.named_ids)
        if (
            len(chosen) >= MAX_PICKS
            or line.type in types
            or line.type in last_types
            or line.type in rested_types
            or _wording(line) in recent_texts
            or _subject(line) in recent_subjects
            or _rested(line, resting)
            or _below_high_water(line, top_step)
            or names & named
            or names & last_names
        ):
            continue
        chosen.append(line)
        types.add(line.type)
        named |= names
    return chosen


def week_picks(
    rows: Sequence[InsightRow],
    held: Sequence[date],
    day: date,
    supersedes: Callable[[str], frozenset[str]],
    facts_for: Callable[[date], Sequence[RecapFact]] | None = None,
) -> list[RecapFact]:
    """The lines for `day`: replay up to HORIZON held regular Sundays from empty history.

    The pool of a Sunday is the eligible stored insights plus `facts_for(that Sunday)`.
    """
    horizon = [d for d in sorted(held) if d <= day][-HORIZON:]
    if not horizon or horizon[-1] != day:
        return []
    history: list[list[RecapFact]] = []
    supersedes = functools.cache(supersedes)  # the registry lookup scans modules: ask once per kind
    for d in horizon:
        pool = [row_line(r) for r in candidates(rows, d, supersedes)]
        pool += facts_for(d) if facts_for is not None else []
        history.append(_pick(pool, history))
    return history[-1]


def week_insights(
    rows: Sequence[InsightRow],
    held: Sequence[date],
    day: date,
    supersedes: Callable[[str], frozenset[str]],
    facts_for: Callable[[date], Sequence[RecapFact]] | None = None,
) -> list[str]:
    """Plain sentences for "This week"."""
    return [x.text for x in week_picks(rows, held, day, supersedes, facts_for)]


def milestone_sentences(fr: InsightFrames, day: date) -> list[tuple[int, str]]:
    """(shooter id, sentence) for each shooter who crossed a thousand-target mark on `day`.

    Built from the engine's own `pf.targets-milestone` facts (before roll-up), so two or more
    crossings on one Sunday each keep their own named sentence with the total; the stored roll-up
    ("New thousand-target marks: A, B and C.") has no numbers and is never used. Best first.
    """
    if fr.as_of is None:
        return []
    kind = registry.get(TARGETS_KIND)
    scope = Scope(sundays=frozenset({day}), as_of=fr.as_of)
    facts = sorted(
        (f for f in kind.evaluate(fr, scope) if f.anchor_date == day and f.variant == ""),
        key=lambda f: (-f.strength, f.subject_id),
    )
    template = kind.templates[""][0]
    out: list[tuple[int, str]] = []
    for fact in facts:
        segments = render(template, fact.params, fr.names)
        if not recap_text_problems(_prose(segments)):
            out.append((int(fact.subject_id), plain(segments)))
    return out
