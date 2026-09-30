import json
import math
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, skill
from sunday_clays.analytics.pipeline import discover_steps
from sunday_clays.analytics.steps import s10_metrics, s30_skill
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.jobs.handlers import load_handlers

D1 = date(2026, 9, 6)
D2 = date(2026, 9, 13)


def _seed_two_events(seed: Any) -> tuple[int, int]:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    for d, a, b in ((D1, 40, 30), (D2, 42, 29)):
        seed.round(d, ann, a)
        seed.round(d, bob, b)
    seed.finish()
    return ann, bob


def _seed_past_burn_in(seed: Any, held_events: int = skill.BURN_IN_HELD_EVENTS + 1) -> None:
    """`held_events` weekly held events for two shooters, the last on D2. The default,
    BURN_IN_HELD_EVENTS + 1 (= 9, Sundays 2026-07-19 .. 2026-09-13), is the fewest that
    lets calibration score an event (the last one)."""
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    first = D2 - timedelta(weeks=held_events - 1)
    for k in range(held_events):
        d = first + timedelta(weeks=k)
        seed.round(d, ann, 40 + k % 3)
        seed.round(d, bob, 30 - k % 2)
    seed.finish()


def _stored_params(session: Session) -> object:
    return session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_params'")
    ).scalar_one_or_none()


def _skill_level(session: Session) -> object:
    return session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_level'")
    ).scalar_one()


def _history_count(session: Session) -> int:
    return int(session.execute(text("SELECT count(*) FROM rating_history")).scalar_one())


def _no_calibration(*args: object, **kwargs: object) -> skill.SkillParams:
    raise AssertionError("calibrate must not run when skill_params is stored")


def test_s30_is_discovered_after_s10() -> None:
    orders = {s.name: s.order for s in discover_steps()}
    assert orders["metrics"] < orders["skill"] == 30


def test_s30_uses_stored_params_without_calibrating(
    seed: Any, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_two_events(seed)
    s30_skill.store_state(
        session, "skill_params", asdict(skill.SkillParams(prior_var=36.0, max_var=36.0))
    )
    monkeypatch.setattr(skill, "calibrate", _no_calibration)

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    first_vars = (
        session.execute(
            text(
                "SELECT m.var_before FROM round_metrics m"
                " JOIN rounds r ON r.id = m.round_id"
                " WHERE r.event_date = :d"
            ),
            {"d": D1},
        )
        .scalars()
        .all()
    )
    assert first_vars == [36.0, 36.0]  # new shooters start at the stored prior_var


@pytest.mark.parametrize(
    ("held_events", "stored"),
    [
        # Exactly the burn-in: every grid point ties at 0.0, so nothing is persisted.
        pytest.param(skill.BURN_IN_HELD_EVENTS, False, id="burn-in-only"),
        pytest.param(skill.BURN_IN_HELD_EVENTS + 1, True, id="one-past-burn-in"),
    ],
)
def test_s30_calibrates_when_absent_and_stores_only_past_the_burn_in(
    seed: Any,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    held_events: int,
    stored: bool,
) -> None:
    _seed_past_burn_in(seed, held_events)
    # One grid point that differs from SkillParams() in three fields, so the stored
    # value can only have come from calibrate() over the patched CALIBRATION_GRID.
    grid = {
        "obs_var": (12.0,),
        "drift_var_per_week": (0.05,),
        "difficulty_var": (2.0,),
        "prior_mu": (30.0,),
        "prior_var": (49.0,),
    }
    monkeypatch.setattr(skill, "CALIBRATION_GRID", grid)

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    calibrated = skill.SkillParams(obs_var=12.0, drift_var_per_week=0.05, difficulty_var=2.0)
    assert _stored_params(session) == (asdict(calibrated) if stored else None)
    assert _history_count(session) == 2 * held_events  # the run completed either way


def test_s30_does_not_store_params_from_burn_in_only_data(seed: Any, session: Session) -> None:
    # 2 held events are all burn-in: every grid point scores 0.0, so the calibrated
    # point is arbitrary and must not be persisted for later runs.
    _seed_two_events(seed)

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    assert _stored_params(session) is None
    level = session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_level'")
    ).scalar_one()
    assert isinstance(level, float)


