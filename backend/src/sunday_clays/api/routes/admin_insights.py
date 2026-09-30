"""GET /api/admin/insights/kinds (Plan 12, spec §3.7): per-kind counts for tuning guards."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights.store import insights_table, readiness_from_db
from sunday_clays.db import SessionDep

router = APIRouter(tags=["admin"])


class InsightKindStatusOut(BaseModel):
    kind: str
    family: str
    subject: str
    pages: list[str]
    count: int
    subjects: int
    anchors: int
    dormant: bool
    reason: str | None


@router.get("/api/admin/insights/kinds")
def insight_kinds(session: SessionDep) -> list[InsightKindStatusOut]:
    t = insights_table()
    readiness = readiness_from_db(session)
    counts = {
        str(kind): (int(n), int(subjects), int(anchors))
        for kind, n, subjects, anchors in session.execute(
            select(
                t.c.kind,
                func.count(),
                func.count(func.distinct(t.c.subject_id)),
                func.count(func.distinct(t.c.anchor_date)),
            ).group_by(t.c.kind)
        )
    }
    out: list[InsightKindStatusOut] = []
    for kind in registry.all_kinds():
        n, subjects, anchors = counts.get(kind.id, (0, 0, 0))
        reason = kind.requires.unmet(readiness)
        out.append(
            InsightKindStatusOut(
                kind=kind.id,
                family=kind.family.value,
                subject=kind.subject.value,
                pages=sorted(p.value for p in kind.pages),
                count=n,
                subjects=subjects,
                anchors=anchors,
                dormant=reason is not None,
                reason=reason,
            )
        )
    return out
