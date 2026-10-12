"""Recap-only facts for the weekly club email's "This week" (owner, 2026-10-11).

The site's stored Sunday insights are mostly roll-ups, wins and first-timers, which the email
leaves out on purpose, so "This week" was short and kept repeating one kind. This module adds a
second source of lines: club-level and attendance facts that make sense to a reader who never
opens the site. Each type says something only when it is genuinely notable (the thresholds below
are named constants), and every fact for a held regular Sunday D is computed only from data dated
on or before D, so the same date always gives the same facts.

Wording rules (the same as the rest of the email): plain words with no site jargon, names read
"First Last", named lines are positive or neutral, never a ranking of people, never he/she/his/her.
"""

from __future__ import annotations

import calendar
import statistics
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise
from typing import Any, Final, cast

import pandas as pd

from sunday_clays.analytics import club_milestones as cm
from sunday_clays.analytics import frames, streaks
from sunday_clays.analytics.insights.context import InsightFrames, Sunday, mean
from sunday_clays.station_label import label_sort_key

FACT_TYPES: Final[tuple[str, ...]] = (
    "turnout",
    "course_type",
    "course_stations",
    "scores_context",
    "weather",
    "on_this_day",
    "year_so_far",
    "club_next",
    "attendance_streak",
    "station_feats",
    "improvement",
    "coming_up",
)

# --- thresholds: tune here ---------------------------------------------------------------------
#: "Biggest/coldest/... since" claims need the last time to be at least this many weeks back.
SINCE_WEEKS: Final = 8
#: "...on record" claims need at least this many earlier held Sundays behind them.
RECORD_MIN_HISTORY: Final = 26
#: A claim about the first Sundays of the data (nothing to compare with) is never made.
MIN_HISTORY: Final = 8
#: A calendar-month claim needs this many earlier Sundays of that month, in two or more years.
MONTH_MIN_PRIOR: Final = 3
MONTH_MIN_YEARS: Final = 2
#: Median score: best for its calendar month in this many days (two years), or overall in 12 weeks.
SCORE_MONTH_DAYS: Final = 730
SCORE_OVERALL_WEEKS: Final = 12
#: A station must have this many entries that day, and the spread must be this many points.
STATION_MIN_ENTRIES: Final = 5
STATION_SPREAD_MIN: Final = 15.0
#: Weather floors: coldest/hottest/windiest only say something at or past these.
COLD_MAX_F: Final = 50.0
HOT_MIN_F: Final = 80.0
GUST_MIN_MPH: Final = 20.0
#: The year-so-far line fires on crossing a multiple of this many rounds, or on passing last year.
YEAR_ROUND_STEP: Final = 100
YEAR_MIN_SUNDAYS: Final = 26  # a "full" earlier year
#: club_next: within this many typical Sundays of the next club milestone.
CLUB_REACH_SUNDAYS: Final = 3
CLUB_TYPICAL_WINDOW: Final = 8
#: attendance streak: a multiple of STREAK_STEP, or at least STREAK_LONG, a multiple of
#: STREAK_LONG_STEP and the club's longest (without the step the longest run is news every week).
STREAK_STEP: Final = 10
STREAK_LONG: Final = 12
STREAK_LONG_STEP: Final = 5
#: station feats: every target broken at this many stations; this many shooters on one station.
FEAT_STATIONS_MIN: Final = 4
FEAT_CLUB_MIN: Final = 3
#: improvement: 20-Sunday average up this many targets on 52 weeks earlier.
IMPROVE_WINDOW: Final = 20
IMPROVE_MIN_GAIN: Final = 2.0
IMPROVE_MIN_LAST_YEAR: Final = 10
YEAR_DAYS: Final = 364
#: coming_up: within this many Sundays of the next multiple of COMING_STEP.
COMING_STEP: Final = 25
COMING_WITHIN: Final = 3

