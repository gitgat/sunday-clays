"""preview_week / preview_correction logic on the fixture-world database."""

import datetime as dt
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.mcp import writes
from sunday_clays.mcp.build import CorrectionInput, WeekInput
from sunday_clays.mcp.writes import Refusal
from sunday_clays.models import AuditLog, Event, Import, McpOperation, Round, Shooter

NEXT_SUNDAY = dt.date(2026, 10, 4)  # the fixture's last event is 2026-09-27
NOW = dt.datetime(2026, 10, 6, 18, 0, tzinfo=dt.UTC)  # Tuesday, inside the 14-day window
TTL = dt.timedelta(hours=1)


def _week(**over: Any) -> WeekInput:
    data: dict[str, Any] = {
        "date": NEXT_SUNDAY,
        "stations": ["1", "2", "3", "4", "5"],
        "counts": [10, 10, 10, 10, 10],
        "shooters": [
            {
                "name": "Testshooter, Alpha",
                "score": 45,
                "status": "Member",
                "class": "12 Gauge",
                "hits": [9, 9, 9, 9, 9],
            },
            {"name": "Testshooter, Beta", "score": 30, "status": "Guest"},
        ],
    }
    data.update(over)
    return WeekInput.model_validate(data)


def _last_event(session: Session) -> dt.date:
    last = session.scalar(select(func.max(Event.event_date)))
    assert last is not None
    return last


def _names_on_last(session: Session, n: int) -> list[str]:
    return list(
        session.scalars(
            select(Shooter.display_name)
            .join(Round, Round.shooter_id == Shooter.id)
            .where(Round.event_date == _last_event(session))
            .order_by(Shooter.display_name)
            .limit(n)
        )
    )


def _pending(session: Session) -> int:
    return session.scalar(select(func.count(Import.id)).where(Import.status == "pending")) or 0


def _refused(session: Session) -> list[McpOperation]:
    return list(session.scalars(select(McpOperation).where(McpOperation.status == "refused")))


def _assert_refused(session: Session, code: str) -> None:
    assert _pending(session) == 0
    rows = _refused(session)
    assert [r.result["code"] for r in rows] == [code]
    audits = session.scalars(select(AuditLog).where(AuditLog.action == "mcp.refuse")).all()
    assert len(audits) == 1
    assert audits[0].role == "mcp"


def test_fixture_last_event_is_what_the_tests_assume(fx_session: Session) -> None:
    assert _last_event(fx_session) == NEXT_SUNDAY - dt.timedelta(days=7)


def test_week_happy_path(fx_session: Session) -> None:
    out = writes.preview_week(fx_session, _week(), now=NOW)
    assert list(out.model_dump()) == [
        "date",
        "head_count",
        "score_sum",
        "average",
        "new_names",
        "possible_duplicates",
        "findings_for_date",
        "historical_findings",
        "preview_id",
        "expires_at",
        "note",
    ]
    assert (out.head_count, out.score_sum, out.average) == (2, 75, 37.5)
    assert sorted(out.new_names) == ["Testshooter, Alpha", "Testshooter, Beta"]
    assert out.expires_at == NOW + TTL
    assert out.note is None
    # Only findings about the previewed Sunday are listed; old noise is just a count.
    assert all(f.event_date == NEXT_SUNDAY for f in out.findings_for_date)
    assert out.historical_findings >= 1
    op = fx_session.get(McpOperation, out.preview_id)
    assert op is not None
    assert (op.kind, op.status, op.event_date) == ("week", "previewed", NEXT_SUNDAY)
    assert op.scores_import_id is not None
    assert op.stations_import_id is not None  # one card had hits
    assert _pending(fx_session) == 2
    assert (
        fx_session.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "mcp.preview"))
        == 1
    )


def test_week_without_hits_stages_scores_only(fx_session: Session) -> None:
    week = _week(
        shooters=[{"name": "Testshooter, Beta", "score": 30, "status": "Guest"}],
    )
    out = writes.preview_week(fx_session, week, now=NOW)
    op = fx_session.get(McpOperation, out.preview_id)
    assert op is not None
    assert op.stations_import_id is None
    assert _pending(fx_session) == 1


def test_many_new_names_adds_a_note(fx_session: Session) -> None:
    rows = [{"name": f"Testshooter, Name{c}", "score": 20, "status": "Guest"} for c in "ABCD"]
    out = writes.preview_week(fx_session, _week(shooters=rows), now=NOW)
    assert out.note is not None
    assert "find_shooters" in out.note


