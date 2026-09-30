import threading
import time
import warnings
from collections.abc import Callable
from datetime import date
from typing import Any

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from sunday_clays.domain.errors import ConflictError, NotFoundError
from sunday_clays.domain.imports import (
    active_scores_import,
    commit_import,
    discard_import,
    get_import_preview,
    list_imports,
    rollback_import,
    stage_import,
)
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.schemas import ImportStatus, ScoresDiff
from sunday_clays.models import (
    DataIssue,
    Event,
    Import,
    LoginAttempt,
    Round,
    StationHit,
    StationLayout,
)

D1, D2, D3 = date(2026, 9, 6), date(2026, 9, 13), date(2026, 9, 20)
LAST_WEEK = date(2026, 9, 27)
HADLEY_9_13_STATION_4 = ("9 13 26", "Hadley, Ike", 1, 1)  # 3 -> 1 hits: station total 36 -> 34


def _fixture_import(session: Session, kind: str) -> int:
    return session.scalars(
        select(Import.id).where(Import.kind == kind, Import.status == "committed")
    ).one()


def _station_state(session: Session) -> dict[str, list[tuple[Any, ...]]]:
    return {
        "layouts": [
            tuple(r)
            for r in session.execute(
                select(
                    StationLayout.event_date,
                    StationLayout.station_no,
                    StationLayout.target_count,
                    StationLayout.source_import_id,
                ).order_by(StationLayout.event_date, StationLayout.station_no)
            )
        ],
        "hits": [
            tuple(r)
            for r in session.execute(
                select(
                    StationHit.event_date,
                    StationHit.entry_row,
                    StationHit.station_no,
                    StationHit.sheet_id,
                    StationHit.shooter_id,
                    Round.name_key,  # the linked round by its natural key: ids change every rebuild
                    Round.ordinal,
                    StationHit.hits,
                )
                .outerjoin(Round, Round.id == StationHit.round_id)
                .order_by(StationHit.event_date, StationHit.entry_row, StationHit.station_no)
            )
        ],
        "events": [
            tuple(r)
            for r in session.execute(
                select(
                    Event.event_date, Event.round_type, Event.round_type_source, Event.has_stations
                )
                .where(Event.event_date >= D1)
                .order_by(Event.event_date)
            )
        ],
        "issues": sorted(
            (c, d) for c, d in session.execute(select(DataIssue.code, DataIssue.event_date))
        ),
    }


def test_commit_refuses_unconfirmed_removals(
    fx_session: Session, scores_bytes: bytes, scores_without_dates: Callable[..., bytes]
) -> None:
    stale = stage_import(
        fx_session, scores_without_dates(scores_bytes, [LAST_WEEK]), "old copy.xlsx"
    )
    assert isinstance(stale.diff, ScoresDiff)
    assert (stale.diff.events_removed, stale.diff.rows_removed) == ([LAST_WEEK], 23)
    assert stale.requires_removal_confirmation is True
    with pytest.raises(ConflictError) as excinfo:
        commit_import(fx_session, stale.import_id)
    assert excinfo.value.code == "removals_not_confirmed"
    assert fx_session.get(Import, stale.import_id).status == "pending"  # type: ignore[union-attr]
    commit_import(fx_session, stale.import_id, confirm_removals=True)
    assert active_scores_import(fx_session) == stale.import_id
    rebuild_live(fx_session)
    event = fx_session.get(Event, LAST_WEEK)
    assert event is not None
    assert (event.has_scores, event.head_count) == (False, 23)


def test_removal_check_uses_the_import_live_at_commit_time(
    session: Session, scores_workbook: Callable[..., bytes]
) -> None:
    base = [("Hadley, Ike", 34, D1), ("Hadley, Ike", 35, D2)]
    commit_import(session, stage_import(session, scores_workbook(base), "v1.xlsx").import_id)
    fixed = stage_import(
        session, scores_workbook([("Hadley, Ike", 36, D1), ("Hadley, Ike", 35, D2)]), "fix.xlsx"
    )
    assert fixed.requires_removal_confirmation is False
    commit_import(
        session,
        stage_import(
            session, scores_workbook([*base, ("Hadley, Ike", 33, D3)]), "v2.xlsx"
        ).import_id,
    )
    with pytest.raises(ConflictError) as excinfo:  # committing "fix" now would drop D3
        commit_import(session, fixed.import_id)
    assert excinfo.value.code == "removals_not_confirmed"