#: How much each type matters, on the scale of the site's ranked insights (care x strength).
CARE: Final[dict[str, float]] = {
    "turnout": 4.0,
    "course_type": 3.0,
    "course_stations": 3.0,
    "scores_context": 3.0,
    "weather": 3.0,
    "on_this_day": 2.0,
    "year_so_far": 3.5,
    "club_next": 3.0,
    "attendance_streak": 3.5,
    "station_feats": 3.5,
    "improvement": 4.0,
    "coming_up": 3.0,
}
MAG_FLOOR: Final = 0.5
MAG_CAP: Final = 2.0

_NOUNS: Final[dict[str, tuple[str, str]]] = {
    "rounds": ("round", "rounds"),
    "clays_thrown": ("clay", "clays"),
    "sundays_held": ("Sunday", "Sundays"),
    "shooters": ("shooter", "shooters"),
}


@dataclass(frozen=True, slots=True)
class RecapFact:
    type: str
    text: str
    named_ids: tuple[int, ...]
    strength: float


def _fact(kind: str, text: str, magnitude: float, named: tuple[int, ...] = ()) -> RecapFact:
    return RecapFact(kind, text, named, CARE[kind] * min(max(magnitude, MAG_FLOOR), MAG_CAP))


def month_year(day: date) -> str:
    return f"{calendar.month_name[day.month]} {day.year}"


def _since(day: date | None) -> str:
    return "on record" if day is None else f"since {month_year(day)}"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n:,} {one if n == 1 else many}"


def _round(value: float) -> int:
    return int(value + 0.5)


def _weeks(earlier: date, later: date) -> int:
    return (later - earlier).days // 7


def _gap_magnitude(last: date | None, today: date) -> float:
    """Half a year back is 1.0; 'on record' is the cap."""
    return MAG_CAP if last is None else _weeks(last, today) / 26


def _crowd(s: Sunday) -> int:
    return s.head_count if s.head_count is not None else s.n


def _num(x: float) -> str:
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.1f}"


def _a(month: int) -> str:
    return "an" if calendar.month_name[month][0] in "AEIO" else "a"


def _long_enough(last: date | None, today: date, history: int) -> bool:
    """A 'since' claim needs the last time at least SINCE_WEEKS back; 'on record' needs history."""
    if last is None:
        return history >= RECORD_MIN_HISTORY
    return _weeks(last, today) >= SINCE_WEEKS


