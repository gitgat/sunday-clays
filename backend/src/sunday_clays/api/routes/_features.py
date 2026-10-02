"""``feature_gate(key)`` (Plan 19 D2): skipped by discovery (leading underscore)."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException

from sunday_clays.auth.deps import require_viewer
from sunday_clays.auth.sessions import Role
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import FeatureKey, switch_on


def feature_gate(key: FeatureKey) -> Any:
    """A route dependency: 404 (the unknown-route body) for a viewer while ``key`` is off.

    It depends on ``require_viewer``, so a request without a session gets 401 first. An admin
    always passes (admin preview). The returned callable carries ``feature_gate_key`` so the
    page-cache pin tests (Plan 19 T11) can see that a route is gated.
    """

    def gate(
        role: Annotated[Role, Depends(require_viewer)],
        session: SessionDep,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> None:
        if role != "admin" and not switch_on(session, settings, key):
            raise HTTPException(status_code=404)

    gate.feature_gate_key = key  # type: ignore[attr-defined]
    return Depends(gate)
