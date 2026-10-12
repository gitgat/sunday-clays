"""Weekly recap facts for the club email (Plan 19 §3.3.1, D14, D15). Admin only (module prefix).

The email complements the club newsletter (owner, 2026-10-05): podium, personal bests and new
shooters are the newsletter's, so the recap carries the turnout, "This week" insights and the
Milestones lines. The server owns the rules and builds the Milestones lines; the SPA lays them out.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.achievements.participation import THREE_BIRD_LABELS, normalize_label
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.club_milestones import club_milestones
from sunday_clays.analytics.insights.store import insights_table, load_rows
from sunday_clays.analytics.insights.templates import natural_name
from sunday_clays.analytics.recap_facts import FactSource
from sunday_clays.analytics.recap_insights import HORIZON, week_insights
from sunday_clays.analytics.recap_insights import milestone_sentences as targets_sentences
from sunday_clays.analytics.recap_trophies import recap_milestone_items
from sunday_clays.analytics.steps.s60_insights import build_frames
from sunday_clays.api.routes._convert import opt_int, opt_str, rows
from sunday_clays.api.routes.insights import held_dates, supersedes_of
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import ConflictError, NotFoundError
from sunday_clays.domain.features import switch_on

router = APIRouter(prefix="/api/admin", tags=["admin"])

THREE_BIRD_CODE = "three_bird_shoot"
CLAYS_BROKEN = "clays_broken"


class RecapOut(BaseModel):
    event_date: date
    kind: Literal["regular", "special"]
    label: str | None
    target_total: int
    shooters: int
    head_count: int | None
    rounds: int
    #: "This week": up to 5 plain sentences, the stored Sunday insights' named headlines plus
    #: recap-only facts (`analytics/recap_facts`), one per type. Not a kind two Sundays running,
    #: not the same (kind, subject) within 12 Sundays, nobody named two Sundays running. Measured
    #: on the fixture world: 3+ lines in 83% of weeks, 4+ in 65%, never empty.
    insights: list[str]
    #: Clays Broken sentences, "First Last: <Trophy> - <N>", "Club: ... all time!".
    milestones: list[str]
    three_bird_new: int | None
    three_bird_holders: int | None
    top_score: int | None
    link: str


def is_three_bird(label: str | None) -> bool:
    return label is not None and normalize_label(label) in THREE_BIRD_LABELS


def three_bird_counts(award_dates: Sequence[date], day: date) -> tuple[int, int]:
    """(first-time earners on `day`, everyone holding it on `day`)."""
    return sum(d == day for d in award_dates), sum(d <= day for d in award_dates)


@cached_by_data_version
def week_texts(
    session: Session, day: date, club_next: bool
) -> tuple[list[str], list[tuple[int, str]]]:
    """("This week" sentences, (shooter id, Clays Broken sentence) pairs) for a regular Sunday.

    "This week" is up to 5 plain sentences (3 or more in about 83% of the fixture world's weeks,
    4 or more in 65%): the eligible stored insights and the recap-only facts, replayed over the
    last 36 held Sundays (analytics/recap_insights.py). The Clays Broken
    sentences are recomputed from the engine's facts, one per shooter who crossed a thousand-target
    mark (named headlines, as the site renders a single crossing), so a stored roll-up can never
    hide anyone. Both come from one set of frames, built once per request and then memoized.
    """
    fr = build_frames(session)
    held = [d for d in held_dates(session) if d <= day]
    t = insights_table()
    rows = load_rows(session, t.c.anchor_date.in_(held[-HORIZON:]), t.c.pages.contains(["sunday"]))
    source = FactSource(fr, club_next=club_next)
    return week_insights(rows, held, day, supersedes_of, source.on), targets_sentences(fr, day)


@router.get("/recap/{date}")
def get_recap(
    event_date: Annotated[date, Path(alias="date")],
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RecapOut:
    calendar = frames.load_calendar(session)
    match = calendar.loc[calendar["event_date"] == event_date]
    if match.empty:
        raise NotFoundError("event_not_found", f"No event on {event_date.isoformat()}")
    event = rows(match)[0]
    if not bool(event["results_complete"]):
        raise ConflictError("recap_not_ready", "This Sunday has no full results yet.")
    special = event["kind"] == frames.EVENT_KIND_SPECIAL
    label = opt_str(event["label"])
    awards = session.execute(
        text(
            "SELECT a.shooter_id, p.display_name, a.code FROM achievements_awarded a "
            "JOIN shooter_profiles p ON p.shooter_id = a.shooter_id "
            "WHERE a.event_date = :d ORDER BY p.display_name, a.code"
        ),
        {"d": event_date},
    ).all()
    club_on = switch_on(session, settings, "club_milestones")
    insights, found = ([], []) if special else week_texts(session, event_date, club_on)
    sentences, told = [line for _, line in found], {i for i, _ in found}
    codes: dict[str, list[str]] = defaultdict(list)
    for shooter, name, code in awards:
        if code == THREE_BIRD_CODE or (int(shooter) in told and str(code).startswith(CLAYS_BROKEN)):
            continue
        codes[str(name)].append(str(code))
    trophy_lines = [
        f"{natural_name(name)}: {item}"
        for name, held in codes.items()
        for item in recap_milestone_items(held)
    ]
    club_lines = (
        [
            f"Club: {c.label} all time!"
            for c in club_milestones(session, event_date).milestones
            if c.event_date == event_date
        ]
        if club_on
        else []
    )
    new = holders = None
    if special and is_three_bird(label):
        dates: list[date] = list(
            session.execute(
                text("SELECT event_date FROM achievements_awarded WHERE code = :c"),
                {"c": THREE_BIRD_CODE},
            ).scalars()
        )
        new, holders = three_bird_counts(dates, event_date)
    top_score = None
    if special:
        day_special = frames.load_special_rounds(session)
        scores = day_special.loc[day_special["event_date"] == event_date, "score"]
        top_score = None if scores.empty else int(scores.max())
    return RecapOut(
        event_date=event_date,
        kind="special" if special else "regular",
        label=label,
        target_total=int(event["target_total"]),
        shooters=int(event["n_shooters"]),
        head_count=opt_int(event["head_count"]),
        rounds=int(event["n_rounds"]),
        insights=insights,
        milestones=[
            *sentences,
            *trophy_lines,
            *club_lines,
        ],
        three_bird_new=new,
        three_bird_holders=holders,
        top_score=top_score,
        link=f"{settings.public_base_url}/l/events/{event_date.isoformat()}",
    )
