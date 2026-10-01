"""/api/sheet/* (Plan 14): the Sunday Sheet, one issue per held Sunday, and its fist bumps.

The issue body is cached by data_version (the memo here and the ETag middleware). Bump counts are
never part of it: they change without a data_version bump, so the client reads them from
GET /api/sheet/{date}/bumps, which is never ETagged or stored (api/etag.py).
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable, Collection
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, sheet, yir
from sunday_clays.analytics.achievements.registry import Metal, trophies
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.insights.picks import picked
from sunday_clays.analytics.insights.store import (
    InsightRow,
    get_new_since,
    insights_table,
    load_picks,
    load_rows,
)
from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.api.routes._convert import opt_float, opt_int, rows
from sunday_clays.api.routes.insights import (
    InsightChartOut,
    InsightOut,
    InsightSegmentOut,
    held_dates,
    insight_out,
    supersedes_of,
)
from sunday_clays.auth.deps import TooManyRequestsError, client_ip
from sunday_clays.auth.ratelimit import bumps_limited, record_bump_action
from sunday_clays.db import SessionDep
from sunday_clays.domain.bumps import add_bump, bump_state, bump_states, remove_bump
from sunday_clays.domain.errors import DomainError, NotFoundError

router = APIRouter(tags=["sheet"])

_AWARDS_SQL = text(
    "SELECT a.shooter_id, p.display_name, a.code FROM achievements_awarded a"
    " JOIN shooter_profiles p ON p.shooter_id = a.shooter_id WHERE a.event_date = :d"
    " ORDER BY a.code, p.display_name, a.shooter_id"
)


class NewerSundayOut(BaseModel):
    """A Sunday after the latest issue that has no full results yet (attendance only or partial):
    the masthead points at it the way Home's Latest Sunday card did."""

    date: dt.date
    has_scores: bool
    head_count: int | None
    n_shooters: int


class SheetMastheadOut(BaseModel):
    date: dt.date
    issue: int  # held Sundays up to and including this one
    previous: dt.date | None
    next: dt.date | None
    latest: bool
    newer: NewerSundayOut | None


class SheetNumbersOut(BaseModel):
    shooters: int
    median: float | None
    top_score: int | None
    trophies: int


class SeeWhyOut(BaseModel):
    """`chart`: an insight's chart link (the frontend builds its URL); `link`: a page `href`."""

    kind: Literal["chart", "link"]
    label: str
    chart: InsightChartOut | None = None
    href: str | None = None


class SheetShooterOut(BaseModel):
    shooter_id: int
    name: str


class SheetTrophyOut(BaseModel):
    code: str
    title: str
    art_key: str
    metal: Metal | None
    holders: list[SheetShooterOut]


class SheetOnThisDayOut(BaseModel):
    years_ago: int
    event_date: date
    n_shooters: int
    top_score: int | None


class SheetPostOut(BaseModel):
    post_key: str
    type: sheet.PostType
    family: str
    headline: list[InsightSegmentOut]
    named_shooter_ids: list[int]
    see_why: SeeWhyOut
    insight: InsightOut | None = None
    trophy: SheetTrophyOut | None = None
    on_this_day: SheetOnThisDayOut | None = None


class SheetMoreGroupOut(BaseModel):
    family: str
    label: str
    posts: list[SheetPostOut]


class SheetOut(BaseModel):
    data_version: int
    masthead: SheetMastheadOut
    numbers: SheetNumbersOut
    headline: InsightOut | None
    recap: InsightOut | None
    spotlight: InsightOut | None
    posts: list[SheetPostOut]
    more: list[SheetMoreGroupOut]


def trophy_catalog() -> dict[str, sheet.TrophyInfo]:
    """Every trophy, titled as the Trophy Room titles it ("Name — Tier")."""
    out: dict[str, sheet.TrophyInfo] = {}
    for t in trophies():
        name = t.achievement.name
        title = name if t.tier is None else f"{name} — {t.tier.label}"
        metal = None if t.tier is None else t.tier.metal.value
        out[t.code] = sheet.TrophyInfo(t.code, title, t.achievement.art_key, metal)
    return out


def _issue_rows(session: Session, day: date, latest: bool) -> list[InsightRow]:
    """Rows anchored on `day`, the day's picks and (latest issue) Home's evergreen rows and the
    FRESH_EVERGREEN kinds (the assembler keeps those about `day`)."""
    t = insights_table()
    keys = [p.insight_key for p in load_picks(session, day)]
    clauses = [t.c.anchor_date == day, t.c.key.in_(keys)]
    if latest:
        evergreen = or_(t.c.pages.contains(["home"]), t.c.kind.in_(sorted(sheet.FRESH_EVERGREEN)))
        clauses.append(and_(t.c.anchor_date.is_(None), evergreen))
    return load_rows(session, or_(*clauses))


