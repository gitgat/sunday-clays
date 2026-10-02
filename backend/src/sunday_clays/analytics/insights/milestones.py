"""Milestone kinds (spec §2.2.1, §2.2.3): personal bests and the other "firsts"."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import (
    FINISH_FIELD,
    Day,
    InsightFrames,
    add_months,
    anchor_days,
    crossed,
    evergreen_days,
    finish_at,
    shot_recently,
)
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
    Int,
    MonthYear,
    NameList,
    Ordinal,
    Shooter,
    ShortDate,
    T,
    Year,
    named,
)
from sunday_clays.analytics.insights.types import (
    PROFILE,
    ROLLUP,
    ChartLink,
    Fact,
    Family,
    Highlight,
    HomeSlot,
    P,
    Polarity,
    Scope,
    SubjectType,
    Window,
    cell,
    na,
    p_date,
    p_ids,
    p_int,
    rows_total,
)
from sunday_clays.explorer.spec import Agg, Dim, Metric

PB_MIN_PRIOR_ROUNDS = 5  # C12 personal_bests rule, shared with Notables and the trophy
PB_PROFILE_SUNDAYS = 52  # the profile row shows the latest PB set in the last 52 held Sundays


def is_pb(day: Day) -> bool:
    """C12: the day's best round beats every round on earlier dates, with >= 5 earlier rounds."""
    return (
        day.prior_rounds >= PB_MIN_PRIOR_ROUNDS
        and day.prior_best is not None
        and day.score > day.prior_best
    )


def first_reached(days: Sequence[Day], score: int) -> date:
    """The first date the shooter shot `score` (the date an earlier best was set)."""
    return next(d.date for d in days if d.score == score)


def _pb_fact(days: Sequence[Day], i: int, old: int, *, variant: str, pages: frozenset[P]) -> Fact:
    day = days[i]
    return Fact(
        subject_id=str(day.shooter_id),
        anchor_date=day.date if variant != PROFILE else None,
        variant=variant,
        pages=pages,
        params={
            "s": day.shooter_id,
            "new": day.score,
            "old": old,
            "old_date": first_reached(days[:i], old),
            "day": day.date,
        },
        strength=1 + (day.score - old) / 2,
        named_shooter_ids=(day.shooter_id,),
    )


def _pb(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        old = days[i].prior_best
        if is_pb(days[i]) and old is not None:
            yield _pb_fact(days, i, old, variant="", pages=frozenset({P.SUNDAY, P.HOME}))
    for _sid, days in evergreen_days(fr, scope):
        latest = next((j for j in range(len(days) - 1, -1, -1) if is_pb(days[j])), None)
        if latest is None:
            continue
        old = days[latest].prior_best
        recent = fr.held_between(days[latest].date, scope.as_of) < PB_PROFILE_SUNDAYS
        if old is not None and recent:
            yield _pb_fact(days, latest, old, variant=PROFILE, pages=frozenset({P.PROFILE}))


PB_LABEL = T(
    named(Shooter("s"), "'s scores, with the personal-best line"),
    you=named("Your scores, with the personal-best line"),
)
PB_ROLLUP_LABEL = charts.RESULTS_LABEL


def _pb_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "trend",
        label=PB_LABEL,
        window=charts.recent(day),
        hl=Highlight(dates=(day,)),
        params={"line": "pb"},
    )


_PB_TEXT = (
    T(
        named(
            "New personal best for ",
            Shooter("s"),
            ": ",
            Int("new"),
            ", beating the ",
            Int("old"),
            " from ",
            MonthYear("old_date"),
            ".",
        ),
        you=named(
            "New personal best: ",
            Int("new"),
            ", beating your ",
            Int("old"),
            " from ",
            MonthYear("old_date"),
            ".",
        ),
    ),
    T(
        named(Shooter("s"), " set a new personal best of ", Int("new"), "."),
        you=named("You set a new personal best of ", Int("new"), "."),
    ),
)
_PB_HOW = (
    T(
        named("A personal best is a round higher than every round on earlier Sundays."),
        you=named(
            "A personal best is a round higher than every round you shot on earlier Sundays."
        ),
    ),
    T(
        named("It needs at least 5 rounds on earlier Sundays, the same rule as the trophy."),
        you=named("It needs at least 5 of your rounds on earlier Sundays, as the trophy does."),
    ),
    T(
        named("All round types count, including a second round that day."),
        you=named("All round types count, including your second round that day."),
    ),
)

