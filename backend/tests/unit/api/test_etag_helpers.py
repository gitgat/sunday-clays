import pytest

from sunday_clays.api import etag


@pytest.mark.parametrize(
    ("method", "path", "eligible"),
    [
        ("GET", "/api/meta", True),
        ("GET", "/api/events/2026-09-13", True),
        ("HEAD", "/api/meta", False),
        ("POST", "/api/explore", False),
        ("GET", "/api/health", False),
        ("GET", "/api/auth/me", False),
        ("GET", "/api/admin/imports", False),
        ("GET", "/api/predictions/next", False),
        ("GET", "/api/insights/home", True),
        ("GET", "/api/bumps", False),
        ("GET", "/api/features", False),
        ("GET", "/api/og/page/events/2026-09-27", False),
        ("GET", "/api/features/", False),
        ("GET", "/api/features-x", True),
        ("GET", "/api/club-events", False),
        ("GET", "/api/club-events/", False),
        ("GET", "/api/club-events/7", False),
        ("GET", "/api/club-events-x", True),
        ("GET", "/index.html", False),
    ],
)
def test_etag_eligibility(method: str, path: str, eligible: bool) -> None:
    assert etag.etag_eligible(method, path) is eligible


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("/api/meta", "private, no-cache"),
        ("/api/health", "private, no-cache"),
        ("/api/auth/me", "no-store"),
        ("/api/admin/jobs/1", "no-store"),
        ("/api/insights/home", "private, no-cache"),
        ("/api/bumps", "no-store"),
        ("/api/features", "no-store"),
        ("/api/og/image/generic.png", None),  # the route's own Cache-Control stands
        ("/api/og/page/", None),
        ("/api/features/", "no-store"),
        ("/api/features-x", "private, no-cache"),
        ("/api/club-events", "no-store"),
        ("/api/club-events/", "no-store"),
        ("/api/club-events/7", "no-store"),
        ("/api/club-events-x", "private, no-cache"),
        ("/assets/app.js", None),
        ("/assets/bumps", None),
    ],
)
def test_cache_control_by_path(path: str, value: str | None) -> None:
    assert etag.cache_control_for(path) == value


def test_compute_etag_shape_and_inputs() -> None:
    tag = etag.compute_etag("1.2.0", 7, "2026-09-27", "/api/meta", "a=1&b=2")
    # sha1("/api/meta?a=1&b=2")[:16], computed independently
    assert tag == 'W/"1.2.0-7-2026-09-27-d416113a7944bb51"'
    assert etag.compute_etag("1.2.1", 7, "2026-09-27", "/api/meta", "a=1&b=2") != tag
    assert etag.compute_etag("1.2.0", 8, "2026-09-27", "/api/meta", "a=1&b=2") != tag
    assert etag.compute_etag("1.2.0", 7, "2026-09-28", "/api/meta", "a=1&b=2") != tag
    assert etag.compute_etag("1.2.0", 7, "2026-09-27", "/api/meta", "a=1&b=3") != tag


@pytest.mark.parametrize(
    ("header", "matches"),
    [
        (None, False),
        ("", False),
        ('W/"x-1"', True),
        ('"x-1"', True),
        ('W/"x-2", W/"x-1"', True),
        ('W/"x-2"', False),
        ("*", True),
    ],
)
def test_if_none_match_weak_comparison(header: str | None, matches: bool) -> None:
    assert etag.if_none_match_matches(header, 'W/"x-1"') is matches
