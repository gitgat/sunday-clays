"""Club events (Plan 20): the pure rules.

The queue (admit and promote, D9), sign-up name keys (§5.3.5), email normalising and the
constant-time email and token checks (D11), club-time conversions (D21), the retention constants
(D16) and the database-error scrubber (D22). Nothing here reads the database; the store
(domain/club_event_store.py) and the organizer actions (domain/club_event_admin.py) do.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import unicodedata
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import ClassVar, Final, Literal
from zoneinfo import ZoneInfo

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.domain.errors import ConflictError, DomainError
from sunday_clays.ingest.names import clean_display_name, name_key

logger = logging.getLogger(__name__)

# D16. The About page's "Your privacy" card states both numbers ("Sign-ups are deleted 30 days
# after the event" and "…until an organizer removes it or it goes two years unused"): change them
# together with frontend/src/features/about (privacy.ts from Plan 20 T7).
ROSTER_RETENTION_DAYS: Final = 30
CONTACT_RETENTION_DAYS: Final = 730
CANCEL_FAIL_PER_REGISTRATION: Final = 5  # failed email cancels on one registration per hour
MAX_ACTIVE_PER_EVENT: Final = 200
SIGNUP_WINDOW: Final = timedelta(minutes=60)
CHECK_WINDOW: Final = timedelta(minutes=10)
CANCEL_FAIL_WINDOW: Final = timedelta(minutes=60)
ATTEMPT_KEEP: Final = timedelta(days=1)
MAX_GUESTS: Final = 10
TITLE_MAX: Final = 80
NOTES_MAX: Final = 2000
CAPACITY_MAX: Final = 500
NAME_MIN: Final = 2
NAME_MAX: Final = 60
EMAIL_MAX: Final = 254
ACTIVE: Final[tuple[str, ...]] = ("going", "waitlist")

TOO_MANY: Final = "Too many tries from here. Wait a bit and try again."
CANCEL_NOT_MATCHED: Final = "That email doesn't match this sign-up. Check it and try again."
BAD_EMAIL: Final = "Enter an email like name@example.com."
SPRING_FORWARD: Final = "That time doesn't exist on that day (clocks spring forward)."

Admission = Literal["going", "waitlist"]
EventState = Literal["open", "closed", "started", "cancelled"]


class InternalError(DomainError):
    """A plain 500 `internal` that carries nothing from the error that caused it (D22)."""

    status_code: ClassVar[int] = 500


# --- the queue (D9) ------------------------------------------------------------------------------


@dataclass(frozen=True)
class QueueRow:
    """One active registration as the queue sees it. Order is `id`; `queue_at` is display only."""

    id: int
    status: str
    guests: int
    queue_at: datetime | None = None

    @property
    def spots(self) -> int:
        return 1 + self.guests


def _in_order(queue: Sequence[QueueRow]) -> list[QueueRow]:
    return sorted(queue, key=lambda row: row.id)


def going_spots(queue: Sequence[QueueRow]) -> int:
    return sum(row.spots for row in queue if row.status == "going")


def admit(queue: Sequence[QueueRow], capacity: int | None, new_spots: int) -> Admission:
    """Going only when there is no limit, or nobody waits and the party fits; else the back of
    the waitlist."""
    if capacity is None:
        return "going"
    if any(row.status == "waitlist" for row in queue):
        return "waitlist"
    return "going" if going_spots(queue) + new_spots <= capacity else "waitlist"


def promotions(queue: Sequence[QueueRow], capacity: int | None) -> list[int]:
    """Waitlist ids to promote, front first, stopping at the first party that does not fit."""
    waiting = [row for row in _in_order(queue) if row.status == "waitlist"]
    if capacity is None:
        return [row.id for row in waiting]
    taken = going_spots(queue)
    promoted: list[int] = []
    for row in waiting:
        if taken + row.spots > capacity:
            break
        taken += row.spots
        promoted.append(row.id)
    return promoted


def waitlist_positions(queue: Sequence[QueueRow]) -> dict[int, int]:
    """1-based place of each waitlist row in queue order."""
    waiting = [row for row in _in_order(queue) if row.status == "waitlist"]
    return {row.id: place for place, row in enumerate(waiting, start=1)}


# --- names (§5.3.5) ------------------------------------------------------------------------------


def signup_key(name: str) -> str:
    """`name_key` with its words sorted: "Ike Hadley" and "Hadley, Ike" share one key."""
    return " ".join(sorted(name_key(name).split()))


def typed_name(raw: str) -> tuple[str, str]:
    """The cleaned display name and its sign-up key; 2-60 characters and at least two words."""
    name = clean_display_name(raw)
    if not NAME_MIN <= len(name) <= NAME_MAX:
        raise DomainError("bad_name", "Enter a name of 2 to 60 characters.")
    key = signup_key(name)
    if len(key.split()) < 2:
        raise DomainError(
            "name_needs_last", "Add your last name too, so organizers know who you are."
        )
    return name, key


# --- emails and tokens (§5.3.6, D11) -------------------------------------------------------------

_EMAIL = re.compile(r"[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}")
DUMMY_TOKEN_HASH: Final = "0" * 64


def fold_email(raw: str) -> str:
    """NFKC, strip, lowercase: the form both sides of a comparison take."""
    return unicodedata.normalize("NFKC", raw).strip().lower()


def normalise_email(raw: str) -> str:
    email = fold_email(raw)
    if len(email) > EMAIL_MAX or _EMAIL.fullmatch(email) is None:
        raise DomainError("bad_email", BAD_EMAIL)
    return email


def _key() -> bytes:
    return get_settings().session_secret.get_secret_value().encode()


def _digest(value: bytes) -> bytes:
    return hmac.new(_key(), value, hashlib.sha256).digest()


def email_matches(stored: str | None, typed: str) -> bool:
    """D11: both sides hashed to 32 bytes, then compared in constant time. Nothing stored
    compares against a fixed dummy, so a missing and a wrong email take the same path and time,
    and a non-ASCII address never reaches compare_digest as a str."""
    given = _digest(fold_email(typed).encode("utf-8", "surrogatepass"))
    expected = (
        _digest(stored.encode("utf-8", "surrogatepass")) if stored else _digest(b"\x00no-email")
    )
    return hmac.compare_digest(given, expected) and bool(stored)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8", "surrogatepass")).hexdigest()


def new_token() -> tuple[str, str]:
    """A fresh device token and the hash that is stored; the token itself is returned once."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_matches(stored_hash: str | None, token: str) -> bool:
    given = token_hash(token).encode()
    expected = (stored_hash or DUMMY_TOKEN_HASH).encode()
    return hmac.compare_digest(given, expected) and stored_hash is not None