@pytest.mark.parametrize(
    ("date", "now", "code"),
    [
        (dt.date(2026, 10, 5), NOW, "not_sunday"),
        (dt.date(2026, 9, 27), NOW, "not_after_last_event"),
        (dt.date(2026, 9, 20), NOW, "not_after_last_event"),
        (dt.date(2026, 10, 4), dt.datetime(2026, 10, 19, 8, 0, tzinfo=dt.UTC), "too_old"),
    ],
)
def test_date_rule_refusals(
    fx_session: Session, date: dt.date, now: dt.datetime, code: str
) -> None:
    with pytest.raises(Refusal) as exc:
        writes.preview_week(fx_session, _week(date=date), now=now)
    assert exc.value.code == code
    _assert_refused(fx_session, code)


def test_fourteen_day_rule_uses_los_angeles_time(fx_session: Session) -> None:
    # 2026-10-19 06:00 UTC is still Sunday 10-18 in Los Angeles (14 days after 10-04): allowed.
    # 08:00 UTC is Monday 10-19 there (15 days): refused, though UTC was already the 19th at 06:00.
    ok = dt.datetime(2026, 10, 19, 6, 0, tzinfo=dt.UTC)
    writes.preview_week(fx_session, _week(), now=ok)
    late = dt.datetime(2026, 10, 19, 8, 0, tzinfo=dt.UTC)
    with pytest.raises(Refusal) as exc:
        writes.preview_week(
            fx_session,
            _week(shooters=[{"name": "Testshooter, Beta", "score": 30, "status": "Guest"}]),
            now=late,
        )
    assert exc.value.code == "too_old"


