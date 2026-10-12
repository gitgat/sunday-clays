"""The email's "This week" insights: what is eligible, how MAX_PICKS are picked, what rests."""

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
from sunday_clays.analytics.recap_facts import RecapFact
from sunday_clays.analytics.recap_insights import (
    ELIGIBLE,
    EXCLUDED,
    HORIZON,
    MAX_PICKS,
    MILESTONE_KINDS,
    NO_REPEAT_WEEKS,
    ON_THIS_DAY_REST_WEEKS,
    recap_text_problems,
    week_insights,
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
            {"t": "text", "v": f" did {kind} on {day}."},
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
    return [x.type for x in week_picks(rows, held, day, no_supersedes)]


# --- eligibility ----------------------------------------------------------------------------------


def test_every_sunday_page_kind_is_decided() -> None:
    sunday_kinds = {k.id for k in registry.all_kinds() if any(p.value == "sunday" for p in k.pages)}
    assert sunday_kinds == set(ELIGIBLE) | set(EXCLUDED) | set(MILESTONE_KINDS)
    assert not set(ELIGIBLE) & set(EXCLUDED)
    assert not set(MILESTONE_KINDS) & (set(ELIGIBLE) | set(EXCLUDED))
    assert all(EXCLUDED.values()), "every exclusion carries its reason"
    for kind_id, variants in ELIGIBLE.items():
        assert variants <= set(registry.get(kind_id).templates), kind_id


def test_the_sections_already_in_the_email_are_excluded() -> None:
    for kind_id in ("pf.pb", "ev.top-score", "ev.close-finish", "ev.new-faces", "pf.wins"):
        assert kind_id in EXCLUDED
    assert "rollup" not in ELIGIBLE["pf.sunday-milestone"]
    assert ELIGIBLE["ev.rain-day"] == {"field"}
    # the newsletter covers welcome-backs (owner, 2026-10-05): "This week" never carries them
    assert "pf.back-strong" in EXCLUDED
    assert "pf.back-strong" not in ELIGIBLE
    # a second visit is the newsletter's new-shooter story, a welcome-back under another name
    assert "ev.second-visit" in EXCLUDED
    assert "ev.second-visit" not in ELIGIBLE
    # personal bests (a tied one included) are the newsletter's story
    assert "pf.tied-best" in EXCLUDED
    assert "pf.tied-best" not in ELIGIBLE


def test_no_podium_or_win_kind_can_be_picked() -> None:
    """The club newsletter shows the podium and the winner (owner, 2026-10-05)."""
    for kind_id in ("pf.podium-run", "pf.career-first"):
        assert kind_id in EXCLUDED
        assert kind_id not in ELIGIBLE
    assert ELIGIBLE["pf.first-since"] == {"score"}  # no "win" or "podium" variant
    rows = [row("pf.podium-run", DAY, score=9, variant=""), row("pf.career-first", DAY, sid=2)]
    rows += [row("pf.career-first", DAY, sid=3, variant="podium")]
    rows += [row("pf.first-since", DAY, sid=n, variant=v) for n, v in ((4, "win"), (5, "podium"))]
    rows += [row("pf.first-since", DAY, sid=6, variant="score")]
    assert picks(rows, [DAY], DAY) == ["pf.first-since"]


def test_ranking_superlatives_and_context_free_openers_are_excluded() -> None:
    assert "ev.week-jump" in EXCLUDED  # "Biggest jump: <Name>" ranks one shooter, no size given
    assert "pf.high-round-count" in EXCLUDED  # opens with "That was", pointing at nothing


def test_vague_roll_ups_are_dropped_consistently() -> None:
    # Each roll-up lists names with no number or length, or reads as a club-wide record.
    for kind_id in (
        "pf.best-stretch",
        "pf.three-rising",
        "pf.above-own-avg-streak",
        "pf.beat-field-streak",
    ):
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
        row(KINDS[2], DAY, score=1, sid=2),
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
    assert [x.type for x in out] == [KINDS[1]]


# --- picking up to MAX_PICKS ---------------------------------------------------------------------


def test_picks_the_five_highest_ranked_and_never_the_you_form() -> None:
    assert MAX_PICKS == 5  # owner, 2026-10-12
    rows = [row(k, DAY, score=10 - i, sid=i + 1) for i, k in enumerate(KINDS[:8])]
    out = week_picks(rows, [DAY], DAY, no_supersedes)
    assert [x.type for x in out] == KINDS[:5]
    assert all("You" not in x.text for x in out)


def test_one_per_type_and_one_named_story_per_shooter() -> None:
    rows = [
        row(KINDS[0], DAY, score=9, sid=1),
        row(KINDS[0], DAY, score=8, sid=2),  # same type: skipped
        row(KINDS[2], DAY, score=7, sid=1),  # same shooter: skipped
        row(KINDS[3], DAY, score=6, sid=3),
    ]
    assert picks(rows, [DAY], DAY) == [KINDS[0], KINDS[3]]


def test_a_line_that_names_nobody_never_blocks_anyone() -> None:
    rows = [row(k, DAY, score=9 - i, named_shooter_ids=()) for i, k in enumerate(KINDS[:3])]
    assert picks(rows, [DAY], DAY) == KINDS[:3]


def test_superseded_rows_are_dropped() -> None:
    rows = [row(KINDS[0], DAY, score=9, sid=1), row(KINDS[1], DAY, score=8, sid=1)]
    out = week_picks(
        rows, [DAY], DAY, lambda k: frozenset({KINDS[1]}) if k == KINDS[0] else frozenset()
    )
    assert [x.type for x in out] == [KINDS[0]]


def test_a_small_pool_gives_fewer_than_four_and_a_special_or_unheld_day_has_none() -> None:
    assert picks([row(KINDS[0], DAY)], [DAY], DAY) == [KINDS[0]]
    assert picks([], [DAY], DAY) == []
    assert picks([row(KINDS[0], DAY)], [DAY - timedelta(weeks=1)], DAY) == []


def fact(kind: str, text: str, strength: float, *named: int, key: str = "") -> RecapFact:
    return RecapFact(kind, text, tuple(named), strength, key)


def test_recap_facts_share_the_pool_with_the_stored_insights() -> None:
    rows = [row(KINDS[0], DAY, score=2.0, sid=1)]  # ranks 2.0 x 1.5 = 3.0
    facts = [fact("turnout", "35 came out.", 9.0), fact("weather", "A wet one.", 1.0)]
    out = week_picks(rows, [DAY], DAY, no_supersedes, lambda d: facts)
    assert [x.type for x in out] == ["turnout", KINDS[0], "weather"]
    assert week_insights(rows, [DAY], DAY, no_supersedes, lambda d: facts)[0] == "35 came out."


def test_only_the_strongest_fact_of_a_type_is_used_and_the_shooter_is_named_once() -> None:
    facts = [
        fact("improvement", "A is up.", 8.0, 1),
        fact("improvement", "B is up.", 7.0, 2),  # same type
        fact("coming_up", "A is close.", 6.0, 1),  # same shooter
        fact("coming_up", "C is close.", 5.0, 3),
    ]
    out = week_picks([], [DAY], DAY, no_supersedes, lambda d: facts)
    assert [x.text for x in out] == ["A is up.", "C is close."]


# --- the previous Sunday's shooters ------------------------------------------------------------


def test_nobody_named_in_the_previous_sundays_recap_is_named_again() -> None:
    days = sundays(3)
    facts = {
        days[0]: [fact("improvement", "A is up.", 9.0, 1)],
        days[1]: [fact("coming_up", "A is close.", 9.0, 1), fact("turnout", "B came.", 1.0, 2)],
        days[2]: [fact("coming_up", "A is close again.", 9.0, 1)],
    }
    lines = lambda d: [x.text for x in week_picks([], days, d, no_supersedes, lambda e: facts[e])]  # noqa: E731
    assert lines(days[0]) == ["A is up."]
    assert lines(days[1]) == ["B came."]  # A was named last week
    assert lines(days[2]) == ["A is close again."]  # A skipped a week: free again


# --- what rests: kind a week, (kind, subject) twelve weeks (owner, 2026-10-12) --------------------


def weekly_pool(days: list[date], kinds: list[str]) -> list[InsightRow]:
    """The same kinds on every Sunday, ranked in the given order, each about a new shooter and
    worded differently each week (numbers do not count as different words)."""

    def headline(n: int, i: int) -> list[Any]:
        week = "".join(chr(97 + (n // 26**p) % 26) for p in range(2))
        return [
            {"t": "shooter", "id": 100 * n + i + 1, "v": "Hadley, Ike"},
            {"t": "text", "v": f" was in the news in week {week}, item {chr(97 + i)}."},
        ]

    return [
        row(k, d, score=100 - i, sid=100 * n + i + 1, headline=headline(n, i))
        for n, d in enumerate(days)
        for i, k in enumerate(kinds)
    ]


def lines_on(pool: dict[int, list[RecapFact]], n: int, at: int) -> list[str]:
    days = sundays(n)
    return [
        x.text
        for x in week_picks(
            [], days, days[at], no_supersedes, lambda d: pool.get(days.index(d), [])
        )
    ]


def test_a_kind_is_never_used_two_weeks_running_but_returns_after_one_week() -> None:
    pool = {
        0: [fact("a", "A one.", 9.0), fact("b", "B one.", 8.0)],
        1: [fact("a", "A two.", 9.0), fact("b", "B two.", 8.0), fact("c", "C two.", 1.0)],
        2: [fact("a", "A three.", 9.0), fact("b", "B three.", 8.0)],
    }
    assert lines_on(pool, 3, 0) == ["A one.", "B one."]
    assert lines_on(pool, 3, 1) == ["C two."]  # a and b were last week's kinds
    assert lines_on(pool, 3, 2) == ["A three.", "B three."]  # back, with different content


def test_a_thin_week_stays_thin_there_is_no_fill() -> None:
    pool = {
        0: [fact(k, f"{k} one.", 9.0) for k in "abcd"],
        1: [fact(k, f"{k} two.", 9.0) for k in "abcd"],
    }
    assert lines_on(pool, 2, 1) == []


def test_the_same_kind_and_person_rest_twelve_held_sundays() -> None:
    pool = {
        0: [fact("station_feats", "Ana climbed a little.", 9.0, 1)],
        2: [fact("station_feats", "Ana climbed some.", 9.0, 1)],
        12: [fact("station_feats", "Ana climbed more.", 9.0, 1)],
        13: [fact("station_feats", "Ana climbed a lot.", 9.0, 1)],
    }
    assert lines_on(pool, 14, 2) == []  # two weeks later: same person, same kind
    assert lines_on(pool, 14, 12) == []  # week 0 is the twelfth Sunday back: still resting
    assert lines_on({0: pool[0], 13: pool[13]}, 14, 13) == ["Ana climbed a lot."]  # thirteen back


def test_the_same_person_in_another_kind_is_free_after_a_week() -> None:
    pool = {
        0: [fact("improvement", "Ana climbed.", 9.0, 1)],
        2: [fact("coming_up", "Ana is close.", 9.0, 1)],
    }
    assert lines_on(pool, 3, 2) == ["Ana is close."]


def test_a_kind_naming_nobody_comes_back_after_one_week_with_new_content() -> None:
    pool = {0: [fact("weather", "Hot: 83.", 9.0)], 2: [fact("weather", "Cold: 40.", 9.0)]}
    assert lines_on(pool, 3, 2) == ["Cold: 40."]


def test_a_milestone_key_rests_twelve_weeks_but_another_milestone_is_free() -> None:
    pool: dict[int, list[RecapFact]] = {
        0: [fact("club_next", "Eighty rounds to go.", 9.0, key="rounds:7500")],
        2: [
            fact("club_next", "Forty-three rounds to go.", 9.0, key="rounds:7500"),
            fact("club_next", "Nine Sundays to go.", 5.0, key="sundays_held:700"),
        ],
    }
    assert lines_on(pool, 3, 2) == ["Nine Sundays to go."]


def test_a_sentence_is_the_same_when_only_its_numbers_differ() -> None:
    pool = {
        0: [fact("a", "19 Sundays since the last round of 49 or better.", 9.0)],
        1: [fact("b", "No news.", 9.0)],
        2: [fact("a", "20 Sundays since the last round of 49 or better.", 9.0)],
        3: [fact("c", "21 Sundays since the last round of 49 or better.", 9.0)],
    }
    assert lines_on(pool, 3, 2) == []  # same kind, new number: the same sentence
    assert lines_on(pool, 4, 3) == []  # another kind saying the same words
    assert NO_REPEAT_WEEKS == 12


def test_a_recap_fact_with_only_other_numbers_is_new_content_unless_it_is_the_same_sentence() -> (
    None
):
    """The digit-blind check is for the stored insights, whose templates carry the numbers; the
    recap facts say what they are about in their key and are judged by that and exact words."""
    pool = {
        0: [fact("on_this_day", "A year ago this week: 28 shooters, top score 46.", 9.0)],
        5: [fact("on_this_day", "A year ago this week: 24 shooters, top score 45.", 9.0)],
        6: [fact("turnout", "A year ago this week: 28 shooters, top score 46.", 9.0)],
    }
    assert lines_on(pool, 6, 5) == ["A year ago this week: 24 shooters, top score 45."]
    assert lines_on(pool, 7, 6) == []  # exactly the sentence of week 0


def test_on_this_day_rests_four_held_sundays_after_each_use() -> None:
    """Owner, 2026-10-12: used on week 0, it is not eligible in weeks 1-4, back in week 5."""
    assert ON_THIS_DAY_REST_WEEKS == 4
    pool = {i: [fact("on_this_day", f"A year ago {i}.", 9.0)] for i in range(12)}
    said = [bool(lines_on(pool, 12, at)) for at in range(12)]
    # each date replays alone: 0 yes, 1-4 rest, 5 yes, 6-9 rest, 10 yes, 11 rests
    assert said == [True, False, False, False, False, True, False, False, False, False, True, False]


def test_the_on_this_day_rest_counts_held_sundays_and_leaves_other_types_to_rule_1() -> None:
    pool = {
        0: [fact("on_this_day", "A year ago 0.", 9.0)],
        1: [fact("weather", "Wet 1.", 9.0)],
        2: [fact("turnout", "Crowd 2.", 9.0)],
    }
    days = sundays(7)
    gap = [days[0], days[1], days[2], days[4], days[5], days[6]]  # days[3] was not held
    on = lambda at: [  # noqa: E731
        x.type
        for x in week_picks([], gap, at, no_supersedes, lambda d: [*pool.get(days.index(d), [])])
    ]
    assert on(days[2]) == ["turnout"]  # only on_this_day rests longer than a week
    pool[4] = [fact("on_this_day", "A year ago 4.", 9.0)]
    pool[5] = [fact("on_this_day", "A year ago 5.", 9.0)]
    pool[6] = [fact("on_this_day", "A year ago 6.", 9.0)]
    assert on(days[4]) == []  # 3 held Sundays after week 0 (4 on the calendar): resting
    assert on(days[5]) == []  # 4 held Sundays after (5 on the calendar): still resting
    assert on(days[6]) == ["on_this_day"]  # 5 held Sundays after: back


def test_improvement_is_a_high_water_mark_a_lower_or_equal_step_is_never_said_again() -> None:
    """Steps 3, 2, 3 (and 3 again thirteen weeks on) say 3 once; only a higher step is news."""
    pool = {
        0: [fact("improvement", "Ana is up 3.4.", 9.0, 1, key="step:3")],
        14: [fact("improvement", "Ana is up 2.2.", 9.0, 1, key="step:2")],
        16: [fact("improvement", "Ana is up 3.1.", 9.0, 1, key="step:3")],
        28: [fact("improvement", "Ana is up 3.9.", 9.0, 1, key="step:3")],
        30: [fact("improvement", "Ana is up 4.1.", 9.0, 1, key="step:4")],
    }
    assert lines_on(pool, 31, 0) == ["Ana is up 3.4."]
    for at in (14, 16, 28):
        assert lines_on(pool, 31, at) == [], at
    assert lines_on(pool, 31, 30) == ["Ana is up 4.1."]


def test_improvement_high_water_is_per_person() -> None:
    pool = {
        0: [fact("improvement", "Ana is up 3.4.", 9.0, 1, key="step:3")],
        14: [fact("improvement", "Bo is up 2.2.", 9.0, 2, key="step:2")],
    }
    assert lines_on(pool, 15, 14) == ["Bo is up 2.2."]


def test_event_facts_are_judged_against_the_whole_replay_not_the_twelve_week_window() -> None:
    """A (person, milestone) said 13 or more weeks ago is still said: coming_up and club_next."""
    pool: dict[int, list[RecapFact]] = {
        0: [
            fact("coming_up", "Bo is 1 Sunday away from 50 Sundays at the club.", 9.0, 2, key="50"),
            fact("club_next", "80 more rounds and the club reaches 7,500.", 8.0, key="rounds:7500"),
        ],
        14: [
            fact("coming_up", "Bo is 2 Sundays from 50 Sundays at the club.", 9.0, 2, key="50"),
            fact("club_next", "40 more rounds and the club reaches 7,500.", 8.0, key="rounds:7500"),
        ],
    }
    assert len(lines_on(pool, 15, 0)) == 2
    assert lines_on(pool, 15, 14) == []


def test_a_streak_rests_the_person_for_twenty_six_weeks_whatever_the_count() -> None:
    pool = {
        0: [fact("attendance_streak", "Cy has come out 10 Sundays in a row.", 9.0, 3, key="")],
        14: [fact("attendance_streak", "Cy has come out 20 Sundays in a row.", 9.0, 3, key="")],
        26: [fact("attendance_streak", "Cy has come out 30 Sundays in a row.", 9.0, 3, key="")],
        27: [fact("attendance_streak", "Cy has come out 35 Sundays in a row.", 9.0, 3, key="")],
    }
    assert lines_on(pool, 28, 14) == []
    assert lines_on(pool, 28, 26) == []  # week 0 is 26 back: still resting
    assert lines_on({0: pool[0], 27: pool[27]}, 28, 27) == [pool[27][0].text]


def test_an_event_fact_blocked_at_two_away_is_still_said_at_one_away() -> None:
    blocked = {
        0: [
            fact("coming_up", "Bo is 2 Sundays away from 25 Sundays at the club.", 9.0, 2, key="25")
        ],
        1: [
            fact(
                "coming_up", "Ike is 2 Sundays away from 50 Sundays at the club.", 9.0, 1, key="50"
            )
        ],
        2: [
            fact("coming_up", "Ike is 1 Sunday away from 50 Sundays at the club.", 9.0, 1, key="50")
        ],
    }
    assert lines_on(blocked, 3, 1) == []  # coming_up was last week's kind
    assert lines_on(blocked, 3, 2) == ["Ike is 1 Sunday away from 50 Sundays at the club."]
    said = {i: blocked[i] for i in (1, 2)}
    assert lines_on(said, 3, 1) == [blocked[1][0].text]
    assert lines_on(said, 3, 2) == []  # said already (and Ike was named last week)


def test_only_held_regular_sundays_count_as_weeks() -> None:
    """A special Sunday is not in `held`: it neither has picks nor ages an earlier week."""
    days = sundays(14)
    x = KINDS[0]
    rows = [row(x, days[0], score=50, sid=1), row(x, days[13], score=50, sid=1)]
    assert x in picks(rows, days, days[13])  # all 14 held: 13 Sundays back, free
    held = [d for d in days if d != days[5]]  # day 5 was special: 12 held Sundays back, resting
    assert x not in picks(rows, held, days[13])


def test_the_same_date_always_gives_the_same_picks_and_only_the_horizon_matters() -> None:
    assert HORIZON == 36
    days = sundays(45)
    rows = weekly_pool(days, KINDS[:9])
    first = picks(rows, days, days[44])
    assert first, "the pool is not empty"
    assert first == picks(rows, days, days[44])
    recent_rows = [r for r in rows if r.anchor_date in days[9:]]  # 36 Sundays ending 44
    assert first == picks(recent_rows, days[9:], days[44])
    older_rows = [r for r in rows if r.anchor_date not in days[:9]]
    assert first == picks(older_rows, days, days[44])


# --- the Milestones section's insight source -----------------------------------------------------

MS = "pf.targets-milestone"


def test_the_targets_milestone_is_a_milestone_source_and_never_a_this_week_pick() -> None:
    assert MS in MILESTONE_KINDS
    assert "" in MILESTONE_KINDS[MS]
    # the roll-up names people with no number, and trophy lines carry the numbers
    assert MILESTONE_KINDS[MS] == {""}
    assert MS not in ELIGIBLE
    rows = [row(MS, DAY, score=9, variant=""), row(KINDS[0], DAY, score=1, sid=2)]
    assert picks(rows, [DAY], DAY) == [KINDS[0]]


def test_the_real_milestone_sentence_passes_the_lint_and_avoids_pronouns() -> None:
    renderings = every_rendering(MS, "")
    assert len(renderings) >= 1
    for text in renderings:
        assert recap_text_problems(text) == [], text
        assert banned_in(text) == [], text
        assert not PRONOUNS.search(text), text
