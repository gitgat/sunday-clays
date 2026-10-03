"""Weekly recap facts for the club email (Plan 19 §3.3.1, D14, D15). Admin only (module prefix).

The server owns the rules (podium ties, the PB rule, first-timers); the SPA owns the wording.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from typing import Annotated, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import text

from sunday_clays.analytics import frames
from sunday_clays.analytics.achievements.participation import THREE_BIRD_LABELS, normalize_label
from sunday_clays.analytics.club_milestones import club_milestones
from sunday_clays.analytics.summary import trophy_title
from sunday_clays.api.routes._convert import opt_int, opt_str, rows
from sunday_clays.api.routes.events import event_notables
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import ConflictError, NotFoundError
from sunday_clays.domain.features import switch_on

router = APIRouter(prefix="/api/admin", tags=["admin"])

THREE_BIRD_CODE = "three_bird_shoot"
PODIUM_PLACES = 3


class PodiumPlaceOut(BaseModel):
    place: Literal[1, 2, 3]
    tied: bool
    score: int
    names: list[str]  # display names, alphabetical


class RecapPbOut(BaseModel):
    display_name: str
    score: int
    previous: int


class RecapTrophiesOut(BaseModel):
    display_name: str
    items: list[str]


class RecapOut(BaseModel):
    event_date: date
    kind: Literal["regular", "special"]
    label: str | None
    target_total: int
    shooters: int
    head_count: int | None
    rounds: int
    podium: list[PodiumPlaceOut]
    pbs: list[RecapPbOut]
    trophies: list[RecapTrophiesOut]
    club_milestones: list[str]
    first_timers: list[str]
    three_bird_new: int | None
    three_bird_holders: int | None
    top_score: int | None
    link: str


def podium_of(day_rounds: pd.DataFrame) -> list[PodiumPlaceOut]:
    """Best rounds with event_rank <= 3 (ties share a rank, so "Tied 1st" is followed by 3rd)."""
    best = day_rounds.loc[day_rounds["is_best_round"].eq(True) & day_rounds["event_rank"].notna()]
    by_place: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for r in rows(best):
        place = int(r["event_rank"])
        if place <= PODIUM_PLACES:
            by_place[place].append((str(r["display_name"]), int(r["score"])))
    return [
        PodiumPlaceOut(
            place=place,
            tied=len(entries) > 1,
            score=entries[0][1],
            names=sorted(name for name, _ in entries),
        )
        for place, entries in sorted(by_place.items())
    ]


def is_three_bird(label: str | None) -> bool:
    return label is not None and normalize_label(label) in THREE_BIRD_LABELS


def three_bird_counts(award_dates: Sequence[date], day: date) -> tuple[int, int]:
    """(first-time earners on `day`, everyone holding it on `day`)."""
    return sum(d == day for d in award_dates), sum(d <= day for d in award_dates)


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
    rounds = frames.load_rounds(session)
    shooters = frames.load_shooters(session)
    notables = event_notables(rounds, shooters, event_date)
    earlier = rounds.loc[rounds["event_date"] < event_date]
    pbs = [
        RecapPbOut(
            display_name=n.display_name,
            score=int(n.value or 0),
            previous=int(earlier.loc[earlier["shooter_id"] == n.shooter_id, "score"].max()),
        )
        for n in notables
        if n.kind == "pb"
    ]
    awards = session.execute(
        text(
            "SELECT p.display_name, a.code FROM achievements_awarded a "
            "JOIN shooter_profiles p ON p.shooter_id = a.shooter_id "
            "WHERE a.event_date = :d ORDER BY p.display_name, a.code"
        ),
        {"d": event_date},
    ).all()
    items: dict[str, list[str]] = defaultdict(list)
    for name, code in awards:
        title = trophy_title(str(code)) if code != THREE_BIRD_CODE else None
        if title is not None:
            items[str(name)].append(title)
    milestones = (
        [
            c.label
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
        podium=[] if special else podium_of(rounds.loc[rounds["event_date"] == event_date]),
        pbs=[] if special else pbs,
        trophies=[RecapTrophiesOut(display_name=n, items=i) for n, i in items.items()],
        club_milestones=milestones,
        first_timers=[n.display_name for n in notables if n.kind == "first_timer"],
        three_bird_new=new,
        three_bird_holders=holders,
        top_score=top_score,
        link=f"{settings.public_base_url}/l/events/{event_date.isoformat()}",
    )
