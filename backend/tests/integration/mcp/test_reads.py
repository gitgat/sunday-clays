"""MCP read queries, called directly on the fixture-world database."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.mcp.reads import find_shooters, get_event, get_job
from sunday_clays.mcp.schemas import EventSummary, JobStatus, NoEvent, NotFound, OperationStatus
from sunday_clays.models import Event, Job, McpOperation, Round, Shooter, ShooterAlias
from sunday_clays.models.live import StationLayout


def _busiest(session: Session) -> Shooter:
    row = session.execute(
        select(Shooter, func.count(Round.id))
        .join(Round, Round.shooter_id == Shooter.id)
        .group_by(Shooter.id)
        .order_by(func.count(Round.id).desc(), Shooter.id)
        .limit(1)
    ).one()
    return row[0]


def _last_first(shooter: Shooter) -> tuple[str, str]:
    last, first = (part.strip() for part in shooter.display_name.split(",", 1))
    return last, first


def test_find_shooters_tokens_any_order(fx_session: Session) -> None:
    shooter = _busiest(fx_session)
    last, first = _last_first(shooter)
    for query in (f"{first} {last}", f"{last.upper()} {first.lower()}", last):
        hits = find_shooters(fx_session, query)
        assert shooter.display_name in [hit.display_name for hit in hits]
    top = find_shooters(fx_session, f"{first} {last}")[0]
    assert top.display_name == shooter.display_name
    assert top.rounds > 0
    assert top.last_shot is not None


@pytest.mark.parametrize("query", ["%", "_", ".*", "\\"])
def test_find_shooters_literal_wildcards(fx_session: Session, query: str) -> None:
    assert find_shooters(fx_session, query) == []


def test_find_shooters_limit_and_order(fx_session: Session) -> None:
    shooter = _busiest(fx_session)
    last, _ = _last_first(shooter)
    letter = last[0]
    hits = find_shooters(fx_session, letter, limit=3)
    assert len(hits) == 3
    assert find_shooters(fx_session, letter, limit=1) == hits[:1]
    # word-prefix matches come first, then rounds descending
    prefix = [
        h
        for h in hits
        if any(
            w.lower().startswith(letter.lower()) for w in h.display_name.replace(",", " ").split()
        )
    ]
    assert prefix == hits
    assert [h.rounds for h in hits] == sorted((h.rounds for h in hits), reverse=True)


def test_find_shooters_prefix_beats_rounds(fx_session: Session) -> None:
    shooter = _busiest(fx_session)
    last, _ = _last_first(shooter)
    inner = last[1:3].lower()  # a mid-word fragment: matches, but not as a word prefix
    hits = find_shooters(fx_session, inner, limit=50)
    flags = [
        any(w.lower().startswith(inner) for w in h.display_name.replace(",", " ").split())
        for h in hits
    ]
    assert flags == sorted(flags, reverse=True)


def test_find_shooters_alias(fx_session: Session) -> None:
    shooter = _busiest(fx_session)
    fx_session.add(ShooterAlias(name_key="zzqx nickname", shooter_id=shooter.id))
    fx_session.flush()
    hits = find_shooters(fx_session, "nickname zzqx")
    assert [h.display_name for h in hits] == [shooter.display_name]


def test_get_event_summary(fx_session: Session) -> None:
    with_stations = select(StationLayout.event_date)
    event = fx_session.scalars(
        select(Event).where(Event.event_date.in_(with_stations)).order_by(Event.event_date.desc())
    ).first()
    assert event is not None
    result = get_event(fx_session, event.event_date)
    assert isinstance(result, EventSummary)
    expected = fx_session.scalar(
        select(func.sum(Round.score)).where(Round.event_date == event.event_date)
    )
    assert result.score_sum == expected
    assert result.head_count == event.head_count
    assert result.round_type == event.round_type
    assert result.target_total == event.target_total
    assert result.n_rounds == fx_session.scalar(
        select(func.count(Round.id)).where(Round.event_date == event.event_date)
    )
    assert result.average == pytest.approx(expected / result.n_rounds, abs=0.01)
    assert result.stations
    assert result.rows is None
    assert "rows" not in result.model_dump(mode="json", exclude_none=True)
    with_rows = get_event(fx_session, event.event_date, include_rows=True)
    assert isinstance(with_rows, EventSummary)
    assert with_rows.rows is not None
    assert len(with_rows.rows) == result.n_rounds
    assert sum(r.score for r in with_rows.rows) == expected


def test_get_event_thrown_out(fx_thrown_out_session: Session) -> None:
    dropped = fx_thrown_out_session.scalars(
        select(StationLayout).where(StationLayout.dropped)
    ).one()
    result = get_event(fx_thrown_out_session, dropped.event_date)
    assert isinstance(result, EventSummary)
    assert result.stats_excluded is True
    by_label = {s.label: s for s in result.stations}
    assert by_label[dropped.station_label].dropped is True
    assert [s.label for s in result.stations if s.dropped] == [dropped.station_label]


def test_get_event_missing_date(fx_session: Session) -> None:
    last = fx_session.scalar(select(func.max(Event.event_date)))
    assert last is not None
    for missing in (last + timedelta(days=7), last + timedelta(days=1), date(1999, 1, 3)):
        result = get_event(fx_session, missing)
        assert isinstance(result, NoEvent)
        assert result.found is False
        assert result.last_event_date == last
        assert result.date == missing


def test_get_job(fx_session: Session) -> None:
    job = Job(kind="import", payload={"x": 1})
    fx_session.add(job)
    fx_session.flush()
    found = get_job(fx_session, job.id)
    assert isinstance(found, JobStatus)
    assert (found.id, found.kind, found.status) == (job.id, "import", "queued")
    assert found.finished_at is None
    assert found.error is None
    assert found.created_at is not None
    assert "payload" not in found.model_dump()
    missing = get_job(fx_session, job.id + 10_000)
    assert isinstance(missing, NotFound)
    assert missing.found is False


def test_get_job_by_preview_id(fx_session: Session) -> None:
    op = McpOperation(kind="week", event_date=date(2026, 11, 1), status="previewed", caller="t")
    fx_session.add(op)
    fx_session.flush()
    found = get_job(fx_session, op.id)
    assert isinstance(found, OperationStatus)
    assert (found.preview_id, found.kind, found.status) == (op.id, "week", "previewed")
    assert found.event_date == date(2026, 11, 1)
    assert found.commit_path is None
    assert found.created_at is not None
    assert "caller" not in found.model_dump()
    assert "result" not in found.model_dump()


def test_get_job_unknown_uuid_not_found(fx_session: Session) -> None:
    missing = get_job(fx_session, uuid4())
    assert isinstance(missing, NotFound)
    assert missing.found is False


def test_find_shooters_alias_date_suffix_not_searchable(fx_session: Session) -> None:
    shooter = _busiest(fx_session)
    fx_session.add(ShooterAlias(name_key="zzqx@2026-09-27", shooter_id=shooter.id))
    fx_session.flush()
    for query in ("@", "2026-09", "-27", "zzqx@2026"):
        names = [h.display_name for h in find_shooters(fx_session, query, limit=25)]
        assert shooter.display_name not in names
    assert [h.display_name for h in find_shooters(fx_session, "zzqx")] == [shooter.display_name]


def test_find_shooters_commas_ignored(fx_session: Session) -> None:
    shooter = _busiest(fx_session)
    last, first = _last_first(shooter)
    hits = find_shooters(fx_session, f"{last}, {first}")
    assert hits[0].display_name == shooter.display_name
    fx_session.add(ShooterAlias(name_key="zzqx nickname", shooter_id=shooter.id))
    fx_session.flush()
    assert [h.display_name for h in find_shooters(fx_session, "zzqx, nickname")] == [
        shooter.display_name
    ]
    assert find_shooters(fx_session, ",") == []


def test_find_shooters_with_no_rounds_anywhere_has_no_usual_status(session: Session) -> None:
    assert session.scalar(select(func.count(Round.id))) == 0
    session.add(Shooter(display_name="Nobody, Newcomer"))
    session.flush()

    hits = find_shooters(session, "newcomer")

    assert [(h.display_name, h.rounds, h.usual_status) for h in hits] == [
        ("Nobody, Newcomer", 0, None)
    ]
