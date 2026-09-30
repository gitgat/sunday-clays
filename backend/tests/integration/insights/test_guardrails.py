"""Guardrails on the fx world (spec §4.1-4.2, §5): nobody is named for doing worse, and every
rendered headline passes the language lints."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from sunday_clays.analytics.insights.context import InsightFrames
from sunday_clays.analytics.insights.engine import apply_rollups, evaluate_all
from sunday_clays.analytics.insights.lints import lint_segments, lint_text
from sunday_clays.analytics.insights.registry import all_kinds
from sunday_clays.analytics.insights.templates import render
from sunday_clays.analytics.insights.types import ROLLUP, Polarity
from sunday_clays.analytics.steps.s60_insights import build_frames

WORSE = 990001
# Effort and welcome kinds that may name anyone who keeps showing up (spec §5, plus the two
# effort counts added in Plan 12: targets broken and the next milestone/calendar trophy).
ALLOWLIST = frozenset(
    {
        "pf.digest-line",
        "pf.back-strong",
        "ev.second-visit",
        "ev.new-faces",
        "pf.sunday-milestone",
        "pf.shooter-anniversary",
        "pf.attendance-year",
        "pf.attendance-streak",
        "pf.months-in-row",
        "pf.targets-milestone",
        "pf.next-trophy",
    }
)


def with_worse_shooter(fr: InsightFrames) -> InsightFrames:
    """A member below the field, below their own history and falling on every dimension, on
    every 4th held Sunday of the last two years."""
    held = [s for s in fr.sundays if s.date > fr.sundays[-1].date - timedelta(days=2 * 365)]
    template = fr.rounds.iloc[0]
    rows = []
    for k, sunday in enumerate(held[::4]):
        median = sunday.median or 30.0
        score = min(round(median) - 6, 31) - k  # below the field and lower every time
        row = template.copy()
        row["round_id"] = 10_000_000 + k
        row["event_date"] = sunday.date
        row["shooter_id"] = WORSE
        row["name_key"] = "worse pat"
        row["display_name"] = "Worse, Pat"
        row["ordinal"] = 1
        row["score"] = score
        row["status"] = "member"
        row["shooter_status"] = "member"
        row["field_median"] = median
        row["adjusted"] = score - median
        row["event_rank"] = sunday.n + 1
        row["is_best_round"] = True
        row["percentile"] = 0.0
        row["expected"] = score + 4.0
        row["residual"] = -4.0
        row["held"] = True
        rows.append(row)
    rounds = pd.concat([fr.rounds, pd.DataFrame(rows)], ignore_index=True)
    shooter = {
        "shooter_id": WORSE,
        "display_name": "Worse, Pat",
        "status": "member",
        "first_event": held[0].date,
        "last_event": held[-1].date,
        "n_rounds": len(rows),
        "n_events": len(rows),
        "left_censored": False,
    }
    shooters = pd.concat([fr.shooters, pd.DataFrame([shooter])], ignore_index=True)
    ratings = pd.DataFrame(
        [
            {"shooter_id": WORSE, "event_date": r["event_date"], "mu": 30.0 - k * 0.1, "var": 4.0}
            for k, r in enumerate(rows)
        ]
    )
    return InsightFrames.from_frames(
        rounds=rounds,
        events=fr.events,
        shooters=shooters,
        rating=pd.concat([fr.rating, ratings], ignore_index=True),
        stations=fr.stations,
        awards=fr.awards,
    )


def test_a_shooter_worse_at_everything_is_named_only_by_effort_kinds(fx_session):
    fr = with_worse_shooter(build_frames(fx_session))
    pairs = apply_rollups(evaluate_all(fr))
    naming = [p for p in pairs if WORSE in p.fact.named_shooter_ids]
    assert naming  # they are still seen: digest line, milestones
    assert {p.kind.id for p in naming} <= ALLOWLIST
    for p in naming:
        if p.fact.variant == ROLLUP:
            continue
        if p.kind.id == "pf.digest-line":
            assert p.fact.variant == "plain"  # no finish, no gap to their usual
        if p.kind.id == "pf.back-strong":
            assert "score" not in p.fact.params


def test_every_rendered_headline_and_how_passes_the_lints(fx_session):
    fr = build_frames(fx_session)
    problems: list[str] = []
    kinds = {k.id: k for k in all_kinds()}
    for pair in apply_rollups(evaluate_all(fr)):
        kind = kinds[pair.kind.id]
        named = kind.polarity in (Polarity.POSITIVE, Polarity.NEUTRAL)
        for template in kind.templates[pair.fact.variant]:
            for you in (False, True) if template.you is not None else (False,):
                segments = render(template, pair.fact.params, fr.names, you=you)
                problems += [f"{kind.id}: {p}" for p in lint_segments(segments, named=named)]
    for kind in kinds.values():
        for label in kind.labels:
            texts = [
                part for clause in label.third for part in clause.parts if isinstance(part, str)
            ]
            problems += [f"{kind.id} label: {p}" for t in texts for p in lint_text(t, named=True)]
    assert sorted(set(problems)) == []


def test_the_database_refuses_a_named_field_negative_row(fx_session):
    """D1's last line of defence (spec §3.1, §5 Guardrails): the CHECK constraint."""
    key = fx_session.scalar(text("SELECT key FROM insights ORDER BY key LIMIT 1"))
    named_negative = text(
        "UPDATE insights SET polarity = 'field_negative', named_shooter_ids = '{1}' WHERE key = :k"
    )
    with (
        pytest.raises(IntegrityError, match="ck_insights_field_negative_unnamed"),
        fx_session.begin_nested(),
    ):
        fx_session.execute(named_negative, {"k": key})
