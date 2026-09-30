from datetime import date

import pytest
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.api.routes._admin import ensure_exists
from sunday_clays.auth.deps import record_audit
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.models import Base

AUDIT = Base.metadata.tables["audit_log"]
SHOOTERS = Base.metadata.tables["shooters"]


def test_record_audit_appends_json_encoded_row(session: Session) -> None:
    record_audit(
        session, "203.0.113.7", "admin", "rules.create", {"event_date": date(2026, 9, 13), "n": 2}
    )
    row = session.execute(select(AUDIT.c.ip, AUDIT.c.role, AUDIT.c.action, AUDIT.c.details)).one()
    assert tuple(row) == (
        "203.0.113.7",
        "admin",
        "rules.create",
        {"event_date": "2026-09-13", "n": 2},
    )


def test_ensure_exists_passes_for_existing_row(session: Session) -> None:
    shooter_id = session.execute(
        insert(SHOOTERS).values(display_name="Hadley, Ike").returning(SHOOTERS.c.id)
    ).scalar_one()
    ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")


def test_ensure_exists_raises_not_found_with_code(session: Session) -> None:
    with pytest.raises(NotFoundError) as exc:
        ensure_exists(session, "shooters", 987_654, "shooter_not_found", "Shooter")
    assert exc.value.code == "shooter_not_found"
    assert exc.value.status_code == 404
