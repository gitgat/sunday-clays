"""Signed, role-bound session tokens for the ``sc_session`` cookie (C8 Sessions)."""

import hashlib
import hmac
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from itsdangerous import BadData, URLSafeTimedSerializer

from sunday_clays.config import Settings

Role = Literal["viewer", "admin"]
COOKIE_NAME: Final = "sc_session"
TTL: Final[Mapping[Role, timedelta]] = {
    "viewer": timedelta(days=30),
    "admin": timedelta(hours=12),
}
_ROLES: Final[Mapping[str, Role]] = {"viewer": "viewer", "admin": "admin"}


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret.get_secret_value(), salt="sc-session")


def _fingerprint(settings: Settings, role: Role) -> str:
    """First 16 hex chars of HMAC-SHA256(session_secret, the role's current password hash)."""
    current = settings.admin_password_hash if role == "admin" else settings.viewer_password_hash
    digest = hmac.new(
        settings.session_secret.get_secret_value().encode(),
        current.get_secret_value().encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest[:16]


def issue_session(settings: Settings, role: Role) -> str:
    """Sign ``{r: role, k: fp}``; itsdangerous embeds the signing timestamp."""
    return _serializer(settings).dumps({"r": role, "k": _fingerprint(settings, role)})


def load_session(settings: Settings, token: str, *, now: datetime | None = None) -> Role | None:
    """Return the token's role, or None if forged, expired for its role, or its password rotated."""
    try:
        payload, signed_at = _serializer(settings).loads(token, return_timestamp=True)
    except BadData:
        return None
    if not isinstance(payload, dict):
        return None
    raw_role, fingerprint = payload.get("r"), payload.get("k")
    role = _ROLES.get(raw_role) if isinstance(raw_role, str) else None
    if role is None or not isinstance(fingerprint, str):
        return None
    if (now or datetime.now(UTC)) - signed_at > TTL[role]:
        return None
    if not hmac.compare_digest(fingerprint, _fingerprint(settings, role)):
        return None
    return role
