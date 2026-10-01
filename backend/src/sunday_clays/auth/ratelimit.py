"""Rate limits per client-IP bucket: failed logins (``login_attempts``, C4, C8) and fist bumps
(``bump_attempts``, Plan 14)."""

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


# --- Plan 14: fist bumps -------------------------------------------------------------------------
BUMP_LIMIT: Final = 120
BUMP_WINDOW: Final = timedelta(minutes=10)


def _bump_attempts() -> Table:
    return Base.metadata.tables["bump_attempts"]


def bumps_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already made ``BUMP_LIMIT`` bump actions in the last ``BUMP_WINDOW``."""
    t = _bump_attempts()
    since = datetime.now(UTC) - BUMP_WINDOW
    actions = session.scalar(
        select(func.count()).select_from(t).where(t.c.ip == ip, t.c.at > since)
    )
    return (actions or 0) >= BUMP_LIMIT


def record_bump_action(session: Session, ip: str) -> None:
    """Insert one action and prune rows outside the window, inside the caller's transaction."""
    t = _bump_attempts()
    now = datetime.now(UTC)
    session.execute(insert(t).values(ip=ip, at=now))
    session.execute(delete(t).where(t.c.at < now - BUMP_WINDOW))
