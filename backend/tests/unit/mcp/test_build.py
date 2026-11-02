import datetime as dt
import io

import openpyxl
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from sunday_clays.ingest import parse_upload
from sunday_clays.ingest.types import ScoresParse, StationsParse
from sunday_clays.mcp.build import (
    BuildError,
    CorrectionInput,
    WeekInput,
    build_correction,
    build_scores,
    build_stations,
)

DAY = dt.date(2099, 1, 4)  # a Sunday after the fixture's history


def _week(**over: object) -> WeekInput:
    data: dict[str, object] = {
        "date": DAY,
        "stations": ["3", "5", "7", "7A", "8"],
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
            {
                "name": "Testshooter, Gamma",
                "score": 40,
                "status": "Member",
                "class": "Pump",
                "hits": [8, 8, 8, 8, 8],
            },
        ],
    }
    data.update(over)
    return WeekInput.model_validate(data)


def _parsed_scores(data: bytes) -> ScoresParse:
    parsed = parse_upload(data)
    assert isinstance(parsed, ScoresParse)
    return parsed


def test_build_scores_adds_exactly_the_new_rows(scores_bytes: bytes) -> None:
    base = _parsed_scores(scores_bytes)
    out = _parsed_scores(build_scores(scores_bytes, _week()))
    assert len(out.score_rows) == len(base.score_rows) + 3
    new = [r for r in out.score_rows if r.event_date == DAY]
    assert [(r.raw_name, r.score) for r in new] == [
        ("Testshooter, Alpha", 45),
        ("Testshooter, Gamma", 40),
        ("Testshooter, Beta", 30),
    ]
    assert [r.gauge_class for r in new] == ["12 Gauge", "Pump", None]
    assert [r.status for r in new] == ["member", "member", "guest"]
    assert next(a for a in out.attendance_rows if a.event_date == DAY).head_count == 3
    old = [r for r in out.score_rows if r.event_date != DAY]
    assert [(r.raw_name, r.score, r.event_date) for r in old] == [
        (r.raw_name, r.score, r.event_date) for r in base.score_rows
    ]


def test_build_scores_date_present(scores_bytes: bytes) -> None:
    once = build_scores(scores_bytes, _week())
    with pytest.raises(BuildError) as exc:
        build_scores(once, _week())
    assert exc.value.code == "date_present"


def test_build_scores_sets_existing_attendance_count(scores_bytes: bytes) -> None:
    wb = openpyxl.load_workbook(io.BytesIO(scores_bytes))
    wb["Attendance History"].append([dt.datetime(2099, 1, 4), 1, None])  # noqa: DTZ001
    buf = io.BytesIO()
    wb.save(buf)
    out = _parsed_scores(build_scores(buf.getvalue(), _week()))
    assert [a.head_count for a in out.attendance_rows if a.event_date == DAY] == [3]


def test_build_stations_parses_with_labels_and_counts() -> None:
    data = build_stations(_week())
    assert data is not None
    parsed = parse_upload(data)
    assert isinstance(parsed, StationsParse)
    (sheet,) = parsed.sheets
    assert sheet.event_date == DAY
    assert [(e.label, e.target_count) for e in sheet.layout] == [
        ("3", 10),
        ("5", 10),
        ("7", 10),
        ("7A", 10),
        ("8", 10),
    ]
    assert [(r.raw_name, [h for _, h in r.hits]) for r in sheet.rows] == [
        ("Testshooter, Alpha", [9] * 5),
        ("Testshooter, Gamma", [8] * 5),
    ]


def test_build_stations_none_without_hits() -> None:
    week = _week(shooters=[{"name": "Testshooter, Beta", "score": 30, "status": "Guest"}])
    assert build_stations(week) is None


def _latest_rows(data: bytes) -> tuple[dt.date, list[tuple[str, int]]]:
    rows = _parsed_scores(data).score_rows
    day = max(r.event_date for r in rows)
    return day, [(r.raw_name, r.score) for r in rows if r.event_date == day]


def test_build_correction_changes_only_named_rows(scores_bytes: bytes) -> None:
    day, before = _latest_rows(scores_bytes)
    name, score = before[0]
    new_score = score - 1 if score else 1
    c = CorrectionInput.model_validate({"date": day, "rows": [{"name": name, "score": new_score}]})
    out, stations = build_correction(scores_bytes, c)
    assert stations is None
    base = _parsed_scores(scores_bytes)
    after = _parsed_scores(out)
    changed = [
        (a.raw_name, a.score)
        for a, b in zip(after.score_rows, base.score_rows, strict=True)
        if (a.raw_name, a.score, a.event_date, a.status, a.gauge_class)
        != (b.raw_name, b.score, b.event_date, b.status, b.gauge_class)
    ]
    assert changed == [(name, new_score)]
    assert after.attendance_rows == base.attendance_rows


def test_build_correction_stations_for_rows_with_hits(scores_bytes: bytes) -> None:
    day, before = _latest_rows(scores_bytes)
    name, _ = before[0]
    c = CorrectionInput.model_validate(
        {
            "date": day,
            "stations": ["1", "2", "3", "4", "5"],
            "counts": [10, 10, 10, 10, 10],
            "rows": [{"name": name, "score": 40, "hits": [8, 8, 8, 8, 8]}],
        }
    )
    _, stations = build_correction(scores_bytes, c)
    assert stations is not None
    parsed = parse_upload(stations)
    assert isinstance(parsed, StationsParse)
    assert [r.raw_name for r in parsed.sheets[0].rows] == [name]


