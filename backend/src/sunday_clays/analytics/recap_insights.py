"""The weekly club email's "This week" insights (owner, 2026-10-04).

The email goes to people who never open the site, so only a vetted subset of the Sunday page's
stored insight rows is eligible, rendered with the named headline, three to five per Sunday, and a
kind is not repeated within 12 held Sundays. Stateless: earlier weeks' picks are recomputed by
replaying the held regular Sundays in date order over a bounded horizon, so the same date always
gives the same picks.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Final

from sunday_clays.analytics.insights import select as sel
from sunday_clays.analytics.insights.rank import RECENCY_TOP
from sunday_clays.analytics.insights.store import InsightRow
from sunday_clays.analytics.insights.templates import Segment, plain

MAX_PICKS: Final = 5
MIN_PICKS: Final = 3
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
    # Not the first-timers list: a second visit is a returning-guest story.
    "ev.second-visit": frozenset({"", "many"}),
    # Club level, names nobody; states the month it was last this way.
    "ev.toughest-since": frozenset({"tough", "easy"}),
    # Roll-ups name people with no number or length, so only single-shooter variants stay for
    # above-own-avg-streak, beat-field-streak, best-stretch, podium-run and tied-best (the same rule
    # as average-milestone and career-first). The roll-ups that remain below carry the fact itself.
    "pf.above-own-avg-streak": frozenset({""}),
    # The average and the mark are both in the sentence; the roll-up is too vague.
    "pf.average-milestone": frozenset({""}),
    "pf.beat-field-streak": frozenset({""}),
    "pf.best-stretch": frozenset({""}),
    # Podium only: "top_third" would publish a named shooter's place below the podium, a ranking
    # beyond the one the email already has. The roll-up ("Career firsts today") says nothing.
    "pf.career-first": frozenset({"podium"}),
    "pf.first-since": frozenset({"win", "podium", "score"}),
    "pf.more-high-rounds": frozenset({""}),
    "pf.podium-run": frozenset({""}),
    "pf.shooter-anniversary": frozenset({"", "rollup"}),
    # Only the look-ahead: the reached Sunday counts are the Events Attended milestone already.
    "pf.sunday-milestone": frozenset({"to_go"}),
    "pf.three-rising": frozenset({"", "rollup"}),
    "pf.tied-best": frozenset({""}),
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
    "pf.pb": "the club newsletter already lists personal bests",
    "pf.wins": "wins are the podium's story (the club newsletter's), and a ranking beyond it",
}

#: Sunday-page kinds the email's Milestones section carries instead of "This week" (owner,
#: 2026-10-05): the Sunday's named headline, as the site renders it. Two or more crossings on one
#: Sunday are stored as one roll-up row (the single rows leave the Sunday page), so both variants.
MILESTONE_KINDS: Final[dict[str, frozenset[str]]] = {
    "pf.targets-milestone": frozenset({"", "rollup"}),
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


def milestone_insights(rows: Sequence[InsightRow], day: date) -> list[str]:
    """The Sunday's milestone sentences (named headlines), best ranked first."""
    pool = [
        r
        for r in rows
        if r.anchor_date == day
        and "sunday" in r.pages
        and r.variant in MILESTONE_KINDS.get(r.kind, frozenset())
        and not recap_text_problems(_prose(r.headline))
    ]
    return [plain(r.headline) for r in sel.ranked(pool, lambda r: r.base_score)]


def candidates(
    rows: Sequence[InsightRow], day: date, supersedes: Callable[[str], frozenset[str]]
) -> list[InsightRow]:
    """The Sunday page's pool, ranked as it ranks them, narrowed to what the email can use."""
    pool = [r for r in rows if r.anchor_date == day and "sunday" in r.pages]
    ordered = sel.ranked(sel.supersede(pool, supersedes), lambda r: r.base_score * RECENCY_TOP)
    return [r for r in ordered if _eligible(r)]


def _pick(
    ordered: Sequence[InsightRow], recent: set[str], last_used: Mapping[str, int]
) -> list[InsightRow]:
    chosen: list[InsightRow] = []
    families: set[str] = set()
    named: set[int] = set()

    def take_if_fits(r: InsightRow) -> None:
        if r.family in families or named & set(r.named_shooter_ids):
            return
        chosen.append(r)
        families.add(r.family)
        named.update(r.named_shooter_ids)

    for r in ordered:
        if len(chosen) < MAX_PICKS and r.kind not in recent:
            take_if_fits(r)
    skipped = sorted(
        (r for r in ordered if r.kind in recent), key=lambda r: last_used.get(r.kind, -1)
    )
    for r in skipped:
        if len(chosen) < MIN_PICKS:
            take_if_fits(r)
    return chosen


def week_picks(
    rows: Sequence[InsightRow],
    held: Sequence[date],
    day: date,
    supersedes: Callable[[str], frozenset[str]],
) -> list[InsightRow]:
    """The insights for `day`: replay up to HORIZON held regular Sundays from empty history."""
    horizon = [d for d in sorted(held) if d <= day][-HORIZON:]
    if not horizon or horizon[-1] != day:
        return []
    history: list[list[InsightRow]] = []
    last_used: dict[str, int] = {}
    for i, d in enumerate(horizon):
        recent = {r.kind for week in history[-NO_REPEAT_WEEKS:] for r in week}
        picked = _pick(candidates(rows, d, supersedes), recent, last_used)
        history.append(picked)
        last_used.update({r.kind: i for r in picked})
    return history[-1]


def week_insights(
    rows: Sequence[InsightRow],
    held: Sequence[date],
    day: date,
    supersedes: Callable[[str], frozenset[str]],
) -> list[str]:
    """Plain sentences, each the row's named headline."""
    return [plain(r.headline) for r in week_picks(rows, held, day, supersedes)]
