"""Role dependencies, client-IP bucketing and the audit helper (C8)."""

import hashlib
import hmac
import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar

from fastapi import Depends, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert
from sqlalchemy.orm import Session

from sunday_clays.auth.sessions import COOKIE_NAME, Role, load_session
from sunday_clays.config import Settings, get_settings
from sunday_clays.domain.errors import DomainError
from sunday_clays.models import Base


class NotAuthenticatedError(DomainError):
    status_code: ClassVar[int] = 401


class ForbiddenError(DomainError):
    status_code: ClassVar[int] = 403


class TooManyRequestsError(DomainError):
    status_code: ClassVar[int] = 429


def _bucket(value: str | None) -> str | None:
    """Normalize an IP; IPv6 collapses to its /64, IPv4-mapped IPv6 to the IPv4 address."""
    if not value:
        return None
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return str(address)


def client_ip(request: Request) -> str:
    """X-Real-IP (always set by Caddy) else the TCP peer; X-Forwarded-For is never read."""
    peer = request.client.host if request.client is not None else None
    return _bucket(request.headers.get("x-real-ip")) or _bucket(peer) or peer or "unknown"


def fingerprint(ip: str) -> str:
    """First 32 hex chars of HMAC-SHA256(session_secret, ip): a stable per-client bucket key."""
    key = get_settings().session_secret.get_secret_value().encode()
    return hmac.new(key, ip.encode(), hashlib.sha256).hexdigest()[:32]


def ip_fingerprint(request: Request) -> str:
    """The value the rate-limit tables store in their ``ip`` column instead of the address.

    Keyed over ``client_ip`` (so IPv6 still buckets per /64), which keeps limits per client while
    a reader of the database cannot read an address or tie a row to one. ``audit_log.ip`` is the
    exception: it records admin actions only, is the owner's own trail, and stays raw.
    """
    return fingerprint(client_ip(request))


def current_role(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> Role | None:
    token = request.cookies.get(COOKIE_NAME)
    return load_session(settings, token) if token else None


def require_viewer(role: Annotated[Role | None, Depends(current_role)]) -> Role:
    if role is None:
        raise NotAuthenticatedError("unauthenticated", "Log in to continue")
    return role


def require_admin(role: Annotated[Role, Depends(require_viewer)]) -> Role:
    if role != "admin":
        raise ForbiddenError("forbidden", "Admin access required")
    return role


@dataclass(frozen=True)
class Actor:
    role: Role
    ip: str


def admin_actor(request: Request, role: Annotated[Role, Depends(require_admin)]) -> Actor:
    # Raw on purpose: audit_log is the owner's own admin trail (admin actions only), outside the
    # About-page claims that cover visitors. Rate-limit tables use ip_fingerprint instead.
    return Actor(role=role, ip=client_ip(request))


def record_audit(
    session: Session, ip: str | None, role: str, action: str, details: Mapping[str, Any]
) -> None:
    """Append one ``audit_log`` row in the caller's transaction (dates/enums JSON-encoded)."""
    audit_log = Base.metadata.tables["audit_log"]
    session.execute(
        insert(audit_log).values(
            ip=ip, role=role, action=action, details=jsonable_encoder(dict(details))
        )
    )
