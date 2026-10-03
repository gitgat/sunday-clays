"""Public link-preview routes (Plan 19 §3.1.2, D6): GET and HEAD under /api/og/ only.

Nothing here reads the session cookie, the User-Agent or the Host header, and nothing is logged
per request. Every answer is built from a ``PreviewFacts``, which has no name field (D10).
"""

from datetime import date
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from sunday_clays.analytics.cache import read_data_version
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import switch_on
from sunday_clays.og.facts import GENERIC, facts_for_path
from sunday_clays.og.html import render_page
from sunday_clays.og.render import card_png

router = APIRouter()

SettingsDep = Annotated[Settings, Depends(get_settings)]
GET_HEAD: Final = ["GET", "HEAD"]
NOINDEX: Final = {"X-Robots-Tag": "noindex, nofollow"}
PAGE_HEADERS: Final = {"Cache-Control": "private, no-cache", "Vary": "User-Agent", **NOINDEX}
SUNDAY_PNG_HEADERS: Final = {"Cache-Control": "public, max-age=3600", **NOINDEX}
GENERIC_PNG_HEADERS: Final = {"Cache-Control": "public, max-age=86400", **NOINDEX}


def _answer(request: Request, body: bytes, media_type: str, headers: dict[str, str]) -> Response:
    """A HEAD gets the GET's status and headers (Content-Length included) and no body (D6)."""
    if request.method == "HEAD":
        head = {**headers, "Content-Length": str(len(body))}
        return Response(content=b"", media_type=media_type, headers=head)
    return Response(content=body, media_type=media_type, headers=headers)


def _page(request: Request, session: SessionDep, settings: Settings, path: str) -> Response:
    facts = facts_for_path(session, path, switch_on(session, settings, "link_previews"))
    page = render_page(facts, path, settings.public_base_url, read_data_version(session))
    return _answer(request, page.encode(), "text/html", PAGE_HEADERS)


@router.api_route("/api/og/page/", methods=GET_HEAD, include_in_schema=False)
def og_home_page(request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    return _page(request, session, settings, "")


@router.api_route("/api/og/page/{path:path}", methods=GET_HEAD, include_in_schema=False)
def og_page(path: str, request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    return _page(request, session, settings, path)


@router.api_route("/api/og/image/generic.png", methods=GET_HEAD, include_in_schema=False)
def og_generic_image(request: Request, session: SessionDep) -> Response:
    return _answer(request, card_png(session, GENERIC), "image/png", GENERIC_PNG_HEADERS)


@router.api_route("/api/og/image/sunday/{day}.png", methods=GET_HEAD, include_in_schema=False)
def og_sunday_image(
    day: str, request: Request, session: SessionDep, settings: SettingsDep
) -> Response:
    """404 while link_previews is off (for every caller: crawlers have no role) or for no Sunday.

    ``?v=<data_version>`` is a cache-buster only and is never read.
    """
    if not switch_on(session, settings, "link_previews"):
        raise HTTPException(status_code=404)
    try:
        event_date = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=404) from None
    facts = facts_for_path(session, f"events/{event_date.isoformat()}", True)
    if facts.kind == "generic":
        raise HTTPException(status_code=404)
    return _answer(request, card_png(session, facts), "image/png", SUNDAY_PNG_HEADERS)
