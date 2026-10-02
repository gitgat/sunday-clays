"""Page selection (spec §3.4)."""

from dataclasses import replace
from datetime import date, timedelta

from sunday_clays.analytics.insights import select as sel
from sunday_clays.analytics.insights.store import InsightRow

REF = date(2026, 9, 27)
HELD = [REF - timedelta(weeks=i) for i in range(10, -1, -1)]
SUPERSEDES = {"pf.pb": frozenset({"pf.tied-best", "pf.season-best", "pf.first-tier"})}


def supersedes(kind_id: str) -> frozenset[str]:
    return SUPERSEDES.get(kind_id, frozenset())


def row(key: str, **changes) -> InsightRow:
    base = InsightRow(
        key=key,
        value_hash="h",
        generation=2,
        first_generation=1,
        kind="pf.hot-form",
        family="form",
        home_slot="person",
        subject_type="shooter",
        subject_id="1",
        anchor_date=None,
        variant="",
        pages=("profile",),
        expires={},
        named_shooter_ids=(1,),
        polarity="positive",
        kudos=False,
        template_id="pf.hot-form::0",
        params={},
        strength=1.0,
        base_score=1.0,
        rank_score=1.0,
        headline=[{"t": "text", "v": key}],
        headline_you=None,
        how=[],
        how_you=None,
        chart={},
    )
    return replace(base, **changes)


def test_profile_pins_the_digest_and_keeps_one_per_family_in_top():
    rows = [
        row("digest", kind="pf.digest-line", family="recap", rank_score=0.1),
        row("a", family="form", rank_score=9),
        row("b", family="form", rank_score=8),
        row("c", family="streak", rank_score=7),
        row("d", family="milestone", rank_score=6),
        row("e", family="race", rank_score=5),
    ]
    feed = sel.feed_profile(rows, 1, REF, HELD, supersedes)
    assert feed.pinned is not None
    assert feed.pinned.key == "digest"
    assert [r.key for r in feed.top] == ["a", "c", "d"]
    assert [r.key for r in feed.more] == ["b", "e"]
    assert feed.n_more == 2


def test_profile_more_is_capped_unless_asked_for_all():
    rows = [row(f"r{i}", family="form", rank_score=100 - i) for i in range(sel.MORE_CAP + 6)]
    capped = sel.feed_profile(rows, 1, REF, HELD, supersedes)
    everything = sel.feed_profile(rows, 1, REF, HELD, supersedes, None)
    assert (len(capped.more), capped.n_more) == (sel.MORE_CAP, sel.MORE_CAP + 5)
    assert (len(everything.more), everything.n_more) == (sel.MORE_CAP + 5, sel.MORE_CAP + 5)
    assert everything.more[: sel.MORE_CAP] == capped.more


def test_profile_shows_at_most_one_conditions_kind():
    rows = [
        row("wet", kind="pf.wet-strength", family="weather", rank_score=9),
        row("temp", kind="pf.best-temp", family="weather", rank_score=8),
        row("tough", kind="pf.tough-days", family="weather", rank_score=7),
    ]
    feed = sel.feed_profile(rows, 1, REF, HELD, supersedes)
    assert [r.key for r in feed.top + feed.more] == ["wet"]


def test_a_fallback_row_shows_only_when_the_profile_has_nothing_else():
    fallback = row("best", kind="pf.best-day-vs-field", variant="fallback", rank_score=5)
    digest = row("digest", kind="pf.digest-line", family="recap")
    alone = sel.feed_profile([digest, fallback], 1, REF, HELD, supersedes)
    assert [r.key for r in alone.top] == ["best"]
    other = row("streak", family="streak", rank_score=0.5)
    crowded = sel.feed_profile([digest, fallback, other], 1, REF, HELD, supersedes)
    assert [r.key for r in crowded.top + crowded.more] == ["streak"]


