from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date

from sqlalchemy.orm import Session

from sunday_clays.domain.identity import identity_resolver, lookup_shooter, resolve_shooter
from sunday_clays.models import Rule

D1 = date(2026, 9, 6)
D2 = date(2026, 9, 13)
CountQueries = Callable[[Session], AbstractContextManager[list[str]]]


def _rule(
    session: Session, rule_type: str, payload: dict[str, object], active: bool = True
) -> None:
    session.add(Rule(rule_type=rule_type, payload=payload, active=active))
    session.flush()


def _seed_precedence_cases(session: Session) -> dict[str, int | None]:
    """The lookup_shooter precedence cases; returns identity key -> expected canonical id."""
    ike = resolve_shooter(session, "Hadley, Ike", D2)
    clint = resolve_shooter(session, "Hadley, Clint", D2)
    a, b, c = (
        resolve_shooter(session, n, D1) for n in ("Preutt, Luther", "Pruett, T", "Pruett, Luther")
    )
    _rule(session, "alias_name", {"name_key": "hadley ike", "shooter_id": clint})  # beats alias
    _rule(session, "alias_name", {"name_key": "hadley ik", "shooter_id": ike})
    _rule(session, "alias_name", {"name_key": "hadley ik", "shooter_id": clint})  # newest wins
    _rule(session, "alias_name", {"name_key": "hadley ikke", "shooter_id": ike}, active=False)
    _rule(session, "alias_name", {"name_key": "pruett jonas", "shooter_id": a})  # target is merged
    _rule(session, "merge_shooter", {"source_shooter_id": a, "target_shooter_id": b})
    _rule(session, "merge_shooter", {"source_shooter_id": b, "target_shooter_id": c})
    return {
        "hadley ike": clint,
        "hadley clint": clint,
        "hadley ik": clint,
        "hadley ikke": None,  # only an inactive rule
        "preutt luther": c,
        "pruett t": c,
        "pruett luther": c,
        "pruett jonas": c,
        "nobody here": None,
    }


def test_resolver_agrees_with_lookup_shooter(session: Session) -> None:
    expected = _seed_precedence_cases(session)
    resolve = identity_resolver(session)
    assert {key: resolve(key) for key in expected} == expected
    assert {key: lookup_shooter(session, key) for key in expected} == expected


def test_resolver_loads_once_and_resolves_in_memory(
    session: Session, count_queries: CountQueries
) -> None:
    expected = _seed_precedence_cases(session)
    with count_queries(session) as loading:
        resolve = identity_resolver(session)
    with count_queries(session) as resolving:
        for key in expected:
            resolve(key)
    assert len(loading) == 3  # alias_name rules, shooter_aliases, merge_shooter rules
    assert resolving == []
