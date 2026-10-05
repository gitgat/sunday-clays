"""The email's "This week" insights: what is eligible, how 3-5 are picked, the 12-week rotation."""

import itertools
import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights.store import InsightRow
from sunday_clays.analytics.insights.templates import (
    Slot,
    Word,
    plain,
    render,
    template_slots,
)
from sunday_clays.analytics.recap_insights import (
    ELIGIBLE,
    EXCLUDED,
    HORIZON,
    NO_REPEAT_WEEKS,
    recap_text_problems,
    week_picks,
)

# The R3 ban list, spelled out independently of the implementation's pattern.
BANNED = (
    "you",
    "your",
    "usual for a day like this",
    "rating",
    "skill",
    "model",
    "tier",
    "level",
    "chart",
    "tap",
    "see the",
    "bronze",
    "silver",
    "gold",
    "platinum",
    "diamond",
)
PRONOUNS = re.compile(r"\b(he|she|his|her|hers|him)\b|\bclass(es)?\b", re.IGNORECASE)


def banned_in(text: str) -> list[str]:
    return [w for w in BANNED if re.search(rf"\b{re.escape(w)}s?\b", text, re.IGNORECASE)]


def no_supersedes(_kind: str) -> frozenset[str]:
    return frozenset()


KINDS = sorted(ELIGIBLE)


def variant_of(kind: str) -> str:
    return sorted(ELIGIBLE[kind])[0] if kind in ELIGIBLE else ""


def row(kind: str, day: date, *, score: float = 1.0, sid: int = 1, **changes: Any) -> InsightRow:
    base = InsightRow(
        key=f"{kind}|{day}|{sid}",
        value_hash="h",
        generation=2,
        first_generation=1,
        kind=kind,
        family=kind,  # one family per kind unless a test says otherwise
        home_slot=None,
        subject_type="shooter",
        subject_id=str(sid),
        anchor_date=day,
        variant=variant_of(kind),
        pages=("sunday",),
        expires={},
        named_shooter_ids=(sid,),
        polarity="positive",
        kudos=False,
        template_id=f"{kind}::0",
        params={},
        strength=1.0,
        base_score=score,
        rank_score=score,
        headline=[
            {"t": "shooter", "id": sid, "v": f"Shooter, N{sid}"},
            {"t": "text", "v": f" did {kind}."},
        ],
        headline_you=[{"t": "text", "v": f"You did {kind}."}],
        how=[],
        how_you=None,
        chart={},
    )
    return replace(base, **changes)


DAY = date(2026, 9, 27)
HELD = [DAY - timedelta(weeks=n) for n in range(40, -1, -1)]


def sundays(n: int) -> list[date]:
    return [DAY + timedelta(weeks=i) for i in range(n)]


def picks(rows: list[InsightRow], held: list[date], day: date) -> list[str]:
    return [r.kind for r in week_picks(rows, held, day, no_supersedes)]


# --- eligibility ----------------------------------------------------------------------------------


def test_every_sunday_page_kind_is_decided() -> None:
    sunday_kinds = {k.id for k in registry.all_kinds() if any(p.value == "sunday" for p in k.pages)}
    assert sunday_kinds == set(ELIGIBLE) | set(EXCLUDED)
    assert not set(ELIGIBLE) & set(EXCLUDED)
    assert all(EXCLUDED.values()), "every exclusion carries its reason"
    for kind_id, variants in ELIGIBLE.items():
        assert variants <= set(registry.get(kind_id).templates), kind_id


def test_the_sections_already_in_the_email_are_excluded() -> None:
    for kind_id in ("pf.pb", "ev.top-score", "ev.close-finish", "ev.new-faces", "pf.wins"):
        assert kind_id in EXCLUDED
    assert "rollup" not in ELIGIBLE["pf.sunday-milestone"]
    assert ELIGIBLE["ev.rain-day"] == {"field"}
    assert "pf.targets-milestone" in EXCLUDED  # the Clays Broken milestone says it
    # a finishing place below the podium is a ranking of people beyond it
    assert ELIGIBLE["pf.career-first"] == {"podium"}


def test_ranking_superlatives_and_context_free_openers_are_excluded() -> None:
    assert "ev.week-jump" in EXCLUDED  # "Biggest jump: <Name>" ranks one shooter, no size given
    assert "pf.high-round-count" in EXCLUDED  # opens with "That was", pointing at nothing


def test_vague_roll_ups_are_dropped_consistently() -> None:
    # Each roll-up lists names with no number or length, or reads as a club-wide record.
    for kind_id in ("pf.best-stretch", "pf.podium-run", "pf.tied-best", "pf.above-own-avg-streak"):
        assert "rollup" not in ELIGIBLE[kind_id], kind_id


