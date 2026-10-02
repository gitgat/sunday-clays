"""Trophy kinds (spec §2.2.10). Dormant until the first trophy is awarded (§4.5)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import cast

from sunday_clays.analytics.achievements import registry as trophy_registry
from sunday_clays.analytics.achievements.context import STATION_COLUMNS, AchContext
from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    InsightFrames,
    add_months,
    evergreen_days,
    shot_recently,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
    Int,
    NameList,
    Shooter,
    T,
    TrophyName,
    named,
)
from sunday_clays.analytics.insights.types import (
    ROLLUP,
    ChartLink,
    Fact,
    Family,
    Highlight,
    HomeSlot,
    P,
    Polarity,
    Requires,
    Scope,
    SubjectType,
    Window,
    na,
    p_date,
    p_ids,
    p_int,
    p_str,
)
from sunday_clays.analytics.leaderboards import active_shooter_ids

RARE_HOLDERS = 5
RARE_SHARE = 0.05
RARE_WARMUP = 26  # trophies earned in the first 26 Sundays on record are not "rare" news
TROPHIES_LABEL = T(named(Shooter("s"), "'s trophies"), you=named("Your trophies"))
RESULTS_LABEL = T(named("Results for the Sunday"))


def trophy_name(code: str) -> str | None:
    """'Sharp Shooter (45 in one round)' for a tier, the name alone for a one-off."""
    found = trophy_registry.trophy(code)
    if found is None:
        return None
    name = found.achievement.name
    return name if found.tier is None else f"{name} ({found.tier.label})"


def trophy_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.results_chart(
            p_date(fact.params, "day"), p_ids(fact.params, "names"), label=RESULTS_LABEL
        )
    day = p_date(fact.params, "day")
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "trophytl",
        label=TROPHIES_LABEL,
        window=Window(add_months(day, -12), day),
        hl=Highlight(keys=(p_str(fact.params, "code"),)),
    )


# --- pf.trophy-rare ------------------------------------------------------------------------------


def _trophy_rare(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    """One Fact per shooter and Sunday: the rarest trophy they earned that day."""
    warm = fr.sundays[RARE_WARMUP].date if len(fr.sundays) > RARE_WARMUP else None
    awards = fr.awards.sort_values(["event_date", "shooter_id", "code"], kind="mergesort")
    holders: dict[str, set[int]] = {}
    found: dict[tuple[int, date], tuple[int, str, str]] = {}
    for day_key, batch in awards.groupby("event_date", sort=True):
        day = cast(date, day_key)
        # Everyone who first earns a trophy on the same Sunday shares one holder count, so a tie
        # is never ranked by shooter id.
        firsts: list[tuple[int, str]] = []
        for sid, code in zip(batch["shooter_id"], batch["code"], strict=True):
            sid, code = int(sid), str(code)
            if sid not in holders.setdefault(code, set()) and (sid, code) not in firsts:
                firsts.append((sid, code))
        for sid, code in firsts:
            holders[code].add(sid)
        if day not in scope.sundays or warm is None or day < warm:
            continue
        for sid, code in firsts:
            name = trophy_name(code)
            n = len(holders[code])
            if name is None or fr.profiles[sid].deceased or n > 2 * RARE_HOLDERS:
                continue
            if n > RARE_HOLDERS and n > RARE_SHARE * len(active_shooter_ids(fr.rounds, day)):
                continue
            if (sid, day) not in found or (n, code) < found[(sid, day)][:2]:
                found[(sid, day)] = (n, code, name)
    for (sid, day), (n, code, name) in sorted(found.items()):
        yield Fact(
            subject_id=str(sid),
            anchor_date=day,
            variant="first" if n == 1 else "",
            pages=frozenset({P.PROFILE, P.HOME}),
            params={"s": sid, "code": code, "trophy": name, "holders": n, "day": day},
            strength=RARE_HOLDERS / n,
            named_shooter_ids=(sid,),
        )


register(
    Kind(
        id="pf.trophy-rare",
        family=Family.TROPHY,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=False,  # spec §2.2.7: not a kudos kind (the 20 K kinds)
        expires={P.HOME: 3, P.PROFILE: 4},
        guard={"holders": RARE_HOLDERS, "share": RARE_SHARE},
        params=frozenset({"s", "code", "trophy", "holders", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        " earned ",
                        TrophyName("trophy"),
                        ", a trophy only ",
                        Count("holders", "shooter"),
                        " hold.",
                    ),
                    you=named(
                        "You earned ",
                        TrophyName("trophy"),
                        ", a trophy only ",
                        Count("holders", "shooter"),
                        " hold.",
                    ),
                ),
            ),
            "first": (
                T(
                    named(Shooter("s"), " is the first to earn ", TrophyName("trophy"), "."),
                    you=named("You are the first to earn ", TrophyName("trophy"), "."),
                ),
            ),
            ROLLUP: (T(named("Rare trophies earned today: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "Rare = 5 or fewer holders, or 5% or fewer of active shooters, when "
                        "it was earned. Shown for 4 Sundays."
                    ),
                    you=named(
                        "Rare = 5 or fewer holders, or 5% or fewer of active shooters, "
                        "when you earned it. Shown for 4 Sundays."
                    ),
                ),
            ),
            ROLLUP: (T(named("Each earned a trophy 5 or fewer shooters hold.")),),
        },
        labels=(TROPHIES_LABEL, RESULTS_LABEL),
        chart=trophy_chart,
        proof=(na("holders", "the trophy's holder count on the achievements page"),),
        evaluate=_trophy_rare,
        requires=Requires(trophy_awards=1),
    )
)


# --- pf.next-trophy ------------------------------------------------------------------------------

NEXT_UNITS = 2.0
NEXT_SHARE = 0.10
EFFORT = frozenset(
    {
        trophy_registry.Category.MILESTONE,
        trophy_registry.Category.CALENDAR,
        trophy_registry.Category.CONDITIONS,
    }
)


def _next_trophy(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    ctx = AchContext.from_frames(
        rounds=fr.rounds,
        events=fr.events,
        station_hits=fr.stations[list(STATION_COLUMNS)],
        rating_history=fr.rating,
        appearances=fr.appearances,
        calendar=fr.calendar,
    )
    active = [sid for sid, days in evergreen_days(fr, scope) if shot_recently(days, scope.as_of)]
    everyone = trophy_registry.progress_many(ctx, active, scope.as_of)
    for sid in active:
        best: tuple[float, trophy_registry.ProgressOut] | None = None
        for item in everyone[sid]:
            if item.next_threshold is None or item.next_level is None:
                continue
            if item.category not in EFFORT:
                continue  # a scoring target "2 short" would quote a score below it (D1)
            left = item.next_threshold - item.value
            if left <= 0 or (left > NEXT_UNITS and left > NEXT_SHARE * item.next_threshold):
                continue
            if best is None or left / item.next_threshold < best[0]:
                best = (left / item.next_threshold, item)
        if best is None:
            continue
        item = best[1]
        code = f"{item.code}:{item.next_level}"
        name = trophy_name(code)
        if name is None or item.next_threshold is None:
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={
                "s": sid,
                "code": code,
                "trophy": name,
                "left": round(item.next_threshold - item.value),
                "day": scope.as_of,
            },
            strength=1.0,
            named_shooter_ids=(sid,),
        )


register(
    Kind(
        id="pf.next-trophy",
        family=Family.TROPHY,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=2,
        anchored=False,
        guard={"units": NEXT_UNITS, "share": NEXT_SHARE},
        params=frozenset({"s", "code", "trophy", "left", "day"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"), " is ", Int("left"), " short of ", TrophyName("trophy"), "."
                    ),
                    you=named("You are ", Int("left"), " short of ", TrophyName("trophy"), "."),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "The next tier of a milestone, calendar or conditions trophy, 2 or "
                        "fewer steps away or within 10%, with a round in the last 8 weeks."
                    ),
                    you=named(
                        "The next tier of one of your milestone, calendar or conditions "
                        "trophies, 2 or fewer steps away or within 10%."
                    ),
                ),
            )
        },
        labels=(TROPHIES_LABEL,),
        chart=trophy_chart,
        proof=(na("left", "the progress bar on the achievements page"),),
        evaluate=_next_trophy,
        requires=Requires(trophy_awards=1),
    )
)
