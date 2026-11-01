"""Read-only queries behind the MCP read tools."""

from datetime import date, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from sunday_clays.mcp.schemas import (
    EventSummary,
    IssueInfo,
    JobStatus,
    NoEvent,
    NotFound,
    RowInfo,
    ShooterHit,
    StationInfo,
)
from sunday_clays.models import DataIssue, Event, Job, Round, Shooter, ShooterAlias
from sunday_clays.models.live import StationLayout

_STATUS_WINDOW_DAYS = 365


def _escape_like(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _word_prefix(tokens: list[str], text: str) -> bool:
    words = text.lower().replace(",", " ").split()
    return all(any(w.startswith(t) for w in words) for t in tokens)


def find_shooters(session: Session, query: str, limit: int = 10) -> list[ShooterHit]:
    """Shooters whose name (or alias) contains every whitespace-separated token, any order."""
    tokens = [t.lower() for t in query.split()]
    if not tokens:
        return []
    patterns = [f"%{_escape_like(t)}%" for t in tokens]
    by_name = and_(*(Shooter.display_name.ilike(p, escape="\\") for p in patterns))
    by_alias = (
        select(ShooterAlias.shooter_id)
        .where(and_(*(ShooterAlias.name_key.ilike(p, escape="\\") for p in patterns)))
        .scalar_subquery()
    )
    totals = (
        select(
            Round.shooter_id.label("shooter_id"),
            func.count(Round.id).label("rounds"),
            func.max(Round.event_date).label("last_shot"),
        )
        .group_by(Round.shooter_id)
        .subquery()
    )
    stmt = (
        select(Shooter.id, Shooter.display_name, totals.c.rounds, totals.c.last_shot)
        .outerjoin(totals, totals.c.shooter_id == Shooter.id)
        .where(or_(by_name, Shooter.id.in_(by_alias)))
    )
    found = [
        (sid, name, rounds or 0, last) for sid, name, rounds, last in session.execute(stmt).all()
    ]
    # token-prefix matches first, then busiest, then name for a stable order
    found.sort(key=lambda r: (not _word_prefix(tokens, r[1]), -r[2], r[1]))
    top = found[:limit]
    usual = _usual_statuses(session, [sid for sid, *_ in top])
    return [
        ShooterHit(display_name=name, rounds=rounds, last_shot=last, usual_status=usual.get(sid))
        for sid, name, rounds, last in top
    ]


def _usual_statuses(session: Session, shooter_ids: list[int]) -> dict[int, str]:
    """Most common rounds.status over the 12 months up to the latest recorded Sunday."""
    if not shooter_ids:
        return {}
    latest = session.scalar(select(func.max(Round.event_date)))
    if latest is None:
        return {}
    since = latest - timedelta(days=_STATUS_WINDOW_DAYS)
    count = func.count().label("n")
    rows = session.execute(
        select(Round.shooter_id, Round.status, count)
        .where(
            Round.shooter_id.in_(shooter_ids),
            Round.event_date > since,
            Round.status.is_not(None),
        )
        .group_by(Round.shooter_id, Round.status)
        .order_by(Round.shooter_id, count.desc(), Round.status)
    ).all()
    result: dict[int, str] = {}
    for sid, status, _n in rows:
        result.setdefault(sid, str(status))
    return result


def get_event(
    session: Session, event_date: date, include_rows: bool = False
) -> EventSummary | NoEvent:
    event = session.get(Event, event_date)
    if event is None:
        last = session.scalar(select(func.max(Event.event_date)))
        return NoEvent(date=event_date, last_event_date=last)
    n_rounds, score_sum = session.execute(
        select(func.count(Round.id), func.coalesce(func.sum(Round.score), 0)).where(
            Round.event_date == event_date
        )
    ).one()
    stations = session.scalars(
        select(StationLayout)
        .where(StationLayout.event_date == event_date)
        .order_by(StationLayout.station_no, StationLayout.station_label)
    ).all()
    issues = session.scalars(
        select(DataIssue).where(DataIssue.event_date == event_date).order_by(DataIssue.id)
    ).all()
    rows: list[RowInfo] | None = None
    if include_rows:
        rows = [
            RowInfo(name=name, score=score, status=status, gauge_class=gauge)
            for name, score, status, gauge in session.execute(
                select(Shooter.display_name, Round.score, Round.status, Round.gauge_class)
                .join(Shooter, Shooter.id == Round.shooter_id)
                .where(Round.event_date == event_date)
                .order_by(Round.score.desc(), Shooter.display_name, Round.ordinal)
            ).all()
        ]
    return EventSummary(
        date=event_date,
        head_count=event.head_count,
        round_type=event.round_type,
        stats_excluded=event.stats_excluded,
        target_total=event.target_total,
        n_rounds=n_rounds,
        score_sum=int(score_sum),
        average=round(int(score_sum) / n_rounds, 2) if n_rounds else None,
        stations=[
            StationInfo(label=s.station_label, targets=s.target_count, dropped=s.dropped)
            for s in stations
        ],
        data_issues=[
            IssueInfo(severity=i.severity, code=i.code, message=i.message) for i in issues
        ],
        rows=rows,
    )


def get_job(session: Session, job_id: int) -> JobStatus | NotFound:
    job = session.get(Job, job_id)
    if job is None:
        return NotFound(id=job_id)
    return JobStatus(
        id=job.id,
        kind=job.kind,
        status=job.status,
        attempts=job.attempts,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
    )
