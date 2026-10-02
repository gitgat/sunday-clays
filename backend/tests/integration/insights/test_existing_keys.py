"""existing_keys (Plan 15 Task 1): which asked keys are stored insights now, in one query."""

from sqlalchemy import event
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.store import existing_keys, load_rows

GONE = "fedcba9876543210fedc"  # insight-shaped, in no insights row


def test_keeps_only_stored_insights_in_one_query(fx_session: Session) -> None:
    rows = load_rows(fx_session)
    assert len(rows) >= 2, "the fx world has insights"
    stored = {rows[0].key, rows[1].key}
    statements: list[str] = []

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        statements.append(statement)

    connection = fx_session.connection()
    event.listen(connection, "before_cursor_execute", record)
    try:
        found = existing_keys(fx_session, [*stored, GONE, rows[0].key])
    finally:
        event.remove(connection, "before_cursor_execute", record)
    assert found == stored
    assert len(statements) == 1


def test_no_keys_asks_nothing(fx_session: Session) -> None:
    assert existing_keys(fx_session, []) == set()
