"""Recompute step 60 on the committed-fixtures world (spec §3.2, §5)."""

from collections import Counter
from datetime import date

from sunday_clays.analytics import frames
from sunday_clays.analytics.insights.store import (
    Pick,
    insights_table,
    load_picks,
    load_rows,
    replace_all,
)
from sunday_clays.analytics.steps import s60_insights
from sunday_clays.api.routes.events import event_notables


def test_pb_rows_match_the_notables_pb_rule_except_deceased(fx_session):
    s60_insights.run(fx_session)
    rows = load_rows(fx_session)
    rounds = frames.load_rounds(fx_session)
    shooters = frames.load_shooters(fx_session)
    deceased = set(shooters.loc[shooters["status"] == "deceased", "shooter_id"])
    events = frames.load_events(fx_session)
    for day in sorted(events.loc[events["results_complete"], "event_date"]):
        ours = {
            int(r.subject_id)
            for r in rows
            if r.kind == "pf.pb" and r.variant == "" and r.anchor_date == day
        }
        notables = {n.shooter_id for n in event_notables(rounds, shooters, day) if n.kind == "pb"}
        assert ours == notables - deceased, day


def test_rows_cover_the_first_kinds(fx_session):
    s60_insights.run(fx_session)
    kinds = Counter(r.kind for r in load_rows(fx_session))
    assert {"pf.pb", "ev.spotlight", "pf.digest-line"} <= set(kinds)


def test_picks_round_trip_through_replace_all_and_load_picks(fx_session):
    s60_insights.run(fx_session)
    rows = load_rows(fx_session)
    pick = Pick(rows[0].anchor_date or date(2024, 1, 7), "hero", rows[0].key)
    replace_all(fx_session, rows, [pick])
    assert load_picks(fx_session) == [pick]
    assert load_picks(fx_session, pick.sunday) == [pick]
    assert load_picks(fx_session, date(1999, 1, 3)) == []
    assert insights_table().name == "insights"
