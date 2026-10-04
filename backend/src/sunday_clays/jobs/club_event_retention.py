"""The `club_event_retention` job (Plan 20 D16, §5.6), once a local day after 03:00.

Deletes every sign-up of each event that started more than 30 days ago (keeping only its two
counts), shooters' emails unused for 730 days, and club-event rate-limit rows older than a day.
Logs counts only. One transaction; the due events are locked in ascending id order (§5.3.9).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.orm import Session

from sunday_clays.domain.club_events import (
    ATTEMPT_KEEP,
    CONTACT_RETENTION_DAYS,
    ROSTER_RETENTION_DAYS,
)
from sunday_clays.jobs.handlers import handler
from sunday_clays.models import ClubEvent, ClubEventAttempt, ClubEventRegistration, ShooterContact

logger = logging.getLogger(__name__)
R = ClubEventRegistration


@dataclass(frozen=True)
class RetentionReport:
    events: int
    contacts: int
    attempts: int


def due_events(cutoff: datetime) -> Select[Any]:
    """Events that started before `cutoff` and still hold their sign-ups, locked in id order in
    one statement."""
    return (
        select(ClubEvent.id)
        .where(ClubEvent.starts_at < cutoff, ClubEvent.roster_purged_at.is_(None))
        .order_by(ClubEvent.id)
        .with_for_update()
    )


def purge_club_events(session: Session, now: datetime) -> RetentionReport:
    """30 days count from the `starts_at` instant, not the local date (§5.6)."""
    event_ids = list(session.scalars(due_events(now - timedelta(days=ROSTER_RETENTION_DAYS))))
    for event_id in event_ids:
        signups, spots = session.execute(
            select(func.count(), func.coalesce(func.sum(R.guests + 1), 0)).where(
                R.event_id == event_id, R.status == "going"
            )
        ).one()
        session.execute(
            update(ClubEvent)
            .where(ClubEvent.id == event_id)
            .values(final_signups=int(signups), final_spots=int(spots), roster_purged_at=now)
        )
        session.execute(delete(R).where(R.event_id == event_id))
    last_touch = func.greatest(
        ShooterContact.updated_at,
        func.coalesce(ShooterContact.last_used_at, ShooterContact.updated_at),
    )
    contacts = session.execute(
        delete(ShooterContact)
        .where(last_touch < now - timedelta(days=CONTACT_RETENTION_DAYS))
        .returning(ShooterContact.shooter_id)
    ).all()
    attempts = session.execute(
        delete(ClubEventAttempt)
        .where(ClubEventAttempt.at < now - ATTEMPT_KEEP)
        .returning(ClubEventAttempt.id)
    ).all()
    return RetentionReport(len(event_ids), len(contacts), len(attempts))


@handler("club_event_retention")
def handle_club_event_retention(session: Session, payload: dict[str, Any]) -> None:
    report = purge_club_events(session, datetime.now(UTC))
    logger.info("club events purged=%d contacts expired=%d", report.events, report.contacts)
