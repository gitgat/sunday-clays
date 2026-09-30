"""Shooter identity: alias lookup and creation, alias_name rules and merge resolution (C5)."""

from collections.abc import Callable
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.domain.errors import DomainError
from sunday_clays.ingest import names
from sunday_clays.models import Rule, Shooter, ShooterAlias


def resolve_shooter(session: Session, raw_name: str, event_date: date) -> int:
    """Shooter id for a score row's name; creates the shooter and its alias on first sight."""
    key = names.identity_key(names.name_key(raw_name), event_date)
    existing = session.scalar(select(ShooterAlias.shooter_id).where(ShooterAlias.name_key == key))
    if existing is not None:
        return existing
    shooter = Shooter(display_name=names.clean_display_name(raw_name))
    session.add(shooter)
    session.flush()
    session.add(ShooterAlias(name_key=key, shooter_id=shooter.id))
    session.flush()
    return shooter.id


def lookup_shooter(session: Session, name_key: str) -> int | None:
    """Canonical shooter id for an identity key, or None; never creates a shooter."""
    alias_rules: list[dict[str, Any]] = list(
        session.scalars(
            select(Rule.payload)
            .where(Rule.rule_type == "alias_name", Rule.active.is_(True))
            .order_by(Rule.id.desc())
        )
    )
    shooter_id: int | None = next(
        (int(p["shooter_id"]) for p in alias_rules if p.get("name_key") == name_key), None
    )
    if shooter_id is None:
        shooter_id = session.scalar(
            select(ShooterAlias.shooter_id).where(ShooterAlias.name_key == name_key)
        )
    if shooter_id is None:
        return None
    return merge_map(session).get(shooter_id, shooter_id)


def identity_resolver(session: Session) -> Callable[[str], int | None]:
    """``lookup_shooter`` for many keys: three queries up front, then every lookup is in memory.

    Same precedence: the newest active alias_name rule for the key, else shooter_aliases, then
    merge_map. merge_map runs here, so a merge cycle raises now rather than at the first lookup
    that finds a shooter (create_rule never stores a cycle).
    """
    payloads: list[dict[str, Any]] = list(
        session.scalars(
            select(Rule.payload)
            .where(Rule.rule_type == "alias_name", Rule.active.is_(True))
            .order_by(Rule.id)
        )
    )
    # ascending ids, so the newest rule per key is the one left in the dict
    rules: dict[object, dict[str, Any]] = {p.get("name_key"): p for p in payloads}
    aliases: dict[str, int] = dict(
        session.execute(select(ShooterAlias.name_key, ShooterAlias.shooter_id)).all()
    )
    merges = merge_map(session)

    def resolve(name_key: str) -> int | None:
        rule = rules.get(name_key)
        shooter_id = int(rule["shooter_id"]) if rule is not None else aliases.get(name_key)
        if shooter_id is None:
            return None
        return merges.get(shooter_id, shooter_id)

    return resolve


def merge_map(session: Session) -> dict[int, int]:
    """source shooter id -> final target id from active merge_shooter rules (newest per source)."""
    direct: dict[int, int] = {}
    payloads: list[dict[str, Any]] = list(
        session.scalars(
            select(Rule.payload)
            .where(Rule.rule_type == "merge_shooter", Rule.active.is_(True))
            .order_by(Rule.id)
        )
    )
    for payload in payloads:
        direct[int(payload["source_shooter_id"])] = int(payload["target_shooter_id"])
    resolved: dict[int, int] = {}
    for source, target in direct.items():
        seen = {source}
        while target in direct:
            if target in seen:
                raise DomainError(
                    "merge_cycle", f"Merge rules form a cycle through shooter {target}"
                )
            seen.add(target)
            target = direct[target]
        resolved[source] = target
    return resolved