def sample_params(template_slots_: list[Slot], word_keys: Mapping[str, str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for slot in template_slots_:
        if isinstance(slot, Word):
            params[slot.param] = word_keys[slot.param]
        elif type(slot).__name__ in {"Shooter"}:
            params[slot.param] = 1
        elif type(slot).__name__ == "NameList":
            params[slot.param] = [1, 2]
        elif type(slot).__name__ in {"ShortDate", "FullDate", "MonthYear", "SundayDate"}:
            params[slot.param] = date(2026, 9, 27)
        elif type(slot).__name__ == "TrophyName":
            params[slot.param] = "x"
        else:
            params[slot.param] = 7  # numbers, years, stations
    return params


def every_rendering(kind_id: str, variant: str) -> list[str]:
    out: list[str] = []
    for template in registry.get(kind_id).templates[variant]:
        slots_ = list(template_slots(template))
        words = [s for s in slots_ if isinstance(s, Word)]
        choice_lists = [[k for k, _ in w.choices] for w in words]
        for combo in itertools.product(*choice_lists):
            keys = {w.param: k for w, k in zip(words, combo, strict=True)}
            params = sample_params(slots_, keys)
            segments = render(template, params, {1: "Hadley, Ike", 2: "Kaplan, Noel"})
            out.append(plain([s for s in segments if s["t"] != "shooter"]))
    return out


def test_no_eligible_headline_trips_the_outsider_lint() -> None:
    rendered = [
        (k, v, text) for k, vs in ELIGIBLE.items() for v in vs for text in every_rendering(k, v)
    ]
    assert len(rendered) > 30
    for kind_id, variant, text in rendered:
        assert banned_in(text) == [], (kind_id, variant, text)
        assert recap_text_problems(text) == [], (kind_id, variant, text)
        assert not PRONOUNS.search(text), (kind_id, variant, text)


def test_the_lint_itself_catches_every_banned_phrase() -> None:
    for word in BANNED:
        assert recap_text_problems(f"Something {word} here."), word
    assert recap_text_problems("Well above their usual for a day like this: A.")
    assert recap_text_problems("Tap for more")
    assert recap_text_problems("Open it. See the chart")
    assert recap_text_problems("Your best")
    assert recap_text_problems("Level 3")
    assert recap_text_problems("A Silver one")
    assert not recap_text_problems("Welcome back after a long break: A and B.")
    assert not recap_text_problems("A golden day; tapestry; modeling; skillet")  # whole words only


def test_an_ineligible_kind_or_variant_is_never_picked() -> None:
    rows = [
        row("pf.pb", DAY, score=9),
        row("ev.top-score", DAY, score=9, sid=2),
        row("ev.rain-day", DAY, score=9, sid=3, variant="both"),
        row("pf.wins", DAY, score=9, sid=4),
        row("ev.record-watch", DAY, score=9, sid=5, variant="tie"),  # "level with" trips the lint
        row("ev.spotlight", DAY, score=9, sid=6),
        row(KINDS[0], DAY, score=1),
    ]
    assert picks(rows, [DAY], DAY) == [KINDS[0]]


def test_a_row_for_another_day_or_page_is_never_picked() -> None:
    rows = [
        row(KINDS[0], DAY - timedelta(weeks=1), score=9),
        row(KINDS[1], DAY, pages=("profile",), score=9),
        row(KINDS[2], DAY, score=1),
    ]
    assert picks(rows, [DAY - timedelta(weeks=1), DAY], DAY) == [KINDS[2]]


def test_a_mixed_or_negative_kind_that_names_someone_is_dropped_and_one_that_names_nobody_stays():
    rows = [
        row(KINDS[0], DAY, polarity="mixed", score=9),
        row(KINDS[1], DAY, polarity="field_negative", score=8, sid=2),
        row(KINDS[2], DAY, polarity="field_negative", score=7, sid=3, named_shooter_ids=()),
        row(KINDS[3], DAY, polarity="neutral", score=6, sid=4),
    ]
    assert picks(rows, [DAY], DAY) == [KINDS[2], KINDS[3]]


def test_text_that_trips_the_lint_is_dropped_but_a_shooter_called_gold_is_not() -> None:
    bad = [{"t": "text", "v": "Your best round yet."}]
    named_gold = [{"t": "shooter", "id": 2, "v": "Gold, Silver"}, {"t": "text", "v": " is up."}]
    rows = [
        row(KINDS[0], DAY, headline=bad, score=9),
        row(KINDS[1], DAY, headline=named_gold, score=1, sid=2),
    ]
    out = week_picks(rows, [DAY], DAY, no_supersedes)
    assert [r.kind for r in out] == [KINDS[1]]


# --- picking 3-5 ---------------------------------------------------------------------------------


def test_picks_the_five_highest_ranked_and_never_the_you_form() -> None:
    rows = [row(k, DAY, score=10 - i, sid=i + 1) for i, k in enumerate(KINDS[:8])]
    out = week_picks(rows, [DAY], DAY, no_supersedes)
    assert [r.kind for r in out] == KINDS[:5]
    assert all("You" not in plain(r.headline) for r in out)


def test_one_per_family_and_one_named_story_per_shooter() -> None:
    rows = [
        row(KINDS[0], DAY, score=9, sid=1, family="form"),
        row(KINDS[1], DAY, score=8, sid=2, family="form"),  # same family: skipped
        row(KINDS[2], DAY, score=7, sid=1, family="streak"),  # same shooter: skipped
        row(KINDS[3], DAY, score=6, sid=3, family="streak"),
    ]
    assert picks(rows, [DAY], DAY) == [KINDS[0], KINDS[3]]


def test_superseded_rows_are_dropped() -> None:
    rows = [row(KINDS[0], DAY, score=9, sid=1), row(KINDS[1], DAY, score=8, sid=1)]
    out = week_picks(
        rows, [DAY], DAY, lambda k: frozenset({KINDS[1]}) if k == KINDS[0] else frozenset()
    )
    assert [r.kind for r in out] == [KINDS[0]]


def test_fewer_than_three_eligible_is_fine_and_a_special_or_unheld_day_has_none() -> None:
    assert picks([row(KINDS[0], DAY)], [DAY], DAY) == [KINDS[0]]
    assert picks([], [DAY], DAY) == []
    assert picks([row(KINDS[0], DAY)], [DAY - timedelta(weeks=1)], DAY) == []


# --- the 12-week rotation ------------------------------------------------------------------------


def weekly_pool(days: list[date], kinds: list[str]) -> list[InsightRow]:
    """The same kinds on every Sunday, ranked in the given order, each about its own shooter."""
    return [row(k, d, score=100 - i, sid=i + 1) for d in days for i, k in enumerate(kinds)]


def test_a_kind_used_in_the_last_12_weeks_is_skipped() -> None:
    days = sundays(3)
    pool = KINDS[:12]
    rows = weekly_pool(days, pool)
    assert picks(rows, days, days[0]) == pool[0:5]
    assert picks(rows, days, days[1]) == pool[5:10]


def test_fewer_than_three_fresh_kinds_fill_from_the_least_recently_used() -> None:
    days = sundays(4)
    pool = KINDS[:12]
    rows = weekly_pool(days, pool)
    # Week 3: only pool[10], pool[11] are unused; pool[0] (week 1) is the least recently used.
    assert picks(rows, days, days[2]) == [pool[10], pool[11], pool[0]]
    # Week 4: nothing is unused; the three least recently used are pool[1..3] (week 1, by rank).
    assert picks(rows, days, days[3]) == [pool[1], pool[2], pool[3]]


def test_the_window_is_exactly_twelve_held_sundays() -> None:
    assert NO_REPEAT_WEEKS == 12
    days = sundays(14)
    x, fillers, fresh = KINDS[0], KINDS[1:2], KINDS[2:12]
    rows = [row(x, days[0], score=50, sid=1)]
    rows += [row(fillers[0], d, score=1, sid=2) for d in days[1:12]]
    # Day 12: X again, with three fresh kinds. Day 13: X again, with three more.
    rows += [row(x, days[12], score=50, sid=1)]
    rows += [row(k, days[12], score=5 - i, sid=10 + i) for i, k in enumerate(fresh[0:3])]
    rows += [row(x, days[13], score=50, sid=1)]
    rows += [row(k, days[13], score=5 - i, sid=10 + i) for i, k in enumerate(fresh[3:6])]
    assert x not in picks(rows, days, days[12])  # day 0 is 12 Sundays back: still blocked
    assert x in picks(rows, days, days[13])  # 13 back: free again


def test_only_held_regular_sundays_count_as_weeks() -> None:
    """A special Sunday is not in `held`: it neither has picks nor ages an earlier week."""
    days = sundays(14)
    x = KINDS[0]
    rows = [row(x, days[0], score=50, sid=1), row(x, days[13], score=50, sid=1)]
    rows += [row(KINDS[1], d, score=1, sid=2) for d in days[1:13]]
    rows += [row(k, days[13], score=5 - i, sid=10 + i) for i, k in enumerate(KINDS[2:5])]
    # All 14 held: X was 13 Sundays back, so it is free.
    assert x in picks(rows, days, days[13])
    # Day 5 was a special Sunday (not held): X was 12 held Sundays back, so it is still blocked.
    held = [d for d in days if d != days[5]]
    assert x not in picks(rows, held, days[13])


def test_the_same_date_always_gives_the_same_picks_and_only_the_horizon_matters() -> None:
    assert HORIZON == 36
    days = sundays(45)
    pool = KINDS[:9]
    rows = weekly_pool(days, pool)
    first = picks(rows, days, days[44])
    assert first == picks(rows, days, days[44])
    recent_rows = [r for r in rows if r.anchor_date in days[9:]]  # 36 Sundays ending 44
    assert first == picks(recent_rows, days[9:], days[44])
    older_rows = [r for r in rows if r.anchor_date not in days[:9]]
    assert first == picks(older_rows, days, days[44])
