"""The Sunday Sheet (Plan 14): one issue per held Sunday, assembled from stored rows. Pure.

An issue's posts are the insights anchored on its Sunday (on the latest issue also Home's
evergreen rows and the profile-only rows that are news that Sunday, FRESH_EVERGREEN), one post per
trophy earned that day and the "On this day" look-backs. The feed takes the best post of every
feed type the issue has, fills up to FEED_CAP by score, and is interleaved so that no type runs
more than MAX_RUN in a row while another type is left. Everything else is "More from this
Sunday", grouped by family. The hero and spotlight picks lead the issue instead of being posts, and
Home's pinned recap is the headline's deck.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from sunday_clays.analytics.insights import select as sel
from sunday_clays.analytics.insights.rank import recency
from sunday_clays.analytics.insights.store import InsightRow
from sunday_clays.analytics.insights.templates import (
    Segment,
    fmt_full_date,
    fmt_int,
    natural_name,
)
from sunday_clays.analytics.yir import OnThisDayItem

PostType = Literal[
    "milestone", "improvement", "trophy", "conditions", "welcome", "on_this_day", "other"
]

FEED_CAP: Final = 10
MAX_RUN: Final = 2
NAMES_SHOWN: Final = 3
# Measured on the fx world: an anchored insight's base score is 8.7 / 12.5 / 18 / 24 at the
# 25th / 50th / 75th / 90th percentile, and the Sheet ranks anchored rows at base x 1.5.
TROPHY_SCORE: Final = 18.0  # a fresh trophy ranks with a median anchored story (12 x 1.5)
OTD_SCORE: Final = 9.0  # a look-back ranks with a light one (6 x 1.5)
NAMED_POLARITIES: Final = frozenset({"positive", "neutral"})

_MILESTONE: Final = (
    "pf.pb",
    "pf.season-best",
    "pf.career-first",
    "pf.first-since",
    "pf.sunday-milestone",
    "pf.targets-milestone",
    "pf.average-milestone",
    "pf.first-tier",
    "pf.shooter-anniversary",
    "ev.top-score",
)
_IMPROVEMENT: Final = (
    "pf.hot-form",
    "pf.rank-climb",
    "pf.up-on-usual",
    "pf.beat-own-usual",
    "pf.three-rising",
    "pf.year-up",
    "lb.most-improved",
    "lb.biggest-climb",
)
_CONDITIONS: Final = ("ev.how-it-played", "ev.toughest-since", "ev.rain-day", "ev.week-jump")
_WELCOME: Final = ("ev.new-faces", "ev.second-visit", "pf.back-strong")
KIND_TYPES: Final[Mapping[str, PostType]] = {
    **dict.fromkeys(_MILESTONE, "milestone"),
    **dict.fromkeys(_IMPROVEMENT, "improvement"),
    **dict.fromkeys(_CONDITIONS, "conditions"),
    **dict.fromkeys(_WELCOME, "welcome"),
}
# Profile-only evergreen kinds the spec lists as feed sources. On the latest issue a row posts when
# its date param (the Sunday it is about) is the issue Sunday, so it is news that Sunday.
FRESH_EVERGREEN: Final[Mapping[str, str]] = {
    "pf.season-best": "day",
    "pf.hot-form": "last",
    "pf.up-on-usual": "day",
    "pf.year-up": "day",
}
FEED_TYPES: Final[frozenset[PostType]] = frozenset(
    {"milestone", "improvement", "trophy", "conditions", "welcome", "on_this_day"}
)
FAMILY_LABELS: Final[Mapping[str, str]] = {
    "form": "Form",
    "streak": "Streaks",
    "milestone": "Milestones",
    "race": "The race",
    "record": "Records",
    "weather": "Weather and the day",
    "turnout": "Turnout",
    "newcomer": "New faces",
    "station": "Stations",
    "trophy": "Trophies",
    "recap": "Recaps",
    "on_this_day": "On this day",
}
_YEARS_AGO: Final[Mapping[int, str]] = {1: "One year", 2: "Two years", 3: "Three years"}


@dataclass(frozen=True)
class Award:
    """One trophy earned on the issue's Sunday (an `achievements_awarded` row with its name)."""

    shooter_id: int
    display_name: str
    code: str


