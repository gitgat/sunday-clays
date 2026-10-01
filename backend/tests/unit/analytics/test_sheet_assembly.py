"""The Sunday Sheet assembler (Plan 14 Task 2), on synthetic rows: pure, no database."""

from dataclasses import replace
from datetime import date
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sunday_clays.analytics import sheet
from sunday_clays.analytics.insights import registry
from sunday_clays.analytics.insights.lints import lint_segments
from sunday_clays.analytics.insights.store import InsightRow
from sunday_clays.analytics.insights.templates import NameList, Shooter
from sunday_clays.analytics.yir import OnThisDayItem, Winner

DAY = date(2026, 9, 27)
HELD = [date(2026, 9, 13), date(2026, 9, 20), DAY]
CATALOG = {
    "first_win": sheet.TrophyInfo("first_win", "First win", "first_win", None),
    "round_score:4": sheet.TrophyInfo("round_score:4", "Round score — 45", "round_score", "gold"),
}


def no_supersedes(_kind: str) -> frozenset[str]:
    return frozenset()


def row(key: str, kind: str = "pf.pb", **overrides: Any) -> InsightRow:
    values: dict[str, Any] = {
        "key": key,
        "value_hash": "h",
        "generation": 1,
        "first_generation": 1,
        "kind": kind,
        "family": "milestone",
        "home_slot": None,
        "subject_type": "shooter",
        "subject_id": "3",
        "anchor_date": DAY,
        "variant": "default",
        "pages": ("home", "profile", "sunday"),
        "expires": {},
        "named_shooter_ids": (3,),
        "polarity": "positive",
        "kudos": False,
        "template_id": "t",
        "params": {},
        "strength": 1.0,
        "base_score": 10.0,
        "rank_score": 15.0,
        "headline": [{"t": "text", "v": f"Story {key}."}],
        "headline_you": None,
        "how": [],
        "how_you": None,
        "chart": {
            "type": "page",
            "label": "x",
            "window": {"from": "2026-09-01", "to": "2026-09-27"},
        },
    }
    values.update(overrides)
    return InsightRow(**values)


def post(key: str, type_: sheet.PostType, score: float) -> sheet.Post:
    return sheet.Post(key, type_, "form", score, (), ())


def assemble(rows: list[InsightRow], day: date = DAY, **kw: Any) -> sheet.Issue:
    args: dict[str, Any] = {
        "hero": None,
        "spotlight": None,
        "awards": [],
        "catalog": CATALOG,
        "on_this_day": [],
        "supersedes": no_supersedes,
    }
    args.update(kw)
    return sheet.assemble(day, HELD, rows, **args)


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        *[(k, "milestone") for k in sheet._MILESTONE],
        ("rec.drought-clock", "milestone"),
        ("rec.anything-new", "milestone"),
        *[(k, "improvement") for k in sheet._IMPROVEMENT],
        *[(k, "conditions") for k in sheet._CONDITIONS],
        *[(k, "welcome") for k in sheet._WELCOME],
        ("pf.best-stretch", "other"),
        ("ev.close-finish", "other"),
        ("no.such-kind", "other"),
    ],
)
def test_every_spec_kind_maps_to_its_post_type(kind: str, expected: str) -> None:
    assert sheet.post_type(kind) == expected


SPEC_KINDS = {
    "milestone": {
        "pf.pb", "pf.season-best", "pf.career-first", "pf.first-since", "pf.sunday-milestone",
        "pf.targets-milestone", "pf.average-milestone", "pf.first-tier",
        "pf.shooter-anniversary", "ev.top-score",
    },
    "improvement": {
        "pf.hot-form", "pf.rank-climb", "pf.up-on-usual", "pf.beat-own-usual",
        "pf.three-rising", "pf.year-up", "lb.most-improved", "lb.biggest-climb",
    },
    "conditions": {"ev.how-it-played", "ev.toughest-since", "ev.rain-day", "ev.week-jump"},
    "welcome": {"ev.new-faces", "ev.second-visit", "pf.back-strong"},
}  # fmt: skip


