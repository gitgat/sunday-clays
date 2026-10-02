"""InsightFrames (spec §3.2 step 2): the frames every kind reads, plus typed per-shooter views.

Kinds read typed Python views, not DataFrames:
- `histories[shooter_id]`: one `Day` per date the shooter has a round (held or not), ascending.
  Each Day carries prefix values over *earlier dates only* (`prior_*`), so a kind that looks at
  `days[: i + 1]` for an anchor Sunday S = `days[i].date` never sees data after S (no-leak, §4.4).
- `sundays`: every held Sunday (C4 `results_complete`), ascending, with its best-round results.
`until(d)` rebuilds everything from frames cut at `event_date <= d`; the no-leak property test
compares Facts computed both ways.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math
import random
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cached_property
from typing import Any

import pandas as pd

from sunday_clays.analytics import frames as fr
from sunday_clays.analytics.insights.templates import natural_name
from sunday_clays.analytics.insights.types import Scope

ACTIVE_WINDOW = timedelta(days=364)  # C7 Activity: (as_of - 364d, as_of]
ACTIVE_MIN_ROUNDS = 5
GUEST_MIN_ROUNDS = 6  # spec §4.3: guests with < 6 rounds get no evergreen profile insight
RECENT = timedelta(weeks=8)  # "shot in the last 8 weeks"
AWARD_COLUMNS: tuple[str, ...] = ("shooter_id", "code", "event_date")


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(k): v for k, v in row.items()} for row in df.to_dict(orient="records")]


def _opt_float(value: object) -> float | None:
    if value is None or value is pd.NA:
        return None
    number = float(value)  # type: ignore[arg-type]
    return None if math.isnan(number) else number


def _opt_int(value: object) -> int | None:
    number = _opt_float(value)
    return None if number is None else round(number)


@dataclass(frozen=True, slots=True)
class Day:
    """One shooter on one date: the best round that day plus prefix values over earlier dates."""

    shooter_id: int
    date: dt.date
    held: bool
    score: int  # best round that day (the is_best_round row)
    round_id: int
    n_rounds: int  # rounds that day (39 fixture days have two)
    adjusted: float | None  # vs the field's middle score (held days only)
    residual: float | None  # vs "usual for a day like this"
    expected: float | None
    rank: int | None  # min-rank among best rounds (held days only)
    field_n: int  # shooters with a round that day
    k: int  # Sundays shot through this date, special ones included (Plan 17)
    prior_rounds: int  # rounds on earlier dates
    prior_best: int | None  # best round on earlier dates
    prior_sum: int  # sum of every round's score on earlier dates
    targets: int  # sum of every round's score through this date
    prev_date: dt.date | None
    first_date: dt.date
    difficulty: float | None
    precip_band: str | None
    temp_band: str | None
    wind_band: str | None
    scores: tuple[int, ...] = ()  # every round that day, highest first

    @property
    def rounds_through(self) -> int:
        return self.prior_rounds + self.n_rounds

    @property
    def prior_mean(self) -> float | None:
        return self.prior_sum / self.prior_rounds if self.prior_rounds else None


@dataclass(frozen=True, slots=True)
class Result:
    shooter_id: int
    score: int
    rank: int
    round_id: int


@dataclass(frozen=True, slots=True)
class Sunday:
    """A held Sunday with its field values and best-round results (rank, then name)."""

    date: dt.date
    i: int  # 0-based position among held Sundays
    n: int  # shooters (best rounds)
    head_count: int | None
    median: float | None  # the field's middle score
    top: int | None
    difficulty: float | None  # positive = tougher than a typical recent Sunday
    precip_in: float | None
    temp_f: float | None
    gust_mph: float | None
    precip_band: str | None
    temp_band: str | None
    wind_band: str | None
    results: tuple[Result, ...]


@dataclass(frozen=True, slots=True)
class Profile:
    shooter_id: int
    name: str  # natural order: "Ike Hadley"
    status: str
    left_censored: bool
    deceased: bool


@dataclass(frozen=True)
class InsightFrames:
    rounds: pd.DataFrame  # C7 load_rounds columns (event_date as datetime.date)
    events: pd.DataFrame  # C7 load_events columns
    shooters: pd.DataFrame  # frames.SHOOTER_COLUMNS
    rating: pd.DataFrame  # frames.RATING_COLUMNS
    stations: pd.DataFrame  # frames.STATION_HIT_COLUMNS
    awards: pd.DataFrame  # AWARD_COLUMNS
    appearances: pd.DataFrame  # frames.APPEARANCE_COLUMNS: special Sundays included (Plan 17)
    calendar: pd.DataFrame  # frames.CALENDAR_COLUMNS: special Sundays included (Plan 17)
    as_of: date | None  # latest held (regular) Sunday in these frames
    histories: Mapping[int, tuple[Day, ...]] = field(repr=False)
    sundays: tuple[Sunday, ...] = field(repr=False)
    sunday_index: Mapping[date, int] = field(repr=False)
    profiles: Mapping[int, Profile] = field(repr=False)
    ratings: Mapping[int, tuple[tuple[date, float], ...]] = field(repr=False)
    appearance_dates: Mapping[int, tuple[date, ...]] = field(repr=False)
    special_days: Mapping[int, tuple[date, ...]] = field(repr=False)

    @classmethod
    def from_frames(
        cls,
        *,
        rounds: pd.DataFrame,
        events: pd.DataFrame,
        shooters: pd.DataFrame,
        rating: pd.DataFrame,
        stations: pd.DataFrame | None = None,
        awards: pd.DataFrame | None = None,
        appearances: pd.DataFrame | None = None,
        calendar: pd.DataFrame | None = None,
    ) -> InsightFrames:
        """Without appearances/calendar, the rounds and events imply them (all regular)."""
        stations = (
            stations if stations is not None else pd.DataFrame(columns=list(fr.STATION_HIT_COLUMNS))
        )
        awards = awards if awards is not None else pd.DataFrame(columns=list(AWARD_COLUMNS))
        appearances = fr.appearances_from_rounds(rounds) if appearances is None else appearances
        calendar = fr.calendar_from_events(events) if calendar is None else calendar
        dates = _dates_by_shooter(appearances)
        sundays = _build_sundays(rounds, events)
        return cls(
            rounds=rounds,
            events=events,
            shooters=shooters,
            rating=rating,
            stations=stations,
            awards=awards,
            appearances=appearances,
            calendar=calendar,
            as_of=sundays[-1].date if sundays else None,
            histories=_build_histories(rounds, events, dates),
            sundays=sundays,
            sunday_index={s.date: s.i for s in sundays},
            profiles=_build_profiles(shooters),
            ratings=_build_ratings(rating),
            appearance_dates=dates,
            special_days=_dates_by_shooter(appearances, special_only=True),
        )

    def until(self, day: date) -> InsightFrames:
        """Everything as it was known on `day`: every frame cut at `event_date <= day`."""

        def cut(df: pd.DataFrame) -> pd.DataFrame:
            return df.loc[[d <= day for d in df["event_date"]]] if len(df) else df

        return InsightFrames.from_frames(
            rounds=cut(self.rounds),
            events=cut(self.events),
            shooters=self.shooters,
            rating=cut(self.rating),
            stations=cut(self.stations),
            awards=cut(self.awards),
            appearances=cut(self.appearances),
            calendar=cut(self.calendar),
        )

    def appearances_through(self, shooter_id: int, day: date) -> int:
        """Sundays the shooter shot up to `day`, special ones included (Plan 17)."""
        return bisect_right(self.appearance_dates.get(shooter_id, ()), day)

    def specials_through(self, shooter_id: int, day: date) -> tuple[date, ...]:
        """The special Sundays the shooter shot up to `day`, oldest first."""
        days = self.special_days.get(shooter_id, ())
        return days[: bisect_right(days, day)]

    @cached_property
    def _held_sorted(self) -> list[date]:
        return self.held_dates()

    def no_held_between(self, earlier: date, later: date) -> bool:
        """No regular held Sunday strictly between the two dates (C7 streaks, Plan 17)."""
        held = self._held_sorted
        return bisect_left(held, later) == bisect_right(held, earlier)

    @property
    def names(self) -> dict[int, str]:
        return {sid: p.name for sid, p in self.profiles.items()}

    def sunday(self, day: date) -> Sunday | None:
        i = self.sunday_index.get(day)
        return None if i is None else self.sundays[i]

    @cached_property
    def held_month_starts(self) -> tuple[tuple[date, str], ...]:
        """(first held Sunday, "YYYY-MM") per month with a held Sunday, oldest first."""
        firsts: dict[str, date] = {}
        for s in self.sundays:
            firsts.setdefault(f"{s.date.year:04d}-{s.date.month:02d}", s.date)
        return tuple((first, key) for key, first in sorted(firsts.items()))

    @cached_property
    def held_month_first_dates(self) -> list[date]:
        return [first for first, _ in self.held_month_starts]

    def held_dates(self) -> list[date]:
        return [s.date for s in self.sundays]

    def held_between(self, start: date, end: date) -> int:
        """Held Sundays in (start, end]."""
        dates = self.held_dates()
        return bisect_right(dates, end) - bisect_right(dates, start)

    def rating_at(self, shooter_id: int, day: date) -> float | None:
        points = self.ratings.get(shooter_id, ())
        i = bisect_right([d for d, _ in points], day)
        return points[i - 1][1] if i else None

    def history_until(self, shooter_id: int, day: date) -> tuple[Day, ...]:
        days = self.histories.get(shooter_id, ())
        return days[: bisect_right([d.date for d in days], day)]


def _dates_by_shooter(
    appearances: pd.DataFrame, *, special_only: bool = False
) -> dict[int, tuple[date, ...]]:
    frame = (
        appearances.loc[appearances["kind"].eq(fr.EVENT_KIND_SPECIAL)]
        if special_only
        else appearances
    )
    out: dict[int, set[date]] = defaultdict(set)
    for sid, day in zip(frame["shooter_id"], frame["event_date"], strict=True):
        out[int(sid)].add(day)
    return {sid: tuple(sorted(days)) for sid, days in out.items()}


def _build_sundays(rounds: pd.DataFrame, events: pd.DataFrame) -> tuple[Sunday, ...]:
    best = rounds.loc[rounds["is_best_round"].eq(True) & rounds["held"].eq(True)]
    results: dict[date, list[Result]] = defaultdict(list)
    names = dict(zip(rounds["shooter_id"], rounds["display_name"], strict=True))
    for sid, day, score, rank, rid in zip(
        best["shooter_id"],
        best["event_date"],
        best["score"],
        best["event_rank"],
        best["round_id"],
        strict=True,
    ):
        results[day].append(Result(int(sid), int(score), _opt_int(rank) or 0, int(rid)))
    held = events.loc[events["results_complete"].eq(True)].sort_values("event_date")
    out: list[Sunday] = []
    for row in _records(held):
        day = row["event_date"]
        ranked = sorted(results.get(day, []), key=lambda r: (r.rank, str(names[r.shooter_id])))
        out.append(
            Sunday(
                date=day,
                i=len(out),
                n=len(ranked),
                head_count=_opt_int(row["head_count"]),
                median=_opt_float(row["median"]),
                top=_opt_int(row["top_score"]),
                difficulty=_opt_float(row["difficulty"]),
                precip_in=_opt_float(row["precip_in"]),
                temp_f=_opt_float(row["temp_f"]),
                gust_mph=_opt_float(row["gust_mph"]),
                precip_band=fr.precip_band(_opt_float(row["precip_in"])),
                temp_band=fr.temp_band(_opt_float(row["temp_f"])),
                wind_band=fr.wind_band(_opt_float(row["gust_mph"])),
                results=tuple(ranked),
            )
        )
    return tuple(out)


def _build_histories(
    rounds: pd.DataFrame,
    events: pd.DataFrame,
    appearance_dates: Mapping[int, tuple[date, ...]] | None = None,
) -> dict[int, tuple[Day, ...]]:
    dates = appearance_dates or {}
    weather: dict[date, dict[str, Any]] = {row["event_date"]: row for row in _records(events)}
    field_n: dict[date, set[int]] = defaultdict(set)
    by_day: dict[tuple[int, date], list[dict[str, Any]]] = defaultdict(list)
    for row in _records(rounds):
        sid, day = int(row["shooter_id"]), row["event_date"]
        field_n[day].add(sid)
        by_day[(sid, day)].append(row)
    out: dict[int, list[Day]] = defaultdict(list)
    for sid, day in sorted(by_day):
        same = sorted(
            by_day[(sid, day)],
            key=lambda r: (r["is_best_round"] is not True, -int(r["score"]), int(r["ordinal"])),
        )
        top, scores = same[0], [int(r["score"]) for r in same]
        days = out[sid]
        prev = days[-1] if days else None
        prior_rounds = prev.rounds_through if prev else 0
        prior_sum = prev.targets if prev else 0
        prior_best = (
            None
            if prev is None
            else prev.score
            if prev.prior_best is None
            else max(prev.score, prev.prior_best)
        )
        ev = weather.get(day, {})
        days.append(
            Day(
                shooter_id=sid,
                date=day,
                held=bool(top["held"]),
                score=max(scores),
                scores=tuple(sorted(scores, reverse=True)),
                round_id=int(top["round_id"]),
                n_rounds=len(scores),
                adjusted=_opt_float(top["adjusted"]),
                residual=_opt_float(top["residual"]),
                expected=_opt_float(top["expected"]),
                rank=_opt_int(top["event_rank"]),
                field_n=len(field_n[day]),
                # Sundays shot through this date, special ones included (Plan 17)
                k=bisect_right(dates[sid], day) if sid in dates else len(days) + 1,
                prior_rounds=prior_rounds,
                prior_best=prior_best,
                prior_sum=prior_sum,
                targets=prior_sum + sum(scores),
                prev_date=prev.date if prev else None,
                first_date=days[0].date if days else day,
                difficulty=_opt_float(ev.get("difficulty")),
                precip_band=fr.precip_band(_opt_float(ev.get("precip_in"))),
                temp_band=fr.temp_band(_opt_float(ev.get("temp_f"))),
                wind_band=fr.wind_band(_opt_float(ev.get("gust_mph"))),
            )
        )
    return {sid: tuple(days) for sid, days in out.items()}


def _build_profiles(shooters: pd.DataFrame) -> dict[int, Profile]:
    return {
        int(row["shooter_id"]): Profile(
            shooter_id=int(row["shooter_id"]),
            name=natural_name(str(row["display_name"])),
            status=str(row["status"]),
            left_censored=bool(row["left_censored"]),
            deceased=str(row["status"]) == "deceased",
        )
        for row in _records(shooters)
    }


def _build_ratings(rating: pd.DataFrame) -> dict[int, tuple[tuple[date, float], ...]]:
    out: dict[int, list[tuple[date, float]]] = defaultdict(list)
    ordered = rating.sort_values(["shooter_id", "event_date"], kind="mergesort")
    for sid, day, mu in zip(
        ordered["shooter_id"], ordered["event_date"], ordered["mu"], strict=True
    ):
        out[int(sid)].append((day, float(mu)))
    return {sid: tuple(points) for sid, points in out.items()}


# --- helpers shared by the kind modules ----------------------------------------------------------


def anchor_days(fr_: InsightFrames, scope: Scope) -> Iterator[tuple[int, tuple[Day, ...]]]:
    """(i, days) for every held shooter-day anchored in scope; `days[: i + 1]` is the no-leak view.

    Deceased shooters are skipped (spec §3.2 exclusions).
    """
    for sid, days in fr_.histories.items():
        if fr_.profiles.get(sid) is not None and fr_.profiles[sid].deceased:
            continue
        for i, day in enumerate(days):
            if day.held and day.date in scope.sundays:
                yield i, days


def evergreen_days(fr_: InsightFrames, scope: Scope) -> Iterator[tuple[int, tuple[Day, ...]]]:
    """(shooter_id, days <= as_of) for every profile subject: active, not deceased, and not a
    guest with fewer than 6 rounds (spec §4.3)."""
    for sid in fr_.histories:
        profile = fr_.profiles.get(sid)
        if profile is None or profile.deceased:
            continue
        days = fr_.history_until(sid, scope.as_of)
        if not days or not is_active(days, scope.as_of):
            continue
        if profile.status == "guest" and days[-1].rounds_through < GUEST_MIN_ROUNDS:
            continue
        yield sid, days


def is_active(days: Sequence[Day], as_of: date) -> bool:
    """C7 Activity as of `as_of`: >= 5 rounds on or before it and >= 1 in (as_of - 364d, as_of]."""
    upto = [d for d in days if d.date <= as_of]
    if not upto or upto[-1].rounds_through < ACTIVE_MIN_ROUNDS:
        return False
    return upto[-1].date > as_of - ACTIVE_WINDOW


def shot_recently(days: Sequence[Day], as_of: date, window: timedelta = RECENT) -> bool:
    return bool(days) and days[-1].date > as_of - window


def held_only(days: Sequence[Day]) -> list[Day]:
    return [d for d in days if d.held]


def split_by_rain(
    days: Sequence[Day], before: date | None = None
) -> tuple[list[float], list[float]]:
    """(wet, dry) vs-the-field of held Sundays with weather, optionally strictly before `before`."""
    wet: list[float] = []
    dry: list[float] = []
    for d in held_only(days):
        if d.adjusted is None or (before is not None and d.date >= before):
            continue
        if d.precip_band == "wet":
            wet.append(float(d.adjusted))
        elif d.precip_band == "dry":
            dry.append(float(d.adjusted))
    return wet, dry


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def sample_var(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return sum((v - m) ** 2 for v in values) / (len(values) - 1)


def stderr_diff(a: Sequence[float], b: Sequence[float]) -> float:
    """Standard error of mean(a) - mean(b) ("noise" in the spec tables)."""
    return math.sqrt(sample_var(a) / len(a) + sample_var(b) / len(b))


def quantile(values: Sequence[float], q: float) -> float:
    """Linear interpolation, as numpy/pandas `quantile` (the Explorer `p25` agg)."""
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def own_tier(days: Sequence[Day]) -> int | None:
    """Own tier T (spec §2.1): the highest of 45/40/35 reached on 10-60% of the last 52 rounds,
    35 only if the usual (the mean of those rounds) is <= 39."""
    last = [d.score for d in days[-52:]]
    if not last:
        return None
    usual = mean([float(s) for s in last])
    for tier in (45, 40, 35):
        share_ = sum(s >= tier for s in last) / len(last)
        if 0.10 <= share_ <= 0.60 and (tier != 35 or usual <= 39):
            return tier
    return None


def stable_seed(*parts: object) -> int:
    """A process-independent seed (Python's hash() is salted per process)."""
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode(), usedforsecurity=False)
    return int.from_bytes(digest.digest()[:8], "big")


