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
from sunday_clays.analytics.club_milestones import club_milestones
from sunday_clays.analytics.insights.store import insights_table, load_rows
from sunday_clays.analytics.insights.templates import natural_name
from sunday_clays.analytics.recap_insights import HORIZON, milestone_insights, week_insights
from sunday_clays.analytics.recap_trophies import recap_milestone_items
from sunday_clays.api.routes._convert import opt_int, opt_str, rows
from sunday_clays.api.routes.insights import held_dates, supersedes_of
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import ConflictError, NotFoundError
from sunday_clays.domain.features import switch_on

router = APIRouter(prefix="/api/admin", tags=["admin"])

THREE_BIRD_CODE = "three_bird_shoot"


class RecapOut(BaseModel):
    event_date: date
    kind: Literal["regular", "special"]
    label: str | None
    target_total: int
    shooters: int
    head_count: int | None
    rounds: int
    insights: list[str]  # "This week": plain sentences, named headlines of the Sunday's insights
    milestones: list[
        str
    ]  # Clays Broken sentences, "First Last: <Trophy> - <N>", "Club: ... all time!"
    three_bird_new: int | None
    three_bird_holders: int | None
    top_score: int | None
    link: str


def is_three_bird(label: str | None) -> bool:
    return label is not None and normalize_label(label) in THREE_BIRD_LABELS


def three_bird_counts(award_dates: Sequence[date], day: date) -> tuple[int, int]:
    """(first-time earners on `day`, everyone holding it on `day`)."""
    return sum(d == day for d in award_dates), sum(d <= day for d in award_dates)


def this_week(session: Session, day: date) -> list[str]:
    """3-5 plain-sentence insights for a held regular Sunday (replayed over the last 36)."""
    held = [d for d in held_dates(session) if d <= day]
    t = insights_table()
    rows = load_rows(session, t.c.anchor_date.in_(held[-HORIZON:]), t.c.pages.contains(["sunday"]))
    return week_insights(rows, held, day, supersedes_of)


def milestone_sentences(session: Session, day: date) -> list[str]:
    """The Sunday's Clays Broken insight sentences (named headlines, as the site renders them)."""
    t = insights_table()
    return milestone_insights(
        load_rows(session, t.c.anchor_date == day, t.c.pages.contains(["sunday"])), day
    )


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
            "SELECT p.display_name, a.code FROM achievements_awarded a "
            "JOIN shooter_profiles p ON p.shooter_id = a.shooter_id "
            "WHERE a.event_date = :d ORDER BY p.display_name, a.code"
        ),
        {"d": event_date},
    ).all()
    codes: dict[str, list[str]] = defaultdict(list)
    for name, code in awards:
        if code != THREE_BIRD_CODE:
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
        if switch_on(session, settings, "club_milestones")
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
        insights=[] if special else this_week(session, event_date),
        milestones=[
            *([] if special else milestone_sentences(session, event_date)),
            *trophy_lines,
            *club_lines,
        ],
        three_bird_new=new,
        three_bird_holders=holders,
        top_score=top_score,
        link=f"{settings.public_base_url}/l/events/{event_date.isoformat()}",
    )
