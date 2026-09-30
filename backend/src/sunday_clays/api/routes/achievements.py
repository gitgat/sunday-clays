"""Achievement read endpoints (C8, Plan 10 T1): Trophy Room, trophy holders, a shooter's Trophy
Case and the trophies earned at one event. Awards come from achievements_awarded (written by
recompute step s50); tier progress is computed per request from the data_version-cached context.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Path
from pydantic import BaseModel
from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from sunday_clays.analytics.achievements.context import cached_context
from sunday_clays.analytics.achievements.registry import (
    Category,
    Metal,
    ProgressOut,
    Tier,
    Trophy,
    progress,
    rarity_pct,
    trophies,
    trophy,
)
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError

router = APIRouter(prefix="/api", tags=["achievements"])

RECENT_LIMIT = 200

_AWARDS_SQL = """
    SELECT a.shooter_id, p.display_name, p.status AS shooter_status, a.code,
           a.event_date, a.round_id, a.details
    FROM achievements_awarded a
    JOIN shooter_profiles p ON p.shooter_id = a.shooter_id
"""


class TrophyOut(BaseModel):
    code: str
    family: str
    name: str
    description: str
    category: Category
    art_key: str
    metal: Metal | None
    level: int | None
    threshold: float | None
    label: str | None
    repeatable: bool
    holders: int
    rarity_pct: float
    last_awarded: date | None


class TrophyAwardOut(BaseModel):
    shooter_id: int
    display_name: str
    code: str
    family: str
    name: str
    label: str | None
    metal: Metal | None
    art_key: str
    event_date: date
    round_id: int | None
    details: dict[str, Any]


class AchievementsOut(BaseModel):
    n_shooters: int
    trophies: list[TrophyOut]
    recent: list[TrophyAwardOut]
    recent_total: int  # every award of a listed trophy; `recent` is the newest RECENT_LIMIT


class TrophyHolderOut(BaseModel):
    shooter_id: int
    display_name: str
    shooter_status: str
    first_date: date
    count: int
    dates: list[date]


class AchievementDetailOut(BaseModel):
    trophy: TrophyOut
    holders: list[TrophyHolderOut]


class EarnedTrophyOut(BaseModel):
    code: str
    family: str
    name: str
    description: str
    category: Category
    art_key: str
    metal: Metal | None
    level: int | None
    label: str | None
    first_date: date
    count: int
    dates: list[date]


class LockedTrophyOut(BaseModel):
    code: str
    name: str
    description: str
    category: Category
    art_key: str
    rarity_pct: float


class ShooterAchievementsOut(BaseModel):
    shooter_id: int
    display_name: str
    earned: list[EarnedTrophyOut]
    progress: list[ProgressOut]
    locked: list[LockedTrophyOut]


class EventAchievementsOut(BaseModel):
    event_date: date
    awards: list[TrophyAwardOut]


def _n_shooters(session: Session) -> int:
    return int(session.execute(text("SELECT count(DISTINCT shooter_id) FROM rounds")).scalar_one())


def _holder_stats(session: Session) -> dict[str, tuple[int, date | None]]:
    result = session.execute(
        text(
            "SELECT code, count(DISTINCT shooter_id) AS holders, max(event_date) AS last_awarded "
            "FROM achievements_awarded GROUP BY code"
        )
    ).mappings()
    return {str(r["code"]): (int(r["holders"]), r["last_awarded"]) for r in result}


def _tier_fields(tier: Tier | None) -> tuple[Metal | None, int | None, str | None]:
    """A trophy's (metal, level, label): its tier's, or all None for a one-off."""
    return (tier.metal, tier.level, tier.label) if tier else (None, None, None)


def _trophy_out(
    t: Trophy, stats: Mapping[str, tuple[int, date | None]], n_shooters: int
) -> TrophyOut:
    holders, last = stats.get(t.code, (0, None))
    a = t.achievement
    metal, level, label = _tier_fields(t.tier)
    return TrophyOut(
        code=t.code,
        family=a.code,
        name=a.name,
        description=a.description,
        category=a.category,
        art_key=a.art_key,
        metal=metal,
        level=level,
        threshold=t.tier.threshold if t.tier else None,
        label=label,
        repeatable=a.repeatable,
        holders=holders,
        rarity_pct=rarity_pct(holders, n_shooters),
        last_awarded=last,
    )


def _award_out(row: RowMapping, t: Trophy) -> TrophyAwardOut:
    metal, _, label = _tier_fields(t.tier)
    return TrophyAwardOut(
        shooter_id=int(row["shooter_id"]),
        display_name=str(row["display_name"]),
        code=t.code,
        family=t.achievement.code,
        name=t.achievement.name,
        label=label,
        metal=metal,
        art_key=t.achievement.art_key,
        event_date=row["event_date"],
        round_id=row["round_id"],
        details=dict(row["details"] or {}),
    )


@router.get("/achievements", response_model=AchievementsOut)
def list_achievements(session: SessionDep) -> AchievementsOut:
    n_shooters = _n_shooters(session)
    stats = _holder_stats(session)
    catalog = {t.code: t for t in trophies()}
    recent = session.execute(
        text(
            _AWARDS_SQL + " WHERE a.code = ANY(:codes)"
            " ORDER BY a.event_date DESC, a.code, a.shooter_id LIMIT :n"
        ),
        {"codes": list(catalog), "n": RECENT_LIMIT},
    ).mappings()
    recent_total: int = session.execute(
        text("SELECT count(*) FROM achievements_awarded WHERE code = ANY(:codes)"),
        {"codes": list(catalog)},
    ).scalar_one()
    return AchievementsOut(
        n_shooters=n_shooters,
        trophies=[_trophy_out(t, stats, n_shooters) for t in catalog.values()],
        recent=[_award_out(r, catalog[str(r["code"])]) for r in recent],
        recent_total=recent_total,
    )


@router.get("/achievements/{code}", response_model=AchievementDetailOut)
def get_achievement(code: str, session: SessionDep) -> AchievementDetailOut:
    found = trophy(code)
    if found is None:
        raise NotFoundError("achievement_not_found", f"No trophy with code {code!r}")
    result = session.execute(
        text(
            _AWARDS_SQL
            + " WHERE a.code = :code ORDER BY a.event_date, p.display_name, a.shooter_id"
        ),
        {"code": code},
    ).mappings()
    holders: dict[int, TrophyHolderOut] = {}
    for r in result:
        shooter_id = int(r["shooter_id"])
        holder = holders.get(shooter_id)
        if holder is None:
            holders[shooter_id] = TrophyHolderOut(
                shooter_id=shooter_id,
                display_name=str(r["display_name"]),
                shooter_status=str(r["shooter_status"]),
                first_date=r["event_date"],
                count=1,
                dates=[r["event_date"]],
            )
        else:
            holder.count += 1
            holder.dates.append(r["event_date"])
    return AchievementDetailOut(
        trophy=_trophy_out(found, _holder_stats(session), _n_shooters(session)),
        holders=list(holders.values()),
    )


@router.get("/shooters/{id}/achievements", response_model=ShooterAchievementsOut)
def get_shooter_achievements(
    shooter_id: Annotated[int, Path(alias="id")], session: SessionDep
) -> ShooterAchievementsOut:
    display_name = session.execute(
        text("SELECT display_name FROM shooter_profiles WHERE shooter_id = :id"), {"id": shooter_id}
    ).scalar_one_or_none()
    if display_name is None:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    catalog = {t.code: t for t in trophies()}
    dates_by_code: dict[str, list[date]] = {}
    for r in session.execute(
        text(
            "SELECT code, event_date FROM achievements_awarded"
            " WHERE shooter_id = :id ORDER BY event_date, code"
        ),
        {"id": shooter_id},
    ).mappings():
        if r["code"] in catalog:
            dates_by_code.setdefault(str(r["code"]), []).append(r["event_date"])
    earned = []
    for code, days in dates_by_code.items():
        t = catalog[code]
        metal, level, label = _tier_fields(t.tier)
        earned.append(
            EarnedTrophyOut(
                code=code,
                family=t.achievement.code,
                name=t.achievement.name,
                description=t.achievement.description,
                category=t.achievement.category,
                art_key=t.achievement.art_key,
                metal=metal,
                level=level,
                label=label,
                first_date=days[0],
                count=len(days),
                dates=days,
            )
        )
    stats = _holder_stats(session)
    n_shooters = _n_shooters(session)
    locked = [
        LockedTrophyOut(
            code=t.code,
            name=t.achievement.name,
            description=t.achievement.description,
            category=t.achievement.category,
            art_key=t.achievement.art_key,
            rarity_pct=rarity_pct(stats.get(t.code, (0, None))[0], n_shooters),
        )
        for t in catalog.values()
        if t.tier is None and t.code not in dates_by_code
    ]
    return ShooterAchievementsOut(
        shooter_id=shooter_id,
        display_name=str(display_name),
        earned=earned,
        progress=progress(cached_context(session), shooter_id, None),
        locked=locked,
    )


@router.get("/events/{date}/achievements", response_model=EventAchievementsOut)
def get_event_achievements(
    event_date: Annotated[date, Path(alias="date")], session: SessionDep
) -> EventAchievementsOut:
    exists = session.execute(
        text("SELECT 1 FROM events WHERE event_date = :d"), {"d": event_date}
    ).first()
    if exists is None:
        raise NotFoundError("event_not_found", f"No event on {event_date.isoformat()}")
    catalog = {t.code: t for t in trophies()}
    result = session.execute(
        text(
            _AWARDS_SQL + " WHERE a.event_date = :d ORDER BY p.display_name, a.code, a.shooter_id"
        ),
        {"d": event_date},
    ).mappings()
    return EventAchievementsOut(
        event_date=event_date,
        awards=[_award_out(r, catalog[str(r["code"])]) for r in result if r["code"] in catalog],
    )