@cached_by_data_version
def build_issue(session: Session, day: date) -> sheet.Issue:
    """The assembled issue for a held Sunday (callers check that `day` is held).

    The check and this read are separate transactions, so a rebuild between them can leave `day`
    unheld: that is a 404, the same as asking for it afterwards, never a 500.
    """
    held = held_dates(session)
    if day not in held:
        raise NotFoundError("sheet_not_found", f"No Sunday Sheet for {day.isoformat()}")
    rows_ = _issue_rows(session, day, day == held[-1])
    hero, spotlight = picked(rows_, load_picks(session, day), day)
    awards = [
        sheet.Award(int(sid), str(name), str(code))
        for sid, name, code in session.execute(_AWARDS_SQL, {"d": day})
    ]
    return sheet.assemble(
        day,
        held,
        rows_,
        hero=hero,
        spotlight=spotlight,
        awards=awards,
        catalog=trophy_catalog(),
        on_this_day=yir.on_this_day(yir.load_yir_frames(session), day),
        supersedes=supersedes_of,
    )


def see_why(post: sheet.Post) -> SeeWhyOut:
    if post.row is not None:
        chart = InsightChartOut.model_validate(dict(post.row.chart))
        return SeeWhyOut(kind="chart", label=chart.label, chart=chart)
    if post.trophy is not None:
        return SeeWhyOut(
            kind="link",
            label=f"{post.trophy.title} in the Trophy Room",
            href=f"/achievements/{post.trophy.code}",
        )
    if post.on_this_day is not None:
        return SeeWhyOut(
            kind="link",
            label="That Sunday's results",
            href=f"/events/{post.on_this_day.event_date.isoformat()}",
        )
    raise ValueError(f"post {post.post_key} has no source")


def _post_out(post: sheet.Post, new_since: int | None) -> SheetPostOut:
    trophy, otd = post.trophy, post.on_this_day
    return SheetPostOut(
        post_key=post.post_key,
        type=post.type,
        family=post.family,
        headline=[InsightSegmentOut.model_validate(s) for s in post.headline],
        named_shooter_ids=list(post.named_shooter_ids),
        see_why=see_why(post),
        insight=None if post.row is None else insight_out(post.row, new_since),
        trophy=None
        if trophy is None
        else SheetTrophyOut(
            code=trophy.code,
            title=trophy.title,
            art_key=trophy.art_key,
            metal=None if trophy.metal is None else Metal(trophy.metal),
            holders=[SheetShooterOut(shooter_id=sid, name=name) for sid, name in trophy.holders],
        ),
        on_this_day=None
        if otd is None
        else SheetOnThisDayOut(
            years_ago=otd.years_ago,
            event_date=otd.event_date,
            n_shooters=otd.n_shooters,
            top_score=otd.top_score,
        ),
    )


def newer_sunday(session: Session, issue: sheet.Issue) -> NewerSundayOut | None:
    """On the latest issue: the newest Sunday when it is after the issue (so not fully scored)."""
    if not issue.latest:
        return None
    events = frames.load_events(session)
    newest = rows(events.loc[events["event_date"] == events["event_date"].max()])[0]
    if newest["event_date"] <= issue.day:
        return None
    return NewerSundayOut(
        date=newest["event_date"],
        has_scores=bool(newest["has_scores"]),
        head_count=opt_int(newest["head_count"]),
        n_shooters=int(newest["n_shooters"]),
    )


def _numbers(session: Session, issue: sheet.Issue) -> SheetNumbersOut:
    events = frames.load_events(session)
    event = rows(events.loc[events["event_date"] == issue.day])[0]
    catalog = trophy_catalog()  # the event page's set: retired codes are not trophies
    return SheetNumbersOut(
        shooters=int(event["n_shooters"]),
        median=opt_float(event["median"]),
        top_score=opt_int(event["top_score"]),
        trophies=sum(
            1 for _, _, code in session.execute(_AWARDS_SQL, {"d": issue.day}) if code in catalog
        ),
    )


@cached_by_data_version
def sheet_body(session: Session, day: date) -> SheetOut:
    issue = build_issue(session, day)
    new_since = get_new_since(session)

    def maybe(row: InsightRow | None) -> InsightOut | None:
        return None if row is None else insight_out(row, new_since)

    return SheetOut(
        data_version=get_data_version(session),
        masthead=SheetMastheadOut(
            date=issue.day,
            issue=issue.number,
            previous=issue.previous,
            next=issue.next,
            latest=issue.latest,
            newer=newer_sunday(session, issue),
        ),
        numbers=_numbers(session, issue),
        headline=maybe(issue.headline),
        recap=maybe(issue.recap),
        spotlight=maybe(issue.spotlight),
        posts=[_post_out(p, new_since) for p in issue.feed],
        more=[
            SheetMoreGroupOut(
                family=g.family, label=g.label, posts=[_post_out(p, new_since) for p in g.posts]
            )
            for g in issue.more
        ],
    )


