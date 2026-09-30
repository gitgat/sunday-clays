"""Templates render to segments, never HTML (spec §3.5)."""

from datetime import date

import pytest

from sunday_clays.analytics.insights.templates import (
    MINUS,
    Count,
    Dec1,
    FullDate,
    Int,
    MonthYear,
    NameList,
    Ordinal,
    Pct,
    Shooter,
    ShortDate,
    Signed,
    SundayDate,
    T,
    TemplateError,
    Word,
    Year,
    field_,
    fmt_ordinal,
    fmt_signed,
    named,
    natural_name,
    plain,
    render,
)

NAMES = {1: "Pat Kay", 2: "Sam Roe", 3: "Alex Tee"}


def test_natural_name_swaps_last_first_and_keeps_other_names():
    assert natural_name("Hadley, Ike") == "Ike Hadley"
    assert natural_name("Cher") == "Cher"
    assert natural_name("Odd, ") == "Odd,"


@pytest.mark.parametrize(
    ("value", "digits", "text"),
    [(2.14, 1, "+2.1"), (-2.14, 1, f"{MINUS}2.1"), (0.04, 1, "0.0"), (9.0, 0, "+9")],
)
def test_signed_uses_a_true_minus_and_no_sign_on_zero(value, digits, text):
    assert fmt_signed(value, digits) == text


@pytest.mark.parametrize(
    ("n", "text"),
    [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"), (22, "22nd"), (113, "113th")],
)
def test_ordinals(n, text):
    assert fmt_ordinal(n) == text


def test_every_slot_type_renders_its_param():
    t = T(
        named(
            Shooter("s"),
            " ",
            Int("n"),
            " ",
            Dec1("x"),
            " ",
            Signed("g"),
            " ",
            Pct("p"),
            " ",
            Ordinal("r"),
            " ",
            Count("k", "Sunday"),
            " ",
            Year("y"),
            " ",
            ShortDate("d"),
            " ",
            FullDate("d"),
            " ",
            MonthYear("d"),
            " ",
            SundayDate("d"),
            " ",
            Word("w", (("wet", "in the rain"),)),
        )
    )
    params = {
        "s": 1,
        "n": 1234,
        "x": 3.46,
        "g": -1.25,
        "p": 61.4,
        "r": 4,
        "k": 1,
        "y": 2026,
        "d": date(2026, 9, 27),
        "w": "wet",
    }
    assert plain(render(t, params, NAMES)) == (
        f"Pat Kay 1,234 3.5 {MINUS}1.2 61% 4th 1 Sunday 2026 Sep 27 Sep 27, 2026 Sep 2026 "
        "Sunday 9/27 in the rain"
    )


def test_names_are_shooter_segments_with_ids_and_lists_join_with_and():
    segs = render(T(named("Kudos: ", NameList("ids"), ".")), {"ids": [1, 2, 3]}, NAMES)
    assert [s for s in segs if s["t"] == "shooter"] == [
        {"t": "shooter", "id": 1, "v": "Pat Kay"},
        {"t": "shooter", "id": 2, "v": "Sam Roe"},
        {"t": "shooter", "id": 3, "v": "Alex Tee"},
    ]
    assert plain(segs) == "Kudos: Pat Kay, Sam Roe and Alex Tee."


def test_adjacent_text_merges_and_clauses_join_with_a_space():
    segs = render(
        T(field_("Rain Sunday."), named("Well done ", Shooter("s"), ".")), {"s": 2}, NAMES
    )
    assert segs[0] == {"t": "text", "v": "Rain Sunday. Well done "}


def test_you_form_is_used_only_when_asked_and_present():
    t = T(named(Shooter("s"), " shot ", Int("n"), "."), you=named("You shot ", Int("n"), "."))
    assert plain(render(t, {"s": 1, "n": 40}, NAMES)) == "Pat Kay shot 40."
    assert plain(render(t, {"s": 1, "n": 40}, NAMES, you=True)) == "You shot 40."


def test_a_missing_or_wrong_param_raises_template_error():
    with pytest.raises(TemplateError, match="missing param 'n'"):
        render(T(named(Int("n"))), {}, NAMES)
    with pytest.raises(TemplateError, match="must be a number"):
        render(T(named(Int("n"))), {"n": "x"}, NAMES)
    with pytest.raises(TemplateError, match="not a known choice"):
        render(T(named(Word("w", (("a", "b"),)))), {"w": "z"}, NAMES)