def test_incomplete_stored_params_trigger_calibration(
    seed: Any, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_past_burn_in(seed)
    s30_skill.store_state(session, "skill_params", {"obs_var": 10.0})
    monkeypatch.setattr(skill, "CALIBRATION_GRID", {**skill.CALIBRATION_GRID, "obs_var": (16.0,)})

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    stored = _stored_params(session)
    assert isinstance(stored, dict)
    assert stored["obs_var"] == 16.0
    assert set(stored) == set(asdict(skill.SkillParams()))  # overwritten in full


def test_invalid_stored_params_trigger_calibration(
    seed: Any, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Complete, but SkillParams rejects it (ValueError): treated exactly like incomplete.
    _seed_past_burn_in(seed)
    s30_skill.store_state(
        session, "skill_params", {**asdict(skill.SkillParams()), "difficulty_var": -4.0}
    )
    monkeypatch.setattr(
        skill, "CALIBRATION_GRID", {**skill.CALIBRATION_GRID, "difficulty_var": (9.0,)}
    )

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    stored = _stored_params(session)
    assert isinstance(stored, dict)
    assert stored["difficulty_var"] == 9.0
    assert skill.SkillParams(**stored).difficulty_var == 9.0  # a valid value replaced it


def test_invalid_stored_params_with_burn_in_only_data_are_left_as_is(
    seed: Any, session: Session
) -> None:
    # Like incomplete params: this run calibrates, but nothing is stored before the burn-in.
    _seed_two_events(seed)
    invalid = {**asdict(skill.SkillParams()), "obs_var": 0.0}
    s30_skill.store_state(session, "skill_params", invalid)

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    assert _stored_params(session) == invalid
    assert _history_count(session) == 4  # the run still completed with calibrated params


def test_recompute_job_with_recalibrate_stores_a_grid_point(seed: Any, session: Session) -> None:
    # The C6 handler end to end with the real pipeline (s10, s20, s30), no stubs.
    _seed_past_burn_in(seed)
    off_grid = skill.SkillParams(obs_var=20.0, prior_mu=28.0, prior_var=36.0, max_var=36.0)
    assert off_grid.obs_var not in skill.CALIBRATION_GRID["obs_var"]
    s30_skill.store_state(session, "skill_params", asdict(off_grid))
    recompute = load_handlers()["recompute"]

    recompute(session, {})
    assert s30_skill.load_params(session) == off_grid  # a plain recompute keeps them

    recompute(session, {"recalibrate": True})

    stored = _stored_params(session)
    assert isinstance(stored, dict)
    params = skill.SkillParams(**stored)
    for key in skill.GRID_KEYS:
        assert getattr(params, key) in skill.CALIBRATION_GRID[key]
    assert params.max_var == params.prior_var
    assert _history_count(session) == 2 * (skill.BURN_IN_HELD_EVENTS + 1)


VALID = asdict(skill.SkillParams())


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param([1, 2], id="not-an-object"),
        pytest.param(30.0, id="a-number"),
        pytest.param({k: v for k, v in VALID.items() if k != "max_var"}, id="missing-field"),
        pytest.param({**VALID, "obs_var": None}, id="null-field"),
        pytest.param({**VALID, "obs_var": "14"}, id="string-field"),
        pytest.param({**VALID, "obs_var": True}, id="boolean-field"),
        pytest.param({**VALID, "prior_var": -49.0}, id="negative-variance"),
        pytest.param({**VALID, "drift_var_per_week": -0.3}, id="negative-drift"),
        pytest.param({**VALID, "obs_var": 10**400}, id="overflows-float"),
    ],
)
def test_load_params_treats_unusable_values_as_absent(session: Session, stored: object) -> None:
    s30_skill.store_state(session, "skill_params", stored)
    assert s30_skill.load_params(session) is None


# Past float range with a fractional part: json.loads gives inf rather than an int that
# float() rejects with OverflowError (the overflows-float case above).
HUGE = "1" + "0" * 400 + ".5"


