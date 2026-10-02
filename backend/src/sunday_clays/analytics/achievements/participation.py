"""Participation trophies (C12, Plan 10 T2): non-ranking milestone families and calendar /
participation one-offs. Every definition reads only data dated on or before its award date."""

from __future__ import annotations

import calendar
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from typing import Any

import pandas as pd

from sunday_clays.analytics import frames
from sunday_clays.analytics.achievements.context import AchContext, empty_value_frame
from sunday_clays.analytics.achievements.registry import (
    Achievement,
    Award,
    Category,
    make_tiers,
    register,
)
from sunday_clays.analytics.frames import season_label

TARGETS_PER_ROUND = 50
PB_MIN_PRIOR_ROUNDS = 5
WELCOME_BACK_DAYS = 180
ANNIVERSARY_WINDOW_DAYS = 7
PERFECT_MONTH_MIN_EVENTS = 3
THREE_BIRD_LABELS = frozenset({"3 bird shoot", "three bird shoot"})


def _series(days: pd.DataFrame, values: pd.Series) -> pd.DataFrame:
    if days.empty:
        return empty_value_frame()
    return pd.DataFrame(
        {
            "shooter_id": days["shooter_id"].to_numpy(),
            "event_date": days["event_ts"].to_numpy(),
            "value": values.to_numpy(dtype=float),
        }
    )


def _round_id(value: Any) -> int | None:
    """A day's best round id, or None on a special Sunday (no scored round, Plan 17)."""
    return None if pd.isna(value) else int(value)


# ---- tiered value functions (cumulative value after each attended date) ---------------------


def clays_broken_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    return _series(days, days["cum_sum"])


def clays_thrown_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    return _series(days, days["cum_rounds"] * TARGETS_PER_ROUND)


def events_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.attendance_days
    return _series(days, days["n_events"])


def years_active_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.attendance_days
    keys = pd.DataFrame({"shooter_id": days["shooter_id"], "year": days["event_ts"].dt.year})
    first_in_year = (~keys.duplicated()).astype(int)
    return _series(days, first_in_year.groupby(days["shooter_id"]).cumsum())


def big_year_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.attendance_days
    year = days["event_ts"].dt.year
    in_year = days.groupby([days["shooter_id"], year]).cumcount() + 1
    return _series(days, in_year.groupby(days["shooter_id"]).cummax())