register(
    Kind(
        id="pf.pb",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=5,
        anchored=True,
        kudos=True,
        guard={"min_prior_rounds": PB_MIN_PRIOR_ROUNDS, "profile_sundays": PB_PROFILE_SUNDAYS},
        params=frozenset({"s", "new", "old", "old_date", "day", "names"}),
        templates={
            "": _PB_TEXT,
            PROFILE: _PB_TEXT,
            ROLLUP: (T(named("Personal bests today: ", NameList("names"), ".")),),
        },
        how={
            "": _PB_HOW,
            PROFILE: _PB_HOW,
            ROLLUP: (
                T(
                    named(
                        "Each beat every round they shot on earlier Sundays, "
                        "with 5 or more earlier rounds."
                    )
                ),
            ),
        },
        labels=(PB_LABEL, PB_ROLLUP_LABEL),
        chart=_pb_chart,
        proof=(
            cell("new", "score"),
            na("old", "the earlier best is the personal-best line's level before this Sunday"),
        ),
        evaluate=_pb,
        supersedes=frozenset(
            {"pf.season-best", "pf.tied-best", "pf.first-tier", "pf.best-day-vs-field"}
        ),
    )
)


# --- shared chart helpers ------------------------------------------------------------------------

RESULTS_LABEL = PB_ROLLUP_LABEL
TREND_LABEL = PB_LABEL


# --- pf.tied-best --------------------------------------------------------------------------------

TIED_PRIOR = 12
TIED_OVER_USUAL = 3.0


def _tied_best(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        d = days[i]
        usual = d.prior_mean
        if d.prior_best is None or usual is None or d.prior_rounds < TIED_PRIOR:
            continue
        if d.score != d.prior_best or d.prior_best < usual + TIED_OVER_USUAL:
            continue
        yield Fact(
            subject_id=str(d.shooter_id),
            anchor_date=d.date,
            variant="",
            pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
            params={
                "s": d.shooter_id,
                "best": d.score,
                "first": first_reached(days[:i], d.score),
                "day": d.date,
            },
            strength=(d.score - usual) / TIED_OVER_USUAL,
            named_shooter_ids=(d.shooter_id,),
        )


def _tied_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    first, day = p_date(fact.params, "first"), p_date(fact.params, "day")
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "trend",
        label=TREND_LABEL,
        window=Window(add_months(first, -1), day),
        hl=Highlight(dates=(first, day)),
        params={"line": "pb"},
    )


register(
    Kind(
        id="pf.tied-best",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        guard={"min_prior_rounds": TIED_PRIOR, "over_usual": TIED_OVER_USUAL},
        params=frozenset({"s", "best", "first", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        " matched a personal best of ",
                        Int("best"),
                        ", first set in ",
                        MonthYear("first"),
                        ".",
                    ),
                    you=named(
                        "You matched your personal best of ",
                        Int("best"),
                        ", first set in ",
                        MonthYear("first"),
                        ".",
                    ),
                ),
            ),
            ROLLUP: (T(named("Personal bests matched today: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "The Sunday's best round equals the highest round on any earlier Sunday."
                    ),
                    you=named(
                        "Your best round that Sunday equals your highest round on any "
                        "earlier Sunday."
                    ),
                ),
                T(
                    named(
                        "Needs 12 earlier rounds, and that best must be 3 or more over their "
                        "average. All round types count."
                    ),
                    you=named(
                        "Needs 12 earlier rounds, and that best must be 3 or more over "
                        "your average. All round types count."
                    ),
                ),
            ),
            ROLLUP: (T(named("Each matched the best round of their own history.")),),
        },
        labels=(TREND_LABEL, RESULTS_LABEL),
        chart=_tied_chart,
        proof=(cell("best", "score"),),
        evaluate=_tied_best,
    )
)


