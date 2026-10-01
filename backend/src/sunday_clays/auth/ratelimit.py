"""Rate limits per client-IP bucket: failed logins (``login_attempts``, C4, C8), fist bumps
(``bump_attempts``, Plan 15) and page-view beacons (``page_view_attempts``, Plan 16)."""

from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import ColumnElement, Table, delete, func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.models import Base

PRUNE_AFTER: Final = timedelta(days=1)


def _attempts() -> Table:
    return Base.metadata.tables["login_attempts"]


def _bump_attempts() -> Table:
    return Base.metadata.tables["bump_attempts"]


def _count_since(
    session: Session, t: Table, ip: str, since: datetime, *extra: ColumnElement[bool]
) -> int:
    """Rows in ``t`` for ``ip`` newer than ``since`` that also match ``extra``."""
    n = session.scalar(
        select(func.count()).select_from(t).where(t.c.ip == ip, t.c.at > since, *extra)
    )
    return n or 0


def _insert_and_prune(session: Session, t: Table, keep_for: timedelta, **values: object) -> None:
    """Insert one row stamped now and delete rows older than ``keep_for``, in the caller's txn."""
    now = datetime.now(UTC)
    session.execute(insert(t).values(at=now, **values))
    session.execute(delete(t).where(t.c.at < now - keep_for))


def is_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already has ``login_max_failures`` failures in the login window."""
    settings = get_settings()
    t = _attempts()
    since = datetime.now(UTC) - timedelta(minutes=settings.login_window_minutes)
    failures = _count_since(session, t, ip, since, t.c.success.is_(False))
    return failures >= settings.login_max_failures


def record_attempt(session: Session, ip: str, success: bool) -> None:
    """Insert one attempt and prune rows older than a day, inside the caller's transaction."""
    _insert_and_prune(session, _attempts(), PRUNE_AFTER, ip=ip, success=success)


# --- Plan 15: fist bumps -------------------------------------------------------------------------
# Per IP, not per device: club Wi-Fi and carrier NAT put 20-30 phones behind one IPv4 address, and
# the shoot is when bumps get used. Bumps are idempotent per device, so this only guards volume.
BUMP_LIMIT: Final = 600
BUMP_WINDOW: Final = timedelta(minutes=10)


def bumps_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already made ``BUMP_LIMIT`` bump actions in the last ``BUMP_WINDOW``."""
    since = datetime.now(UTC) - BUMP_WINDOW
    return _count_since(session, _bump_attempts(), ip, since) >= BUMP_LIMIT


def record_bump_action(session: Session, ip: str) -> None:
    """Insert one action and prune rows outside the window, inside the caller's transaction."""
    _insert_and_prune(session, _bump_attempts(), BUMP_WINDOW, ip=ip)


# --- Plan 16: page views -------------------------------------------------------------------------
# Per IP, like bumps: club Wi-Fi puts many phones behind one address. Each device's views are
# already deduped per page kind, so this only guards volume. The limit is settings.page_view_limit
# (default 600) so the one-IP e2e stack can raise it. Rows older than the window are pruned on the
# next beacon and by the daily page_view_rollup job (prune_page_view_attempts).
PAGE_VIEW_WINDOW: Final = timedelta(minutes=10)


def _page_view_attempts() -> Table:
    return Base.metadata.tables["page_view_attempts"]


def page_views_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already sent ``page_view_limit`` beacons within ``PAGE_VIEW_WINDOW``."""
    since = datetime.now(UTC) - PAGE_VIEW_WINDOW
    limit = get_settings().page_view_limit
    return _count_since(session, _page_view_attempts(), ip, since) >= limit


def record_page_view_attempt(session: Session, ip: str) -> None:
    """Insert one beacon and prune rows outside the window, inside the caller's transaction."""
    _insert_and_prune(session, _page_view_attempts(), PAGE_VIEW_WINDOW, ip=ip)


def prune_page_view_attempts(session: Session) -> None:
    """Delete beacons older than the window, in the caller's transaction. The daily rollup job
    calls this so the last burst before a quiet spell does not keep its IPs until the next
    beacon."""
    t = _page_view_attempts()
    session.execute(delete(t).where(t.c.at < datetime.now(UTC) - PAGE_VIEW_WINDOW))