def test_the_spec_tables_kinds_are_all_mapped() -> None:
    """The spec's Posts table, written out: a typo in a kind id fails here."""
    expected = {kind: type_ for type_, kinds in SPEC_KINDS.items() for kind in kinds}
    assert dict(sheet.KIND_TYPES) == expected
    assert len(expected) == 25


def test_posts_are_the_sundays_anchored_rows_ranked_with_its_recency() -> None:
    issue = assemble(
        [
            row("a", base_score=10.0),
            row("b", base_score=20.0),
            row("old", anchor_date=date(2026, 9, 20)),
            row("profile-only", anchor_date=None, pages=("profile",)),
        ]
    )
    assert [p.post_key for p in issue.posts] == ["b", "a"]
    assert [p.score for p in issue.posts] == [30.0, 15.0]


def test_the_latest_issue_adds_homes_evergreen_rows_only() -> None:
    rows = [
        row("a"),
        row(
            "home-ever",
            "cl.turnout-trend",
            anchor_date=None,
            family="turnout",
            named_shooter_ids=(),
        ),
        row("profile-ever", "pf.hot-form", anchor_date=None, pages=("profile",)),
    ]
    assert assemble(rows).post_keys == {"a", "home-ever"}
    past = assemble(
        [replace(r, anchor_date=date(2026, 9, 20)) if r.key == "a" else r for r in rows],
        day=date(2026, 9, 20),
    )
    assert past.post_keys == {"a"}


@pytest.mark.parametrize(("kind", "param"), sorted(sheet.FRESH_EVERGREEN.items()))
def test_profile_only_spec_kinds_post_on_the_latest_issue_when_about_that_sunday(
    kind: str, param: str
) -> None:
    def ever(key: str, day: date) -> InsightRow:
        return row(key, kind, anchor_date=None, pages=("profile",), params={param: day.isoformat()})

    rows = [ever("fresh", DAY), ever("stale", date(2026, 9, 20))]
    issue = assemble(rows)
    assert issue.post_keys == {"fresh"}
    assert issue.posts[0].type == sheet.post_type(kind)
    assert assemble(rows, day=date(2026, 9, 20)).post_keys == set()  # past issues: never


def test_named_posts_are_positive_or_neutral_only() -> None:
    issue = assemble(
        [
            row("pos"),
            row("neu", polarity="neutral"),
            row("mixed-named", "ev.rain-day", polarity="mixed"),
            row("mixed-unnamed", "ev.rain-day", polarity="mixed", named_shooter_ids=()),
            row("field", "ev.how-it-played", polarity="field_negative", named_shooter_ids=()),
            row("field-named", "ev.how-it-played", polarity="field_negative"),
        ]
    )
    assert issue.post_keys == {"pos", "neu", "mixed-unnamed", "field"}
    for p in issue.posts:
        assert p.row is not None
        assert not p.named_shooter_ids or p.row.polarity in {"positive", "neutral"}


def test_a_named_negative_pick_never_leads() -> None:
    bad = row("bad", polarity="mixed")
    issue = assemble([bad], hero=bad, spotlight=bad)
    assert issue.headline is None
    assert issue.spotlight is None
    field = row("field-named", "ev.how-it-played", polarity="field_negative")
    issue = assemble([field], hero=field, spotlight=field)
    assert (issue.headline, issue.spotlight) == (None, None)
    assert issue.post_keys == frozenset()


def test_the_recap_is_the_deck_and_the_picks_lead_instead_of_posting() -> None:
    recap = row("recap", "home.sunday-recap", polarity="mixed", named_shooter_ids=())
    hero, spot, other = row("hero"), row("spot"), row("other")
    issue = assemble([recap, hero, spot, other], hero=hero, spotlight=spot)
    assert issue.recap == recap
    assert (issue.headline, issue.spotlight) == (hero, spot)
    assert issue.post_keys == {"other"}