# --- pf.sunday-milestone -------------------------------------------------------------------------

SUNDAY_LEVELS = (25, 50, 100, 150, 200, 250, 300)
SUNDAY_STRENGTH = {25: 1.0, 50: 1.25, 100: 1.5, 150: 1.75, 200: 1.75, 250: 2.0, 300: 2.0}
TO_GO_MAX = 3


def _sunday_milestone(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    reached: dict[int, list[tuple[date, int]]] = {}
    for sid, days in fr.histories.items():
        for d in days:
            if d.k in SUNDAY_LEVELS:
                reached.setdefault(d.k, []).append((d.date, sid))
    for i, days in anchor_days(fr, scope):
        d = days[i]
        if d.k not in SUNDAY_LEVELS:
            continue
        club = sum(1 for day, _sid in reached[d.k] if day <= d.date)
        yield Fact(
            subject_id=str(d.shooter_id),
            anchor_date=d.date,
            variant="first" if club == 1 else "",
            pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
            params={
                "s": d.shooter_id,
                "level": d.k,
                "club": club,
                "first": d.first_date,
                "day": d.date,
            },
            strength=SUNDAY_STRENGTH[d.k],
            named_shooter_ids=(d.shooter_id,),
        )
    for sid, days in evergreen_days(fr, scope):
        last = days[-1]
        shot = fr.appearances_through(sid, scope.as_of)  # special Sundays count (Decision 11)
        nxt = next((level for level in SUNDAY_LEVELS if level > shot), None)
        if nxt is None or nxt - shot > TO_GO_MAX or not shot_recently(days, scope.as_of):
            continue
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant="to_go",
            pages=frozenset({P.HOME}),  # the profile's Stats card owns "Next milestone" (D12)
            params={
                "s": sid,
                "next": nxt,
                "to_go": nxt - shot,
                "first": last.first_date,
                "day": last.date,
            },
            strength=1.0,
            named_shooter_ids=(sid,),
        )


def _sunday_milestone_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    day = p_date(fact.params, "day")
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "cal",
        label=charts.CAL_LABEL,
        window=Window(p_date(fact.params, "first"), day),
        hl=Highlight(dates=(day,)),
    )


register(
    Kind(
        id="pf.sunday-milestone",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.NEUTRAL,
        care=4,
        variant_care={"to_go": 2},
        anchored=True,
        kudos=True,
        guard={"to_go": TO_GO_MAX},
        params=frozenset({"s", "level", "club", "to_go", "next", "first", "day", "names"}),
        templates={
            "": (
                T(
                    named(
                        Ordinal("level"),
                        " Sunday for ",
                        Shooter("s"),
                        ", one of ",
                        Int("club"),
                        " shooters to get there.",
                    ),
                    you=named(
                        "Your ",
                        Ordinal("level"),
                        " Sunday: you are one of ",
                        Int("club"),
                        " shooters to get there.",
                    ),
                ),
            ),
            "to_go": (
                T(
                    named(
                        Shooter("s"),
                        " is ",
                        Count("to_go", "Sunday"),
                        " from a ",
                        Ordinal("next"),
                        ".",
                    ),
                    you=named(
                        "You are ", Count("to_go", "Sunday"), " from your ", Ordinal("next"), "."
                    ),
                ),
            ),
            "first": (
                T(
                    named(
                        Ordinal("level"),
                        " Sunday for ",
                        Shooter("s"),
                        ", the first shooter to get there.",
                    ),
                    you=named(
                        "Your ",
                        Ordinal("level"),
                        " Sunday: you are the first shooter to get there.",
                    ),
                ),
            ),
            ROLLUP: (T(named("Sunday milestones today: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "Sundays shot = every Sunday with at least one round, since their "
                        "first on record."
                    ),
                    you=named(
                        "Sundays shot = every Sunday you have at least one round, since "
                        "your first on record."
                    ),
                ),
                T(
                    named(
                        "Milestones: 25, 50, 100, 150, 200, 250 and 300. There is no "
                        "per-shooter record before 2020."
                    ),
                    you=named(
                        "Your milestones: 25, 50, 100, 150, 200, 250 and 300. There is no "
                        "per-shooter record before 2020."
                    ),
                ),
            ),
            ROLLUP: (
                T(named("Each reached 25, 50, 100, 150, 200, 250 or 300 Sundays shot today.")),
            ),
        },
        labels=(charts.CAL_LABEL, RESULTS_LABEL),
        chart=_sunday_milestone_chart,
        proof=(
            rows_total("level"),
            na("club", "the number of shooters who got there is quoted, not charted"),
            na("to_go", "the Sundays to go are counted from the calendar's total"),
            na("next", "the next milestone is a target, not a charted value"),
        ),
        evaluate=_sunday_milestone,
    )
)


