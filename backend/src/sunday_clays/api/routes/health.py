"""``GET /api/health`` (public; C8)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sunday_clays.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthOut:
    return HealthOut(status="ok", version=settings.app_version)
