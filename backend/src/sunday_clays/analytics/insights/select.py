"""Selection (spec §3.4): which stored rows a page shows, in what order. Pure; the API calls it.

Rules, in order: page pool and expiry -> supersedes -> ranking -> one conditions kind per profile
-> one per family in `top` (the rest go to "More", capped at 30) -> page extras (pinned digest
line or recap, Sunday conditions card, home slots with one named story per shooter, kudos).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from sunday_clays.analytics.insights.rank import RECENCY_TOP, sundays_between
from sunday_clays.analytics.insights.store import InsightRow
from sunday_clays.analytics.insights.types import ROLLUP

TOP_SIZES = {
    "profile": 3,
    "sunday": 3,
    "home": 4,
    "club": 3,
    "leaderboards": 2,
    "records": 2,
    "stations": 2,
}
MORE_CAP = 30
MORE_CAP_BY_PAGE = {"stations": 8}  # pages whose More list is shorter than MORE_CAP
STATION_BEST = "pf.station-best"
PINNED_PROFILE = "pf.digest-line"
PINNED_HOME = "home.sunday-recap"
NEVER_NEW = frozenset({PINNED_PROFILE, PINNED_HOME})
PROFILE_CONDITIONS = frozenset(
    {"pf.wet-strength", "pf.weather-steady", "pf.best-temp", "pf.tough-days"}
)
SUNDAY_CONDITIONS = frozenset({"ev.rain-day"})  # cold and windy join when those kinds ship
HOME_SLOTS = ("field", "person", "milestone", "race_record")
HOME_SUNDAYS = 2  # home shows rows anchored to the last 2 held Sundays, or evergreen


@dataclass(frozen=True)
class KudosChip:
    shooter_id: int
    row: InsightRow


@dataclass(frozen=True)
class Feed:
    as_of: date | None
    pinned: InsightRow | None = None
    hero: InsightRow | None = None
    spotlight: InsightRow | None = None
    conditions: InsightRow | None = None
    top: tuple[InsightRow, ...] = ()
    kudos: tuple[KudosChip, ...] = ()
    more: tuple[InsightRow, ...] = ()
    n_more: int = 0


FALLBACK_VARIANT = "fallback"  # shown only when the profile has nothing else (spec §2.2.5)


def is_fallback(row: InsightRow) -> bool:
    return row.variant == FALLBACK_VARIANT


def not_expired(row: InsightRow, page: str, ref: date, held: Sequence[date]) -> bool:
    """A row leaves a page after that page's `expires` count of later held Sundays (spec §3.1)."""
    limit = row.expires.get(page)
    if limit is None or row.anchor_date is None:
        return True
    return sundays_between(row.anchor_date, ref, held) < limit


def _story_day(row: InsightRow) -> str | None:
    """The Sunday a row is about: its anchor, or an evergreen row's `day` param (ISO text).

    Comparing this, not the anchor alone, lets an evergreen profile row (the `pf.pb` profile
    variant) supersede an anchored one about the same Sunday (`pf.first-tier`, spec §3.4).
    """
    if row.anchor_date is not None:
        return row.anchor_date.isoformat()
    day = row.params.get("day")
    return None if day is None else str(day)


def _same_story(a: InsightRow, b: InsightRow) -> bool:
    if a.subject_id != b.subject_id:
        return False
    day_a, day_b = _story_day(a), _story_day(b)
    return day_a is not None and day_a == day_b


def supersede(
    rows: Sequence[InsightRow], supersedes: Callable[[str], frozenset[str]]
) -> list[InsightRow]:
    """Drop a row when another row about the same shooter/Sunday supersedes its kind."""
    return [
        r
        for r in rows
        if not any(r.kind in supersedes(o.kind) and _same_story(r, o) for o in rows if o is not r)
    ]


def ranked(
    rows: Iterable[InsightRow], score: Callable[[InsightRow], float] | None = None
) -> list[InsightRow]:
    key = score or (lambda r: r.rank_score)
    return sorted(rows, key=lambda r: (-key(r), r.key))


def one_per_family(rows: Sequence[InsightRow], n: int) -> tuple[list[InsightRow], list[InsightRow]]:
    top: list[InsightRow] = []
    rest: list[InsightRow] = []
    families: set[str] = set()
    for r in rows:
        if len(top) < n and r.family not in families:
            top.append(r)
            families.add(r.family)
        else:
            rest.append(r)
    return top, rest


def _more(
    rest: Sequence[InsightRow], cap: int | None = MORE_CAP
) -> tuple[tuple[InsightRow, ...], int]:
    """The first `cap` of the rest (all of them when `cap` is None) and how many there are."""
    return tuple(rest if cap is None else rest[:cap]), len(rest)


def kudos_chips(rows: Iterable[InsightRow], day: date) -> tuple[KudosChip, ...]:
    """One chip per shooter: their top kudos row whose kudos Sunday is `day` (uncapped, D10)."""
    best: dict[int, InsightRow] = {}
    for r in ranked(r for r in rows if r.kudos and r.kudos_sunday == day):
        sid = int(r.subject_id)
        best.setdefault(sid, r)
    return tuple(KudosChip(sid, r) for sid, r in best.items())


