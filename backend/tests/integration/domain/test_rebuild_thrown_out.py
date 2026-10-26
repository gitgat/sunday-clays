"""Rebuild marks thrown-out stations and Sundays, reports them and flags them in the preview."""

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import date
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.domain.identity import lookup_shooter
from sunday_clays.domain.imports import PREVIEW_STATION_CODES, stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule
from sunday_clays.domain.schemas import Severity
from sunday_clays.models import DataIssue, Event, Round, ShooterProfile, StationLayout

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)
LAYOUT = (7, 7, 7, 7, 7, 7, 8)
CLEAN4 = (7, 5, 5, 5, 5, 5, 5)  # 37
NAMES = [
    "Hadley, Ike",
    "Devlin, Sid",
    "Crenshaw, Noel",
    "Kaplan, Noel",
    "Kim, Pat",
    "Pruett, Luther",
    "Linwood, Luther",
    "Abernathy, Preston",
]
MSG4 = (
    "Station 4 on 2026-09-13 looks thrown out (every shooter perfect). "
    "It's marked * and left out of stats. Override in Rules if that's wrong."
)
LETTERED = (4, 5, 6, 7, "7A", 8, 9)
CLEAN7A = (5, 5, 5, 5, 7, 5, 5)

CountQueries = Callable[[Session], AbstractContextManager[list[str]]]
Sheet = Sequence[tuple[str, Sequence[int]]]


