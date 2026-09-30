"""Recap kinds (spec §2.2.3, §2.2.5): pinned lines that sum up a Sunday or a year."""

from __future__ import annotations

from collections.abc import Iterator

from sunday_clays.analytics.insights import charts
from sunday_clays.analytics.insights.context import InsightFrames, evergreen_days
from sunday_clays.analytics.insights.milestones import is_pb
from sunday_clays.analytics.insights.registry import Kind, register
from sunday_clays.analytics.insights.templates import (
    Count,
    Int,
    NameList,
    Ordinal,
    Part,
    Shooter,
    SundayDate,
    T,
    Template,
    Word,
    field_,
    named,
)
from sunday_clays.analytics.insights.types import (
    ChartLink,
    Fact,
    Family,
    P,
    Polarity,
    Scope,
    SubjectType,
    cell,
    na,
    p_date,
    p_ids,
    p_int,
    rows_total,
)

DIGEST_MIN_OVER = 1  # "2 over their usual" only when at least 1 over


def _digest(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    """The profile's pinned line about the latest held Sunday, for everyone who shot it (D11)."""
    for sid, days in evergreen_days(fr, scope):
        last = days[-1]
        if last.date != scope.as_of or not last.held:
            continue
        finish = last.rank is not None and last.rank <= last.field_n / 2
        over = None if last.residual is None else round(last.residual)
        usual = over is not None and over >= DIGEST_MIN_OVER
        variant = {(True, True): "full", (True, False): "finish", (False, True): "usual"}.get(
            (finish, usual), "plain"
        )
        params: dict[str, object] = {"s": sid, "day": last.date, "score": last.score}
        if finish:
            params |= {"rank": last.rank, "n": last.field_n}
        if usual:
            params |= {"over": over}
        yield Fact(
            subject_id=str(sid),
            anchor_date=None,
            variant=variant,
            pages=frozenset({P.PROFILE}),
            params=params,
            strength=1.0,
            named_shooter_ids=(sid,),
        )


DIGEST_LABEL = T(named("Results for ", SundayDate("day")))


def _digest_chart(fact: Fact) -> ChartLink:
    return charts.results_chart(
        p_date(fact.params, "day"), (p_int(fact.params, "s"),), label=DIGEST_LABEL
    )


_HEAD = (SundayDate("day"), ": ", Shooter("s"), " shot ", Int("score"))
_HEAD_YOU = (SundayDate("day"), ": you shot ", Int("score"))
_FINISH = (", ", Ordinal("rank"), " of ", Int("n"))
_USUAL = (", ", Int("over"), " over their usual for a day like this")
_USUAL_YOU = (", ", Int("over"), " over your usual for a day like this")

register(
    Kind(
        id="pf.digest-line",
        family=Family.RECAP,
        home_slot=None,
        subject=SubjectType.SHOOTER,
        pages=frozenset({P.PROFILE}),
        polarity=Polarity.NEUTRAL,
        care=1,
        anchored=False,
        guard={"min_over": DIGEST_MIN_OVER},
        params=frozenset({"s", "day", "score", "rank", "n", "over"}),
        templates={
            "plain": (T(named(*_HEAD, "."), you=named(*_HEAD_YOU, ".")),),
            "finish": (T(named(*_HEAD, *_FINISH, "."), you=named(*_HEAD_YOU, *_FINISH, ".")),),
            "usual": (T(named(*_HEAD, *_USUAL, "."), you=named(*_HEAD_YOU, *_USUAL_YOU, ".")),),
            "full": (
                T(
                    named(*_HEAD, *_FINISH, *_USUAL, "."),
                    you=named(*_HEAD_YOU, *_FINISH, *_USUAL_YOU, "."),
                ),
            ),
        },
        how={
            "": (
                T(
                    named("The best round of the latest Sunday with full results."),
                    you=named("Your best round of the latest Sunday with full results."),
                ),
                T(
                    named("The finish shows only in the top half of the field."),
                    you=named("Your finish shows only in the top half of the field."),
                ),
                T(
                    named("The gap to their usual shows only when it is 1 target or more over."),
                    you=named("The gap to your usual shows only when it is 1 target or more over."),
                ),
            )
        },
        labels=(DIGEST_LABEL,),
        chart=_digest_chart,
        proof=(
            cell("score", "score", key="s"),
            cell("rank", "rank", key="s"),
            rows_total("n"),
            cell("over", "residual", key="s"),
        ),
        evaluate=_digest,
        expires={},
    )
)


# --- home.sunday-recap (mixed; pinned on home) ---------------------------------------------------

RECAP_MIN_SLOTS = 3
TEMP_WORDS = (
    ("<40", "cold"),
    ("40-55", "cool"),
    ("55-70", "mild"),
    ("70-85", "warm"),
    ("85+", "hot"),
)
WIND_WORDS = (("<10", "calm"), ("10-20", "breezy"), ("20+", "windy"))
PLAYED_WORDS = (
    ("same", "Scores ran about as usual."),
    ("bit_tough", "Scores ran a little tougher."),
    ("tough", "Scores ran tougher."),
    ("bit_easy", "Scores ran a little easier."),
    ("easy", "Scores ran easier."),
)
PLAYED_SAME, PLAYED_BIG = 1.0, 2.5
# Optional parts, in headline order; a variant is the string of the letters present.
RECAP_PARTS = ("w", "p", "t", "b", "f")  # weather, played, tie at the top, PBs, first-timers


def played_word(difficulty: float) -> str:
    size = abs(difficulty)
    if size < PLAYED_SAME:
        return "same"
    way = "tough" if difficulty > 0 else "easy"
    return way if size >= PLAYED_BIG else f"bit_{way}"


def _sunday_recap(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    for sunday in fr.sundays:
        if sunday.date not in scope.sundays or not sunday.results:
            continue
        top = sunday.results[0].score
        winners = [r.shooter_id for r in sunday.results if r.score == top]
        pbs = 0
        firsts = 0
        for r in sunday.results:
            if fr.profiles[r.shooter_id].deceased:
                continue
            days = fr.histories[r.shooter_id]
            # Every shooter with a result has that Sunday in their history: InsightFrames builds
            # both from the same rounds.
            day = next(d for d in days if d.date == sunday.date)
            pbs += is_pb(day)
            firsts += days[0].date == sunday.date
        params: dict[str, object] = {
            "day": sunday.date,
            "n": sunday.n,
            "top": top,
            "s": winners[0],
            "names": winners,
        }
        flags = ""
        if sunday.temp_band is not None and sunday.wind_band is not None:
            flags += "w"
            params |= {"temp": sunday.temp_band, "wind": sunday.wind_band}
        if sunday.difficulty is not None:
            flags += "p"
            params["played"] = played_word(sunday.difficulty)
        if len(winners) > 1:
            flags += "t"
        if pbs:
            flags += "b"
            params["pbs"] = pbs
        if firsts:
            flags += "f"
            params["firsts"] = firsts
        slots = 2 + sum(flag in flags for flag in "wpbf")  # crowd and top score always
        if slots < RECAP_MIN_SLOTS:
            continue
        yield Fact(
            subject_id=sunday.date.isoformat(),
            anchor_date=sunday.date,
            variant=flags,
            pages=frozenset({P.HOME}),
            params=params,
            strength=1.0,
            named_shooter_ids=tuple(winners),
        )


def _recap_template(flags: str) -> Template:
    crowd: list[Part] = [SundayDate("day"), ": ", Count("n", "shooter")]
    if "w" in flags:
        crowd += [" on a ", Word("temp", TEMP_WORDS), ", ", Word("wind", WIND_WORDS), " morning"]
    clauses = [field_(*crowd, ".")]
    if "p" in flags:
        clauses.append(field_(Word("played", PLAYED_WORDS)))
    if "t" in flags:
        clauses.append(
            named(NameList("names"), " shared the top of the board with ", Int("top"), ".")
        )
    else:
        clauses.append(named(Shooter("s"), " topped the board with a ", Int("top"), "."))
    tail: list[Part] = []
    if "b" in flags:
        tail += [Count("pbs", "shooter"), " set a personal best"]
    if "f" in flags:
        tail += [" and " if tail else "", Count("firsts", "first-timer"), " joined us"]
    if tail:
        clauses.append(field_(*[p for p in tail if p != ""], "."))
    return T(*clauses)


def _all_flags() -> list[str]:
    out = [""]
    for part in RECAP_PARTS:
        out += [f + part for f in out]
    return out


RECAP_LABEL = T(named("Results for ", SundayDate("day")))

register(
    Kind(
        id="home.sunday-recap",
        family=Family.RECAP,
        home_slot=None,
        subject=SubjectType.SUNDAY,
        pages=frozenset({P.HOME}),
        polarity=Polarity.MIXED,
        care=3,
        anchored=True,
        guard={"min_slots": RECAP_MIN_SLOTS},
        params=frozenset(
            {"day", "n", "top", "s", "names", "temp", "wind", "played", "pbs", "firsts"}
        ),
        templates={flags: (_recap_template(flags),) for flags in _all_flags()},
        how={
            "": (
                T(
                    named(
                        "The latest Sunday in one line: the crowd and the morning's weather, how "
                        "it played, the top score, personal bests and first-timers."
                    )
                ),
                T(
                    named(
                        "How it played comes from the skill model; a little = 1 to 2.5 targets "
                        "from a typical Sunday."
                    )
                ),
            )
        },
        labels=(RECAP_LABEL,),
        chart=lambda fact: charts.results_chart(
            p_date(fact.params, "day"), p_ids(fact.params, "names"), label=RECAP_LABEL
        ),
        proof=(
            rows_total("n"),
            cell("top", "score"),
            na("pbs", "the Sunday page lists them"),
            na("firsts", "the Sunday page lists them"),
        ),
        evaluate=_sunday_recap,
        expires={P.HOME: 1},
    )
)
