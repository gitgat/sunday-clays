from datetime import date
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.pipeline import discover_steps
from sunday_clays.analytics.steps import s10_metrics
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule

D = date(2026, 9, 13)


def test_s10_is_discovered_at_order_10() -> None:
    steps = {s.name: s.order for s in discover_steps()}
    assert steps["metrics"] == 10


def test_s10_writes_round_and_event_metrics(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    a1 = seed.round(D, ann, 44)
    a2 = seed.round(D, ann, 30)
    b1 = seed.round(D, bob, 42)
    seed.finish()

    s10_metrics.STEP.run(session)

    rows = session.execute(
        text(
            "SELECT round_id, field_median, adjusted, event_rank, is_best_round,"
            " percentile"
            " FROM round_metrics ORDER BY round_id"
        )
    ).all()
    assert [tuple(r) for r in rows] == [
        (a1, 42.0, 2.0, 1, True, 1.0),
        (a2, 42.0, -12.0, None, False, None),
        (b1, 42.0, 0.0, 2, True, 0.0),
    ]
    event = session.execute(
        text("SELECT n, median, mean, top_score, difficulty FROM event_metrics")
    ).one()
    # event_metrics.mean is `real` (float4)
    assert tuple(event) == (3, 42.0, pytest.approx(116 / 3, rel=1e-6), 44, None)


def test_s10_leaves_no_stale_memo(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D, ann, 40)
    seed.finish()
    assert not frames.load_rounds(session)["is_best_round"].any()  # memoized, pre-s10

    # run_pipeline bumps data_version only after all steps, so nothing bumps it here
    s10_metrics.STEP.run(session)

    assert frames.load_rounds(session)["is_best_round"].tolist() == [True]


def test_s10_reads_fresh_rounds_not_a_memoized_frame(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D, ann, 40)
    seed.finish()
    frames.load_rounds(session)  # memoized with one round
    # a live change without a data_version bump (e.g. a memo left by a rolled-back run)
    best = seed.round(D, ann, 45)

    s10_metrics.STEP.run(session)

    rows = session.execute(
        text("SELECT round_id FROM round_metrics WHERE is_best_round ORDER BY round_id")
    ).scalars()
    assert list(rows) == [best]
    assert session.execute(text("SELECT count(*) FROM round_metrics")).scalar_one() == 2


def test_s10_rerun_replaces_rows(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D, ann, 40)
    seed.finish()
    s10_metrics.STEP.run(session)
    s10_metrics.STEP.run(session)
    assert session.execute(text("SELECT count(*) FROM round_metrics")).scalar_one() == 1
    assert session.execute(text("SELECT count(*) FROM event_metrics")).scalar_one() == 1


def test_s10_on_empty_live_tables(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D, ann, 40)
    seed.finish()
    s10_metrics.STEP.run(session)  # a previous run's rows
    # a rebuild with nothing committed empties the live tables (round_metrics via its FK to
    # rounds) but never touches event_metrics: only s10 drops the stale event row
    rebuild_live(session)
    assert session.execute(text("SELECT count(*) FROM rounds")).scalar_one() == 0
    assert session.execute(text("SELECT count(*) FROM event_metrics")).scalar_one() == 1

    s10_metrics.STEP.run(session)

    assert session.execute(text("SELECT count(*) FROM round_metrics")).scalar_one() == 0
    assert session.execute(text("SELECT count(*) FROM event_metrics")).scalar_one() == 0


def test_hide_best_round_promotes_other_round(fx_session: Session) -> None:
    # 2020-03-01: "ackerly alton" shot 48 (ordinal 1) and 43 (ordinal 2); 40 shooters.
    create_rule(
        fx_session,
        RuleType.HIDE_ROUND,
        {"event_date": "2020-03-01", "name_key": "ackerly alton", "ordinal": 1},
        "test: hide best round",
    )
    rebuild_live(fx_session)

    s10_metrics.STEP.run(fx_session)

    rows = fx_session.execute(
        text(
            "SELECT r.ordinal, r.score, m.is_best_round, m.event_rank FROM rounds r"
            " JOIN round_metrics m ON m.round_id = r.id"
            " WHERE r.event_date = '2020-03-01' AND r.name_key = 'ackerly alton'"
        )
    ).all()
    assert [tuple(r) for r in rows] == [(2, 43, True, 5)]
    leader = fx_session.execute(
        text(
            "SELECT r.name_key FROM rounds r JOIN round_metrics m ON m.round_id = r.id"
            " WHERE r.event_date = '2020-03-01' AND m.event_rank = 1"
        )
    ).scalar_one()
    assert leader == "hamlin ethan"
