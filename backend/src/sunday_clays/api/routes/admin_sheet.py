"""Admin: fist bumps on Sunday Sheet posts (Plan 14). Lists the bumped posts and wipes one."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import select

from sunday_clays.analytics import sheet
from sunday_clays.analytics.insights.store import insights_table
from sunday_clays.analytics.insights.templates import plain
from sunday_clays.api.routes.sheet import post_issue_dates, resolves_all
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.db import SessionDep
from sunday_clays.domain.bumps import bump_totals, wipe_bumps

router = APIRouter(prefix="/api/admin/sheet", tags=["admin"])

ActorDep = Annotated[Actor, Depends(admin_actor)]
LIST_LIMIT = 100


class BumpTotalOut(BaseModel):
    post_key: str
    bumps: int
    last_at: dt.datetime
    label: str
    issue_date: dt.date | None
    current: bool  # still a post on its Sheet; a stale key is kept but never shown


class WipeOut(BaseModel):
    post_key: str
    wiped: int


def post_label(post_key: str, headlines: Mapping[str, str]) -> str:
    """What an admin reads for a key: the insight's headline, or the trophy / look-back it names."""
    if post_key in headlines:
        return headlines[post_key]
    day = sheet.synthetic_key_date(post_key)
    if day is not None and post_key.startswith("trophy:"):
        code = post_key.removeprefix("trophy:").rsplit(":", 1)[0]
        return f"Trophy {code}, {day.isoformat()}"
    if day is not None:
        return f"On this day, {day.isoformat()}"
    return "No longer on a Sheet"


@router.get("/bumps")
def list_bumped_posts(session: SessionDep) -> list[BumpTotalOut]:
    """The most recently bumped posts first, at most LIST_LIMIT."""
    totals = bump_totals(session, LIST_LIMIT)
    t = insights_table()
    headlines = {
        str(key): plain(headline)
        for key, headline in session.execute(
            select(t.c.key, t.c.headline).where(t.c.key.in_([x.post_key for x in totals]))
        )
    }
    keys = [x.post_key for x in totals]
    days = post_issue_dates(session, keys)  # batched: no query per row
    current = resolves_all(session, keys)
    return [
        BumpTotalOut(
            post_key=x.post_key,
            bumps=x.bumps,
            last_at=x.last_at,
            label=post_label(x.post_key, headlines),
            issue_date=days[x.post_key],
            current=current[x.post_key],
        )
        for x in totals
    ]


@router.delete("/bumps/{post_key}")
def wipe_post_bumps(
    post_key: Annotated[str, Path(min_length=1, max_length=200)],
    session: SessionDep,
    actor: ActorDep,
) -> WipeOut:
    """Wipes every bump on one post, current or stale, and records it in the audit log."""
    wiped = wipe_bumps(session, post_key)
    record_audit(
        session, actor.ip, actor.role, "sheet.wipe_bumps", {"post_key": post_key, "wiped": wiped}
    )
    return WipeOut(post_key=post_key, wiped=wiped)
