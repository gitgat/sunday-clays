"""Chart links on the fx world (spec §5): valid specs, known anchors, and proven numbers."""

from collections import defaultdict

from sunday_clays.analytics.insights.anchors import ANCHORS
from sunday_clays.analytics.insights.engine import Pair, apply_rollups, evaluate_all
from sunday_clays.analytics.insights.proof import proof_problems
from sunday_clays.analytics.steps.s60_insights import build_frames
from sunday_clays.explorer import engine as explorer_engine

SAMPLE = 20  # facts per (kind, variant): the latest ones


def _sample(pairs: list[Pair]) -> list[Pair]:
    groups: dict[tuple[str, str], list[Pair]] = defaultdict(list)
    for p in pairs:
        groups[(p.kind.id, p.fact.variant)].append(p)
    out: list[Pair] = []
    for group in groups.values():
        group.sort(key=lambda p: (p.fact.anchor_date is not None, p.fact.anchor_date or 0))
        out.extend(group[-SAMPLE:])
    return out


def test_every_chart_link_is_valid_and_proves_its_numbers(fx_session):
    fr = build_frames(fx_session)
    ex = explorer_engine.load_explorer_frames(fx_session)
    problems: list[str] = []
    for pair in _sample(apply_rollups(evaluate_all(fr))):
        kind, fact = pair.kind, pair.fact
        where = f"{kind.id}/{fact.variant} {fact.subject_id} {fact.anchor_date}"
        link = kind.chart(fact)
        if not any(link.label is label for label in kind.labels):
            problems.append(f"{where}: label is not one of the kind's labels")
        if link.window.start > link.window.end:
            problems.append(f"{where}: empty window")
        if link.type == "explorer":
            assert link.spec is not None
            explorer_engine.run_query(ex, link.spec)
        elif link.anchor not in ANCHORS:
            problems.append(f"{where}: unknown anchor {link.anchor}")
        problems.extend(f"{where}: {p}" for p in proof_problems(kind, fact, fr, ex))
    assert problems == [], "\n".join(problems)