def test_the_deck_is_the_recap_anchored_on_the_issues_own_sunday() -> None:
    older = row(
        "old-recap",
        "home.sunday-recap",
        polarity="mixed",
        named_shooter_ids=(),
        anchor_date=date(2026, 9, 20),
    )
    mine = replace(older, key="recap", anchor_date=DAY)
    assert assemble([older, mine]).recap == mine
    assert assemble([older]).recap is None


def test_the_recap_names_shooters_only_in_its_positive_clauses() -> None:
    """The deck skips `names_ok` (it is Home's pinned line, polarity mixed), so the template must
    keep every name inside a `named` clause that only celebrates the top score."""
    kind = registry.get("home.sunday-recap")
    assert len(kind.templates) == 32
    for flags, (template,) in kind.templates.items():
        for clause in template.third:
            has_name = any(isinstance(p, Shooter | NameList) for p in clause.parts)
            text = "".join(p for p in clause.parts if isinstance(p, str))
            if has_name:
                assert clause.role == "named", flags
                assert "top" in text, flags
                assert "board" in text, flags
            else:
                assert clause.role == "field", flags


def test_superseded_rows_are_dropped() -> None:
    first = row("first-tier", "pf.first-tier", base_score=30.0)
    pb = row("pb")

    def supersedes(kind: str) -> frozenset[str]:
        return frozenset({"pf.first-tier"}) if kind == "pf.pb" else frozenset()

    assert assemble([first, pb], supersedes=supersedes).post_keys == {"pb"}


def test_one_trophy_post_per_trophy_names_everyone_who_earned_it() -> None:
    awards = [
        sheet.Award(2, "Bee, Bob", "first_win"),
        sheet.Award(1, "Ace, Amy", "first_win"),
        sheet.Award(3, "Hadley, Ike", "round_score:4"),
        sheet.Award(4, "Cy, Cal", "retired_trophy"),  # not in the catalog: skipped
    ]
    issue = assemble([], awards=awards)
    trophies = {p.post_key: p for p in issue.posts}
    assert set(trophies) == {"trophy:first_win:2026-09-27", "trophy:round_score:4:2026-09-27"}
    win = trophies["trophy:first_win:2026-09-27"]
    assert win.trophy is not None
    assert win.trophy.holders == ((1, "Amy Ace"), (2, "Bob Bee"))
    assert win.named_shooter_ids == (1, 2)
    assert "".join(s["v"] for s in win.headline) == "First win unlocked by Amy Ace and Bob Bee."
    assert trophies["trophy:round_score:4:2026-09-27"].trophy == sheet.TrophyPost(
        "round_score:4", "Round score — 45", "round_score", "gold", ((3, "Ike Hadley"),)
    )


def test_name_lists_join_with_commas_and_and_then_count_the_rest() -> None:
    people = [(1, "A"), (2, "B"), (3, "C"), (4, "D"), (5, "E")]

    def text(n: int) -> str:
        return "".join(s["v"] for s in sheet.name_list(people[:n]))

    assert [text(n) for n in range(1, 6)] == [
        "A",
        "A and B",
        "A, B and C",
        "A, B, C and 1 more",
        "A, B, C and 2 more",
    ]


def otd(
    years: int,
    *,
    has_scores: bool = True,
    winners: tuple[Winner, ...] = (),
    top_score: int | None = 48,
) -> OnThisDayItem:
    return OnThisDayItem(
        years_ago=years,
        event_date=date(2026 - years, 9, 28),
        has_scores=has_scores,
        head_count=None,
        n_shooters=31 if years != 3 else 1,
        top_score=top_score,
        median=40.0,
        winners=winners,
    )