@dataclass(frozen=True)
class TrophyInfo:
    """A trophy's catalog entry: `title` is "Name — Tier" as the Trophy Room writes it."""

    code: str
    title: str
    art_key: str
    metal: str | None


@dataclass(frozen=True)
class TrophyPost:
    code: str
    title: str
    art_key: str
    metal: str | None
    holders: tuple[tuple[int, str], ...]  # (shooter_id, "First Last"), by name


@dataclass(frozen=True)
class Post:
    post_key: str
    type: PostType
    family: str
    score: float
    headline: tuple[Segment, ...]
    named_shooter_ids: tuple[int, ...]
    row: InsightRow | None = None
    trophy: TrophyPost | None = None
    on_this_day: OnThisDayItem | None = None


@dataclass(frozen=True)
class MoreGroup:
    family: str
    label: str
    posts: tuple[Post, ...]


@dataclass(frozen=True)
class Issue:
    day: date
    number: int  # held Sundays up to and including this one
    previous: date | None
    next: date | None
    latest: bool
    headline: InsightRow | None
    recap: InsightRow | None
    spotlight: InsightRow | None
    feed: tuple[Post, ...]
    more: tuple[MoreGroup, ...]

    @property
    def posts(self) -> tuple[Post, ...]:
        return self.feed + tuple(p for group in self.more for p in group.posts)

    @property
    def post_keys(self) -> frozenset[str]:
        return frozenset(p.post_key for p in self.posts)


def post_type(kind: str) -> PostType:
    if kind.startswith("rec."):
        return "milestone"
    return KIND_TYPES.get(kind, "other")


def names_ok(row: InsightRow) -> bool:
    """Owner rule: a post that names a shooter is positive or neutral."""
    return not row.named_shooter_ids or row.polarity in NAMED_POLARITIES


def fresh_on(row: InsightRow, day: date) -> bool:
    """True for a FRESH_EVERGREEN row whose date param is `day`."""
    param = FRESH_EVERGREEN.get(row.kind)
    return param is not None and str(row.params.get(param)) == day.isoformat()


def trophy_key(code: str, day: date) -> str:
    return f"trophy:{code}:{day.isoformat()}"


def otd_key(day: date, years_ago: int) -> str:
    return f"otd:{day.isoformat()}:{years_ago}"


def synthetic_key_date(post_key: str) -> date | None:
    """The issue date a trophy or "On this day" key names; None for any other key."""
    try:
        if post_key.startswith("trophy:"):
            return date.fromisoformat(post_key.rsplit(":", 1)[1])
        if post_key.startswith("otd:"):
            return date.fromisoformat(post_key.split(":")[1])
    except (ValueError, IndexError):
        return None
    return None


def name_list(people: Sequence[tuple[int, str]], shown: int = NAMES_SHOWN) -> list[Segment]:
    """Names as "A", "A and B", "A, B and C" or "A, B, C and 2 more".

    Only ", " and " and " ever sit between two names (D9).
    """
    head = list(people[:shown])
    rest = len(people) - len(head)
    out: list[Segment] = []
    for i, (sid, name) in enumerate(head):
        if i > 0:
            last = i == len(head) - 1 and rest == 0
            out.append({"t": "text", "v": " and " if last else ", "})
        out.append({"t": "shooter", "v": name, "id": sid})
    if rest > 0:
        out.append({"t": "text", "v": f" and {rest} more"})
    return out


def trophy_headline(trophy: TrophyPost) -> list[Segment]:
    return [
        {"t": "trophy", "v": trophy.title},
        {"t": "text", "v": " unlocked by "},
        *name_list(trophy.holders),
        {"t": "text", "v": "."},
    ]


