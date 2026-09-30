"""POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me (C8)."""

import threading
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from sunday_clays.auth.deps import (
    NotAuthenticatedError,
    TooManyRequestsError,
    client_ip,
    record_audit,
    require_viewer,
)
from sunday_clays.auth.passwords import match_role
from sunday_clays.auth.ratelimit import is_limited, record_attempt
from sunday_clays.auth.sessions import COOKIE_NAME, TTL, Role, issue_session
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep

router = APIRouter(prefix="/api/auth", tags=["auth"])

# At most 4 argon2 verifies (~19 MiB each) run at once; a request waits up to 5 s for a slot.
_VERIFY_SLOTS = threading.BoundedSemaphore(4)
VERIFY_ACQUIRE_TIMEOUT_S = 5.0


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class RoleOut(BaseModel):
    role: Role


@router.post("/login")
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RoleOut:
    ip = client_ip(request)
    if is_limited(session, ip):
        raise TooManyRequestsError("rate_limited", "Too many failed logins. Try again later.")
    # End the SELECT's transaction so no pooled connection is held through the slot wait and
    # the argon2 verify (up to seconds); record_attempt starts a fresh one.
    session.commit()
    if not _VERIFY_SLOTS.acquire(timeout=VERIFY_ACQUIRE_TIMEOUT_S):
        raise TooManyRequestsError("login_busy", "The server is busy. Try again in a moment.")
    try:
        role = match_role(settings, body.password)
    finally:
        _VERIFY_SLOTS.release()
    record_attempt(session, ip, role is not None)
    if role is None:
        session.commit()  # get_session rolls back on any exception; keep the failure row
        raise NotAuthenticatedError("invalid_password", "Wrong password")
    if role == "admin":
        record_audit(session, ip, role, "auth.login", {})
    response.set_cookie(
        COOKIE_NAME,
        issue_session(settings, role),
        max_age=int(TTL[role].total_seconds()),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return RoleOut(role=role)


@router.post("/logout", status_code=204)
def logout(response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    response.delete_cookie(
        COOKIE_NAME, path="/", secure=settings.cookie_secure, httponly=True, samesite="strict"
    )


@router.get("/me")
def me(role: Annotated[Role, Depends(require_viewer)]) -> RoleOut:
    return RoleOut(role=role)
