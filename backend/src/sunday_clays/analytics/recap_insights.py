"""The weekly club email's "This week" lines (owner, 2026-10-04; amended 2026-10-11).

The email goes to people who never open the site, so only a vetted subset of the Sunday page's
stored insight rows is eligible (rendered with the named headline), and they share the pool with
the recap-only facts of `recap_facts`. Four to six lines a Sunday, one per type, nobody named
twice or named in the previous Sunday's recap, and a type is not repeated within 12 held Sundays
(unless fewer than four lines remain). Stateless: earlier weeks' picks are recomputed by replaying
the held regular Sundays in date order over a bounded horizon, so the same date always gives the
same picks.
"""

import functools
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Final

from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights import select as sel
from sunday_clays.analytics.insights.context import InsightFrames
from sunday_clays.analytics.insights.rank import RECENCY_TOP
from sunday_clays.analytics.insights.store import InsightRow
from sunday_clays.analytics.insights.templates import Segment, plain, render
from sunday_clays.analytics.insights.types import Scope
from sunday_clays.analytics.recap_facts import RecapFact

TARGETS_KIND: Final = "pf.targets-milestone"
MAX_PICKS: Final = 6
MIN_PICKS: Final = 4
NO_REPEAT_WEEKS: Final = 12
HORIZON: Final = 36  # held regular Sundays replayed, ending at the requested date

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


def _pick(
    pool: Sequence[RecapFact],
    recent: set[str],
    last_used: Mapping[str, int],
    previous_names: set[int],
    recent_texts: set[str],
) -> list[RecapFact]:
    """4-6 lines (R2): strongest first, one per type, nobody named twice or named last week.

    A type used in the previous 12 held Sundays is skipped; only if fewer than MIN_PICKS remain
    are the least recently used types let back in (nobody named last week, and never a sentence
    sent in the previous 12 weeks).
    """
    chosen: list[RecapFact] = []
    types: set[str] = set()
    named: set[int] = set()

    def take_if_fits(line: RecapFact) -> None:
        if (
            line.type in types
            or line.text in recent_texts
            or named & set(line.named_ids)
            or previous_names & set(line.named_ids)
        ):
            return
        chosen.append(line)
        types.add(line.type)
        named.update(line.named_ids)

    ordered = sorted(pool, key=_order)
    for line in ordered:
        if len(chosen) < MAX_PICKS and line.type not in recent:
            take_if_fits(line)
    skipped = sorted((x for x in ordered if x.type in recent), key=lambda x: last_used[x.type])
    for line in skipped:  # stable sort: ties keep the strongest first
        if len(chosen) < MIN_PICKS:
            take_if_fits(line)
    return sorted(chosen, key=_order)


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
    last_used: dict[str, int] = {}
    supersedes = functools.cache(supersedes)  # the registry lookup scans modules: ask once per kind
    for i, d in enumerate(horizon):
        window = history[-NO_REPEAT_WEEKS:]
        pool = [row_line(r) for r in candidates(rows, d, supersedes)]
        pool += facts_for(d) if facts_for is not None else []
        picked = _pick(
            pool,
            {x.type for week in window for x in week},
            last_used,
            {n for x in history[-1] for n in x.named_ids} if history else set(),
            {x.text for week in window for x in week},
        )
        history.append(picked)
        last_used.update({x.type: i for x in picked})
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
