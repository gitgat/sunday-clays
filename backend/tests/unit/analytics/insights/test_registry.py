"""Import-time registry validation (spec §3.3, §4.1, §4.2)."""

import pytest

from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights.registry import KindError, register, validate
from sunday_clays.analytics.insights.templates import Int, NameList, Shooter, T, field_, named
from sunday_clays.analytics.insights.types import (
    P,
    Polarity,
    SubjectType,
)

LABEL = T(named("A chart"))
NO_YOU = T(named(Shooter("s"), " shot ", Int("n"), "."))
PRONOUN = T(named("She shot ", Int("n"), "."), you=named("You shot ", Int("n")))
YOU_IN_THIRD = T(named("You shot ", Int("n"), "."), you=named("You shot ", Int("n")))
YOU_WITHOUT_YOU = T(named(Shooter("s"), " shot ", Int("n"), "."), you=named("Shot ", Int("n")))
YOU_LABEL = T(named(Shooter("s"), "'s scores"), you=named("Your scores"))


def test_a_well_formed_kind_is_valid(good):
    assert validate(good()) == []


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"id": "Bad Id"}, "bad id"),
        ({"care": 6}, "care must be 1-5"),
        ({"pages": frozenset({P.HOME}), "home_slot": None}, "needs a home_slot"),
        ({"polarity": Polarity.MIXED}, "positive or neutral"),
        ({"proof": ()}, "no proof check for ['n']"),
        ({"params": frozenset({"s"})}, "slot 'n' is not a declared param"),
        ({"how": {}}, "has no 'how' bullet"),
        ({"labels": ()}, "no chart label"),
        (
            {"templates": {"": (T(named(Shooter("s"), " shot ", Int("n"), ".")),)}},
            "needs a 'you' form",
        ),
        (
            {
                "templates": {
                    "": (T(named("She shot ", Int("n"), "."), you=named("You shot ", Int("n"))),)
                }
            },
            "pronoun",
        ),
        (
            {
                "templates": {
                    "": (T(named("You shot ", Int("n"), "."), you=named("You shot ", Int("n"))),)
                }
            },
            "third-person form says 'you'",
        ),
        (
            {
                "templates": {
                    "": (
                        T(
                            named(Shooter("s"), " shot ", Int("n"), "."),
                            you=named("Shot ", Int("n")),
                        ),
                    )
                }
            },
            "never says you/your",
        ),
        ({"pages": frozenset({P.PROFILE, P.SUNDAY}), "anchored": True}, "needs a 'rollup'"),
        ({"labels": (T(named(Shooter("s"), "'s scores")),)}, "needs a 'you' form"),
    ],
)
def test_broken_kinds_are_rejected(good, changes, problem):
    assert any(problem in p for p in validate(good(**changes)))


def test_a_person_vs_person_template_fails_registry_load(good):
    beat = T(named(Shooter("s"), " beat ", NameList("others"), "."), you=named("You won."))
    kind = good(templates={"": (beat,)}, params=frozenset({"s", "n", "others"}))
    with pytest.raises(KindError, match="only a list is allowed"):
        register(kind)


def test_a_field_negative_kind_may_not_name_a_shooter(good):
    kind = good(
        id="ev.test-kind",
        subject=SubjectType.SUNDAY,
        polarity=Polarity.FIELD_NEGATIVE,
        templates={"": (T(named("Tough day for ", Shooter("s"), ".")),)},
        how={"": (T(named("Counted.")),)},
        labels=(LABEL,),
    )
    assert any("field_negative kind names no shooter" in p for p in validate(kind))


def test_a_field_clause_holding_a_name_is_rejected(good):
    kind = good(
        id="ev.test-kind",
        subject=SubjectType.SUNDAY,
        polarity=Polarity.MIXED,
        templates={"": (T(field_("A slow day for ", Shooter("s"), "."), named("Well done.")),)},
        how={"": (T(named("Counted.")),)},
        labels=(LABEL,),
    )
    assert "field clause names a shooter" in validate(kind)


def test_duplicate_ids_are_rejected(good, monkeypatch):
    monkeypatch.setattr(registry, "_REGISTRY", {})
    register(good())
    with pytest.raises(KindError, match="duplicate"):
        register(good())


def test_every_real_kind_loads_and_passes_validation():
    kinds = registry.all_kinds()
    assert kinds
    assert all(validate(k) == [] for k in kinds)
    assert [k.id for k in kinds] == sorted(k.id for k in kinds)