def post_issue_dates(session: Session, post_keys: Collection[str]) -> dict[str, date | None]:
    """The held Sunday whose issue each key would be on: a trophy or "On this day" key names it; an
    insight key's anchor (an evergreen row: the latest issue). None for an unknown key.

    Two queries however many keys there are: the held dates and one lookup of the insight keys."""
    keys = set(post_keys)
    held = held_dates(session)
    if not held:
        return dict.fromkeys(keys)
    synthetic = {key: sheet.synthetic_key_date(key) for key in keys}
    plain_keys = sorted(key for key, day in synthetic.items() if day is None)
    anchors: dict[str, date | None] = {}
    if plain_keys:
        t = insights_table()
        anchors = {
            str(key): anchor
            for key, anchor in session.execute(
                select(t.c.key, t.c.anchor_date).where(t.c.key.in_(plain_keys))
            )
        }
    out: dict[str, date | None] = {}
    for key in keys:
        day = synthetic[key]
        if day is None:
            if key not in anchors:
                out[key] = None
                continue
            day = held[-1] if anchors[key] is None else anchors[key]
        out[key] = day if day in held else None
    return out


def resolves_all(session: Session, post_keys: Collection[str]) -> dict[str, bool]:
    """Per key: is it a post on its issue as the data stands now (feed or "More")? One issue build
    (memoised by data_version) per distinct date, however many keys."""
    days = post_issue_dates(session, post_keys)
    issues = {day: build_issue(session, day).post_keys for day in {d for d in days.values() if d}}
    return {key: day is not None and key in issues[day] for key, day in days.items()}


def resolves(session: Session, post_key: str) -> bool:
    """True when the key is a post on its issue as the data stands now (feed or "More")."""
    return resolves_all(session, [post_key])[post_key]


def held_or_404(session: Session, day: date) -> None:
    if day not in held_dates(session):
        raise NotFoundError("sheet_not_found", f"No Sunday Sheet for {day.isoformat()}")


@router.get("/api/sheet/latest")
def latest_sheet(session: SessionDep) -> SheetOut:
    held = held_dates(session)
    if not held:
        raise NotFoundError("sheet_not_found", "No Sunday has full results yet")
    return sheet_body(session, held[-1])


@router.get("/api/sheet/{date}")
def sheet_for_date(day: Annotated[date, Path(alias="date")], session: SessionDep) -> SheetOut:
    held_or_404(session, day)
    return sheet_body(session, day)


# --- Fist bumps (Plan 14 Task 3) ------------------------------------------------------------------
class BumpIn(BaseModel):
    post_key: str = Field(min_length=1, max_length=200)
    device_id: str = Field(min_length=1)


class BumpStateOut(BaseModel):
    bumps: int
    bumped: bool


def parse_device_id(value: str) -> uuid.UUID:
    """A canonical UUID (8-4-4-4-12 hex, any case), else a 400."""
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        parsed = None
    if parsed is None or str(parsed) != value.lower():
        raise DomainError("bad_device_id", "device_id must be a UUID")
    return parsed


@router.get("/api/sheet/{date}/bumps")
def sheet_bumps(
    day: Annotated[date, Path(alias="date")],
    session: SessionDep,
    device_id: str | None = None,
) -> dict[str, BumpStateOut]:
    """Counts for every post on the issue (zeros included); a stale key is never listed."""
    held_or_404(session, day)
    device = None if device_id is None else parse_device_id(device_id)
    states = bump_states(session, build_issue(session, day).post_keys, device)
    return {key: BumpStateOut(bumps=s.bumps, bumped=s.bumped) for key, s in states.items()}


def _bump_action(
    request: Request,
    session: Session,
    body: BumpIn,
    act: Callable[[Session, str, uuid.UUID], None],
) -> BumpStateOut:
    ip = client_ip(request)
    if bumps_limited(session, ip):
        raise TooManyRequestsError("rate_limited", "Too many bumps from here. Try again soon.")
    record_bump_action(session, ip)
    session.commit()  # get_session rolls back on any error; a refused action still counts
    device = parse_device_id(body.device_id)
    if not resolves(session, body.post_key):
        raise NotFoundError("post_not_found", "That post is not on a Sunday Sheet")
    act(session, body.post_key, device)
    state = bump_state(session, body.post_key, device)
    return BumpStateOut(bumps=state.bumps, bumped=state.bumped)


@router.post("/api/sheet/bumps")
def bump_post(body: BumpIn, request: Request, session: SessionDep) -> BumpStateOut:
    """Idempotent: bumping twice from one device counts once."""
    return _bump_action(request, session, body, add_bump)


@router.delete("/api/sheet/bumps")
def unbump_post(body: BumpIn, request: Request, session: SessionDep) -> BumpStateOut:
    """Idempotent: taking back a bump that is not there changes nothing."""
    return _bump_action(request, session, body, remove_bump)
