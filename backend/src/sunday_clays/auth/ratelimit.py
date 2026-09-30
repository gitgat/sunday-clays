"""Failed-login rate limit per client-IP bucket, stored in ``login_attempts`` (C4, C8)."""

from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import Table, delete, func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.models import Base

PRUNE_AFTER: Final = timedelta(days=1)


def _attempts() -> Table:
    return Base.metadata.tables["login_attempts"]


def is_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already has ``login_max_failures`` failures in the login window."""
    settings = get_settings()
    t = _attempts()
    since = datetime.now(UTC) - timedelta(minutes=settings.login_window_minutes)
    failures = session.scalar(
        select(func.count())
        .select_from(t)
        .where(t.c.ip == ip, t.c.success.is_(False), t.c.at > since)
    )
    return (failures or 0) >= settings.login_max_failures


def record_attempt(session: Session, ip: str, success: bool) -> None:
    """Insert one attempt and prune rows older than a day, inside the caller's transaction."""
    t = _attempts()
    now = datetime.now(UTC)
    session.execute(insert(t).values(ip=ip, at=now, success=success))
    session.execute(delete(t).where(t.c.at < now - PRUNE_AFTER))