@pytest.mark.parametrize(
    ("field", "number"),
    [
        pytest.param("prior_mu", HUGE, id="inf-mean"),  # SkillParams does not bound prior_mu
        pytest.param("obs_var", HUGE, id="inf-variance"),  # inf > 0 passes validation
        pytest.param("prior_mu", "-" + HUGE, id="minus-inf-mean"),
    ],
)
def test_load_params_treats_non_finite_numbers_as_absent(
    session: Session, field: str, number: str
) -> None:
    assert not math.isfinite(json.loads(number))
    members = (f'"{k}": {number if k == field else json.dumps(v)}' for k, v in VALID.items())
    session.execute(
        text("INSERT INTO app_state (key, value) VALUES ('skill_params', CAST(:v AS jsonb))"),
        {"v": "{" + ", ".join(members) + "}"},
    )
    stored = _stored_params(session)
    assert isinstance(stored, dict)
    assert not math.isfinite(stored[field])  # what load_params reads back from jsonb

    assert s30_skill.load_params(session) is None


def test_load_params_reads_complete_values(session: Session) -> None:
    assert s30_skill.load_params(session) is None  # absent
    s30_skill.store_state(
        session, "skill_params", {**VALID, "obs_var": 12, "prior_mu": 28, "extra": "kept"}
    )
    params = s30_skill.load_params(session)
    assert params == skill.SkillParams(obs_var=12.0, prior_mu=28.0)
    assert params is not None
    assert isinstance(params.obs_var, float)


def test_s30_writes_history_difficulty_and_level(seed: Any, session: Session) -> None:
    ann, bob = _seed_two_events(seed)

    seed.analyze()

    history = session.execute(
        text("SELECT shooter_id, event_date FROM rating_history ORDER BY event_date, shooter_id")
    ).all()
    assert [tuple(h) for h in history] == [(ann, D1), (bob, D1), (ann, D2), (bob, D2)]
    difficulty = dict(
        session.execute(text("SELECT event_date, difficulty FROM event_metrics")).all()
    )
    assert difficulty[D1] == pytest.approx(0.0, abs=1e-6)  # level = the only day's d
    level = session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_level'")
    ).scalar_one()
    assert isinstance(level, float)
    missing = session.execute(
        text("SELECT count(*) FROM round_metrics WHERE expected IS NULL OR mu_after IS NULL")
    ).scalar_one()
    assert missing == 0


def test_s30_published_values_match_the_model(seed: Any, session: Session) -> None:
    _seed_two_events(seed)

    seed.analyze()

    result = skill.run_skill_model(frames.load_rounds(session), skill.SkillParams())
    history = session.execute(
        text("SELECT shooter_id, event_date, mu, var FROM rating_history")
    ).all()
    expected_history = {
        (int(r.shooter_id), r.event_date): (r.mu, r.var) for r in result.history.itertuples()
    }
    assert {(h.shooter_id, h.event_date): (h.mu, h.var) for h in history} == {
        key: (pytest.approx(mu, rel=1e-6), pytest.approx(var, rel=1e-6))
        for key, (mu, var) in expected_history.items()
    }
    difficulty = dict(
        session.execute(text("SELECT event_date, difficulty FROM event_metrics")).all()
    )
    assert difficulty == {
        e.event_date: pytest.approx(e.difficulty, rel=1e-6, abs=1e-6)
        for e in result.events.itertuples()
    }
    assert _skill_level(session) == pytest.approx(result.current_level, rel=1e-12)
    # Every skill column by value, so a swapped SET (mu_before <-> mu_after,
    # expected <-> residual) fails here; Task 5's rating_delta reads these directly.
    columns = ("expected", "residual", "mu_before", "var_before", "mu_after", "var_after")
    assert columns == skill.ROUND_OUTPUT_COLUMNS[1:]
    stored_rounds = session.execute(
        text(
            "SELECT round_id, expected, residual, mu_before, var_before, mu_after, var_after"
            " FROM round_metrics"
        )
    ).all()
    assert {r.round_id: tuple(r[1:]) for r in stored_rounds} == {
        int(r.round_id): tuple(pytest.approx(getattr(r, c), rel=1e-6, abs=1e-6) for c in columns)
        for r in result.rounds.itertuples()
    }


