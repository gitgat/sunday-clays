from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.identity import lookup_shooter, merge_map, resolve_shooter
from sunday_clays.models import Rule, Shooter, ShooterAlias

D1 = date(2026, 9, 6)
D2 = date(2026, 9, 13)


def _count(session: Session, model: type[Shooter] | type[ShooterAlias]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _merge(session: Session, source: int, target: int, *, active: bool = True) -> None:
    session.add(
        Rule(
            rule_type="merge_shooter",
            payload={"source_shooter_id": source, "target_shooter_id": target},
            active=active,
        )
    )
    session.flush()


def test_resolve_creates_one_shooter_per_identity_key(session: Session) -> None:
    first = resolve_shooter(session, "Linwood, Luther", D1)
    again = resolve_shooter(
        session, "Linwood Luther" + chr(0xA0), D2
    )  # missing comma, trailing NBSP
    assert again == first
    assert _count(session, Shooter) == 1
    assert session.get(Shooter, first).display_name == "Linwood, Luther"  # type: ignore[union-attr]
    assert session.scalars(select(ShooterAlias.name_key)).all() == ["linwood luther"]


def test_first_name_only_names_are_event_scoped(session: Session) -> None:
    jim_d1 = resolve_shooter(session, "Desmond", D1)
    jim_d2 = resolve_shooter(session, "Desmond", D2)
    assert jim_d1 != jim_d2
    assert resolve_shooter(session, "Desmond ", D1) == jim_d1
    assert sorted(session.scalars(select(ShooterAlias.name_key))) == [
        "desmond@2026-09-06",
        "desmond@2026-09-13",
    ]


def test_lookup_never_creates_a_shooter(session: Session) -> None:
    assert lookup_shooter(session, "nobody here") is None
    assert _count(session, Shooter) == 0
    assert _count(session, ShooterAlias) == 0


def test_lookup_finds_existing_alias(session: Session) -> None:
    hadley = resolve_shooter(session, "Hadley, Ike", D2)
    assert lookup_shooter(session, "hadley ike") == hadley


def test_lookup_prefers_active_alias_name_rule(session: Session) -> None:
    hadley = resolve_shooter(session, "Hadley, Ike", D2)
    session.add(
        Rule(rule_type="alias_name", payload={"name_key": "hadley ik", "shooter_id": hadley})
    )
    session.add(
        Rule(
            rule_type="alias_name",
            payload={"name_key": "hadley ikke", "shooter_id": hadley},
            active=False,
        )
    )
    session.flush()
    assert lookup_shooter(session, "hadley ik") == hadley
    assert lookup_shooter(session, "hadley ikke") is None  # inactive rules are ignored


def test_alias_name_rule_beats_existing_alias(session: Session) -> None:
    ike = resolve_shooter(session, "Hadley, Ike", D2)
    clint = resolve_shooter(session, "Hadley, Clint", D2)
    session.add(
        Rule(rule_type="alias_name", payload={"name_key": "hadley ike", "shooter_id": clint})
    )
    session.flush()
    assert lookup_shooter(session, "hadley ike") == clint != ike


def test_newest_alias_name_rule_wins(session: Session) -> None:
    older = resolve_shooter(session, "Hadley, Ike", D2)
    newer = resolve_shooter(session, "Hadley, Clint", D2)
    for target in (older, newer):
        session.add(
            Rule(rule_type="alias_name", payload={"name_key": "hadley ik", "shooter_id": target})
        )
        session.flush()
    assert lookup_shooter(session, "hadley ik") == newer


def test_merge_map_resolves_chains(session: Session) -> None:
    a, b, c = (
        resolve_shooter(session, n, D1) for n in ("Preutt, Luther", "Pruett, T", "Pruett, Luther")
    )
    _merge(session, a, b)
    _merge(session, b, c)
    assert merge_map(session) == {a: c, b: c}
    assert lookup_shooter(session, "preutt luther") == c


def test_merge_map_ignores_inactive_rules_and_newest_rule_wins(session: Session) -> None:
    a, b, c = (
        resolve_shooter(session, n, D1)
        for n in ("Hamond, Warren", "Hammond, Warren", "Hammond, Irwin")
    )
    _merge(session, a, c, active=False)
    _merge(session, a, b)
    assert merge_map(session) == {a: b}
    _merge(session, a, c)
    assert merge_map(session) == {a: c}


def test_merge_cycle_is_a_domain_error(session: Session) -> None:
    a = resolve_shooter(session, "Roland, Sam", D1)
    b = resolve_shooter(session, "Rolland, Sam", D1)
    _merge(session, a, b)
    _merge(session, b, a)
    with pytest.raises(DomainError) as excinfo:
        merge_map(session)
    assert excinfo.value.code == "merge_cycle"
