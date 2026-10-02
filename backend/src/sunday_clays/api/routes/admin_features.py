"""Admin launch switches (Plan 19 §3.0): list and flip, audited."""

from typing import Annotated

from fastapi import APIRouter, Depends

from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import (
    FeatureSwitchIn,
    FeatureSwitchOut,
    list_switches,
    set_switch,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

ActorDep = Annotated[Actor, Depends(admin_actor)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/features")
def get_feature_switches(session: SessionDep, settings: SettingsDep) -> list[FeatureSwitchOut]:
    return list_switches(session, settings)


@router.put("/features/{key}")
def put_feature_switch(
    key: str, body: FeatureSwitchIn, session: SessionDep, settings: SettingsDep, actor: ActorDep
) -> FeatureSwitchOut:
    out = set_switch(session, settings, key, body.enabled)
    record_audit(
        session, actor.ip, actor.role, "feature_switch", {"key": out.key, "enabled": out.enabled}
    )
    return out
