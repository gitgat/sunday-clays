"""build_issue under a rebuild race: the Sunday stopped being held between two reads."""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from sunday_clays.api.routes import sheet as sheet_routes
from sunday_clays.domain.errors import NotFoundError


@pytest.mark.parametrize("held", [[], [date(2026, 9, 20)]])
def test_a_day_that_is_no_longer_held_is_not_found_not_a_500(
    monkeypatch: pytest.MonkeyPatch, held: list[date]
) -> None:
    monkeypatch.setattr(sheet_routes, "held_dates", lambda _s: held)
    # The data it would load once past the check: nothing, so only the assembler can fail.
    monkeypatch.setattr(sheet_routes, "_issue_rows", lambda *_a: [])
    monkeypatch.setattr(sheet_routes, "load_picks", lambda *_a: [])
    monkeypatch.setattr(sheet_routes, "picked", lambda *_a: (None, None))
    monkeypatch.setattr(sheet_routes, "trophy_catalog", lambda: {})
    monkeypatch.setattr(sheet_routes.yir, "load_yir_frames", lambda _s: None)
    monkeypatch.setattr(sheet_routes.yir, "on_this_day", lambda *_a: [])
    session = MagicMock()
    session.execute.return_value = []
    # The memo wrapper reads the data version from the database; the race is in the body.
    body: Any = sheet_routes.build_issue.__wrapped__  # type: ignore[attr-defined]
    with pytest.raises(NotFoundError) as caught:
        body(cast(Session, session), date(2026, 9, 27))
    assert caught.value.code == "sheet_not_found"