def test_s30_non_held_event_carries_rating_forward(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    seed.event(D2, held=False)
    for d, a, b in ((D1, 40, 30), (D2, 42, 29)):
        seed.round(d, ann, a)
        seed.round(d, bob, b)
    seed.finish()

    seed.analyze()

    rows = session.execute(
        text(
            "SELECT m.expected, m.residual, m.mu_before, m.mu_after, m.var_before, m.var_after"
            " FROM round_metrics m JOIN rounds r ON r.id = m.round_id"
            " WHERE r.event_date = :d"
        ),
        {"d": D2},
    ).all()
    assert len(rows) == 2
    for expected, residual, mu_before, mu_after, var_before, var_after in rows:
        assert (expected, residual) == (None, None)
        assert (mu_before, var_before) == (mu_after, var_after)
    difficulty = dict(
        session.execute(text("SELECT event_date, difficulty FROM event_metrics")).all()
    )
    assert difficulty[D2] is None
    mus = session.execute(
        text("SELECT event_date, mu FROM rating_history WHERE shooter_id = :s ORDER BY event_date"),
        {"s": ann},
    ).all()
    assert [m.event_date for m in mus] == [D1, D2]
    assert mus[1].mu == mus[0].mu  # no update at a non-held event


def test_s30_leaves_no_stale_memo(seed: Any, session: Session) -> None:
    _seed_two_events(seed)
    s30_skill.store_state(session, "skill_params", asdict(skill.SkillParams()))
    s10_metrics.STEP.run(session)
    assert frames.load_rounds(session)["mu_before"].isna().all()  # memoized, pre-s30

    s30_skill.STEP.run(session)  # a later step (e.g. s50) must see the skill columns

    assert frames.load_rounds(session)["mu_before"].notna().all()


def test_s30_reads_fresh_rounds_not_a_memoized_frame(seed: Any, session: Session) -> None:
    _, bob = _seed_two_events(seed)
    s30_skill.store_state(session, "skill_params", asdict(skill.SkillParams()))
    s10_metrics.STEP.run(session)
    frames.load_rounds(session)  # memoized with two events
    d3 = D2 + timedelta(weeks=1)
    seed.round(d3, bob, 31)  # a live change without a data_version bump

    s30_skill.STEP.run(session)

    dates = (
        session.execute(
            text("SELECT event_date FROM rating_history WHERE shooter_id = :s ORDER BY 1"),
            {"s": bob},
        )
        .scalars()
        .all()
    )
    assert dates == [D1, D2, d3]


def test_s30_rerun_replaces_history_and_empty_run_clears_it(seed: Any, session: Session) -> None:
    _seed_two_events(seed)
    seed.analyze()
    seed.analyze()  # a rerun replaces every row (no primary-key clash)
    assert _history_count(session) == 4

    rebuild_live(session)  # nothing committed: live tables empty, rating_history untouched
    assert _history_count(session) == 4
    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    assert _history_count(session) == 0
    assert _skill_level(session) == 0.0


def test_s30_on_empty_live_tables(session: Session) -> None:
    s30_skill.store_state(session, "skill_params", asdict(skill.SkillParams()))
    s30_skill.STEP.run(session)
    level = session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_level'")
    ).scalar_one()
    assert level == 0.0


def test_fx_pipeline_calibrates_on_the_real_fixture(fx_session: Session) -> None:
    # fx_engine ran rebuild_live + run_pipeline with no stored params, so s30 calibrated
    # over CALIBRATION_GRID and, with far more than 8 held events, stored the result.
    # Golden: SkillParams() but difficulty_var 4 -> 2. Later fx goldens (Tasks 5-9)
    # depend on it, so a calibration drift fails here first, where the cause is plain.
    assert _stored_params(fx_session) == asdict(skill.SkillParams(difficulty_var=2.0))
    assert isinstance(_skill_level(fx_session), float)
    # one rating_history row per attended (shooter, event); NULL skill fields exactly at
    # non-held events
    attended = fx_session.execute(
        text("SELECT count(*) FROM (SELECT DISTINCT shooter_id, event_date FROM rounds) a")
    ).scalar_one()
    assert _history_count(fx_session) == attended
    mismatched = fx_session.execute(
        text(
            "SELECT count(*) FROM rounds r JOIN events e ON e.event_date = r.event_date"
            " JOIN round_metrics m ON m.round_id = r.id"
            " WHERE (m.expected IS NULL) = e.results_complete OR m.mu_after IS NULL"
        )
    ).scalar_one()
    assert mismatched == 0
    difficulty_mismatch = fx_session.execute(
        text(
            "SELECT count(*) FROM event_metrics m JOIN events e ON e.event_date = m.event_date"
            " WHERE (m.difficulty IS NULL) = e.results_complete"
        )
    ).scalar_one()
    assert difficulty_mismatch == 0