# --- club time (D21) -----------------------------------------------------------------------------


def local_to_utc(local: str, tz: str) -> datetime:
    """`YYYY-MM-DDTHH:MM` in the club zone as an instant. A time inside the spring-forward gap is
    refused; one inside the fall-back hour is its first occurrence."""
    day, sep, clock = local.partition("T")
    wall_day: date | None
    wall_time: time | None
    try:
        wall_day = date.fromisoformat(day)
        wall_time = time.fromisoformat(clock).replace(fold=0)
    except ValueError:
        wall_day = wall_time = None
    if not sep or wall_day is None or wall_time is None:
        raise DomainError("bad_local_time", "Enter a date and a time.")
    zone = ZoneInfo(tz)
    instant = datetime.combine(wall_day, wall_time, tzinfo=zone).astimezone(UTC)
    back = instant.astimezone(zone)
    if (back.date(), back.time()) != (wall_day, wall_time):
        raise DomainError("bad_local_time", SPRING_FORWARD)
    return instant


def local_parts(instant: datetime, tz: str) -> tuple[date, str]:
    """The club-time calendar date and `HH:MM` of an instant."""
    local = instant.astimezone(ZoneInfo(tz))
    return local.date(), local.strftime("%H:%M")


def event_state(
    now: datetime, starts_at: datetime, deadline: datetime, cancelled_at: datetime | None
) -> EventState:
    if cancelled_at is not None:
        return "cancelled"
    if now >= starts_at:
        return "started"
    return "open" if now < deadline else "closed"


def is_upcoming(starts_at: datetime, now: datetime, tz: str) -> bool:
    """Upcoming while the event's club-time date is today or later (§4)."""
    zone = ZoneInfo(tz)
    return starts_at.astimezone(zone).date() >= now.astimezone(zone).date()


# --- guests (§5.3.4) -----------------------------------------------------------------------------


def check_guests(guests: int, allow_guests: bool, max_guests: int) -> None:
    if not allow_guests and guests != 0:
        raise DomainError("bad_guests", "This event is members only, no guests.")
    if not 0 <= guests <= max_guests:
        raise DomainError("bad_guests", f"Bring up to {max_guests} guests.")


# --- database errors (D22.2) ---------------------------------------------------------------------

DUPLICATE_INDEXES: Final = frozenset(
    {"uq_club_event_registrations_shooter", "uq_club_event_registrations_name"}
)


def _constraint(exc: DBAPIError) -> str | None:
    name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    return name if isinstance(name, str) else None


@contextmanager
def scrub_db_errors(
    session: Session, duplicate_message: str = "That name is already on the list."
) -> Iterator[None]:
    """Run a club-event write so no database error can carry an email out of the app.

    The block's statements are flushed at the end, so a violation surfaces here and never at the
    request's commit. A `DBAPIError` rolls the session back, logs its class and constraint name
    only, and becomes a plain `DomainError` raised from None: neither the message (Postgres's
    "Failing row contains (…)") nor the cause chain reaches a log. A race on the duplicate
    indexes, which the event lock should already prevent, is 409 `already_signed_up`.
    """
    try:
        yield
        session.flush()
    except DBAPIError as exc:
        constraint = _constraint(exc)
        session.rollback()
        logger.error(
            "club event write failed: %s on %s", type(exc).__name__, constraint or "no constraint"
        )
        if constraint in DUPLICATE_INDEXES:
            raise ConflictError("already_signed_up", duplicate_message) from None
        raise InternalError("internal", "Internal server error") from None