def test_on_this_day_posts_name_the_top_score_and_keep_attendance_only_sundays() -> None:
    items = [
        otd(1, winners=(Winner(1, "Ace, Amy", 48),)),
        replace(otd(2, has_scores=False, top_score=None), head_count=18),
        otd(3),
    ]
    issue = assemble([], on_this_day=items)
    by_key = {p.post_key: p for p in issue.posts}
    assert set(by_key) == {"otd:2026-09-27:1", "otd:2026-09-27:2", "otd:2026-09-27:3"}
    assert "".join(s["v"] for s in by_key["otd:2026-09-27:2"].headline) == (
        "Two years ago, on Sep 28, 2024, 18 shooters came out (attendance only)."
    )
    assert by_key["otd:2026-09-27:2"].named_shooter_ids == ()
    one_head = sheet.otd_posts([replace(otd(2, has_scores=False), head_count=1)], DAY)[0]
    assert "".join(s["v"] for s in one_head.headline).endswith(
        " 1 shooter came out (attendance only)."
    )
    no_count = sheet.otd_posts([otd(2, has_scores=False)], DAY)[0]
    assert "".join(s["v"] for s in no_count.headline) == (
        "Two years ago, on Sep 28, 2024, a Sunday was shot; no scores were recorded."
    )
    one = by_key["otd:2026-09-27:1"]
    assert "".join(s["v"] for s in one.headline) == (
        "One year ago, on Sep 28, 2025, 31 shooters came out; "
        "the top score of 48 was shot by Amy Ace."
    )
    assert one.named_shooter_ids == (1,)
    three = by_key["otd:2026-09-27:3"]
    assert "".join(s["v"] for s in three.headline) == (
        "Three years ago, on Sep 28, 2023, 1 shooter came out and the top score was 48."
    )
    no_top = sheet.otd_posts([otd(2, top_score=None)], DAY)[0]
    assert "".join(s["v"] for s in no_top.headline) == (
        "Two years ago, on Sep 28, 2024, 31 shooters came out."
    )


def test_on_this_day_names_nobody_when_there_is_no_top_score() -> None:
    winners = (Winner(1, "Ace, Amy", 48),)
    (no_top,) = sheet.otd_posts([otd(1, winners=winners, top_score=None)], DAY)
    assert no_top.named_shooter_ids == ()
    assert "Amy" not in "".join(s["v"] for s in no_top.headline)
    (with_top,) = sheet.otd_posts([otd(1, winners=winners)], DAY)
    assert with_top.named_shooter_ids == (1,)


def test_trophy_and_on_this_day_headlines_pass_the_insight_lints() -> None:
    issue = assemble(
        [],
        awards=[sheet.Award(1, "Ace, Amy", "first_win"), sheet.Award(2, "Bee, Bob", "first_win")],
        on_this_day=[
            otd(1, winners=(Winner(1, "Ace, Amy", 48), Winner(2, "Bee, Bob", 48))),
            replace(otd(2, has_scores=False), head_count=18),
            otd(3, has_scores=False),
        ],
    )
    assert len(issue.posts) == 4
    for p in issue.posts:
        assert lint_segments(p.headline) == []


def test_the_feed_interleaves_types_and_caps_at_ten() -> None:
    posts = [
        *[post(f"m{i}", "milestone", 100 - i) for i in range(8)],
        post("t0", "trophy", 50),
        post("w0", "welcome", 40),
        *[post(f"o{i}", "other", 200 - i) for i in range(3)],
    ]
    feed, rest = sheet.interleave(sheet.ranked(posts))
    assert [p.post_key for p in feed] == [
        "m0", "m1", "t0", "m2", "m3", "w0", "m4", "m5", "m6", "m7",
    ]  # fmt: skip
    assert [p.post_key for p in rest] == ["o0", "o1", "o2"]