def test_lifecycle_state_errors(session: Session, scores_workbook: Callable[..., bytes]) -> None:
    committed = stage_import(
        session, scores_workbook([("Hadley, Ike", 34, D1)]), "a.xlsx"
    ).import_id
    commit_import(session, committed)
    pending = stage_import(session, scores_workbook([("Hadley, Ike", 35, D1)]), "b.xlsx").import_id
    for action, import_id, code in (
        (commit_import, committed, "not_pending"),
        (discard_import, committed, "not_pending"),
        (rollback_import, pending, "not_committed"),
    ):
        with pytest.raises(ConflictError) as conflict:
            action(session, import_id)
        assert conflict.value.code == code
    for action in (commit_import, discard_import, rollback_import):
        with pytest.raises(NotFoundError) as missing:
            action(session, 999_999)
        assert missing.value.code == "import_not_found"


def test_discarded_import_never_goes_live(
    session: Session, scores_workbook: Callable[..., bytes]
) -> None:
    preview = stage_import(session, scores_workbook([("Hadley, Ike", 34, D1)]), "a.xlsx")
    discard_import(session, preview.import_id)
    assert session.get(Import, preview.import_id).status == "discarded"  # type: ignore[union-attr]
    assert active_scores_import(session) is None
    with pytest.raises(ConflictError):
        commit_import(session, preview.import_id)


def test_list_imports_newest_first(session: Session, scores_workbook: Callable[..., bytes]) -> None:
    first = stage_import(session, scores_workbook([("Hadley, Ike", 34, D1)]), "a.xlsx").import_id
    commit_import(session, first)
    second = stage_import(session, scores_workbook([("Hadley, Ike", 35, D1)]), "b.xlsx").import_id
    summaries = list_imports(session)
    assert [(s.id, s.status, s.filename) for s in summaries] == [
        (second, ImportStatus.PENDING, "b.xlsx"),
        (first, ImportStatus.COMMITTED, "a.xlsx"),
    ]
    assert summaries[1].committed_at is not None
    assert summaries[0].committed_at is None
    assert len(summaries[0].sha256) == 64


def test_rollback_middle_station_import(
    fx_session: Session, stations_bytes: bytes, stations_edited: Callable[..., bytes]
) -> None:
    v1 = _fixture_import(fx_session, "stations")
    v2 = stage_import(
        fx_session,
        stations_edited(stations_bytes, drop_tabs=["9 6 26"], hit=HADLEY_9_13_STATION_4),
        "v2.xlsx",
    ).import_id
    commit_import(fx_session, v2)
    rollback_import(fx_session, v1)  # the older import, not the newest
    rebuild_live(fx_session)
    sources = dict(
        fx_session.execute(
            select(StationLayout.event_date, StationLayout.source_import_id).distinct()
        ).all()
    )
    assert sources == {D2: v2}  # 9/6 had no other source, so it disappears
    d1 = fx_session.get(Event, D1)
    assert d1 is not None
    assert (d1.has_stations, d1.round_type, d1.round_type_source) == (
        False,
        "sporting",
        "none",
    )
    assert (
        fx_session.scalar(select(func.count()).where(DataIssue.code == "station_score_mismatch"))
        == 0
    )


def test_rollback_non_latest_scores_import_keeps_latest_active(
    fx_session: Session, scores_bytes: bytes, scores_with_score: Callable[..., bytes]
) -> None:
    v2 = stage_import(
        fx_session, scores_with_score(scores_bytes, "Hadley, Ike", D2, 36), "v2.xlsx"
    ).import_id
    commit_import(fx_session, v2)
    v3 = stage_import(
        fx_session, scores_with_score(scores_bytes, "Hadley, Ike", D2, 35), "v3.xlsx"
    ).import_id
    commit_import(fx_session, v3)
    rollback_import(fx_session, v2)
    assert active_scores_import(fx_session) == v3
    rebuild_live(fx_session)
    assert (
        fx_session.scalars(
            select(Round.score).where(Round.name_key == "hadley ike", Round.event_date == D2)
        ).one()
        == 35
    )