def test_date_has_rounds(fx_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    # Rounds cannot exist past the last event (a foreign key), so the guard is a backstop: make
    # the "latest event" look older than the stored Sunday to reach it.
    monkeypatch.setattr(writes, "_last_event", lambda session: dt.date(2026, 9, 20))
    stored = dt.date(2026, 9, 27)
    with pytest.raises(Refusal) as exc:
        writes.preview_week(fx_session, _week(date=stored), now=NOW)
    assert exc.value.code == "date_has_rounds"
    _assert_refused(fx_session, "date_has_rounds")


def test_no_base(session: Session) -> None:
    with pytest.raises(Refusal) as exc:
        writes.preview_week(session, _week(), now=NOW)
    assert exc.value.code == "no_base"
    _assert_refused(session, "no_base")


def test_not_append_only_discards_both_imports(
    fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = writes.build_scores

    def changed(base: bytes, week: WeekInput) -> bytes:
        import io

        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(real(base, week)))
        ws = wb["ALL SCORE DETAIL"]
        ws.cell(2, 2).value = 1 if ws.cell(2, 2).value != 1 else 2  # alter a stored score
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    monkeypatch.setattr(writes, "build_scores", changed)
    with pytest.raises(Refusal) as exc:
        writes.preview_week(fx_session, _week(), now=NOW)
    assert exc.value.code == "not_append_only"
    _assert_refused(fx_session, "not_append_only")
    discarded = fx_session.scalar(select(func.count(Import.id)).where(Import.status == "discarded"))
    assert discarded == 2  # scores and stations were both staged, then both discarded


def test_unparseable_build_is_invalid_input(
    fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(writes, "build_scores", lambda base, week: b"not a workbook")
    with pytest.raises(Refusal) as exc:
        writes.preview_week(fx_session, _week(), now=NOW)
    assert exc.value.code == "invalid_input"
    _assert_refused(fx_session, "invalid_input")


def test_same_input_returns_the_same_preview(fx_session: Session) -> None:
    first = writes.preview_week(fx_session, _week(), now=NOW)
    again = writes.preview_week(fx_session, _week(), now=NOW + dt.timedelta(minutes=5))
    assert again.preview_id == first.preview_id
    assert _pending(fx_session) == 2
    assert fx_session.scalar(select(func.count(McpOperation.id))) == 1


def test_identical_bytes_for_a_changed_preview_refuse_duplicate(
    fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = writes.preview_week(fx_session, _week(), now=NOW)
    op = fx_session.get(McpOperation, first.preview_id)
    assert op is not None
    scores_bytes = fx_session.scalars(
        select(Import.file_bytes).where(Import.id == op.scores_import_id)
    ).one()
    # Different request, but the workbook built from it is byte-identical to a staged one.
    monkeypatch.setattr(writes, "build_scores", lambda base, week: scores_bytes)
    other = _week(
        shooters=[{"name": "Testshooter, Beta", "score": 31, "status": "Guest"}],
    )
    with pytest.raises(Refusal) as exc:
        writes.preview_week(fx_session, other, now=NOW)
    assert exc.value.code == "duplicate"
    assert fx_session.get(McpOperation, first.preview_id).status == "previewed"  # type: ignore[union-attr]
    assert _pending(fx_session) == 2  # the first preview's imports are untouched


def test_expiry_sweep(fx_session: Session) -> None:
    first = writes.preview_week(fx_session, _week(), now=NOW)
    assert _pending(fx_session) == 2
    later = NOW + TTL + dt.timedelta(seconds=1)
    with pytest.raises(Refusal):  # the sweep runs even when the new request is refused
        writes.preview_week(fx_session, _week(date=dt.date(2026, 10, 5)), now=later)
    op = fx_session.get(McpOperation, first.preview_id)
    assert op is not None
    assert op.status == "expired"
    assert _pending(fx_session) == 0


def test_a_fresh_preview_is_not_swept(fx_session: Session) -> None:
    first = writes.preview_week(fx_session, _week(), now=NOW)
    with pytest.raises(Refusal):
        writes.preview_week(
            fx_session, _week(date=dt.date(2026, 10, 5)), now=NOW + TTL - dt.timedelta(seconds=1)
        )
    assert fx_session.get(McpOperation, first.preview_id).status == "previewed"  # type: ignore[union-attr]


def test_new_preview_supersedes_the_old_one(fx_session: Session) -> None:
    first = writes.preview_week(fx_session, _week(), now=NOW)
    second = writes.preview_week(
        fx_session,
        _week(shooters=[{"name": "Testshooter, Beta", "score": 31, "status": "Guest"}]),
        now=NOW,
    )
    assert second.preview_id != first.preview_id
    old = fx_session.get(McpOperation, first.preview_id)
    assert old is not None
    assert old.status == "expired"
    statuses = {
        i.id: i.status
        for i in fx_session.scalars(
            select(Import).where(Import.status.in_(("pending", "discarded")))
        )
    }
    assert statuses[old.scores_import_id] == "discarded"
    assert statuses[old.stations_import_id] == "discarded"
    new = fx_session.get(McpOperation, second.preview_id)
    assert new is not None
    assert statuses[new.scores_import_id] == "pending"
    assert sum(1 for s in statuses.values() if s == "pending") == 1  # one commit-able import


def test_correction_happy_path(fx_session: Session) -> None:
    names = _names_on_last(fx_session, 2)
    c = CorrectionInput.model_validate(
        {"date": _last_event(fx_session), "rows": [{"name": names[0], "score": 7}]}
    )
    out = writes.preview_correction(fx_session, c, now=NOW)
    assert out.needs_human_approval is True
    assert [(ch.name, ch.new_score) for ch in out.changes] == [(names[0], 7)]
    assert out.changes[0].old_score != 7
    op = fx_session.get(McpOperation, out.preview_id)
    assert op is not None
    assert (op.kind, op.status, op.stations_import_id) == ("correction", "previewed", None)
    assert _pending(fx_session) == 1


def test_correction_not_latest_event(fx_session: Session) -> None:
    name = _names_on_last(fx_session, 1)[0]
    c = CorrectionInput.model_validate(
        {"date": dt.date(2026, 9, 20), "rows": [{"name": name, "score": 7}]}
    )
    with pytest.raises(Refusal) as exc:
        writes.preview_correction(fx_session, c, now=NOW)
    assert exc.value.code == "not_latest_event"
    _assert_refused(fx_session, "not_latest_event")


def test_correction_name_not_on_date(fx_session: Session) -> None:
    c = CorrectionInput.model_validate(
        {"date": _last_event(fx_session), "rows": [{"name": "Nobody, Nemo", "score": 7}]}
    )
    with pytest.raises(Refusal) as exc:
        writes.preview_correction(fx_session, c, now=NOW)
    assert exc.value.code == "name_not_on_date"
    _assert_refused(fx_session, "name_not_on_date")


def test_correction_to_the_same_score_is_refused(fx_session: Session) -> None:
    name = _names_on_last(fx_session, 1)[0]
    stored = fx_session.scalar(
        select(Round.score)
        .join(Shooter, Shooter.id == Round.shooter_id)
        .where(Round.event_date == _last_event(fx_session), Shooter.display_name == name)
    )
    c = CorrectionInput.model_validate(
        {"date": _last_event(fx_session), "rows": [{"name": name, "score": stored}]}
    )
    with pytest.raises(Refusal) as exc:
        writes.preview_correction(fx_session, c, now=NOW)
    assert exc.value.code == "invalid_input"
    _assert_refused(fx_session, "invalid_input")


def test_run_write_commits_the_refusal_record_before_raising(fx_session: Session) -> None:
    from contextlib import contextmanager

    events: list[str] = []

    @contextmanager
    def factory():  # type: ignore[no-untyped-def]
        try:
            yield fx_session
        except BaseException:
            events.append("rollback")
            raise
        else:
            events.append("commit")

    with pytest.raises(Refusal):
        writes.run_write(
            factory, lambda s: writes.preview_week(s, _week(date=dt.date(2026, 10, 5)), now=NOW)
        )
    assert events == ["commit"]
    assert len(_refused(fx_session)) == 1
