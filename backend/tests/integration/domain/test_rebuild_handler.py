from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.domain.imports import stage_import
from sunday_clays.jobs import rebuild_handler
from sunday_clays.jobs.handlers import load_handlers
from sunday_clays.models import Event, EventWeather, Job

D1 = date(2026, 9, 6)


def test_rebuild_job_rebuilds_recomputes_and_requests_weather(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    mark_committed(
        session,
        stage_import(session, scores_workbook([("Hadley, Ike", 35, D1)]), "s.xlsx").import_id,
    )
    before = get_data_version(session)
    load_handlers()["rebuild"](session, {})
    assert session.scalars(select(Event.event_date)).all() == [D1]
    assert get_data_version(session) == before + 2  # rebuild_live, then run_pipeline
    jobs = session.execute(select(Job.kind, Job.status, Job.dedupe_key)).all()
    assert jobs == [("weather_sync", "queued", "weather_sync")]


def test_rebuild_job_skips_weather_when_every_event_has_weather(
    session: Session,
    scores_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_committed(
        session,
        stage_import(session, scores_workbook([("Hadley, Ike", 35, D1)]), "s.xlsx").import_id,
    )
    session.add(EventWeather(event_date=D1, condition="clear", source="archive"))
    session.flush()
    # Later plans add recompute steps that rewrite event_weather; keep this test about the handler.
    monkeypatch.setattr(rebuild_handler, "run_pipeline", lambda s: [])
    load_handlers()["rebuild"](session, {})
    assert session.scalars(select(Job)).all() == []
