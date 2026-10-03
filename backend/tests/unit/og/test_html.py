"""Preview copy and meta page (Plan 19 §3.1.2, §3.1.4)."""

from datetime import date

import pytest

from sunday_clays.domain.round_type import RoundType
from sunday_clays.og.facts import GENERIC, PreviewFacts, page_path
from sunday_clays.og.html import (
    SITE_TITLE,
    description_of,
    image_alt_of,
    image_lines,
    image_url,
    render_page,
)

BASE = "https://sundayclays.claysmasher.com"
SUNDAY = PreviewFacts("sunday", date(2026, 9, 27), 23, RoundType.SPORTING)
SPECIAL = PreviewFacts("special", date(2026, 9, 20), 40, RoundType.SPORTING, "3-Bird Shoot")


@pytest.mark.parametrize(
    ("facts", "description", "alt"),
    [
        (
            GENERIC,
            "Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club.",
            "Sunday Clays logo",
        ),
        (
            SUNDAY,
            "Sunday, Sep 27, 2026 · 23 shooters · Sporting",
            "Sunday Clays, Sunday Sep 27, 2026",
        ),
        (SPECIAL, "3-Bird Shoot · 40 shooters", "Sunday Clays, 3-Bird Shoot on Sep 20, 2026"),
    ],
)
def test_copy_table(facts: PreviewFacts, description: str, alt: str) -> None:
    assert description_of(facts) == description
    assert image_alt_of(facts) == alt


def test_title_is_always_the_club() -> None:
    assert SITE_TITLE == "Sunday Clays · Tri-County Gun Club"


def test_singular_super_sporting_and_no_count() -> None:
    one = PreviewFacts("sunday", date(2026, 9, 27), 1, RoundType.SUPER_SPORTING)
    assert description_of(one) == "Sunday, Sep 27, 2026 · 1 shooter · Super Sporting"
    none = PreviewFacts("sunday", date(2026, 9, 27), None, RoundType.SPORTING)
    assert description_of(none) == "Sunday, Sep 27, 2026 · Sporting"
    assert description_of(PreviewFacts("special", date(2026, 9, 20), None, None, "X")) == "X"


def test_image_lines() -> None:
    assert image_lines(GENERIC) is None
    assert image_lines(SUNDAY) == ("Sunday, Sep 27, 2026", "23 shooters · Sporting")
    assert image_lines(SPECIAL) == ("3-Bird Shoot", "Special shoot · 40 shooters")


def test_image_url_carries_the_data_version_only_for_a_sunday() -> None:
    assert image_url(GENERIC, BASE, 9) == f"{BASE}/api/og/image/generic.png"
    assert image_url(SUNDAY, BASE, 9) == f"{BASE}/api/og/image/sunday/2026-09-27.png?v=9"


@pytest.mark.parametrize(
    ("raw", "stripped"),
    [
        ("/", ""),
        ("", ""),
        ("l/events/2026-09-27", "events/2026-09-27"),
        ("/events/x", "events/x"),
        ("l//evil.com", "evil.com"),
        ("l/\\evil.com", "evil.com"),
        ("\\evil.com", "evil.com"),
    ],
)
def test_page_path_strips_the_share_prefix(raw: str, stripped: str) -> None:
    assert page_path(raw) == stripped


@pytest.mark.parametrize(
    "raw", ["l//evil.com", "l/\\evil.com", "\\evil.com", "//evil.com", "l/\\/evil.com"]
)
def test_render_page_never_links_off_site(raw: str) -> None:
    page = render_page(GENERIC, raw, BASE, 1)
    assert 'href="//' not in page
    assert 'href="/\\' not in page


def test_golden_sunday_page() -> None:
    expected = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        "<title>Sunday Clays · Tri-County Gun Club</title>\n"
        '<meta name="description" content="Sunday, Sep 27, 2026 · 23 shooters · Sporting">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        '<meta property="og:type" content="website">\n'
        '<meta property="og:site_name" content="Sunday Clays">\n'
        '<meta property="og:title" content="Sunday Clays · Tri-County Gun Club">\n'
        '<meta property="og:description" content="Sunday, Sep 27, 2026 · 23 shooters · Sporting">\n'
        f'<meta property="og:url" content="{BASE}/l/events/2026-09-27">\n'
        f'<meta property="og:image" content="{BASE}/api/og/image/sunday/2026-09-27.png?v=4">\n'
        '<meta property="og:image:width" content="1200">\n'
        '<meta property="og:image:height" content="630">\n'
        '<meta property="og:image:alt" content="Sunday Clays, Sunday Sep 27, 2026">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        '<meta name="twitter:title" content="Sunday Clays · Tri-County Gun Club">\n'
        '<meta name="twitter:description" '
        'content="Sunday, Sep 27, 2026 · 23 shooters · Sporting">\n'
        f'<meta name="twitter:image" content="{BASE}/api/og/image/sunday/2026-09-27.png?v=4">\n'
        '</head><body><p><a href="/events/2026-09-27">Open Sunday Clays</a></p></body></html>\n'
    )
    assert render_page(SUNDAY, "/l/events/2026-09-27", BASE, 4) == expected
    assert (
        render_page(SUNDAY, "/events/2026-09-27", BASE, 4) == expected
    )  # og:url is /l/ either way


def test_generic_and_special_pages_have_their_own_facts() -> None:
    generic = render_page(GENERIC, "/", BASE, 4)
    assert f'<meta property="og:url" content="{BASE}/l/">' in generic
    assert f'content="{BASE}/api/og/image/generic.png"' in generic
    assert '<a href="/">Open Sunday Clays</a>' in generic
    special = render_page(SPECIAL, "/events/2026-09-20", BASE, 4)
    assert 'content="3-Bird Shoot · 40 shooters"' in special


def test_every_value_is_escaped_and_the_page_has_no_script_or_style() -> None:
    hostile = PreviewFacts("special", date(2026, 9, 20), 3, None, '<b a="1">&x')
    page = render_page(hostile, '/events/2026-09-20"><script>', BASE, 4)
    assert "<b " not in page
    assert '"1">' not in page
    assert "&lt;b a=&quot;1&quot;&gt;&amp;x" in page
    assert "<script" not in page.lower()
    assert "style=" not in page.lower()
