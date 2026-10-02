"""Launch switches (Plan 19 §3.0): one ``app_state`` row per key, ``feature.<key>``.

The value is ``{"enabled": bool, "updated_at": "<ISO timestamp>"}``. ``updated_at`` comes from
the database (``now()`` inside the upsert), never the app clock. A missing row means off, unless
the key is listed in ``settings.features_default_on`` (D4). A corrupt value reads as off and logs
one warning per read that names the key only, never the stored value.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, Literal, get_args
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.domain.errors import NotFoundError

logger = logging.getLogger(__name__)

FeatureKey = Literal[
    "link_previews",
    "tour_glossary",
    "weekly_recap",
    "pwa",
    "club_milestones",
    "summary_card",
]
KEY_PREFIX: Final = "feature."


@dataclass(frozen=True)
class Feature:
    key: FeatureKey
    label: str
    description: str


FEATURES: Final[tuple[Feature, ...]] = (
    Feature(
        "link_previews",
        "Link previews",
        "Links shared in chat apps show the Sunday's date, how many shot and the round type. "
        "While off, every link shows the plain club preview.",
    ),
    Feature(
        "tour_glossary",
        "Welcome tour and glossary",
        'A 5-step tour on a first visit to Home, the Glossary page, and "Words used here" '
        "links in chart explainers.",
    ),
    Feature(
        "weekly_recap",
        "Weekly recap",
        "Admin tool: paste-ready text and an image of a Sunday for the club email.",
    ),
    Feature(
        "pwa",
        "Add to Home Screen",
        "Lets phones install the app, and shows a small install tip on Home.",
    ),
    Feature(
        "club_milestones",
        "Club milestones",
        "Club totals such as clays thrown and Sundays held, dated at the Sunday each round "
        "number was passed. Home card and Club page.",
    ),
    Feature(
        "summary_card",
        "Summary card",
        "A shareable card on every profile for the chosen time window.",
    ),
)
_BY_KEY: Final[dict[str, Feature]] = {f.key: f for f in FEATURES}
if set(_BY_KEY) != set(get_args(FeatureKey)):  # pragma: no cover - import-time guard
    raise RuntimeError("FEATURES must list every FeatureKey once")


class FeatureSwitchOut(BaseModel):
    key: FeatureKey
    label: str
    description: str
    enabled: bool
    updated_at: datetime | None
    updated_on: date | None  # updated_at as a date in the club timezone (D26)


class FeatureSwitchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


class FeaturesOut(BaseModel):
    switches: dict[FeatureKey, bool]


def feature(key: str) -> Feature:
    """The registered feature for ``key``; 404 ``feature_not_found`` otherwise."""
    found = _BY_KEY.get(key)
    if found is None:
        raise NotFoundError("feature_not_found", f"No feature switch named {key!r}")
    return found


def _default_on(settings: Settings) -> frozenset[str]:
    return frozenset(k.strip() for k in settings.features_default_on.split(",") if k.strip())


def _stored(value: Any, key: str) -> tuple[bool, datetime | None] | None:
    """(enabled, updated_at) from a stored value; None (and a warning) when it is corrupt."""
    if isinstance(value, dict) and isinstance(value.get("enabled"), bool):
        raw = value.get("updated_at")
        try:
            updated = datetime.fromisoformat(raw) if isinstance(raw, str) else None
        except ValueError:
            updated = None
        return bool(value["enabled"]), updated
    logger.warning("feature switch %s has a corrupt value; reading it as off", key)
    return None


def _rows(session: Session) -> dict[str, Any]:
    result = session.execute(
        text("SELECT key, value FROM app_state WHERE key LIKE 'feature.%'")
    ).all()
    return {str(k).removeprefix(KEY_PREFIX): v for k, v in result}


def _state(rows: dict[str, Any], settings: Settings, f: Feature) -> tuple[bool, datetime | None]:
    if f.key not in rows:
        return f.key in _default_on(settings), None
    stored = _stored(rows[f.key], f.key)
    return (False, None) if stored is None else stored


def read_switches(session: Session, settings: Settings) -> dict[FeatureKey, bool]:
    """Every registered key with its effective value (one SELECT)."""
    rows = _rows(session)
    return {f.key: _state(rows, settings, f)[0] for f in FEATURES}


def switch_on(session: Session, settings: Settings, key: FeatureKey) -> bool:
    return read_switches(session, settings)[key]


def _out(f: Feature, enabled: bool, updated: datetime | None, tz: str) -> FeatureSwitchOut:
    return FeatureSwitchOut(
        key=f.key,
        label=f.label,
        description=f.description,
        enabled=enabled,
        updated_at=updated,
        updated_on=None if updated is None else updated.astimezone(ZoneInfo(tz)).date(),
    )


def list_switches(session: Session, settings: Settings) -> list[FeatureSwitchOut]:
    rows = _rows(session)
    return [_out(f, *_state(rows, settings, f), settings.timezone) for f in FEATURES]


_UPSERT = text(
    "INSERT INTO app_state (key, value) "
    "VALUES (:key, jsonb_build_object("
    "'enabled', CAST(:enabled AS boolean), 'updated_at', now())) "
    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value "
    "RETURNING value"
)


def set_switch(session: Session, settings: Settings, key: str, enabled: bool) -> FeatureSwitchOut:
    """Upsert one switch; ``updated_at`` is the database's ``now()`` (D1)."""
    f = feature(key)
    params = {"key": KEY_PREFIX + f.key, "enabled": enabled}
    value: dict[str, Any] = session.execute(_UPSERT, params).scalar_one()
    # the upsert just wrote this value, so it is well formed
    updated = datetime.fromisoformat(value["updated_at"])
    return _out(f, bool(value["enabled"]), updated, settings.timezone)