def test_stations_rollback_restores_previous_state(
    fx_session: Session, stations_bytes: bytes, stations_edited: Callable[..., bytes]
) -> None:
    v1 = _fixture_import(fx_session, "stations")
    before = _station_state(fx_session)
    v2 = stage_import(
        fx_session,
        stations_edited(stations_bytes, drop_tabs=["9 6 26"], hit=HADLEY_9_13_STATION_4),
        "v2.xlsx",
    ).import_id
    commit_import(fx_session, v2)
    rebuild_live(fx_session)
    sources = dict(
        fx_session.execute(
            select(StationLayout.event_date, StationLayout.source_import_id).distinct()
        ).all()
    )
    assert sources == {D1: v1, D2: v2}  # the tab missing from v2 keeps its v1 week
    hadley_total = fx_session.scalar(
        select(func.sum(StationHit.hits)).where(
            StationHit.event_date == D2, StationHit.name_key == "hadley ike"
        )
    )
    assert hadley_total == 34
    rollback_import(fx_session, v2)
    rebuild_live(fx_session)
    assert _station_state(fx_session) == before


def _failed_logins(session: Session) -> int | None:
    return session.scalar(
        select(func.count()).select_from(LoginAttempt).where(LoginAttempt.success.is_(False))
    )


def test_fx_world_holds_both_committed_fixtures(
    fx_session: Session, fx_client: TestClient, session: Session
) -> None:
    assert fx_session.scalar(select(func.count()).select_from(Event)) == 360
    assert sorted(fx_session.scalars(select(Import.kind).where(Import.status == "committed"))) == [
        "scores",
        "stations",
    ]
    # fx_client's requests run on fx_session (in <test db>_fx), never on the main test database:
    # the failed login's attempt row is visible only through fx_session's open transaction.
    assert str(fx_session.scalar(select(func.current_database()))).endswith("_fx")
    response = fx_client.post("/api/auth/login", json={"password": "not the password"})
    assert response.status_code == 401
    assert (_failed_logins(fx_session), _failed_logins(session)) == (1, 0)


def test_fx_stations_import_was_previewed_against_the_live_scores(fx_session: Session) -> None:
    """Staged after the scores import went live, as an admin uploads it: one real mismatch."""
    preview = get_import_preview(fx_session, _fixture_import(fx_session, "stations"))
    station = [
        (f.code, f.sheet, f.row, f.event_date, f.name)
        for f in preview.findings
        if f.code.startswith("station_")
    ]
    assert station == [("station_score_mismatch", "9 13 26", 15, D2, "Hadley, Ike")]


# --- concurrent lifecycle calls serialize on one advisory lock -----------------------------
BASE = [("Hadley, Ike", 34, D1), ("Hadley, Ike", 35, D2)]
WITH_D3 = [*BASE, ("Hadley, Ike", 33, D3)]
FIXED = [("Hadley, Ike", 36, D1), ("Hadley, Ike", 35, D2)]  # changes D1; drops D3 if it is live


def _race(
    engine: Engine, first: Callable[[Session], None], second: Callable[[Session], None]
) -> tuple[str | None, Exception | None]:
    """Run ``first`` and keep its transaction open while ``second`` starts on another connection.

    Returns the lock type ``second`` waited on (None if it never waited) and the exception it
    raised (None if it succeeded); ``second``'s transaction is rolled back.
    """
    holder, waiter = Session(engine), Session(engine)
    probe = engine.connect()
    pid = waiter.scalar(select(func.pg_backend_pid()))
    raised: list[Exception] = []

    def run_second() -> None:
        try:
            second(waiter)
        except Exception as exc:  # returned to the test
            raised.append(exc)

    worker = threading.Thread(target=run_second)
    waited_on: str | None = None
    try:
        first(holder)
        worker.start()
        deadline = time.monotonic() + 10
        while waited_on is None and worker.is_alive() and time.monotonic() < deadline:
            waited_on = probe.scalar(
                text("SELECT min(locktype) FROM pg_locks WHERE pid = :pid AND NOT granted"),
                {"pid": pid},
            )
            time.sleep(0.02)
        holder.commit()
        worker.join(timeout=30)
        assert not worker.is_alive()
    finally:
        holder.close()  # rolls back if the commit was never reached, releasing its locks
        worker.join(timeout=30)
        waiter.close()
        probe.close()
    return waited_on, (raised[0] if raised else None)


