"""Preview copy (§3.1.4) and the script-free, style-free meta page (§3.1.2)."""

import html
from datetime import date
from typing import Final

from sunday_clays.domain.round_type import RoundType
from sunday_clays.og.facts import PreviewFacts, page_path

SITE_TITLE: Final = "Sunday Clays · Tri-County Gun Club"
GENERIC_DESCRIPTION: Final = (
    "Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club."
)
_MONTHS: Final = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
_ROUND_TYPES: Final = {RoundType.SPORTING: "Sporting", RoundType.SUPER_SPORTING: "Super Sporting"}


def _short(day: date) -> str:
    """Sep 27, 2026 (fixed English months: the container locale never matters)."""
    return f"{_MONTHS[day.month - 1]} {day.day}, {day.year}"


def _shooters(n: int | None) -> list[str]:
    if n is None:
        return []
    return ["1 shooter" if n == 1 else f"{n} shooters"]


def _round_type(facts: PreviewFacts) -> list[str]:
    return [] if facts.round_type is None else [_ROUND_TYPES[facts.round_type]]


def title_of(facts: PreviewFacts) -> str:
    return SITE_TITLE


def description_of(facts: PreviewFacts) -> str:
    if facts.kind == "generic" or facts.event_date is None:
        return GENERIC_DESCRIPTION
    if facts.kind == "special":
        return " · ".join([facts.label or "Special shoot", *_shooters(facts.n_shooters)])
    parts = [f"Sunday, {_short(facts.event_date)}", *_shooters(facts.n_shooters)]
    return " · ".join([*parts, *_round_type(facts)])


def image_alt_of(facts: PreviewFacts) -> str:
    if facts.kind == "generic" or facts.event_date is None:
        return "Sunday Clays logo"
    if facts.kind == "special":
        return f"Sunday Clays, {facts.label or 'Special shoot'} on {_short(facts.event_date)}"
    return f"Sunday Clays, Sunday {_short(facts.event_date)}"


def image_lines(facts: PreviewFacts) -> tuple[str, str] | None:
    """Line A and line B of a Sunday card; None for the generic card."""
    if facts.kind == "generic" or facts.event_date is None:
        return None
    if facts.kind == "special":
        line_b = " · ".join(["Special shoot", *_shooters(facts.n_shooters)])
        return facts.label or "Special shoot", line_b
    line_b = " · ".join([*_shooters(facts.n_shooters), *_round_type(facts)])
    return f"Sunday, {_short(facts.event_date)}", line_b


def image_url(facts: PreviewFacts, base_url: str, data_version: int) -> str:
    if facts.kind == "generic" or facts.event_date is None:
        return f"{base_url}/api/og/image/generic.png"
    return f"{base_url}/api/og/image/sunday/{facts.event_date.isoformat()}.png?v={data_version}"


def render_page(facts: PreviewFacts, path: str, base_url: str, data_version: int) -> str:
    """The meta page. Every value is escaped; ``og:url`` is always the ``/l/`` form (D7)."""

    def e(value: str) -> str:
        return html.escape(value, quote=True)

    shown = page_path(path)
    title, description = e(title_of(facts)), e(description_of(facts))
    image = e(image_url(facts, base_url, data_version))
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f'<meta name="description" content="{description}">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        '<meta property="og:type" content="website">\n'
        '<meta property="og:site_name" content="Sunday Clays">\n'
        f'<meta property="og:title" content="{title}">\n'
        f'<meta property="og:description" content="{description}">\n'
        f'<meta property="og:url" content="{e(f"{base_url}/l/{shown}")}">\n'
        f'<meta property="og:image" content="{image}">\n'
        '<meta property="og:image:width" content="1200">\n'
        '<meta property="og:image:height" content="630">\n'
        f'<meta property="og:image:alt" content="{e(image_alt_of(facts))}">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{title}">\n'
        f'<meta name="twitter:description" content="{description}">\n'
        f'<meta name="twitter:image" content="{image}">\n'
        f'</head><body><p><a href="/{e(shown)}">Open Sunday Clays</a></p></body></html>\n'
    )