class FactSource:
    """Facts for any held regular Sunday of one set of frames (built once, asked per Sunday)."""

    def __init__(self, fr: InsightFrames, *, club_next: bool = True) -> None:
        self.fr = fr
        self.club_next = club_next
        events = fr.events
        self._types: dict[date, tuple[str, str]] = {
            d: (str(t), str(src))
            for d, t, src in zip(
                events["event_date"], events["round_type"], events["round_type_source"], strict=True
            )
        }
        counts = Counter(fr.rounds["event_date"])
        self._round_dates = sorted(counts)
        self._rounds_on = counts
        total = 0
        self._cumulative: list[int] = []
        for d in self._round_dates:
            total += counts[d]
            self._cumulative.append(total)
        stations = fr.stations
        self._stations: dict[date, pd.DataFrame] = (
            {cast(date, d): g for d, g in stations.groupby("event_date", sort=False)}
            if len(stations)
            else {}
        )
        self._series: tuple[cm.TotalsRow, ...] | None = None
        self._series_days: list[date] = []

    # --- shared helpers ---------------------------------------------------------------------

    def _rounds_through(self, day: date) -> int:
        i = bisect_right(self._round_dates, day)
        return self._cumulative[i - 1] if i else 0

    def _known_type(self, day: date) -> str | None:
        entry = self._types.get(day)
        return None if entry is None or entry[1] == "none" else entry[0]

    def _club_series(self) -> tuple[cm.TotalsRow, ...]:
        if self._series is None:
            fr = self.fr
            self._series = (
                ()
                if fr.as_of is None
                else cm.compute_milestones(fr.rounds, fr.appearances, fr.calendar, fr.as_of).series
            )
            self._series_days = [row.event_date for row in self._series]
        return self._series

    # --- the public call --------------------------------------------------------------------

    def on(self, day: date) -> list[RecapFact]:
        i = self.fr.sunday_index.get(day)
        if i is None:
            return []
        found: list[RecapFact] = [
            *self._turnout(i),
            *self._course_type(i),
            *self._course_stations(day),
            *self._scores_context(i),
            *self._weather(i),
            *self._on_this_day(i),
            *self._year_so_far(i),
            *(self._club_next(day) if self.club_next else []),
            *self._attendance_streak(i),
            *self._station_feats(i),
            *self._improvement(i),
            *self._coming_up(i),
        ]
        return sorted(found, key=lambda f: (-f.strength, f.type, f.text))

    # --- 1. turnout -------------------------------------------------------------------------

    def _turnout(self, i: int) -> list[RecapFact]:
        sundays = self.fr.sundays
        today, prior = sundays[i], sundays[:i]
        n = _crowd(today)
        if n < 1 or len(prior) < MIN_HISTORY:
            return []
        options: list[RecapFact] = []
        bigger = [s for s in prior if _crowd(s) >= n]
        last = bigger[-1].date if bigger else None
        if _long_enough(last, today.date, len(prior)):
            options.append(
                _fact(
                    "turnout",
                    f"{n} came out, the biggest crowd {_since(last)}.",
                    _gap_magnitude(last, today.date),
                )
            )
        same = [s for s in prior if s.date.month == today.date.month]
        years = {s.date.year for s in same}
        if (
            len(same) >= MONTH_MIN_PRIOR
            and len(years) >= MONTH_MIN_YEARS
            and all(n > _crowd(s) for s in same)
        ):
            month = calendar.month_name[today.date.month]
            options.append(
                _fact("turnout", f"{n} came out, the biggest {month} Sunday on record.", 1.0)
            )
        return [max(options, key=lambda f: f.strength)] if options else []

    # --- 2. course --------------------------------------------------------------------------

    def _course_type(self, i: int) -> list[RecapFact]:
        sundays = self.fr.sundays
        today, prior = sundays[i], sundays[:i]
        current = self._known_type(today.date)
        if current is None or len(prior) < MIN_HISTORY:
            return []
        previous = next((s for s in reversed(prior) if self._known_type(s.date) is not None), None)
        if previous is None or self._known_type(previous.date) == current:
            return []
        same = next((s for s in reversed(prior) if self._known_type(s.date) == current), None)
        last = None if same is None else same.date
        label = current.replace("_", " ")
        return [
            _fact(
                "course_type",
                f"The first {label} course {_since(last)}.",
                _gap_magnitude(last, today.date),
            )
        ]

    def _course_stations(self, day: date) -> list[RecapFact]:
        frame = self._stations.get(day)
        if frame is None:
            return []
        table: dict[str, float] = {}
        for label, group in frame.groupby("station_label", sort=False):
            targets = float(group["target_count"].sum())
            if len(group) >= STATION_MIN_ENTRIES and targets > 0:
                table[str(label)] = 100.0 * float(group["hits"].sum()) / targets
        if len(table) < 2:
            return []
        ordered = sorted(table, key=lambda label: (table[label], label_sort_key(label)))
        hardest, easiest = ordered[0], ordered[-1]
        spread = table[easiest] - table[hardest]
        if spread < STATION_SPREAD_MIN:
            return []
        text = (
            f"Toughest station: Station {hardest}, {_round(table[hardest])}% of targets broken. "
            f"Easiest: Station {easiest}, {_round(table[easiest])}%."
        )
        return [_fact("course_stations", text, spread / 30.0)]

    # --- 3. scores_context ------------------------------------------------------------------

    def _scores_context(self, i: int) -> list[RecapFact]:
        sundays = self.fr.sundays
        today = sundays[i]
        middle = today.median
        if middle is None:
            return []
        prior = [s for s in sundays[:i] if s.median is not None]
        month = today.date.month
        same = [s for s in prior if s.date.month == month]
        beaten = [s for s in same if s.median is not None and s.median >= middle]
        span: int | None
        if beaten:
            span = (today.date - beaten[-1].date).days
            since = f"since {beaten[-1].date.year}"
        elif same:
            span = (today.date - same[0].date).days
            since = "on record"
        else:
            span = None
            since = ""
        if span is not None and span >= SCORE_MONTH_DAYS:
            name = calendar.month_name[month]
            text = (
                f"The middle score of {_num(middle)} was the highest for "
                f"{_a(month)} {name} Sunday {since}."
            )
            return [_fact("scores_context", text, span / SCORE_MONTH_DAYS)]
        better = [s for s in prior if s.median is not None and s.median >= middle]
        last = better[-1].date if better else None
        if _long_enough(last, today.date, len(prior)) and (
            last is None or _weeks(last, today.date) >= SCORE_OVERALL_WEEKS
        ):
            text = f"The middle score of {_num(middle)} was the highest {_since(last)}."
            return [_fact("scores_context", text, _gap_magnitude(last, today.date))]
        return []

    # --- 4. weather -------------------------------------------------------------------------

    def _weather(self, i: int) -> list[RecapFact]:
        sundays = self.fr.sundays
        today, prior = sundays[i], sundays[:i]
        options: list[RecapFact] = []

        def consider(
            wording: Callable[[date | None], str],
            value: float | None,
            qualifies: Callable[[float], bool],
            matches: Callable[[Sunday], bool],
            measured: Callable[[Sunday], float | None],
        ) -> None:
            if value is None or not qualifies(value):
                return
            last = next((s.date for s in reversed(prior) if matches(s)), None)
            history = sum(measured(s) is not None for s in prior)
            if _long_enough(last, today.date, history):
                options.append(_fact("weather", wording(last), _gap_magnitude(last, today.date)))

        temp, gust, rain = today.temp_f, today.gust_mph, today.precip_in
        shown_t, shown_g = _round(temp or 0.0), _round(gust or 0.0)
        consider(
            lambda last: f"The coldest Sunday {_since(last)}: {shown_t} °F.",
            temp,
            lambda v: v <= COLD_MAX_F,
            lambda s: s.temp_f is not None and s.temp_f <= (temp or 0.0),
            lambda s: s.temp_f,
        )
        consider(
            lambda last: f"The hottest Sunday {_since(last)}: {shown_t} °F.",
            temp,
            lambda v: v >= HOT_MIN_F,
            lambda s: s.temp_f is not None and s.temp_f >= (temp or 0.0),
            lambda s: s.temp_f,
        )
        consider(
            lambda last: f"The windiest Sunday {_since(last)}: gusts up to {shown_g} mph.",
            gust,
            lambda v: v >= GUST_MIN_MPH,
            lambda s: s.gust_mph is not None and s.gust_mph >= (gust or 0.0),
            lambda s: s.gust_mph,
        )
        consider(
            lambda last: f"The first wet Sunday {_since(last)}.",
            rain,
            lambda v: v >= frames.WET_PRECIP_IN,
            lambda s: s.precip_in is not None and s.precip_in >= frames.WET_PRECIP_IN,
            lambda s: s.precip_in,
        )
        return [max(options, key=lambda f: (f.strength, f.text))] if options else []

    # --- 5. on_this_day ---------------------------------------------------------------------

    def _on_this_day(self, i: int) -> list[RecapFact]:
        sundays = self.fr.sundays
        today = sundays[i]
        target = today.date - timedelta(days=YEAR_DAYS)
        near = [s for s in sundays[:i] if abs((s.date - target).days) <= 7]
        if not near:
            return []
        then = min(near, key=lambda s: (abs((s.date - target).days), s.date))
        shooters = _plural(_crowd(then), "shooter", "shooters")
        top = "" if then.top is None else f", top score {then.top}"
        return [_fact("on_this_day", f"A year ago this week: {shooters}{top}.", 0.5)]

    # --- 6. year_so_far ---------------------------------------------------------------------

    def _year_so_far(self, i: int) -> list[RecapFact]:
        sundays = self.fr.sundays
        today = sundays[i]
        year = today.date.year
        start = date(year, 1, 1)
        so_far = self._rounds_through(today.date) - self._rounds_through(start - timedelta(days=1))
        before = so_far - self._rounds_on[today.date]
        held = sum(s.date.year == year for s in sundays[: i + 1])
        lead = f"{year} so far: {so_far:,} rounds over {_plural(held, 'Sunday', 'Sundays')}"
        last_start = date(year - 1, 1, 1)
        last_total = self._rounds_through(start - timedelta(days=1)) - self._rounds_through(
            last_start - timedelta(days=1)
        )
        last_held = sum(s.date.year == year - 1 for s in sundays[:i])
        if last_held >= YEAR_MIN_SUNDAYS and before <= last_total < so_far:
            text = f"{lead}, already more than all of {year - 1} ({last_total:,} rounds)."
            return [_fact("year_so_far", text, 1.5)]
        crossed = so_far // YEAR_ROUND_STEP
        if crossed > before // YEAR_ROUND_STEP:
            text = f"{lead}, past the {crossed * YEAR_ROUND_STEP:,}-round mark."
            return [_fact("year_so_far", text, 1.0)]
        return []

    # --- 7. club_next -----------------------------------------------------------------------

    def _club_next(self, day: date) -> list[RecapFact]:
        series = self._club_series()
        index = bisect_right(self._series_days, day) - 1
        if index < 0:
            return []
        row = series[index]
        window = series[max(0, index - CLUB_TYPICAL_WINDOW) : index + 1]
        out: list[RecapFact] = []
        for metric in cm.METRICS:
            current = int(getattr(row, metric))
            upcoming = next((t for t in cm.THRESHOLDS[metric] if t > current), None)
            if upcoming is None:
                continue
            steps = [int(getattr(b, metric)) - int(getattr(a, metric)) for a, b in pairwise(window)]
            typical = statistics.median(steps) if steps else 0.0
            limit = CLUB_REACH_SUNDAYS * max(typical, 1.0)
            remaining = upcoming - current
            if remaining > limit:
                continue
            one, many = _NOUNS[metric]
            text = (
                f"{_plural(remaining, 'more ' + one, 'more ' + many)} and the club reaches "
                f"{cm.milestone_label(metric, upcoming)} all time."
            )
            out.append(_fact("club_next", text, 2.0 - 1.5 * remaining / limit))
        return out

    # --- 8. attendance_streak ---------------------------------------------------------------

    def _attendance_streak(self, i: int) -> list[RecapFact]:
        fr = self.fr
        today = fr.sundays[i]
        came = {r.shooter_id for r in today.results}
        app, cal = fr.appearances, fr.calendar
        run = streaks.streaks(
            app.loc[[d <= today.date for d in app["event_date"]]],
            cal.loc[[d <= today.date for d in cal["event_date"]]],
            today.date,
        )
        current = {
            int(s): int(c)
            for s, c in zip(run["shooter_id"], run["current_streak"], strict=True)
            if fr.profiles.get(int(s)) is not None and not fr.profiles[int(s)].deceased
        }
        longest = max(current.values(), default=0)
        out: list[RecapFact] = []
        for sid, s in sorted(current.items()):
            if sid not in came:
                continue
            tier = s >= STREAK_STEP and s % STREAK_STEP == 0
            long_one = s >= STREAK_LONG and s == longest and s % STREAK_LONG_STEP == 0
            if tier or long_one:
                text = f"{fr.profiles[sid].name} has come out {s} Sundays in a row."
                out.append(_fact("attendance_streak", text, s / 30.0, (sid,)))
        return out

    # --- 9. station_feats -------------------------------------------------------------------

    def _station_feats(self, i: int) -> list[RecapFact]:
        fr = self.fr
        day = fr.sundays[i].date
        frame = self._stations.get(day)
        if frame is None:
            return []
        entries: dict[tuple[Any, Any], list[tuple[str, bool]]] = defaultdict(list)
        owner: dict[tuple[Any, Any], int] = {}
        for sheet, row, sid, label, hits, count in zip(
            frame["sheet_id"],
            frame["entry_row"],
            frame["shooter_id"],
            frame["station_label"],
            frame["hits"],
            frame["target_count"],
            strict=True,
        ):
            key = (sheet, row)
            entries[key].append((str(label), int(count) > 0 and int(hits) == int(count)))
            if not pd.isna(sid):
                owner[key] = int(sid)
        best: dict[int, tuple[int, int]] = {}  # shooter -> (stations cleaned, stations shot)
        cleaners: dict[str, set[int]] = defaultdict(set)
        for key, found in entries.items():
            who = owner.get(key)
            if who is None:
                continue
            cleaned = sum(flag for _, flag in found)
            best[who] = max(best.get(who, (0, 0)), (cleaned, len(found)))
            for label, flag in found:
                if flag:
                    cleaners[label].add(who)
        out: list[RecapFact] = []
        for sid, (cleaned, shot) in sorted(best.items()):
            profile = fr.profiles.get(sid)
            if cleaned >= FEAT_STATIONS_MIN and profile is not None and not profile.deceased:
                text = f"{profile.name} broke every target at {cleaned} of {shot} stations."
                out.append(_fact("station_feats", text, cleaned / 4.0, (sid,)))
        crowded = {label: len(who) for label, who in cleaners.items() if len(who) >= FEAT_CLUB_MIN}
        if crowded:
            label = min(crowded, key=lambda lab: (-crowded[lab], label_sort_key(lab)))
            n = crowded[label]
            text = f"{_plural(n, 'shooter', 'shooters')} broke every target at Station {label}."
            out.append(_fact("station_feats", text, n / 4.0))
        return out

    # --- 10. improvement --------------------------------------------------------------------

    def _improvement(self, i: int) -> list[RecapFact]:
        fr = self.fr
        today = fr.sundays[i]
        cutoff = today.date - timedelta(days=YEAR_DAYS)
        out: list[RecapFact] = []
        for result in today.results:
            sid = result.shooter_id
            profile = fr.profiles.get(sid)
            if profile is None or profile.deceased:
                continue
            days = fr.history_until(sid, today.date)
            old = [d for d in days if d.date <= cutoff]
            if len(old) < IMPROVE_WINDOW or len(days) - len(old) < IMPROVE_MIN_LAST_YEAR:
                continue
            now = mean([float(d.score) for d in days[-IMPROVE_WINDOW:]])
            then = mean([float(d.score) for d in old[-IMPROVE_WINDOW:]])
            gain = round(now - then, 1)
            if gain >= IMPROVE_MIN_GAIN:
                text = (
                    f"{profile.name}'s average over the last {IMPROVE_WINDOW} Sundays is up "
                    f"{gain:.1f} targets on a year ago."
                )
                out.append(_fact("improvement", text, gain / 3.0, (sid,)))
        return out

    # --- 11. coming_up ----------------------------------------------------------------------

    def _coming_up(self, i: int) -> list[RecapFact]:
        fr = self.fr
        today = fr.sundays[i]
        out: list[RecapFact] = []
        for result in today.results:
            sid = result.shooter_id
            profile = fr.profiles.get(sid)
            if profile is None or profile.deceased:
                continue
            count = fr.appearances_through(sid, today.date)
            upcoming = (count // COMING_STEP + 1) * COMING_STEP
            to_go = upcoming - count  # 25 when today is itself the round number: Milestones'
            if to_go > COMING_WITHIN:
                continue
            text = (
                f"{profile.name} is {_plural(to_go, 'Sunday', 'Sundays')} away from "
                f"a {upcoming}th Sunday."
            )
            bonus = 0.5 if upcoming % 100 == 0 else 0.0
            out.append(_fact("coming_up", text, 1.2 - 0.2 * to_go + bonus, (sid,)))
        return out


def week_facts(fr: InsightFrames, day: date, *, club_next: bool = True) -> list[RecapFact]:
    """Every notable fact for held regular Sunday `day`, strongest first."""
    return FactSource(fr, club_next=club_next).on(day)
