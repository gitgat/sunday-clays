"""GET /api/features (Plan 19 D3): the switches the SPA needs to show or hide a feature."""

from typing import Annotated

from fastapi import APIRouter, Depends

from sunday_clays.auth.deps import require_viewer
from sunday_clays.auth.sessions import Role
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import FeaturesOut, read_switches

router = APIRouter()


@router.get("/api/features")
def get_features(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    role: Annotated[Role, Depends(require_viewer)],
) -> FeaturesOut:
    """A viewer gets only the keys that are on (missing means off); an admin gets every key."""
    switches = read_switches(session, settings)
    if role != "admin":
        switches = {key: True for key, on in switches.items() if on}
    return FeaturesOut(switches=switches)
