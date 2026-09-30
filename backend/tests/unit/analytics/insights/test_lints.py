"""Language lints (spec §4.1 b, §4.2)."""

import pytest

from sunday_clays.analytics.insights.lints import (
    d9_problems,
    lint_clauses,
    lint_segments,
    lint_text,
)
from sunday_clays.analytics.insights.templates import Int, NameList, Shooter, field_, named


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("an upset on Sunday", "person-vs-person"),
        ("the giant-killer of the day", "person-vs-person"),
        ("head to head record", "person-vs-person"),
        ("her best round", "pronoun"),
        ("He shot 40", "pronoun"),
        ("top of the class", "class"),
        ("the best event", "event"),
        ("the median score", "jargon"),
        ("vs expected", "jargon"),
    ],
)
def test_banned_words_fail_everywhere(text, code):
    assert any(p.startswith(code) for p in lint_text(text, named=False))


@pytest.mark.parametrize(
    "text", ["the worst day", "a slump", "fell off", "below the field", "struggling"]
)
def test_negative_words_fail_only_in_named_text(text):
    assert lint_text(text, named=True)
    assert lint_text(text, named=False) == []


def test_clean_text_passes():
    assert lint_text("Scores up 3 Sundays straight: their best run of the year.", named=True) == []


def test_d9_allows_only_list_joiners_between_names():
    assert d9_problems(named(Shooter("a"), " and ", Shooter("b"), " both shot 49.")) == []
    assert d9_problems(named(Shooter("a"), ", ", Shooter("b"), " and ", Shooter("c"), ".")) == []
    assert d9_problems(named(Shooter("a"), " beat ", Shooter("b"), "."))
    assert d9_problems(named(Shooter("a"), " finished ahead of ", NameList("b"), "."))


def test_a_field_clause_may_not_name_anyone():
    assert d9_problems(field_("6 fewer shooters turned out.")) == []
    assert d9_problems(field_("Tough day for ", Shooter("a"), ".")) == [
        "field clause names a shooter"
    ]


def test_rendered_names_never_trip_the_pronoun_lint():
    segments = [{"t": "text", "v": "Well played, "}, {"t": "shooter", "id": 1, "v": "Her Hish"}]
    assert lint_segments(segments) == []


def test_a_banned_phrase_split_across_literal_parts_is_caught():
    problems = lint_clauses([named("They came ", Int("n"), " in last ", "place.")])
    assert any("place" in p for p in problems)
