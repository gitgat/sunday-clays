"""Anchor registry (spec §3.6.4): every page chart an insight can link to, and its rows.

`ANCHORS` is the backend half of `frontend/src/features/insights/anchors.ts`; a backend test
exports the ids to `tests/golden/insight_anchors.json` and a frontend test checks each resolves
to a rendered `ChartFrame` with `id="chart-{urlKey}"`. `source` returns the rows the target
chart draws (the chart-proof test reads headline numbers off them), with key columns named as
the Explorer names them: `event` (ISO date), `shooter_id`, `year`, or `key`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import date

import pandas as pd

from sunday_clays.analytics.cohorts import cohort_returns, first_round_scores
from sunday_clays.analytics.insights.context import Day, InsightFrames, mean
from sunday_clays.analytics.insights.types import ChartLink
from sunday_clays.analytics.leaderboards import (
    LeaderboardMetric,
    LeaderboardPeriod,
    leaderboard,
    make_leaderboard_frames,
    period_bounds,
)
from sunday_clays.analytics.points import event_points
from sunday_clays.analytics.profile import learning_curve
from sunday_clays.analytics.streaks import streaks

Source = Callable[[InsightFrames, ChartLink], pd.DataFrame]


@dataclass(frozen=True)
class Anchor:
    id: str
    route: str  # the route pattern, for the anchor table and the frontend check
    feature: str
    source: Source


def _route_id(link: ChartLink) -> int:
    return int(str(link.route).rstrip("/").rsplit("/", 1)[-1])


def _route_date(link: ChartLink) -> date:
    return date.fromisoformat(str(link.route).rstrip("/").rsplit("/", 1)[-1])


def _in_window(days: tuple[Day, ...], link: ChartLink) -> list[Day]:
    return [d for d in days if link.window.start <= d.date <= link.window.end]


def trend_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """Score history: best round each Sunday plus the trend chart's optional lines."""
    days = fr.histories.get(_route_id(link), ())
    rows = []
    for i, d in enumerate(days):
        scores = [x.score for x in days[: i + 1]]
        rows.append(
            {
                "event": d.date.isoformat(),
                "score": d.score,
                "adjusted": d.adjusted,
                "pb": max(scores),
                "so_far": d.prior_mean,
                "roll10": mean([float(s) for s in scores[-10:]]) if len(scores) >= 10 else None,
                "roll20": mean([float(s) for s in scores[-20:]]) if len(scores) >= 20 else None,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    start, end = link.window.start.isoformat(), link.window.end.isoformat()
    return frame[(frame["event"] >= start) & (frame["event"] <= end)].reset_index(drop=True)


def rating_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    points = fr.ratings.get(_route_id(link), ())
    return pd.DataFrame(
        [
            {"event": d.isoformat(), "value": mu}
            for d, mu in points
            if link.window.start <= d <= link.window.end
        ],
        columns=["event", "value"],
    )


def calendar_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    days = _in_window(fr.histories.get(_route_id(link), ()), link)
    return pd.DataFrame(
        [
            {
                "event": d.date.isoformat(),
                "value": d.score,
                "held_value": d.score if d.held else None,
                "month": d.date.strftime("%Y-%m"),
            }
            for d in days
        ],
        columns=["event", "value", "held_value", "month"],
    )


def finishes_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    days = _in_window(fr.histories.get(_route_id(link), ()), link)
    return pd.DataFrame(
        [
            {"event": d.date.isoformat(), "value": d.rank, "n": d.field_n}
            for d in days
            if d.held and d.rank is not None
        ],
        columns=["event", "value", "n"],
    )


def tough_days_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    days = _in_window(fr.histories.get(_route_id(link), ()), link)
    return pd.DataFrame(
        [
            {"event": d.date.isoformat(), "difficulty": d.difficulty, "value": d.adjusted}
            for d in days
            if d.held and d.difficulty is not None and d.adjusted is not None
        ],
        columns=["event", "difficulty", "value"],
    )


def learning_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """The profile's learning curve: vs-the-field by career Sunday number, and the club's median
    at each number (Plan 06 `profile.learning_curve`, left-censored shooters left out)."""
    points = learning_curve(fr.rounds, fr.shooters, _route_id(link))
    return pd.DataFrame(
        [{"key": str(p.k), "value": p.value, "club": p.club_median} for p in points],
        columns=["key", "value", "club"],
    )


def results_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    day = _route_date(link)
    rows = []
    for sid, days in fr.histories.items():
        d = next((x for x in days if x.date == day), None)
        if d is not None:
            rows.append(
                {
                    "shooter_id": sid,
                    "score": d.score,
                    "rank": d.rank,
                    "residual": d.residual,
                    "adjusted": d.adjusted,
                    "value": d.score,
                }
            )
    columns = ["shooter_id", "score", "rank", "residual", "adjusted", "value"]
    if not rows:
        return pd.DataFrame(rows, columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["score", "shooter_id"], ascending=[False, True]
    )


def highest_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """The records page's highest rounds (48 and up), with the date and the shooter."""
    rows = [
        {
            "event": d.isoformat(),
            "shooter_id": int(sid),
            "value": int(score),
            "perfect": int(score) if score == 50 else None,
            "high": int(score) if score >= 49 else None,
        }
        for d, sid, score in zip(
            fr.rounds["event_date"], fr.rounds["shooter_id"], fr.rounds["score"], strict=True
        )
        if score >= 48 and link.window.start <= d <= link.window.end
    ]
    return pd.DataFrame(rows, columns=["event", "shooter_id", "value", "perfect", "high"])


def streak_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    table = streaks(fr.appearances, fr.calendar, link.window.end)
    return pd.DataFrame(
        {
            "shooter_id": table["shooter_id"].to_numpy(),
            "value": table["longest_streak"].to_numpy(),
            "current": table["current_streak"].to_numpy(),
        }
    )


def season_points_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """Points after the linked Sunday (`at`) over the link's period, as the race chart shows them.

    The race page defaults to the rolling 12 months; a ``period`` param picks another window.
    """
    at = date.fromisoformat(link.params.get("at", link.window.end.isoformat()))
    period = LeaderboardPeriod(link.params.get("period", "rolling_12"))
    start, _ = period_bounds(period, at)
    r = fr.rounds
    in_window = r[[(start is None or start <= d) and d <= at for d in r["event_date"]]]
    totals: dict[int, int] = {}
    earned = event_points(in_window)
    for sid, points in zip(earned["shooter_id"], earned["points"], strict=True):
        totals[int(sid)] = totals.get(int(sid), 0) + int(points)
    ordered = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return pd.DataFrame(
        [
            {"shooter_id": sid, "value": value, "rank": 1 + sum(v > value for v in totals.values())}
            for sid, value in ordered
        ],
        columns=["shooter_id", "value", "rank"],
    )


def newcomer_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """The club page's newcomers chart: first-round year, newcomers, and those who came back."""
    rounds = fr.rounds.loc[[d <= link.window.end for d in fr.rounds["event_date"]]]
    table = cohort_returns(rounds, fr.shooters)
    return pd.DataFrame(
        {
            "year": table["cohort_year"].astype(str).to_numpy(),
            "value": table["n_cohort"].to_numpy(),
            "returned": table["n_returned"].to_numpy(),
        }
    )


def board_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """The leaderboards page board for the link's metric over its window.

    The page takes its range from the header window (the link's Custom window), so the board is
    the "season" board with `since` = the window start; a start that is exactly YTD's or
    rolling-12's becomes that period, as on the page.
    """
    frames = make_leaderboard_frames(fr.rounds, fr.events, fr.rating)
    board = leaderboard(
        frames,
        LeaderboardPeriod.SEASON,
        LeaderboardMetric(link.params.get("metric", "season_points")),
        link.window.end,
        since=link.window.start,
    )
    return board.rows[["shooter_id", "value", "rank"]].reset_index(drop=True)


def movers_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """The leaderboards page's rating-gain board (gainers only) over the link window."""
    return board_rows(fr, replace(link, params={**link.params, "metric": "rating_gain"}))


def station_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """The stations page hit-rate chart: hit % per station over the window."""
    s = fr.stations
    frame = s.loc[[link.window.start <= d <= link.window.end for d in s["event_date"]]]
    rows = []
    labels = {
        (int(no), str(label))
        for no, label in zip(frame["station_no"], frame["station_label"], strict=True)
    }
    for _, label in sorted(labels):
        group = frame[frame["station_label"] == label]
        targets = float(group["target_count"].sum())
        value = 100.0 * float(group["hits"].sum()) / targets if targets else None
        rows.append({"station": label, "value": value})
    return pd.DataFrame(rows, columns=["station", "value"])


def first_round_rows(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """The club page's first-round histogram: first rounds per score over the window."""
    scores = first_round_scores(fr.rounds, link.window.start, link.window.end)
    counts = Counter(scores)
    return pd.DataFrame(
        {"score": [str(s) for s in sorted(counts)], "value": [counts[s] for s in sorted(counts)]},
        columns=["score", "value"],
    )


def page_rows_unavailable(fr: InsightFrames, link: ChartLink) -> pd.DataFrame:
    """Anchors whose numbers are quoted with `na` proof checks only."""
    return pd.DataFrame()


ANCHORS: Mapping[str, Anchor] = {
    a.id: a
    for a in (
        Anchor("trend", "/shooters/:id", "shooters", trend_rows),
        Anchor("rating", "/shooters/:id", "shooters", rating_rows),
        Anchor("cal", "/shooters/:id", "shooters", calendar_rows),
        Anchor("learn", "/shooters/:id", "shooters", learning_rows),
        Anchor("finishes", "/shooters/:id", "shooters", finishes_rows),
        Anchor("tough-days", "/shooters/:id", "shooters", tough_days_rows),
        Anchor("trophytl", "/shooters/:id", "achievements", page_rows_unavailable),
        Anchor("results", "/events/:date", "events", results_rows),
        Anchor("new", "/club", "club", newcomer_rows),
        Anchor("first-rounds", "/club", "club", first_round_rows),
        Anchor("rec-highest", "/records", "records", highest_rows),
        Anchor("rec-streaks", "/records", "records", streak_rows),
        Anchor("lb-board", "/leaderboards", "leaderboards", board_rows),
        Anchor("lb-movers", "/leaderboards", "leaderboards", movers_rows),
        Anchor("race-bars", "/race", "race", season_points_rows),
        Anchor("sthit", "/stations", "stations", station_rows),
    )
}