def otd_headline(item: OnThisDayItem) -> list[Segment]:
    """Reads "One year ago, on Sep 28, 2025, 31 shooters came out; the top score of 48 was shot
    by Amy Ace." Winners are named only beside the top score: positive, never against anyone. A
    Sunday without scores reads "... 18 shooters came out (attendance only)." as Home's card did."""
    ago = _YEARS_AGO.get(item.years_ago, f"{item.years_ago} years")
    out: list[Segment] = [
        {"t": "text", "v": f"{ago} ago, on "},
        {"t": "date", "v": fmt_full_date(item.event_date)},
    ]
    if not item.has_scores:
        if item.head_count is None:
            out.append({"t": "text", "v": ", a Sunday was shot; no scores were recorded."})
            return out
        noun = "shooter" if item.head_count == 1 else "shooters"
        out += [
            {"t": "text", "v": ", "},
            {"t": "num", "v": fmt_int(item.head_count)},
            {"t": "text", "v": f" {noun} came out (attendance only)."},
        ]
        return out
    noun = "shooter" if item.n_shooters == 1 else "shooters"
    out += [
        {"t": "text", "v": ", "},
        {"t": "num", "v": fmt_int(item.n_shooters)},
        {"t": "text", "v": f" {noun} came out"},
    ]
    if item.top_score is not None and item.winners:
        winners = [(w.shooter_id, natural_name(w.display_name)) for w in item.winners]
        out += [
            {"t": "text", "v": "; the top score of "},
            {"t": "num", "v": str(item.top_score)},
            {"t": "text", "v": " was shot by "},
            *name_list(winners),
        ]
    elif item.top_score is not None:
        out += [
            {"t": "text", "v": " and the top score was "},
            {"t": "num", "v": str(item.top_score)},
        ]
    out.append({"t": "text", "v": "."})
    return out


def insight_pool(
    rows: Iterable[InsightRow],
    day: date,
    *,
    latest: bool,
    supersedes: Callable[[str], frozenset[str]],
    exclude: frozenset[str],
) -> list[InsightRow]:
    """The issue's insight posts: rows anchored on `day`, plus (latest issue) Home's evergreen rows
    and the FRESH_EVERGREEN rows about `day`; never the recap, a negative named row, a superseded
    row or an `exclude` key."""
    candidates = [
        r
        for r in rows
        if (
            r.anchor_date == day
            or (latest and r.anchor_date is None and ("home" in r.pages or fresh_on(r, day)))
        )
        and r.kind != sel.PINNED_HOME
        and names_ok(r)
    ]
    return [r for r in sel.supersede(candidates, supersedes) if r.key not in exclude]


def insight_posts(pool: Iterable[InsightRow], day: date, held: Sequence[date]) -> list[Post]:
    """Ranked as on the Sunday page: base score x recency (1.5 for the issue's own Sunday)."""
    return [
        Post(
            post_key=r.key,
            type=post_type(r.kind),
            family=r.family,
            score=r.base_score * recency(r.anchor_date, day, held),
            headline=tuple(r.headline),
            named_shooter_ids=r.named_shooter_ids,
            row=r,
        )
        for r in pool
    ]


def trophy_posts(
    awards: Iterable[Award], catalog: Mapping[str, TrophyInfo], day: date
) -> list[Post]:
    """One post per trophy earned that day, naming everyone who earned it."""
    by_code: dict[str, set[tuple[int, str]]] = {}
    for a in awards:
        if a.code in catalog:
            by_code.setdefault(a.code, set()).add((a.shooter_id, natural_name(a.display_name)))
    posts: list[Post] = []
    for code in sorted(by_code):
        info = catalog[code]
        holders = tuple(sorted(by_code[code], key=lambda h: (h[1], h[0])))
        trophy = TrophyPost(code, info.title, info.art_key, info.metal, holders)
        posts.append(
            Post(
                post_key=trophy_key(code, day),
                type="trophy",
                family="trophy",
                score=TROPHY_SCORE,
                headline=tuple(trophy_headline(trophy)),
                named_shooter_ids=tuple(sid for sid, _ in holders),
                trophy=trophy,
            )
        )
    return posts


