"""Helpers shared by the admin_* route modules (leading underscore: skipped by discovery)."""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.domain.errors import NotFoundError
from sunday_clays.models import Base


class JobRefOut(BaseModel):
    job_id: int


class RuleMutationOut(BaseModel):
    rule_id: int
    job_id: int


def ensure_exists(session: Session, table: str, row_id: int, code: str, noun: str) -> None:
    """Raise NotFoundError(code) → 404 unless ``table`` has a row with ``id == row_id``."""
    t = Base.metadata.tables[table]
    if session.scalar(select(t.c.id).where(t.c.id == row_id)) is None:
        raise NotFoundError(code, f"{noun} {row_id} does not exist")