def shuffle_share(a: Sequence[float], b: Sequence[float], *, seed: int, n: int = 1000) -> float:
    """Share of `n` label shuffles whose mean(a) - mean(b) the real gap beats (spec §2.1)."""
    real = mean(a) - mean(b)
    pooled = [*a, *b]
    rng = random.Random(seed)  # noqa: S311 - a reproducible shuffle, not a secret
    beaten = 0
    head, tail = len(a), len(b)
    for _ in range(n):
        rng.shuffle(pooled)
        if real > sum(pooled[:head]) / head - sum(pooled[head:]) / tail:
            beaten += 1
    return beaten / n


def add_months(day: date, months: int) -> date:
    """`day` moved by whole calendar months, the day clamped to the shorter month."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    next_first = date(year + (month == 12), month % 12 + 1, 1)
    last_day = (next_first - timedelta(days=1)).day
    return date(year, month, min(day.day, last_day))


def jan1(day: date) -> date:
    return date(day.year, 1, 1)


def weeks(n: int) -> timedelta:
    return timedelta(weeks=n)


def crossed(before: float, now: float, levels: Sequence[int]) -> int | None:
    """The highest level L with before < L <= now (a threshold crossed upward), else None."""
    hits = [level for level in levels if before < level <= now]
    return max(hits) if hits else None


FINISH_FIELD = 15  # finish-based kinds need a field of 15 or more (spec §4.3)


def finish_at(day: Day, level: int) -> bool | None:
    """Finished in the top `level` of a full field. None: not a held Sunday with a rank;
    False: a field under FINISH_FIELD never counts as a finish (podium, first-since, wins)."""
    if not day.held or day.rank is None:
        return None
    return day.rank <= level and day.field_n >= FINISH_FIELD


def top_third(day: Day) -> bool | None:
    """Finished in the top third of a full field (same guard as finish_at)."""
    if not day.held or day.rank is None:
        return None
    return day.rank * 3 <= day.field_n and day.field_n >= FINISH_FIELD


SHOOTER_WRAP_MIN = 12  # Sundays a shooter needs in the year for "pf.year-wrapped"


def wrap_year(as_of: date) -> int | None:
    """Year Y is wrapped while the latest Sunday is in December Y or January Y + 1.

    The one rule for the shooter wrap and the club wrap, so home never shows two different years.
    """
    if as_of.month == 12:
        return as_of.year
    if as_of.month == 1:
        return as_of.year - 1
    return None


def run_back(days: Sequence[Day], ok: Callable[[Day], bool | None]) -> int:
    """Length of the run of days at the end of `days` where ok() is True; None skips a day."""
    n = 0
    for d in reversed(days):
        verdict = ok(d)
        if verdict is None:
            continue
        if not verdict:
            break
        n += 1
    return n


def run_start(days: Sequence[Day], ok: Callable[[Day], bool | None], length: int) -> Day:
    """The first day of the trailing run of `length` counted days (see run_back)."""
    counted = [d for d in days if ok(d) is not None]
    if not 0 < length <= len(counted):
        raise ValueError(f"run length {length} does not fit {len(counted)} counted days")
    return counted[-length]


def in_year(days: Sequence[Day], year: int) -> list[Day]:
    return [d for d in days if d.date.year == year]