# --- pf.wins -------------------------------------------------------------------------------------

WIN_CAREER_PRIOR = 8
WIN_COUNT_MIN = 2


def _wins(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        d = days[i]
        if d.rank != 1:
            continue
        earlier = [x for x in days[:i] if x.held and x.rank == 1]
        if not earlier:
            # A first win that fails the career guard is silent, and so is that year's "first".
            if d.prior_rounds < WIN_CAREER_PRIOR or d.field_n < FINISH_FIELD:
                continue
            variant, strength = "career", 2.0
        elif all(x.date.year != d.date.year for x in earlier):
            variant, strength = "year", 1.5
        else:
            continue
        yield Fact(
            subject_id=str(d.shooter_id),
            anchor_date=d.date,
            variant=variant,
            pages=frozenset({P.SUNDAY, P.HOME}),
            params={"s": d.shooter_id, "year": d.date.year, "day": d.date, "n": d.field_n},
            strength=strength,
            named_shooter_ids=(d.shooter_id,),
        )
    for sid, days in evergreen_days(fr, scope):
        year = scope.as_of.year
        wins = [d for d in days if d.held and d.rank == 1 and d.date.year == year]
        if len(wins) >= WIN_COUNT_MIN:
            yield Fact(
                subject_id=str(sid),
                anchor_date=None,
                variant=PROFILE,
                pages=frozenset({P.PROFILE}),
                params={
                    "s": sid,
                    "wins": len(wins),
                    "year": year,
                    "first": days[0].date,
                    "day": wins[-1].date,
                },
                strength=len(wins) / 2,
                named_shooter_ids=(sid,),
            )


WINS_LABEL = T(named(Shooter("s"), "'s wins by year"), you=named("Your wins by year"))


def _wins_chart(fact: Fact) -> ChartLink:
    if fact.variant == PROFILE:
        sid = p_int(fact.params, "s")
        window = Window(p_date(fact.params, "first"), p_date(fact.params, "day"))
        query = charts.spec(Metric.WINS, Agg.SUM, Dim.YEAR, window=window, shooters=(sid,))
        return charts.explorer(
            query, label=WINS_LABEL, hl=Highlight(keys=(str(p_int(fact.params, "year")),))
        )
    return charts.results_chart(
        p_date(fact.params, "day"),
        (p_int(fact.params, "s"),) if fact.variant != ROLLUP else p_ids(fact.params, "names"),
        label=RESULTS_LABEL,
    )


register(
    Kind(
        id="pf.wins",
        family=Family.RACE,
        home_slot=HomeSlot.RACE_RECORD,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=5,
        anchored=True,
        kudos=True,
        guard={
            "career_prior_rounds": WIN_CAREER_PRIOR,
            "career_field": FINISH_FIELD,
            "count": WIN_COUNT_MIN,
        },
        params=frozenset({"s", "year", "day", "n", "wins", "first", "names"}),
        templates={
            "career": (
                T(
                    named(
                        "First win of ", Shooter("s"), "'s career, in a field of ", Int("n"), "."
                    ),
                    you=named("The first win of your career, in a field of ", Int("n"), "."),
                ),
            ),
            "year": (
                T(
                    named("First Sunday win of ", Year("year"), " for ", Shooter("s"), "."),
                    you=named("Your first Sunday win of ", Year("year"), "."),
                ),
            ),
            PROFILE: (
                T(
                    named(
                        Shooter("s"),
                        " has ",
                        Count("wins", "win"),
                        " in ",
                        Year("year"),
                        " so far.",
                    ),
                    you=named("You have ", Count("wins", "win"), " in ", Year("year"), " so far."),
                ),
            ),
            ROLLUP: (T(named("Sharing the top spot today: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "A win = the top score of the Sunday with their best round; a tie for "
                        "the top counts as a win for each."
                    ),
                    you=named(
                        "A win = the top score of the Sunday with your best round; a tie "
                        "for the top counts for each."
                    ),
                ),
                T(
                    named(
                        "A first career win needs 8 earlier rounds and a field of 15 or more. "
                        "All round types count."
                    ),
                    you=named(
                        "A first career win needs 8 earlier rounds and a field of 15 or "
                        "more. All round types count."
                    ),
                ),
            ),
            PROFILE: (
                T(
                    named(
                        "Wins this calendar year, counted with their best round each Sunday; "
                        "ties at the top count for each. Shown from 2."
                    ),
                    you=named(
                        "Your wins this calendar year, with your best round each Sunday; "
                        "ties at the top count. Shown from 2."
                    ),
                ),
            ),
            ROLLUP: (T(named("Tied for the top score of the Sunday.")),),
        },
        labels=(RESULTS_LABEL, WINS_LABEL),
        chart=_wins_chart,
        proof=(cell("wins"), rows_total("n")),
        evaluate=_wins,
        supersedes=frozenset({"pf.career-first"}),
    )
)


# --- pf.back-strong ------------------------------------------------------------------------------

BACK_DAYS = 180


def _back_strong(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        d = days[i]
        if d.prev_date is None or (d.date - d.prev_date).days < BACK_DAYS:
            continue
        gap = (d.date - d.prev_date).days
        usual = d.prior_mean
        show_score = usual is not None and d.score >= usual
        params: dict[str, object] = {
            "s": d.shooter_id,
            "months": max(6, round(gap / 30.44)),
            "prev": d.prev_date,
            "day": d.date,
        }
        if show_score:
            params["score"] = d.score
        yield Fact(
            subject_id=str(d.shooter_id),
            anchor_date=d.date,
            variant="score" if show_score else "",
            pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
            params=params,
            strength=gap / BACK_DAYS,
            named_shooter_ids=(d.shooter_id,),
        )


def _back_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    prev, day = p_date(fact.params, "prev"), p_date(fact.params, "day")
    return charts.profile_chart(
        p_int(fact.params, "s"),
        "cal",
        label=charts.CAL_LABEL,
        window=Window(add_months(prev, -1), day),
        hl=Highlight(dates=(prev, day)),
    )


_BACK_HOW = (
    T(
        named("Their previous round was 180 or more days before this Sunday."),
        you=named("Your previous round was 180 or more days before this Sunday."),
    ),
    T(
        named("The score shows only when it is at or above their average before the break."),
        you=named("Your score shows only when it is at or above your average before the break."),
    ),
)

register(
    Kind(
        id="pf.back-strong",
        family=Family.NEWCOMER,
        home_slot=HomeSlot.PERSON,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.NEUTRAL,
        care=3,
        anchored=True,
        guard={"min_days": BACK_DAYS},
        params=frozenset({"s", "months", "prev", "day", "score", "names"}),
        templates={
            "": (
                T(
                    named(
                        "Welcome back, ", Shooter("s"), ", after ", Count("months", "month"), "."
                    ),
                    you=named("Welcome back: your first Sunday in ", Count("months", "month"), "."),
                ),
            ),
            "score": (
                T(
                    named(
                        "Welcome back, ",
                        Shooter("s"),
                        ", after ",
                        Count("months", "month"),
                        ", with a ",
                        Int("score"),
                        ".",
                    ),
                    you=named(
                        "Welcome back: your first round in ",
                        Count("months", "month"),
                        " was a ",
                        Int("score"),
                        ".",
                    ),
                ),
            ),
            ROLLUP: (T(named("Welcome back after a long break: ", NameList("names"), ".")),),
        },
        how={
            "": _BACK_HOW,
            "score": _BACK_HOW,
            ROLLUP: (T(named("Each came back after 180 or more days away.")),),
        },
        labels=(charts.CAL_LABEL, RESULTS_LABEL),
        chart=_back_chart,
        proof=(
            cell("score", key="day"),
            na("months", "the gap is between the two highlighted Sundays"),
        ),
        evaluate=_back_strong,
    )
)


# --- pf.first-tier -------------------------------------------------------------------------------

TIER_LEVELS = (40, 45, 48)
TIER_STRENGTH = {40: 1.0, 45: 1.5, 48: 2.0}
TIER_PRIOR = 10


def _first_tier(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        d = days[i]
        if d.prior_rounds < TIER_PRIOR or d.prior_best is None:
            continue
        level = crossed(d.prior_best, d.score, TIER_LEVELS)
        if level is None:
            continue
        yield Fact(
            subject_id=str(d.shooter_id),
            anchor_date=d.date,
            variant="",
            pages=frozenset({P.PROFILE}),
            params={
                "s": d.shooter_id,
                "level": level,
                "score": d.score,
                "first": days[0].date,
                "day": d.date,
            },
            strength=TIER_STRENGTH[level],
            named_shooter_ids=(d.shooter_id,),
        )


def _first_tier_chart(fact: Fact) -> ChartLink:
    day = p_date(fact.params, "day")
    query = charts.spec(
        Metric.SCORE,
        Agg.MAX,
        Dim.EVENT,
        window=Window(p_date(fact.params, "first"), day),
        shooters=(p_int(fact.params, "s"),),
    )
    return charts.explorer(
        query,
        label=charts.BEST_EACH_LABEL,
        chart_type="line",
        hl=Highlight(dates=(day,)),
        ref=p_int(fact.params, "level"),
    )


register(
    Kind(
        id="pf.first-tier",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        expires={P.PROFILE: 12},
        guard={"min_prior_rounds": TIER_PRIOR},
        params=frozenset({"s", "level", "score", "first", "day"}),
        templates={
            "": (
                T(
                    named(
                        Shooter("s"),
                        " broke ",
                        Int("level"),
                        " for the first time: ",
                        Int("score"),
                        " on ",
                        ShortDate("day"),
                        ".",
                    ),
                    you=named(
                        "You broke ",
                        Int("level"),
                        " for the first time: ",
                        Int("score"),
                        " on ",
                        ShortDate("day"),
                        ".",
                    ),
                ),
            )
        },
        how={
            "": (
                T(
                    named(
                        "The first round ever at 40, 45 or 48 or better (the highest mark "
                        "passed). Needs 10 earlier rounds."
                    ),
                    you=named(
                        "Your first round ever at 40, 45 or 48 or better (the highest mark "
                        "passed). Needs 10 earlier rounds."
                    ),
                ),
                T(
                    named(
                        "Shown on the profile for 12 Sundays; the Sunday page shows it as a "
                        "personal best."
                    ),
                    you=named(
                        "Shown on your profile for 12 Sundays; the Sunday page shows it as a "
                        "personal best."
                    ),
                ),
            )
        },
        labels=(charts.BEST_EACH_LABEL,),
        chart=_first_tier_chart,
        proof=(cell("score"), na("level", "the dashed reference line")),
        evaluate=_first_tier,
    )
)


# --- pf.first-since ------------------------------------------------------------------------------

SINCE_DAYS = 365
SINCE_ROUNDS = 15
SINCE_TIMES = 2
SINCE_LEVELS: tuple[tuple[str, int], ...] = (
    ("win", 1),
    ("podium", 3),
    ("score", 45),
    ("score", 40),
)


def _reached(day: Day, variant: str, level: int) -> bool:
    if variant == "score":
        return day.score >= level
    return day.held and day.rank is not None and day.rank <= level  # any field size (history)


def _first_since(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        d = days[i]
        for variant, level in SINCE_LEVELS:
            if not _reached(d, variant, level):
                continue
            if variant != "score" and finish_at(d, level) is not True:
                continue  # the reported Sunday needs a full field (spec 4.3); history does not
            before = [x for x in days[:i] if _reached(x, variant, level)]
            if len(before) < SINCE_TIMES:
                continue
            last = before[-1]
            away = (d.date - last.date).days
            if away < SINCE_DAYS or d.prior_rounds - last.rounds_through < SINCE_ROUNDS:
                break  # a higher level reached recently outranks a lower one
            yield Fact(
                subject_id=str(d.shooter_id),
                anchor_date=d.date,
                variant=variant,
                pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
                params={"s": d.shooter_id, "level": level, "last": last.date, "day": d.date},
                strength=away / SINCE_DAYS,
                named_shooter_ids=(d.shooter_id,),
            )
            break


def _since_chart(fact: Fact) -> ChartLink:
    if fact.variant == ROLLUP:
        return charts.rollup_results(fact)
    last, day = p_date(fact.params, "last"), p_date(fact.params, "day")
    window, hl = Window(add_months(last, -1), day), Highlight(dates=(last, day))
    if fact.variant == "score":
        return charts.profile_chart(
            p_int(fact.params, "s"),
            "trend",
            label=charts.BEST_EACH_LABEL,
            window=window,
            hl=hl,
            params={"ref": str(p_int(fact.params, "level"))},
        )
    return charts.profile_chart(
        p_int(fact.params, "s"), "finishes", label=charts.FINISH_LABEL, window=window, hl=hl
    )


register(
    Kind(
        id="pf.first-since",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        guard={"days": SINCE_DAYS, "rounds": SINCE_ROUNDS, "times_before": SINCE_TIMES},
        params=frozenset({"s", "level", "last", "day", "names"}),
        templates={
            "win": (
                T(
                    named("First win since ", MonthYear("last"), " for ", Shooter("s"), "."),
                    you=named("Your first win since ", MonthYear("last"), "."),
                ),
            ),
            "podium": (
                T(
                    named("First podium since ", MonthYear("last"), " for ", Shooter("s"), "."),
                    you=named("Your first podium since ", MonthYear("last"), "."),
                ),
            ),
            "score": (
                T(
                    named(
                        "First round of ",
                        Int("level"),
                        " or better since ",
                        MonthYear("last"),
                        " for ",
                        Shooter("s"),
                        ".",
                    ),
                    you=named(
                        "Your first round of ",
                        Int("level"),
                        " or better since ",
                        MonthYear("last"),
                        ".",
                    ),
                ),
            ),
            ROLLUP: (
                T(
                    named(
                        "Back to a mark last reached a year or more ago: ", NameList("names"), "."
                    )
                ),
            ),
        },
        how={
            "": (
                T(
                    named(
                        "A win, a podium, or a round of 45 or 40 or better, last reached a year "
                        "or more and 15 or more rounds earlier."
                    ),
                    you=named(
                        "A win, a podium, or a round of 45 or 40 or better that you last "
                        "reached a year or more and 15 or more rounds earlier."
                    ),
                ),
                T(
                    named("The mark must have been reached at least twice before."),
                    you=named("You must have reached the mark at least twice before."),
                ),
            ),
            ROLLUP: (T(named("Each reached a mark for the first time in a year or more.")),),
        },
        labels=(charts.BEST_EACH_LABEL, charts.FINISH_LABEL, RESULTS_LABEL),
        chart=_since_chart,
        proof=(na("level", "the dashed reference line, or the podium places on the strip"),),
        evaluate=_first_since,
    )
)


# --- pf.career-first -----------------------------------------------------------------------------

CAREER_PRIOR = 8


# History counts finishes in fields of any size; the field-of-15 guard is on the reported Sunday.
def _top_third(day: Day) -> bool:
    return day.held and day.rank is not None and day.rank * 3 <= day.field_n


def _podium(day: Day) -> bool:
    return day.held and day.rank is not None and day.rank <= 3


def _career_first(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for i, days in anchor_days(fr, scope):
        d = days[i]
        if d.rank is None or d.rank == 1 or d.prior_rounds < CAREER_PRIOR:
            continue
        if d.field_n < FINISH_FIELD:
            continue
        if _podium(d) and not any(_podium(x) for x in days[:i]):
            variant, strength = "podium", 1.5
        elif not _podium(d) and _top_third(d) and not any(_top_third(x) for x in days[:i]):
            variant, strength = "top_third", 1.0
        else:
            continue
        yield Fact(
            subject_id=str(d.shooter_id),
            anchor_date=d.date,
            variant=variant,
            pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
            params={"s": d.shooter_id, "rank": d.rank, "n": d.field_n, "day": d.date},
            strength=strength,
            named_shooter_ids=(d.shooter_id,),
        )


def _career_first_chart(fact: Fact) -> ChartLink:
    ids = p_ids(fact.params, "names") if fact.variant == ROLLUP else (p_int(fact.params, "s"),)
    return charts.results_chart(p_date(fact.params, "day"), ids, label=RESULTS_LABEL)


register(
    Kind(
        id="pf.career-first",
        family=Family.MILESTONE,
        home_slot=HomeSlot.MILESTONE,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE, P.SUNDAY, P.HOME}),
        polarity=Polarity.POSITIVE,
        care=4,
        anchored=True,
        kudos=True,
        expires={P.HOME: 3, P.PROFILE: 12},
        guard={"min_prior_rounds": CAREER_PRIOR, "field": FINISH_FIELD},
        params=frozenset({"s", "rank", "n", "day", "names"}),
        templates={
            "podium": (
                T(
                    named(
                        "First podium of ",
                        Shooter("s"),
                        "'s career: ",
                        Ordinal("rank"),
                        " of ",
                        Int("n"),
                        ".",
                    ),
                    you=named("Your first podium: ", Ordinal("rank"), " of ", Int("n"), "."),
                ),
            ),
            "top_third": (
                T(
                    named(
                        "First top-third finish for ",
                        Shooter("s"),
                        ": ",
                        Ordinal("rank"),
                        " of ",
                        Int("n"),
                        ".",
                    ),
                    you=named(
                        "Your first top-third finish: ", Ordinal("rank"), " of ", Int("n"), "."
                    ),
                ),
            ),
            ROLLUP: (T(named("Career firsts today: ", NameList("names"), ".")),),
        },
        how={
            "": (
                T(
                    named(
                        "Place by best round among everyone who shot, ties sharing the place. "
                        "A first win shows as a win instead."
                    ),
                    you=named(
                        "Your place by best round among everyone who shot, ties sharing the "
                        "place. A first win shows as a win instead."
                    ),
                ),
                T(
                    named("Needs 8 earlier rounds and a field of 15 or more."),
                    you=named("Needs 8 earlier rounds and a field of 15 or more."),
                ),
            ),
            ROLLUP: (T(named("Each had a first podium or first top-third finish.")),),
        },
        labels=(RESULTS_LABEL,),
        chart=_career_first_chart,
        proof=(cell("rank", "rank", key="s"), rows_total("n")),
        evaluate=_career_first,
    )
)
