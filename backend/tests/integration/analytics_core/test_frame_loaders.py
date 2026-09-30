import math
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames

D1 = date(2026, 9, 6)
D2 = date(2026, 9, 13)


def test_load_rounds_columns_and_values(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann", status="guest")
    bob = seed.shooter("Pratt, Bob", status="deceased")
    seed.event(D1, round_type="super_sporting")
    seed.round(D1, ann, 41, gauge_class="Sub-Gauge", status="guest")
    seed.round(D1, bob, 38, status="member")
    seed.weather(D1, temp_f=48.0, gust_mph=22.0, precip_in=0.05, condition="rain")
    seed.finish()

    df = frames.load_rounds(session)

    assert list(df.columns) == list(frames.ROUND_COLUMNS)
    ann_row = df[df["shooter_id"] == ann].iloc[0]
    assert ann_row["event_date"] == D1
    assert ann_row["display_name"] == "Oakley, Ann"
    assert ann_row["score"] == 41
    assert ann_row["gauge"] == "Sub-Gauge"
    assert ann_row["round_type"] == "super_sporting"
    assert bool(ann_row["held"]) is True
    assert ann_row["temp_f"] == 48.0
    assert ann_row["condition"] == "rain"
    assert math.isnan(ann_row["field_median"])
    assert bool(ann_row["is_best_round"]) is False
    bob_row = df[df["shooter_id"] == bob].iloc[0]
    assert bob_row["gauge"] == "unspecified"
    assert bob_row["status"] == "member"
    assert bob_row["shooter_status"] == "deceased"


def test_load_rounds_reads_round_metrics_when_present(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    rid = seed.round(D1, ann, 41)
    seed.finish()
    session.execute(
        text(
            "INSERT INTO round_metrics (round_id, field_median, adjusted, event_rank,"
            " is_best_round, percentile) VALUES (:r, 41, 0, 1, true, 1.0)"
        ),
        {"r": rid},
    )
    seed.bump()

    row = frames.load_rounds(session).iloc[0]

    assert row["event_rank"] == 1.0
    assert bool(row["is_best_round"]) is True


def test_load_events_joins_metrics_and_weather(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.event(D1, head_count=12)
    seed.event(D2, held=False, has_scores=False, head_count=9)
    seed.round(D1, ann, 30)
    seed.weather(D1, temp_f=61.0)
    seed.finish()

    ev = frames.load_events(session)

    assert list(ev.columns) == list(frames.EVENT_COLUMNS)
    assert ev["event_date"].tolist() == [D1, D2]
    assert ev["head_count"].tolist() == [12.0, 9.0]
    assert ev["n_rounds"].tolist() == [1, 0]
    assert ev["results_complete"].tolist() == [True, False]
    assert ev["temp_f"].iloc[0] == 61.0
    assert math.isnan(ev["temp_f"].iloc[1])


def test_load_shooters_and_empty_rating_history(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann", left_censored=True)
    seed.round(D1, ann, 30)
    seed.round(D2, ann, 33)
    seed.finish()

    shooters = frames.load_shooters(session)
    history = frames.load_rating_history(session)

    assert shooters.to_dict(orient="records") == [
        {
            "shooter_id": ann,
            "display_name": "Oakley, Ann",
            "status": "member",
            "first_event": D1,
            "last_event": D2,
            "n_rounds": 2,
            "n_events": 2,
            "left_censored": True,
        },
    ]
    assert list(history.columns) == ["shooter_id", "event_date", "mu", "var"]
    assert history.empty


def test_loaders_are_memoized_until_data_version_changes(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D1, ann, 30)
    seed.finish()
    assert len(frames.load_rounds(session)) == 1

    seed.round(D2, ann, 31)
    session.execute(text("UPDATE events SET n_rounds = 1 WHERE event_date = :d"), {"d": D2})
    assert len(frames.load_rounds(session)) == 1  # same data_version: memo hit

    seed.finish()
    assert len(frames.load_rounds(session)) == 2


def test_load_station_hits_on_committed_fixtures(fx_session: Session) -> None:
    hits = frames.load_station_hits(fx_session)

    assert list(hits.columns) == list(frames.STATION_HIT_COLUMNS)
    assert len(hits) == 259  # (24 + 13) entries x 7 stations
    assert sorted(set(hits["event_date"])) == [D1, D2]
    assert set(hits["round_type"]) == {"super_sporting"}
    hadley = hits[(hits["event_date"] == D2) & (hits["name_key"] == "hadley ike")]
    assert hadley["hits"].sum() == 36
    assert hadley["target_count"].tolist() == [7, 7, 7, 7, 7, 7, 8]


def test_fx_row_counts_match_the_live_tables(fx_session: Session) -> None:
    rounds = frames.load_rounds(fx_session)

    assert len(rounds) == 7480  # every live round: the shooter_profiles join drops none
    assert int(rounds["held"].sum()) == 7473
    assert len(frames.load_events(fx_session)) == 360