def test_supersedes_hides_the_lesser_story_about_the_same_sunday():
    day = HELD[-1]
    rows = [
        row("pb", kind="pf.pb", anchor_date=day, pages=("sunday",), family="milestone"),
        row("tied", kind="pf.tied-best", anchor_date=day, pages=("sunday",), family="milestone"),
        row("other", kind="pf.tied-best", anchor_date=HELD[-2], pages=("sunday",)),
    ]
    feed = sel.feed_sunday(rows, day, supersedes)
    assert [r.key for r in feed.top + feed.more] == ["pb"]


def test_an_evergreen_profile_row_supersedes_an_anchored_row_about_its_sunday():
    day = HELD[-2]
    pb = row("pb", kind="pf.pb", variant="profile", family="milestone", params={"day": str(day)})
    first = row("first", kind="pf.first-tier", family="milestone", anchor_date=day)
    older = row("older", kind="pf.first-tier", family="milestone", anchor_date=HELD[-3])
    feed = sel.feed_profile([pb, first, older], 1, REF, HELD, supersedes)
    assert sorted(r.key for r in feed.top + feed.more) == ["older", "pb"]


def test_anchored_rows_expire_per_page_after_n_later_held_sundays():
    fresh = row("fresh", anchor_date=HELD[-3], expires={"profile": 3})
    stale = row("stale", anchor_date=HELD[-4], expires={"profile": 3})
    feed = sel.feed_profile([fresh, stale], 1, REF, HELD, supersedes)
    assert [r.key for r in feed.top] == ["fresh"]


def test_sunday_feed_splits_conditions_and_ranks_by_base_score():
    day = HELD[-5]
    rows = [
        row("rain", kind="ev.rain-day", family="weather", anchor_date=day, pages=("sunday",)),
        row("low", anchor_date=day, pages=("sunday",), base_score=1.0, rank_score=50),
        row(
            "high",
            anchor_date=day,
            pages=("sunday",),
            base_score=3.0,
            rank_score=0.1,
            family="milestone",
        ),
    ]
    feed = sel.feed_sunday(rows, day, supersedes)
    assert feed.conditions is not None
    assert feed.conditions.key == "rain"
    assert [r.key for r in feed.top] == ["high", "low"]


def test_kudos_is_one_chip_per_shooter_uncapped():
    day = HELD[-1]
    rows = [
        row(f"k{sid}-{n}", subject_id=str(sid), kudos=True, anchor_date=day, rank_score=float(n))
        for sid in range(1, 16)
        for n in (1, 2)
    ]
    chips = sel.kudos_chips(rows, day)
    assert len(chips) == 15
    assert all(c.row.key.endswith("-2") for c in chips)


def test_kudos_anchor_can_come_from_params():
    day = HELD[-1]
    improved = row("mi", kudos=True, anchor_date=None, params={"kudos_sunday": day.isoformat()})
    assert [c.row.key for c in sel.kudos_chips([improved], day)] == ["mi"]


def test_home_fills_the_four_slots_with_one_story_per_shooter():
    day = HELD[-1]
    rows = [
        row(
            "recap",
            kind="home.sunday-recap",
            family="recap",
            anchor_date=day,
            pages=("home",),
            home_slot=None,
            named_shooter_ids=(),
        ),
        row(
            "f",
            home_slot="field",
            family="weather",
            pages=("home",),
            rank_score=9,
            named_shooter_ids=(),
        ),
        row(
            "p1",
            home_slot="person",
            family="form",
            pages=("home",),
            rank_score=8,
            named_shooter_ids=(5,),
        ),
        row(
            "m1",
            home_slot="milestone",
            family="milestone",
            pages=("home",),
            rank_score=7,
            named_shooter_ids=(5,),
        ),
        row(
            "m2",
            home_slot="milestone",
            family="milestone",
            pages=("home",),
            rank_score=6,
            named_shooter_ids=(6,),
        ),
        row(
            "r",
            home_slot="race_record",
            family="race",
            pages=("home",),
            rank_score=5,
            named_shooter_ids=(7,),
        ),
        row("old", home_slot="person", pages=("home",), anchor_date=HELD[-3], rank_score=99),
    ]
    feed = sel.feed_home(rows, REF, HELD, supersedes)
    assert feed.pinned is not None
    assert feed.pinned.key == "recap"
    assert [r.key for r in feed.top] == ["f", "p1", "m2", "r"]