@pytest.fixture
def live(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> Callable[..., None]:
    def _live(
        sheet: Sheet,
        extra_scores: Sequence[tuple[object, ...]] = (),
        rules: Sequence[dict[str, Any]] = (),
        stations: Sequence[int | str] = (4, 5, 6, 7, 8, 9, 10),
    ) -> None:
        scores = [(n, sum(h), D2) for n, h in sheet if n != "Nobody, New"] + list(extra_scores)
        mark_committed(session, stage_import(session, scores_workbook(scores), "s.xlsx").import_id)
        tab = stations_workbook([("9 13 26", D2, LAYOUT, sheet)], stations)
        mark_committed(session, stage_import(session, tab, "st.xlsx").import_id)
        for payload in rules:
            create_rule(session, RuleType.STATION_DROP, payload, None)
        rebuild_live(session)

    return _live


def _layouts(session: Session) -> list[tuple[str, bool, str | None]]:
    return [
        (r.station_label, r.dropped, r.dropped_source)
        for r in session.scalars(
            select(StationLayout)
            .where(StationLayout.event_date == D2)
            .order_by(StationLayout.station_no, StationLayout.station_label)
        )
    ]


def _issues(session: Session, code: str) -> list[DataIssue]:
    return list(
        session.scalars(select(DataIssue).where(DataIssue.code == code).order_by(DataIssue.id))
    )


def _clean(names: Sequence[str]) -> Sheet:
    return [(n, CLEAN4) for n in names]


def test_a_station_every_entry_cleaned_is_thrown_out_and_still_counts(
    session: Session, live: Callable[..., None], count_queries: CountQueries
) -> None:
    with count_queries(session) as statements:
        live(_clean(NAMES), extra_scores=[("Hadley, Ike", 30, D1)])
    assert session.get(Event, D2).stats_excluded is True  # type: ignore[union-attr]
    assert session.get(Event, D1).stats_excluded is False  # type: ignore[union-attr]
    assert _layouts(session) == [
        ("4", True, "auto"),
        *[(str(n), False, None) for n in range(5, 11)],
    ]
    [issue] = _issues(session, "station_thrown_out")
    assert (issue.severity, issue.event_date, issue.shooter_id, issue.message, issue.details) == (
        "info",
        D2,
        None,
        MSG4,
        {"station_label": "4", "n_entries": 8, "target_count": 7},
    )
    assert session.scalars(select(Round.score).where(Round.event_date == D2)).all() == [37] * 8
    assert session.get(Event, D2).results_complete is True  # type: ignore[union-attr]
    profile = session.get(ShooterProfile, lookup_shooter(session, "hadley ike"))
    assert profile is not None
    assert profile.n_rounds == 2
    assert sum(s.startswith("INSERT INTO station_layouts") for s in statements) == 1


def test_seven_entries_are_not_enough(session: Session, live: Callable[..., None]) -> None:
    live(_clean(NAMES[:7]))
    assert session.get(Event, D2).stats_excluded is False  # type: ignore[union-attr]
    assert _issues(session, "station_thrown_out") == []


def test_a_second_round_entry_counts_toward_the_eight_entries(
    session: Session, live: Callable[..., None]
) -> None:
    live([*_clean(NAMES[:7]), (NAMES[0], CLEAN4)])
    assert session.get(Event, D2).stats_excluded is True  # type: ignore[union-attr]
    [issue] = _issues(session, "station_thrown_out")
    assert issue.details["n_entries"] == 8


@pytest.mark.parametrize(("hit", "dropped"), [(7, True), (6, False)])
def test_an_unlinked_entry_counts_toward_the_rule(
    session: Session, live: Callable[..., None], hit: int, dropped: bool
) -> None:
    live([*_clean(NAMES[:7]), ("Nobody, New", (hit, 4, 4, 4, 4, 4, 4))])
    assert session.get(Event, D2).stats_excluded is dropped  # type: ignore[union-attr]
    assert _layouts(session)[0] == ("4", dropped, "auto" if dropped else None)


def test_override_off_keeps_an_auto_station_in_stats(
    session: Session, live: Callable[..., None]
) -> None:
    live(
        _clean(NAMES),
        rules=[{"event_date": "2026-09-13", "station_label": "4", "dropped": False}],
    )
    assert session.get(Event, D2).stats_excluded is False  # type: ignore[union-attr]
    assert _layouts(session)[0] == ("4", False, "override")
    assert _issues(session, "station_thrown_out") == []


def test_override_on_marks_a_station_that_was_not_all_perfect(
    session: Session, live: Callable[..., None]
) -> None:
    live(
        [(n, (5,) * 7) for n in NAMES[:2]],
        rules=[{"event_date": "2026-09-13", "station_label": "5", "dropped": True}],
    )
    assert session.get(Event, D2).stats_excluded is True  # type: ignore[union-attr]
    assert _layouts(session)[1] == ("5", True, "override")
    assert _issues(session, "station_thrown_out") == []


def _seven(session: Session) -> list[tuple[str, bool, str | None]]:
    return [r for r in _layouts(session) if r[0] in ("7", "7A")]


def test_a_lettered_station_is_detected_and_named(
    session: Session, live: Callable[..., None]
) -> None:
    live([(n, CLEAN7A) for n in NAMES], stations=LETTERED)
    assert session.get(Event, D2).stats_excluded is True  # type: ignore[union-attr]
    assert _seven(session) == [("7", False, None), ("7A", True, "auto")]
    [issue] = _issues(session, "station_thrown_out")
    assert issue.message.startswith("Station 7A on 2026-09-13 looks thrown out")


def test_a_lower_case_rule_matches_the_lettered_station(
    session: Session, live: Callable[..., None]
) -> None:
    live(
        [(n, (5,) * 7) for n in NAMES[:2]],
        stations=LETTERED,
        rules=[{"event_date": "2026-09-13", "station_label": "7a", "dropped": True}],
    )
    assert _seven(session) == [("7", False, None), ("7A", True, "override")]


def test_a_rule_for_07_touches_only_station_7(session: Session, live: Callable[..., None]) -> None:
    live(
        [(n, CLEAN7A) for n in NAMES],
        stations=LETTERED,
        rules=[{"event_date": "2026-09-13", "station_label": "07", "dropped": False}],
    )
    assert _seven(session) == [("7", False, "override"), ("7A", True, "auto")]
    assert session.get(Event, D2).stats_excluded is True  # type: ignore[union-attr]


def test_a_sunday_level_override_excludes_a_sunday_without_a_sheet(
    session: Session, live: Callable[..., None]
) -> None:
    live(
        _clean(NAMES[:2]),
        extra_scores=[("Hadley, Ike", 30, D1)],
        rules=[{"event_date": "2026-09-06", "dropped": True}],
    )
    first = session.get(Event, D1)
    assert first is not None
    assert (first.stats_excluded, first.has_stations) == (True, False)
    assert session.get(Event, D2).stats_excluded is False  # type: ignore[union-attr]


def test_unmatched_station_drop_rules_are_reported(
    session: Session, live: Callable[..., None]
) -> None:
    live(_clean(NAMES[:2]))
    r12 = create_rule(
        session,
        RuleType.STATION_DROP,
        {"event_date": "2026-09-13", "station_label": "12", "dropped": True},
        None,
    )
    r20 = create_rule(
        session, RuleType.STATION_DROP, {"event_date": "2026-09-20", "dropped": True}, None
    )
    rebuild_live(session)
    a, b = _issues(session, "rule_target_missing")
    assert (a.event_date, a.message, a.details) == (
        D2,
        f"Rule {r12} targets Station 12 on 2026-09-13,"
        " which has no such station on a regular Sunday",
        {"rule_id": r12, "event_date": "2026-09-13", "station_label": "12", "dropped": True},
    )
    assert (b.event_date, b.message) == (
        date(2026, 9, 20),
        f"Rule {r20} marks 2026-09-20 as thrown out, which has no regular Sunday",
    )


def test_a_special_sunday_is_never_thrown_out(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    scores = scores_workbook([("Hadley, Ike", 41, D2)])
    mark_committed(session, stage_import(session, scores, "s.xlsx").import_id)
    special = special_workbook([(n, (6,) + (5,) * 9) for n in NAMES])
    mark_committed(session, stage_import(session, special, "sp.xlsx").import_id)
    rid = create_rule(
        session, RuleType.STATION_DROP, {"event_date": "2026-09-20", "dropped": True}, None
    )
    rebuild_live(session)
    assert session.get(Event, date(2026, 9, 20)).stats_excluded is False  # type: ignore[union-attr]
    assert {(r.dropped, r.dropped_source) for r in session.scalars(select(StationLayout))} == {
        (False, None)
    }
    assert _issues(session, "station_thrown_out") == []
    [missing] = _issues(session, "rule_target_missing")
    assert (
        missing.message == f"Rule {rid} marks 2026-09-20 as thrown out, which has no regular Sunday"
    )


def test_the_stations_preview_flags_a_station_that_looks_thrown_out(
    session: Session,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
    mark_committed: Callable[[Session, int], None],
) -> None:
    scores = scores_workbook([(n, 37, D2) for n in NAMES])
    mark_committed(session, stage_import(session, scores, "s.xlsx").import_id)
    rebuild_live(session)
    tab = stations_workbook([("9 13 26", D2, LAYOUT, _clean(NAMES))])
    preview = stage_import(session, tab, "st.xlsx")
    assert "station_dropped" in PREVIEW_STATION_CODES
    assert [
        (f.code, f.severity, f.sheet, f.event_date, f.message)
        for f in preview.findings
        if f.code == "station_dropped"
    ] == [
        (
            "station_dropped",
            Severity.INFO,
            "9 13 26",
            D2,
            "Station 4 on 2026-09-13 looks thrown out (every shooter perfect). "
            "It will be marked * and left out of stats. Override in Rules if that's wrong.",
        )
    ]