def feed_profile(
    rows: Sequence[InsightRow],
    shooter_id: int,
    ref: date,
    held: Sequence[date],
    supersedes: Callable[[str], frozenset[str]],
    more_cap: int | None = MORE_CAP,
) -> Feed:
    pool = [
        r
        for r in rows
        if r.subject_type == "shooter"
        and r.subject_id == str(shooter_id)
        and "profile" in r.pages
        and not_expired(r, "profile", ref, held)
    ]
    pinned = next((r for r in pool if r.kind == PINNED_PROFILE), None)
    candidates = ranked(r for r in supersede(pool, supersedes) if r.kind != PINNED_PROFILE)
    if any(not is_fallback(r) for r in candidates):
        candidates = [r for r in candidates if not is_fallback(r)]
    conditions = [r for r in candidates if r.kind in PROFILE_CONDITIONS]
    candidates = [r for r in candidates if r.kind not in PROFILE_CONDITIONS or r is conditions[0]]
    top, rest = one_per_family(candidates, TOP_SIZES["profile"])
    more, n_more = _more(rest, more_cap)
    return Feed(as_of=ref, pinned=pinned, top=tuple(top), more=more, n_more=n_more)


def feed_sunday(
    rows: Sequence[InsightRow], day: date, supersedes: Callable[[str], frozenset[str]]
) -> Feed:
    pool = [r for r in rows if r.anchor_date == day and "sunday" in r.pages]
    candidates = ranked(supersede(pool, supersedes), lambda r: r.base_score * RECENCY_TOP)
    conditions = next((r for r in candidates if r.kind in SUNDAY_CONDITIONS), None)
    candidates = [r for r in candidates if r is not conditions]
    top, rest = one_per_family(candidates, TOP_SIZES["sunday"])
    more, n_more = _more(rest)
    return Feed(
        as_of=day,
        conditions=conditions,
        top=tuple(top),
        kudos=kudos_chips(rows, day),
        more=more,
        n_more=n_more,
    )


def home_pool(rows: Sequence[InsightRow], ref: date, held: Sequence[date]) -> list[InsightRow]:
    recent = {d for d in held if d <= ref}
    last = sorted(recent)[-HOME_SUNDAYS:]
    return [
        r
        for r in rows
        if "home" in r.pages
        and (r.anchor_date is None or r.anchor_date in last)
        and not_expired(r, "home", ref, held)
    ]


def fill_home_slots(
    candidates: Sequence[InsightRow], taken_names: set[int]
) -> tuple[list[InsightRow], list[InsightRow]]:
    """One card per home slot (an empty slot takes the next best row of any slot), one named
    story per shooter, one per family."""
    chosen: list[InsightRow] = []
    families: set[str] = set()

    def fits(r: InsightRow) -> bool:
        return r.family not in families and not (set(r.named_shooter_ids) & taken_names)

    def take(r: InsightRow) -> None:
        chosen.append(r)
        families.add(r.family)
        taken_names.update(r.named_shooter_ids)

    for slot in HOME_SLOTS:
        pick = next((r for r in candidates if r.home_slot == slot and fits(r)), None)
        if pick is not None:
            take(pick)
    for r in candidates:
        if len(chosen) >= TOP_SIZES["home"]:
            break
        if r not in chosen and fits(r):
            take(r)
    rest = [r for r in candidates if r not in chosen]
    return chosen[: TOP_SIZES["home"]], rest


def feed_home(
    rows: Sequence[InsightRow],
    ref: date,
    held: Sequence[date],
    supersedes: Callable[[str], frozenset[str]],
    *,
    hero: InsightRow | None = None,
    spotlight: InsightRow | None = None,
) -> Feed:
    pool = supersede(home_pool(rows, ref, held), supersedes)
    pinned = next((r for r in pool if r.kind == PINNED_HOME and r.anchor_date == ref), None)
    candidates = ranked(
        r for r in pool if r.kind != PINNED_HOME and r is not hero and r is not spotlight
    )
    # One named story per shooter: the hero and "Shooter to know" names are taken first.
    taken = {
        sid for pick in (hero, spotlight) if pick is not None for sid in pick.named_shooter_ids
    }
    top, rest = fill_home_slots(candidates, taken)
    more, n_more = _more(rest)
    return Feed(
        as_of=ref,
        pinned=pinned,
        hero=hero,
        spotlight=spotlight,
        top=tuple(top),
        kudos=kudos_chips(rows, ref),
        more=more,
        n_more=n_more,
    )


def _edge(row: InsightRow) -> float:
    return float(row.params.get("mine", 0)) - float(row.params.get("field", 0))


def one_specialist_per_station(rows: Sequence[InsightRow]) -> list[InsightRow]:
    """Keep one `pf.station-best` row per station: the largest edge (mine - field), ties by
    rank score then subject id. Every other kind passes through. Pure."""
    best: dict[str, InsightRow] = {}
    for r in rows:
        if r.kind != STATION_BEST:
            continue
        station = str(r.params.get("station"))
        cur = best.get(station)
        if cur is None or _specialist_order(r) < _specialist_order(cur):
            best[station] = r
    return [r for r in rows if r.kind != STATION_BEST or best[str(r.params.get("station"))] is r]


def _specialist_order(r: InsightRow) -> tuple[float, float, str]:
    return (-_edge(r), -r.rank_score, r.subject_id)


def feed_page(
    rows: Sequence[InsightRow],
    page: str,
    ref: date,
    held: Sequence[date],
    supersedes: Callable[[str], frozenset[str]],
) -> Feed:
    """Club, leaderboards, records and stations: the page's own pool, top N, More."""
    pool = [r for r in rows if page in r.pages and not_expired(r, page, ref, held)]
    if page == "stations":
        pool = one_specialist_per_station(pool)
    candidates = ranked(supersede(pool, supersedes))
    top, rest = one_per_family(candidates, TOP_SIZES[page])
    more, n_more = _more(rest, MORE_CAP_BY_PAGE.get(page, MORE_CAP))
    return Feed(as_of=ref, top=tuple(top), more=more, n_more=n_more)


def is_rollup(row: InsightRow) -> bool:
    return row.variant == ROLLUP