def test_build_correction_name_not_on_date(scores_bytes: bytes) -> None:
    day, _ = _latest_rows(scores_bytes)
    c = CorrectionInput.model_validate(
        {"date": day, "rows": [{"name": "Testshooter, Nobody", "score": 10}]}
    )
    with pytest.raises(BuildError) as exc:
        build_correction(scores_bytes, c)
    assert exc.value.code == "name_not_on_date"


def test_correction_hits_need_layout() -> None:
    with pytest.raises(ValidationError):
        CorrectionInput.model_validate(
            {"date": DAY, "rows": [{"name": "Testshooter, Beta", "score": 2, "hits": [1, 1]}]}
        )


# --- validation rules -----------------------------------------------------------------------
@pytest.mark.parametrize(
    "over",
    [
        {"counts": [10, 10, 10, 10, 9]},  # sum 49
        {"counts": [10, 10, 10, 10, 11]},  # count > 10
        {"counts": [10, 10, 10, 20]},  # length mismatch
        {"stations": ["3", "5", "7", "7", "8"]},
        {"stations": ["3", "5", "7", "x", "8"]},
        {"expected_total": 1},
        {"shooters": []},
        {
            "shooters": [
                {"name": "Testshooter, Beta", "score": 3, "status": "Guest"},
                {"name": "TESTSHOOTER, BETA", "score": 4, "status": "Guest"},
            ]
        },
        {"shooters": [{"name": "Beta Testshooter", "score": 3, "status": "Guest"}]},
        {"shooters": [{"name": "Test, Sh, Beta", "score": 3, "status": "Guest"}]},
        {"shooters": [{"name": "Testshooter, Beta", "score": 51, "status": "Guest"}]},
        {"shooters": [{"name": "Testshooter, Beta", "score": 3, "status": "Other"}]},
        {
            "shooters": [
                {"name": "Testshooter, Beta", "score": 3, "status": "Guest", "class": "Bazooka"}
            ]
        },
        {
            "shooters": [
                {"name": "Testshooter, Beta", "score": 5, "status": "Guest", "hits": [1, 1, 1, 1]}
            ]
        },
        {
            "shooters": [
                {
                    "name": "Testshooter, Beta",
                    "score": 6,
                    "status": "Guest",
                    "hits": [1, 1, 1, 1, 1],
                }
            ]
        },
        {
            "shooters": [
                {
                    "name": "Testshooter, Beta",
                    "score": 11,
                    "status": "Guest",
                    "hits": [11, 0, 0, 0, 0],
                }
            ]
        },
        {"shooters": [{"name": "Testshooter, Beta", "score": 3, "status": "Guest", "x": 1}]},
        {"bogus": 1},
    ],
)
def test_week_rule_violations_rejected(over: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _week(**over)


_NAMES = st.builds(lambda a, b: f"Last{a}, First{b}", st.integers(0, 999), st.integers(0, 999))


@st.composite
def valid_weeks(draw: st.DrawFn) -> dict[str, object]:
    n = draw(st.integers(5, 12))  # fewer than 5 stations cannot hold 50 targets at <=10 each
    counts = [50 // n + (1 if i < 50 % n else 0) for i in range(n)]
    for _ in range(draw(st.integers(0, 10))):  # shuffle targets between stations
        src, dst = draw(st.integers(0, n - 1)), draw(st.integers(0, n - 1))
        if counts[src] > 1 and counts[dst] < 10:
            counts[src] -= 1
            counts[dst] += 1
    stations = [str(i + 1) for i in range(n)]
    names = draw(st.lists(_NAMES, min_size=1, max_size=10, unique_by=str.casefold))
    shooters: list[dict[str, object]] = []
    for name in names:
        hits = [draw(st.integers(0, c)) for c in counts]
        row: dict[str, object] = {
            "name": name,
            "score": sum(hits),
            "status": draw(st.sampled_from(["Member", "Guest"])),
            "class": draw(st.sampled_from([None, "12 Gauge", "28 Gauge", ".410", "Pump"])),
        }
        if draw(st.booleans()):
            row["hits"] = hits
        shooters.append(row)
    return {
        "date": DAY,
        "stations": stations,
        "counts": counts,
        "expected_total": sum(int(str(s["score"])) for s in shooters),
        "shooters": shooters,
    }


@given(valid_weeks())
def test_valid_weeks_round_trip(data: dict[str, object]) -> None:
    week = WeekInput.model_validate(data)
    assert WeekInput.model_validate(week.model_dump(by_alias=True)) == week
    assert WeekInput.model_validate_json(week.model_dump_json(by_alias=True)) == week


@given(valid_weeks(), st.integers(1, 5))
def test_violations_rejected(data: dict[str, object], bump: int) -> None:
    shooters = list(data["shooters"])  # type: ignore[call-overload]
    bad_total = {**data, "expected_total": int(str(data["expected_total"])) + bump}
    with pytest.raises(ValidationError):
        WeekInput.model_validate(bad_total)
    dup = {
        **data,
        "shooters": [*shooters, {**shooters[0], "name": str(shooters[0]["name"]).upper()}],
    }
    with pytest.raises(ValidationError):
        WeekInput.model_validate(dup)
    bad_counts = list(data["counts"])  # type: ignore[call-overload]
    bad_counts[0] = 11
    with pytest.raises(ValidationError):
        WeekInput.model_validate({**data, "counts": bad_counts})
    with_hits = [s for s in shooters if "hits" in s]
    if with_hits:
        broken = {**with_hits[0], "score": int(str(with_hits[0]["score"])) + bump}
        others = [s for s in shooters if s is not with_hits[0]]
        with pytest.raises(ValidationError):
            WeekInput.model_validate(
                {**data, "expected_total": None, "shooters": [broken, *others]}
            )