def test_home_cards_skip_the_shooter_to_know():
    spot = row("spot", home_slot="person", pages=("home",), named_shooter_ids=(5,))
    p1 = row("p1", home_slot="person", family="form", pages=("home",), named_shooter_ids=(5,))
    p2 = row("p2", home_slot="person", family="form", pages=("home",), named_shooter_ids=(6,))
    feed = sel.feed_home([spot, p1, p2], REF, HELD, supersedes, spotlight=spot)
    assert [r.key for r in feed.top] == ["p2"]


def test_silence_when_nothing_passes():
    feed = sel.feed_page([], "club", REF, HELD, supersedes)
    assert (feed.top, feed.more, feed.n_more) == ((), (), 0)


def station_row(key: str, shooter: int, station: str, mine: int, field: int = 50, **changes):
    fields = {
        "kind": "pf.station-best",
        "family": "station",
        "home_slot": None,
        "subject_id": str(shooter),
        "named_shooter_ids": (shooter,),
        "pages": ("profile", "stations"),
        "params": {"s": shooter, "station": station, "mine": mine, "field": field},
    }
    return row(key, **{**fields, **changes})


def station_page(rows):
    return sel.feed_page(rows, "stations", REF, HELD, supersedes)


def test_stations_page_keeps_the_biggest_edge_per_station():
    level = row(
        "hard",
        kind="st.hardest-easiest",
        family="station",
        subject_type="station",
        subject_id="x",
        pages=("stations",),
        named_shooter_ids=(),
        rank_score=0.5,
    )
    rows = [
        station_row("a", 1, "Station 5", 70, rank_score=9),
        station_row("b", 2, "Station 5", 90, rank_score=1),
        station_row("c", 3, "Station 5", 80, rank_score=5),
        station_row("d", 4, "Station 3", 65, rank_score=3),
        level,
    ]
    feed = station_page(rows)
    keys = {r.key for r in (*feed.top, *feed.more)}
    assert keys == {"b", "d", "hard"}
    assert feed.n_more + len(feed.top) == 3


def test_stations_page_edge_tie_goes_to_rank_then_subject_id():
    by_rank = [
        station_row("lo", 1, "Station 5", 80, rank_score=1),
        station_row("hi", 2, "Station 5", 80, rank_score=2),
    ]
    page = station_page(by_rank)
    assert [r.key for r in (*page.top, *page.more)] == ["hi"]
    by_id = [
        station_row("p9", 9, "Station 5", 80, rank_score=1),
        station_row("p2", 2, "Station 5", 80, rank_score=1),
    ]
    for rows in (by_id, by_id[::-1]):
        page = station_page(rows)
        assert [r.key for r in (*page.top, *page.more)] == ["p2"]


def test_stations_more_is_capped_at_8_and_counts_the_deduped_total():
    rows = [
        station_row(f"s{i}", i, f"Station {i}", 80, rank_score=100 - i, family=f"f{i}")
        for i in range(1, 15)
    ]
    feed = station_page(rows)
    assert len(feed.top) == sel.TOP_SIZES["stations"]
    assert len(feed.more) == 8
    assert feed.n_more == 14 - sel.TOP_SIZES["stations"]


def test_profile_feed_still_shows_the_shooters_own_station_best():
    rows = [
        station_row("mine", 1, "Station 5", 70),
        station_row("theirs", 2, "Station 5", 90),
    ]
    feed = sel.feed_profile(rows, 1, REF, HELD, supersedes)
    assert [r.key for r in feed.top] == ["mine"]