@given(
    st.lists(
        st.tuples(st.sampled_from(sorted(sheet.FEED_TYPES | {"other"})), st.integers(0, 50)),
        max_size=30,
    )
)
def test_interleave_never_runs_a_type_three_times_while_another_is_left(
    spec: list[tuple[sheet.PostType, int]],
) -> None:
    posts = sheet.ranked(post(f"p{i}", t, float(s)) for i, (t, s) in enumerate(spec))
    feed, rest = sheet.interleave(posts)
    eligible = [p for p in posts if p.type in sheet.FEED_TYPES]
    assert len(feed) == min(sheet.FEED_CAP, len(eligible))
    assert {p.type for p in feed} == {p.type for p in eligible}  # every type present posts
    assert sorted(p.post_key for p in feed + rest) == sorted(p.post_key for p in posts)
    assert rest == [p for p in posts if p not in feed]
    for i in range(sheet.MAX_RUN, len(feed)):
        window = {p.type for p in feed[i - sheet.MAX_RUN : i + 1]}
        if len(window) == 1:  # a third in a row: only when nothing else chosen was left
            assert {p.type for p in feed[i:]} == window


def test_the_feed_has_one_post_of_every_type_the_issue_has() -> None:
    """A lopsided Sunday: twelve strong milestones cannot push out the one trophy, look-back or
    welcome, however low they score."""
    posts = sheet.ranked(
        [
            *[post(f"m{i:02}", "milestone", 100 - i) for i in range(12)],
            post("t0", "trophy", sheet.TROPHY_SCORE),
            post("d0", "on_this_day", sheet.OTD_SCORE),
            post("w0", "welcome", 1.0),
        ]
    )
    feed, rest = sheet.interleave(posts)
    assert len(feed) == sheet.FEED_CAP
    assert [p.post_key for p in feed] == [
        "m00", "m01", "t0", "m02", "m03", "d0", "m04", "m05", "w0", "m06",
    ]  # fmt: skip
    assert [p.post_key for p in rest] == [f"m{i:02}" for i in range(7, 12)]


def test_a_thin_sunday_puts_every_post_in_the_feed() -> None:
    issue = assemble(
        [row("a")],
        awards=[sheet.Award(1, "Ace, Amy", "first_win")],
        on_this_day=[otd(1)],
    )
    assert {p.type for p in issue.feed} == {"milestone", "trophy", "on_this_day"}
    assert issue.more == ()


def test_more_groups_by_family_in_rank_order() -> None:
    rows = [row(f"m{i}", base_score=50 - i) for i in range(11)]
    rows += [
        row("s1", "pf.podium-run", family="streak", base_score=60.0),
        row("s2", "pf.tier-run", family="streak", base_score=1.0),
        row("x", "pf.wins", family="mystery", base_score=2.0),
    ]
    issue = assemble(rows)
    assert len(issue.feed) == 10
    assert [(g.family, g.label, [p.post_key for p in g.posts]) for g in issue.more] == [
        ("streak", "Streaks", ["s1", "s2"]),
        ("milestone", "Milestones", ["m10"]),
        ("mystery", "Mystery", ["x"]),
    ]


def test_issue_numbers_and_neighbours() -> None:
    first = assemble([], day=HELD[0])
    assert (first.number, first.previous, first.next, first.latest) == (1, None, HELD[1], False)
    last = assemble([])
    assert (last.number, last.previous, last.next, last.latest) == (3, HELD[1], None, True)
    mid = assemble([], day=HELD[1])
    assert (mid.number, mid.previous, mid.next, mid.latest) == (2, HELD[0], HELD[2], False)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("trophy:first_win:2026-09-27", DAY),
        ("trophy:round_score:4:2026-09-27", DAY),
        ("otd:2026-09-27:2", DAY),
        ("trophy:first_win:nonsense", None),
        ("otd:", None),
        ("otd:2026-13-01:1", None),
        ("0123456789abcdef0123", None),
    ],
)
def test_synthetic_keys_name_their_issue(key: str, expected: date | None) -> None:
    assert sheet.synthetic_key_date(key) == expected