def otd_posts(items: Iterable[OnThisDayItem], day: date) -> list[Post]:
    """One post per look-back Sunday, with or without scores."""
    return [
        Post(
            post_key=otd_key(day, item.years_ago),
            type="on_this_day",
            family="on_this_day",
            score=OTD_SCORE,
            headline=tuple(otd_headline(item)),
            # Named only where the headline names them: beside a top score.
            named_shooter_ids=(
                tuple(w.shooter_id for w in item.winners)
                if item.has_scores and item.top_score is not None
                else ()
            ),
            on_this_day=item,
        )
        for item in items
    ]


def ranked(posts: Iterable[Post]) -> list[Post]:
    return sorted(posts, key=lambda p: (-p.score, p.post_key))


def interleave(
    posts: Sequence[Post], cap: int = FEED_CAP, max_run: int = MAX_RUN
) -> tuple[list[Post], list[Post]]:
    """(feed, rest) from `posts`, best first.

    The feed takes the best post of every feed type present (so a thin type such as "On this day"
    always shows), then the best of the rest up to `cap`. It is ordered greedily: each step takes
    the best chosen post that does not make a run of more than `max_run` of one type; when only
    that type is left, it takes it anyway. `rest` keeps the input order."""
    eligible = [p for p in posts if p.type in FEED_TYPES]
    seeds: dict[PostType, Post] = {}
    for p in eligible:
        seeds.setdefault(p.type, p)
    chosen = {p.post_key for p in list(seeds.values())[:cap]}
    for p in eligible:
        if len(chosen) >= cap:
            break
        chosen.add(p.post_key)
    pending = [p for p in eligible if p.post_key in chosen]
    feed: list[Post] = []
    while pending:
        run = feed[-max_run:]
        blocked = run[0].type if len(run) == max_run and len({p.type for p in run}) == 1 else None
        pick = next((p for p in pending if p.type != blocked), pending[0])
        feed.append(pick)
        pending.remove(pick)
    taken = {p.post_key for p in feed}
    return feed, [p for p in posts if p.post_key not in taken]


def group_more(rest: Iterable[Post]) -> list[MoreGroup]:
    """The rest by family, families in the order of their best post, posts best first."""
    by_family: dict[str, list[Post]] = {}
    for p in rest:
        by_family.setdefault(p.family, []).append(p)
    return [
        MoreGroup(family, FAMILY_LABELS.get(family, family.capitalize()), tuple(posts))
        for family, posts in by_family.items()
    ]


def assemble(
    day: date,
    held: Sequence[date],
    rows: Sequence[InsightRow],
    *,
    hero: InsightRow | None,
    spotlight: InsightRow | None,
    awards: Iterable[Award],
    catalog: Mapping[str, TrophyInfo],
    on_this_day: Iterable[OnThisDayItem],
    supersedes: Callable[[str], frozenset[str]],
) -> Issue:
    """The issue for `day`, which must be one of `held` (sorted)."""
    i = list(held).index(day)
    latest = i == len(held) - 1
    lead = hero if hero is not None and names_ok(hero) else None
    spot = spotlight if spotlight is not None and names_ok(spotlight) else None
    # The recap is the deck, not a post, so it skips `names_ok`: its template names shooters only
    # in the positive "topped the board" clause and keeps every negative in name-free field clauses.
    recap = next((r for r in rows if r.kind == sel.PINNED_HOME and r.anchor_date == day), None)
    exclude = frozenset(r.key for r in (lead, spot) if r is not None)
    pool = insight_pool(rows, day, latest=latest, supersedes=supersedes, exclude=exclude)
    posts = ranked(
        [
            *insight_posts(pool, day, held),
            *trophy_posts(awards, catalog, day),
            *otd_posts(on_this_day, day),
        ]
    )
    feed, rest = interleave(posts)
    return Issue(
        day=day,
        number=i + 1,
        previous=held[i - 1] if i > 0 else None,
        next=None if latest else held[i + 1],
        latest=latest,
        headline=lead,
        recap=recap,
        spotlight=spot,
        feed=tuple(feed),
        more=tuple(group_more(rest)),
    )
