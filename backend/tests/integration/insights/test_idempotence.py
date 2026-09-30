"""Idempotence (spec §5, D5): recomputing on unchanged data rewrites identical content."""

from __future__ import annotations

from sqlalchemy import text

from sunday_clays.analytics.insights.store import get_new_since, load_rows, set_new_since
from sunday_clays.analytics.pipeline import get_data_version, run_pipeline
from sunday_clays.jobs import rebuild_handler
from sunday_clays.jobs.handlers import handle_recompute

CONTENT = (
    "SELECT key, headline, headline_you, template_id, params, chart, first_generation, "
    "generation FROM insights ORDER BY key"
)


def test_a_second_run_changes_nothing_but_the_generation(fx_session):
    before = fx_session.execute(text(CONTENT)).all()
    run_pipeline(fx_session)
    after = fx_session.execute(text(CONTENT)).all()
    assert [r[:6] for r in after] == [r[:6] for r in before]
    assert [r.first_generation for r in after] == [r.first_generation for r in before]
    assert all(r.generation == before[0].generation + 1 for r in after)
    new = fx_session.scalar(
        text("SELECT count(*) FROM insights WHERE first_generation = generation")
    )
    assert new == 0  # nothing is "New" after an unchanged recompute


def test_a_changed_row_is_the_only_new_one(fx_session):
    key = fx_session.scalar(
        text("SELECT key FROM insights WHERE kind = 'pf.digest-line' ORDER BY key LIMIT 1")
    )
    fx_session.execute(text("UPDATE insights SET value_hash = 'stale' WHERE key = :k"), {"k": key})
    run_pipeline(fx_session)
    new = fx_session.scalars(
        text("SELECT key FROM insights WHERE first_generation = generation")
    ).all()
    assert new == [key]


def _new_keys(session) -> set[str]:
    since = get_new_since(session)
    return {r.key for r in load_rows(session) if r.is_new_since(since)}


def test_a_weather_only_recompute_keeps_the_uploads_new_rows(fx_session):
    """The `recompute` a weather sync enqueues after an upload must not clear "New" (I-1)."""
    set_new_since(fx_session, get_data_version(fx_session) + 1)
    key = fx_session.scalar(
        text("SELECT key FROM insights WHERE kind = 'pf.digest-line' ORDER BY key LIMIT 1")
    )
    fx_session.execute(text("UPDATE insights SET value_hash = 'stale' WHERE key = :k"), {"k": key})
    run_pipeline(fx_session)  # the upload's own run: only the changed row is New
    before = fx_session.execute(text(CONTENT)).all()
    new_before = _new_keys(fx_session)
    assert new_before == {key}

    handle_recompute(fx_session, {})  # weather sync, later
    after = fx_session.execute(text(CONTENT)).all()
    assert [r[:6] for r in after] == [r[:6] for r in before]
    assert [r.first_generation for r in after] == [r.first_generation for r in before]
    assert _new_keys(fx_session) == new_before


def test_a_second_upload_makes_only_its_own_changes_new(fx_session):
    set_new_since(fx_session, get_data_version(fx_session) + 1)
    run_pipeline(fx_session)
    handle_recompute(fx_session, {})
    keys = fx_session.scalars(
        text("SELECT key FROM insights WHERE kind = 'pf.digest-line' ORDER BY key LIMIT 2")
    ).all()
    fx_session.execute(
        text("UPDATE insights SET value_hash = 'stale' WHERE key = :k"), {"k": keys[1]}
    )
    set_new_since(fx_session, get_data_version(fx_session) + 1)  # what handle_rebuild does
    run_pipeline(fx_session)
    assert _new_keys(fx_session) == {keys[1]}


def test_handle_rebuild_records_the_generation_its_pipeline_run_writes(fx_session, monkeypatch):
    seen: dict[str, int] = {}
    monkeypatch.setattr(rebuild_handler, "rebuild_live", lambda s: None)
    monkeypatch.setattr(
        rebuild_handler,
        "run_pipeline",
        lambda s: seen.update(since=get_new_since(s) or -1, version=get_data_version(s)),
    )
    rebuild_handler.handle_rebuild(fx_session, {})
    assert seen["since"] == seen["version"] + 1