def iron_streak_value(ctx: AchContext) -> pd.DataFrame:
    """Longest run of consecutive held events attended, from analytics.streaks.streaks() (C7)."""
    days = ctx.attendance_days
    if days.empty:
        return empty_value_frame()
    parts: list[pd.DataFrame] = []
    for day in sorted(set(days["event_date"])):
        longest = ctx.streaks_at(day).set_index("shooter_id")["longest_streak"]
        attending = days[days["event_date"] == day]
        parts.append(
            pd.DataFrame(
                {
                    "shooter_id": attending["shooter_id"].to_numpy(),
                    "event_date": attending["event_ts"].to_numpy(),
                    "value": attending["shooter_id"].map(longest).fillna(0).to_numpy(dtype=float),
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def personal_bests_value(ctx: AchContext) -> pd.DataFrame:
    """New PBs: the day's best round beats every round on earlier dates (>= 5 of them).

    At most one per day, however many rounds the shooter shot that day."""
    days = ctx.shooter_days
    new_pb = (
        (days["prior_rounds"] >= PB_MIN_PRIOR_ROUNDS) & (days["day_best"] > days["prior_best"])
    ).astype(int)
    return _series(days, new_pb.groupby(days["shooter_id"]).cumsum())


# ---- one-offs ---------------------------------------------------------------------------------


def _doubleheader(ctx: AchContext) -> Iterator[Award]:
    days = ctx.shooter_days
    hits = days[days["n_rounds"] >= 2]
    for sid, day, n in zip(hits["shooter_id"], hits["event_date"], hits["n_rounds"], strict=True):
        yield Award(int(sid), "doubleheader", day, None, {"rounds": int(n)})


def _new_year(ctx: AchContext) -> Iterator[Award]:
    """The year's first regular held Sunday, and any special Sunday before it (Decision 10).

    Each shooter at most once a year, at the earliest of those Sundays they shot."""
    regular = ctx.held_dates()
    first_regular: dict[int, date] = {}
    for day in regular:
        first_regular.setdefault(day.year, day)
    regular_days = set(regular)
    qualifying = set(first_regular.values()) | {
        day
        for day in ctx.calendar_held_dates()
        if day not in regular_days
        and (day.year not in first_regular or day < first_regular[day.year])
    }
    days = ctx.attendance_days
    hits = days[days["event_date"].isin(qualifying)]
    hits = hits.assign(year=hits["event_ts"].dt.year).drop_duplicates(["shooter_id", "year"])
    for sid, day, rid in zip(
        hits["shooter_id"], hits["event_date"], hits["best_round_id"], strict=True
    ):
        yield Award(int(sid), "new_year", day, _round_id(rid), {"year": day.year})


def normalize_label(label: str) -> str:
    """Casefolded, hyphens and underscores as spaces, whitespace collapsed."""
    return " ".join(label.casefold().replace("-", " ").replace("_", " ").split())


def _three_bird_shoot(ctx: AchContext) -> Iterator[Award]:
    """The first special Sunday a shooter shot whose label is a 3-bird shoot (appearances and
    calendar only; a later 3-bird shoot never awards again or moves the date)."""
    cal = ctx.calendar
    special = cal[cal["kind"].eq(frames.EVENT_KIND_SPECIAL)]
    labels = {
        day: str(label)
        for day, label in zip(special["event_date"], special["label"], strict=True)
        if isinstance(label, str) and normalize_label(label) in THREE_BIRD_LABELS
    }
    if not labels:
        return
    days = ctx.attendance_days
    hits = days[days["special"] & days["event_date"].isin(labels)].drop_duplicates("shooter_id")
    for sid, day in zip(hits["shooter_id"], hits["event_date"], strict=True):
        yield Award(
            int(sid),
            "three_bird_shoot",
            day,
            None,
            {"label": labels[day], "event_date": day.isoformat()},
        )


def _anniversary(years: int) -> Callable[[AchContext], Iterator[Award]]:
    code = f"anniversary_{years}"
    low = 365 * years - ANNIVERSARY_WINDOW_DAYS
    high = 365 * years + ANNIVERSARY_WINDOW_DAYS

    def evaluate(ctx: AchContext) -> Iterator[Award]:
        days = ctx.attendance_days
        since_first = (
            days["event_ts"] - days.groupby("shooter_id")["event_ts"].transform("min")
        ).dt.days
        hits = days[(since_first >= low) & (since_first <= high)]
        for sid, day in zip(hits["shooter_id"], hits["event_date"], strict=True):
            yield Award(int(sid), code, day, None, {"years": years})

    return evaluate


def _welcome_back(ctx: AchContext) -> Iterator[Award]:
    days = ctx.attendance_days
    gap = (days["event_ts"] - days["prev_ts"]).dt.days
    back = gap >= WELCOME_BACK_DAYS
    hits = days[back]
    for sid, day, rid, away in zip(
        hits["shooter_id"], hits["event_date"], hits["best_round_id"], gap[back], strict=True
    ):
        yield Award(int(sid), "welcome_back", day, _round_id(rid), {"days_away": int(away)})


def _joined_club(ctx: AchContext) -> Iterator[Award]:
    rounds = ctx.rounds
    first_guest = rounds[rounds["status"] == "guest"].groupby("shooter_id")["event_ts"].min()
    if first_guest.empty:
        return
    members = rounds[rounds["status"] == "member"].sort_values(
        ["shooter_id", "event_ts", "ordinal"], kind="stable"
    )
    later = members[members["event_ts"] > pd.to_datetime(members["shooter_id"].map(first_guest))]
    first = later.groupby("shooter_id", sort=True).head(1)
    for sid, ts, rid in zip(first["shooter_id"], first["event_ts"], first["round_id"], strict=True):
        yield Award(int(sid), "joined_club", ts.date(), int(rid), {})


def _both_disciplines(ctx: AchContext) -> Iterator[Award]:
    typed = ctx.rounds
    if typed.empty:
        return
    firsts = (
        typed.groupby(["shooter_id", "round_type"])["event_ts"]
        .min()
        .unstack()
        .reindex(columns=["sporting", "super_sporting"])
        .dropna()
    )
    for sid, sporting, super_sporting in zip(
        firsts.index, firsts["sporting"], firsts["super_sporting"], strict=True
    ):
        yield Award(int(sid), "both_disciplines", max(sporting, super_sporting).date(), None, {})


def _four_seasons(ctx: AchContext) -> Iterator[Award]:
    days = ctx.attendance_days
    if days.empty:
        return
    frame = pd.DataFrame(
        {
            "shooter_id": days["shooter_id"],
            "event_ts": days["event_ts"],
            "event_date": days["event_date"],
        }
    )
    frame["season_year"] = frame["event_ts"].dt.year + (frame["event_ts"].dt.month == 12).astype(
        int
    )
    frame["season"] = [season_label(day) for day in frame["event_date"]]
    new_season = (~frame.duplicated(["shooter_id", "season_year", "season"])).astype(int)
    frame["n_seasons"] = new_season.groupby([frame["shooter_id"], frame["season_year"]]).cumsum()
    first = frame[frame["n_seasons"] >= 4].groupby("shooter_id", sort=True).head(1)
    for sid, day, season_year in zip(
        first["shooter_id"], first["event_date"], first["season_year"], strict=True
    ):
        yield Award(int(sid), "four_seasons", day, None, {"season_year": int(season_year)})


def last_sunday(year: int, month: int) -> date:
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() + 1) % 7)


def _perfect_month(ctx: AchContext) -> Iterator[Award]:
    """Month M with >= 3 Sundays, every regular held one attended.

    Dated at the closing event: the first held event on or after M's last calendar Sunday L
    (L itself when L was held). Only M's held events up to the closing event count, so a held
    non-Sunday after a held L cannot change an award already dated L (no leak, never moves).
    A special Sunday shot in M up to the closing event counts toward the three and is never
    required (Plan 17, Decision 10)."""
    held = ctx.held_dates()
    days = ctx.attendance_days
    attendees: dict[date, set[int]] = {}
    specials: dict[int, list[date]] = {}
    for sid, day, special in zip(
        days["shooter_id"], days["event_date"], days["special"], strict=True
    ):
        if special:
            specials.setdefault(int(sid), []).append(day)
        else:
            attendees.setdefault(day, set()).add(int(sid))
    months: dict[tuple[int, int], list[date]] = {}
    for day in held:
        months.setdefault((day.year, day.month), []).append(day)
    for (year, month), month_days in sorted(months.items()):
        cutoff = last_sunday(year, month)
        closing = next((day for day in held if day >= cutoff), None)
        if closing is None:
            continue
        counted = [day for day in month_days if day <= closing]
        perfect = set(attendees.get(counted[0], set()))
        for day in counted[1:]:
            perfect &= attendees.get(day, set())
        for sid in sorted(perfect):
            extra = sum(
                1
                for day in specials.get(sid, ())
                if (day.year, day.month) == (year, month) and day <= closing
            )
            if len(counted) + extra < PERFECT_MONTH_MIN_EVENTS:
                continue
            yield Award(sid, "perfect_month", closing, None, {"month": f"{year:04d}-{month:02d}"})


# ---- registration -----------------------------------------------------------------------------

register(
    Achievement(
        code="clays_broken",
        name="Clays Broken",
        description="Lifetime targets broken (the sum of every round's score).",
        category=Category.MILESTONE,
        art_key="clays_broken",
        tiers=make_tiers((100, 500, 1000, 2500, 5000, 10000), "clays broken"),
        value=clays_broken_value,
    )
)
register(
    Achievement(
        code="clays_thrown",
        name="Clays Thrown",
        description="Lifetime targets thrown at you: 50 per round.",
        category=Category.MILESTONE,
        art_key="clays_thrown",
        tiers=make_tiers((500, 1000, 2500, 5000, 10000), "clays thrown"),
        value=clays_thrown_value,
    )
)
register(
    Achievement(
        code="events",
        name="Events Attended",
        description="Sundays shot.",
        category=Category.MILESTONE,
        art_key="events",
        tiers=make_tiers((1, 10, 25, 50, 100, 150, 200, 250), "events", singular="event"),
        value=events_value,
    )
)
register(
    Achievement(
        code="years_active",
        name="Years Active",
        description="Calendar years with at least one Sunday shot.",
        category=Category.MILESTONE,
        art_key="years_active",
        tiers=make_tiers((2, 3, 5, 7), "years"),
        value=years_active_value,
    )
)
register(
    Achievement(
        code="big_year",
        name="Big Year",
        description="Most events attended in a single calendar year.",
        category=Category.MILESTONE,
        art_key="big_year",
        tiers=make_tiers((20, 30, 40), "events in one year"),
        value=big_year_value,
    )
)
register(
    Achievement(
        code="iron_streak",
        name="Iron Streak",
        description=(
            "Consecutive held events attended; attendance-only dates neither extend nor break it."
        ),
        category=Category.MILESTONE,
        art_key="iron_streak",
        tiers=make_tiers((4, 8, 12, 26), "straight events"),
        value=iron_streak_value,
    )
)
register(
    Achievement(
        code="personal_bests",
        name="Personal Bests",
        description="Days whose best round beat every earlier round (after at least 5 rounds).",
        category=Category.SCORING,
        art_key="personal_bests",
        tiers=make_tiers((1, 5, 10), "personal bests", singular="personal best"),
        value=personal_bests_value,
    )
)
register(
    Achievement(
        code="doubleheader",
        name="Doubleheader",
        description="Shot two rounds on the same Sunday.",
        category=Category.MILESTONE,
        art_key="doubleheader",
        evaluate=_doubleheader,
    )
)
register(
    Achievement(
        code="new_year",
        name="New Year's Shooter",
        description="Shot the first Sunday of a calendar year.",
        category=Category.CALENDAR,
        art_key="new_year",
        evaluate=_new_year,
    )
)
register(
    Achievement(
        code="anniversary_1",
        name="One-Year Anniversary",
        description="Shot within a week of the first anniversary of your first event.",
        category=Category.CALENDAR,
        art_key="anniversary_1",
        evaluate=_anniversary(1),
    )
)
register(
    Achievement(
        code="anniversary_5",
        name="Five-Year Anniversary",
        description="Shot within a week of the fifth anniversary of your first event.",
        category=Category.CALENDAR,
        art_key="anniversary_5",
        evaluate=_anniversary(5),
    )
)
register(
    Achievement(
        code="welcome_back",
        name="Welcome Back",
        description="Returned after 180 or more days away.",
        category=Category.CALENDAR,
        art_key="welcome_back",
        evaluate=_welcome_back,
        repeatable=True,
    )
)
register(
    Achievement(
        code="joined_club",
        name="Joined the Club",
        description="Shot as a member after first shooting as a guest.",
        category=Category.MILESTONE,
        art_key="joined_club",
        evaluate=_joined_club,
    )
)
register(
    Achievement(
        code="both_disciplines",
        name="Both Disciplines",
        description="Shot both a sporting and a super sporting day.",
        category=Category.MILESTONE,
        art_key="both_disciplines",
        evaluate=_both_disciplines,
    )
)
register(
    Achievement(
        code="four_seasons",
        name="Four Seasons",
        description=(
            "Shot in winter, spring, summer and fall of one year "
            "(December counts toward the next winter)."
        ),
        category=Category.CALENDAR,
        art_key="four_seasons",
        evaluate=_four_seasons,
    )
)
register(
    Achievement(
        code="perfect_month",
        name="Perfect Month",
        description="Shot every Sunday held in a month with three or more Sundays.",
        category=Category.CALENDAR,
        art_key="perfect_month",
        evaluate=_perfect_month,
        repeatable=True,
    )
)
register(
    Achievement(
        code="three_bird_shoot",
        name="3-Bird Shoot",
        description="Shot the 3-Bird Shoot.",
        category=Category.CALENDAR,
        art_key="three_bird_shoot",
        evaluate=_three_bird_shoot,
    )
)