def _staged(session: Session, workbook: Callable[..., bytes], rows: list[Any], name: str) -> int:
    return stage_import(session, workbook(rows), name).import_id


def test_concurrent_commit_rediffs_against_the_commit_that_won(
    committed_engine: Engine, scores_workbook: Callable[..., bytes]
) -> None:
    with Session(committed_engine) as setup:
        commit_import(setup, _staged(setup, scores_workbook, BASE, "v1.xlsx"))
        adds_d3 = _staged(setup, scores_workbook, WITH_D3, "v2.xlsx")
        fixed = _staged(setup, scores_workbook, FIXED, "fix.xlsx")
        setup.commit()

    def commit_adds_d3(s: Session) -> None:
        commit_import(s, adds_d3)

    def commit_fixed(s: Session) -> None:  # harmless against v1, but drops D3 once v2 is live
        commit_import(s, fixed)

    waited_on, error = _race(committed_engine, commit_adds_d3, commit_fixed)
    assert waited_on == "advisory"
    assert isinstance(error, ConflictError)
    assert error.code == "removals_not_confirmed"
    with Session(committed_engine) as check:
        assert active_scores_import(check) == adds_d3
        assert check.get(Import, fixed).status == "pending"  # type: ignore[union-attr]


def test_commit_racing_a_rollback_rediffs_against_the_restored_import(
    committed_engine: Engine, scores_workbook: Callable[..., bytes]
) -> None:
    with Session(committed_engine) as setup:
        with_d3 = _staged(setup, scores_workbook, WITH_D3, "v1.xlsx")
        commit_import(setup, with_d3)
        without_d3 = _staged(setup, scores_workbook, BASE, "v2.xlsx")
        commit_import(setup, without_d3, confirm_removals=True)
        fixed = _staged(setup, scores_workbook, FIXED, "fix.xlsx")
        setup.commit()

    def roll_back_without_d3(s: Session) -> None:  # v1, which has D3, is live again
        rollback_import(s, without_d3)

    def commit_fixed(s: Session) -> None:
        commit_import(s, fixed)

    waited_on, error = _race(committed_engine, roll_back_without_d3, commit_fixed)
    assert waited_on == "advisory"
    assert isinstance(error, ConflictError)
    assert error.code == "removals_not_confirmed"
    with Session(committed_engine) as check:
        assert active_scores_import(check) == with_d3


def test_commit_racing_a_discard_sees_the_discard(
    committed_engine: Engine, scores_workbook: Callable[..., bytes]
) -> None:
    with Session(committed_engine) as setup:
        pending = _staged(setup, scores_workbook, BASE, "a.xlsx")
        setup.commit()

    def discard(s: Session) -> None:
        discard_import(s, pending)

    def read_then_commit(s: Session) -> None:
        seen = s.get(Import, pending)  # held, so the identity map keeps this pending copy
        assert seen is not None
        assert seen.status == "pending"
        commit_import(s, pending)

    waited_on, error = _race(committed_engine, discard, read_then_commit)
    assert waited_on == "advisory"
    assert isinstance(error, ConflictError)
    assert error.code == "not_pending"
    with Session(committed_engine) as check:
        imp = check.get(Import, pending)
        assert imp is not None
        assert (imp.status, imp.committed_at) == ("discarded", None)


# --- the fixture-variant editors -------------------------------------------------------------
def test_workbook_edits_silence_only_the_data_validation_notice(
    stations_bytes: bytes, stations_edited: Callable[..., bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        stations_edited(stations_bytes)  # the real fixture carries a data-validation extension
    assert [str(w.message) for w in caught] == []
    real_load = openpyxl.load_workbook

    def load_with_another_notice(*args: Any, **kwargs: Any) -> Any:
        warnings.warn_explicit(
            "Conditional Formatting extension is not supported and will be removed",
            UserWarning,
            "_reader.py",
            1,
            module="openpyxl.worksheet._reader",
        )
        return real_load(*args, **kwargs)

    monkeypatch.setattr(openpyxl, "load_workbook", load_with_another_notice)
    with pytest.warns(UserWarning, match="Conditional Formatting extension"):
        stations_edited(stations_bytes)
