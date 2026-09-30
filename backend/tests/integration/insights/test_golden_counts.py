"""Golden counts on the fx world (spec §5): per kind, total rows, the share of the last 145
held Sundays with a row, and how many profile subjects have an evergreen row; how many eligible
shooters' profiles actually show each kind; plus coverage.

`tests/golden/insights_counts.json` and `insights_profile_visible.json` were recorded from this
world when Plan 12 was written (Decision 8 compares them with the spec's spot-check rates). A
change to a guard shows up here; update the files in the same PR and explain the move.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import text

from sunday_clays.analytics.insights import select as sel
from sunday_clays.analytics.insights.context import evergreen_days
from sunday_clays.analytics.insights.store import insights_table, load_rows
from sunday_clays.analytics.insights.types import Scope
from sunday_clays.analytics.steps.s60_insights import build_frames
from sunday_clays.api.routes.insights import supersedes_of

GOLDEN = Path(__file__).parents[2] / "golden" / "insights_counts.json"
PROFILE_VISIBLE = GOLDEN.with_name("insights_profile_visible.json")
LAST = 145
# Of the shooters eligible for profile insights (spec §5 coverage). Plan 12 recorded 9; the fx world
# measures 10. This is expiry, not selection: those shooters hold only Sunday/home-only pf.pb rows
# (the profile gets an evergreen pb variant only within 52 held Sundays) or anchored rows past their
# profile expiry (pf.back-strong 3, pf.sunday-milestone 3, pf.targets-milestone 4 held Sundays),
# and have too few rounds for the evergreen kinds (shooters 26 and 188 have no profile rows at all).
MAX_UNCOVERED = 10


def counts(fx_session) -> dict[str, dict[str, float]]:
    held = list(
        fx_session.scalars(
            text("SELECT event_date FROM events WHERE results_complete ORDER BY event_date")
        )
    )
    recent = set(held[-LAST:])
    rows = fx_session.execute(
        text("SELECT kind, subject_type, subject_id, anchor_date, pages FROM insights")
    ).all()
    out: dict[str, dict[str, float]] = defaultdict(
        lambda: {"rows": 0, "sundays_pct": 0.0, "profile": 0}
    )
    sundays: dict[str, set] = defaultdict(set)
    profiles: dict[str, set] = defaultdict(set)
    for kind, subject_type, subject_id, anchor, pages in rows:
        out[kind]["rows"] += 1
        if anchor in recent:
            sundays[kind].add(anchor)
        if anchor is None and subject_type == "shooter" and "profile" in pages:
            profiles[kind].add(subject_id)
    for kind in out:
        out[kind]["sundays_pct"] = round(100 * len(sundays[kind]) / LAST, 1)
        out[kind]["profile"] = len(profiles[kind])
    return dict(sorted(out.items()))


def test_counts_match_the_golden_file(fx_session):
    assert counts(fx_session) == json.loads(GOLDEN.read_text())


def profile_visible(fx_session) -> dict[str, int]:
    """Per kind, how many eligible shooters' profiles show it: anchored rows until they expire,
    after the supersede, fallback and one-conditions-kind rules (what a viewer sees, §3.4)."""
    fr = build_frames(fx_session)
    held = fr.held_dates()
    scope = Scope(sundays=frozenset(held), as_of=held[-1])
    t = insights_table()
    seen: Counter[str] = Counter()
    for sid, _days in evergreen_days(fr, scope):
        rows = load_rows(fx_session, t.c.subject_type == "shooter", t.c.subject_id == str(sid))
        feed = sel.feed_profile(rows, sid, held[-1], held, supersedes_of)
        shown = [*([] if feed.pinned is None else [feed.pinned]), *feed.top, *feed.more]
        seen.update({r.kind for r in shown})
    return dict(sorted(seen.items()))


def test_profile_visible_counts_match_the_golden_file(fx_session):
    assert profile_visible(fx_session) == json.loads(PROFILE_VISIBLE.read_text())


def test_nearly_every_eligible_shooter_has_a_profile_insight(fx_session):
    fr = build_frames(fx_session)
    held = fr.held_dates()
    scope = Scope(sundays=frozenset(held), as_of=held[-1])
    t = insights_table()
    uncovered = []
    for sid, _days in evergreen_days(fr, scope):
        rows = load_rows(fx_session, t.c.subject_type == "shooter", t.c.subject_id == str(sid))
        if not sel.feed_profile(rows, sid, held[-1], held, supersedes_of).top:
            uncovered.append(sid)
    assert len(uncovered) <= MAX_UNCOVERED
