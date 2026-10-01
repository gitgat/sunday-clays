"""POST /api/pageviews (Plan 16): one anonymous page-view beacon from the SPA.

Answers 204 with no body whether the view was stored or dropped: an admin session is dropped
before anything is written (Decision 6), and the same device and kind inside 30 minutes is
deduped (domain/page_views.py). The server's clock stamps the view; the browser's ``at`` is
accepted and ignored (Decision 4). The IP feeds only the rate-limit log, as for bumps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from sunday_clays.api.routes.bumps import parse_device_id
from sunday_clays.auth.deps import TooManyRequestsError, client_ip, require_viewer
from sunday_clays.auth.ratelimit import page_views_limited, record_page_view_attempt
from sunday_clays.auth.sessions import Role
from sunday_clays.db import SessionDep
from sunday_clays.domain.page_views import MeState, PageKind, record_page_view

router = APIRouter(tags=["pageviews"])


class PageViewIn(BaseModel):
    device_id: str
    page_kind: PageKind
    me_state: MeState
    at: datetime | None = None  # the browser's clock: accepted, never stored


@router.post("/api/pageviews", status_code=204)
def page_view(
    body: PageViewIn,
    request: Request,
    session: SessionDep,
    role: Annotated[Role, Depends(require_viewer)],
) -> None:
    if role == "admin":
        return
    ip = client_ip(request)
    if page_views_limited(session, ip):
        raise TooManyRequestsError("rate_limited", "Too many page views from here. Try again soon.")
    record_page_view_attempt(session, ip)
    session.commit()  # get_session rolls back on any error; a refused beacon still counts
    device = parse_device_id(body.device_id)
    record_page_view(session, device, body.page_kind, body.me_state, datetime.now(UTC))
