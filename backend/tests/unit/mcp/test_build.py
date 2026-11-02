import datetime as dt
import io

import openpyxl
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from sunday_clays.ingest import parse_upload
from sunday_clays.ingest.names import name_key
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
    out = build_correction(scores_bytes, c)
    assert isinstance(out, bytes)
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


def test_build_correction_name_not_on_date(scores_bytes: bytes) -> None:
    day, _ = _latest_rows(scores_bytes)
    c = CorrectionInput.model_validate(
        {"date": day, "rows": [{"name": "Testshooter, Nobody", "score": 10}]}
    )
    with pytest.raises(BuildError) as exc:
        build_correction(scores_bytes, c)
    assert exc.value.code == "name_not_on_date"


def test_build_correction_name_ambiguous(scores_bytes: bytes) -> None:
    day, before = _latest_rows(scores_bytes)
    name = before[0][0]
    wb = openpyxl.load_workbook(io.BytesIO(scores_bytes))
    wb["ALL SCORE DETAIL"].append(
        [name, 1, dt.datetime(day.year, day.month, day.day), "Member", None]  # noqa: DTZ001
    )
    buf = io.BytesIO()
    wb.save(buf)
    c = CorrectionInput.model_validate({"date": day, "rows": [{"name": name, "score": 2}]})
    with pytest.raises(BuildError) as exc:
        build_correction(buf.getvalue(), c)
    assert exc.value.code == "name_ambiguous"


def test_correction_row_rejects_hits() -> None:
    with pytest.raises(ValidationError, match="hits"):
        CorrectionInput.model_validate(
            {"date": DAY, "rows": [{"name": "Testshooter, Beta", "score": 2, "hits": [1, 1]}]}
        )


def test_correction_input_rejects_station_layout() -> None:
    row = {"name": "Testshooter, Beta", "score": 2}
    with pytest.raises(ValidationError, match="stations"):
        CorrectionInput.model_validate({"date": DAY, "rows": [row], "stations": ["1"]})


def test_correction_duplicate_names_by_name_key() -> None:
    rows = [
        {"name": "Testshooter, Beta", "score": 2},
        {"name": "Testshooter,  Beta", "score": 3},
    ]
    with pytest.raises(ValidationError, match="duplicate"):
        CorrectionInput.model_validate({"date": DAY, "rows": rows})


# --- validation rules -----------------------------------------------------------------------
def _shooter(**over: object) -> dict[str, object]:
    return {"name": "Testshooter, Beta", "score": 3, "status": "Guest", **over}


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"counts": [10, 10, 10, 10, 9]}, "must sum to 50"),
        ({"counts": [11, 9, 10, 10, 10]}, "target count must be 1-10"),
        ({"counts": [0, 10, 10, 10, 10, 10], "stations": ["1", "2", "3", "4", "5", "6"]}, "1-10"),
        ({"counts": [10, 10, 10, 10]}, "same length"),
        ({"stations": ["3", "5", "7", "7", "8"]}, "duplicate station"),
        ({"stations": ["3", "5", "7", "x", "8"]}, "station must be a label"),
        ({"stations": []}, "at least 1"),
        ({"expected_total": 1}, "expected_total"),
        ({"shooters": []}, "at least 1"),
        ({"shooters": [_shooter(), _shooter(name="TESTSHOOTER, BETA")]}, "duplicate shooter"),
        ({"shooters": [_shooter(), _shooter(name="Testshooter,  Beta")]}, "duplicate shooter"),
        ({"shooters": [_shooter(), _shooter(name="Testshooter , Beta")]}, "duplicate shooter"),
        ({"shooters": [_shooter(), _shooter(name="Testshooter, Beta.")]}, "duplicate shooter"),
        (
            {"shooters": [_shooter(name="O'Neil, Al"), _shooter(name="O\u2019Neil, Al")]},
            "duplicate shooter",
        ),
        ({"shooters": [_shooter(name="Beta Testshooter")]}, "exactly one comma"),
        ({"shooters": [_shooter(name="Test, Sh, Beta")]}, "exactly one comma"),
        ({"shooters": [_shooter(name="Testshooter, ")]}, "Last, First"),
        ({"shooters": [_shooter(score=51)]}, "less than or equal to 50"),
        ({"shooters": [_shooter(status="Other")]}, "String should match"),
        ({"shooters": [_shooter(**{"class": "Bazooka"})]}, "class must be one of"),
        ({"shooters": [_shooter(score=5, hits=[1, 1, 1, 1])]}, "one value per station"),
        ({"shooters": [_shooter(score=6, hits=[1, 1, 1, 1, 1])]}, "hits sum to 5"),
        ({"shooters": [_shooter(score=11, hits=[11, 0, 0, 0, 0])]}, "outside 0..target"),
        ({"shooters": [_shooter(score=5, hits=[-1, 6, 0, 0, 0])]}, "outside 0..target"),
        ({"shooters": [_shooter(x=1)]}, "Extra inputs"),
        ({"bogus": 1}, "Extra inputs"),
        ({"shooters": [_shooter(score=True)]}, "valid integer"),
        ({"shooters": [_shooter(score="3")]}, "valid integer"),
        ({"shooters": [_shooter(score=3, hits=[True, 1, 1, 0, 0])]}, "valid integer"),
        ({"counts": [True, 10, 10, 10, 19]}, "valid integer"),
    ],
)
def test_week_rule_violations_rejected(over: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _week(**over)


@pytest.mark.parametrize(
    "name",
    [
        '=HYPERLINK("http://x"), Beta',
        "=1+1, Beta",
        "+Testshooter, Beta",
        "-Testshooter, Beta",
        "@Testshooter, Beta",
        "Testshooter, =Beta",
        "Testshooter, @Beta",
        "Testshooter,\nBeta",
        "Test\nshooter, Beta",
        "Testshooter, Be\x00ta",
        "Testshooter, Be\tta",
        "Testshooter, Beta1",
        "Test_shooter, Beta",
        "Testshooter, Be(ta)",
        "'Testshooter, Beta",
    ],
)
def test_unsafe_names_rejected(name: str) -> None:
    with pytest.raises(ValidationError, match="name"):
        _week(shooters=[_shooter(name=name)])
    with pytest.raises(ValidationError, match="name"):
        CorrectionInput.model_validate({"date": DAY, "rows": [{"name": name, "score": 3}]})


@pytest.mark.parametrize(
    "name",
    ["O'Testshooter, Zo\u00eb-Ann", "O\u2019Testshooter, Jos\u00e9", "Van Testshooter, J. R."],
)
def test_real_looking_names_accepted(name: str) -> None:
    week = _week(shooters=[_shooter(name=name)])
    assert week.shooters[0].name == name


def test_name_parts_are_stripped() -> None:
    assert _week(shooters=[_shooter(name="  Testshooter ,  Beta ")]).shooters[0].name == (
        "Testshooter, Beta"
    )


def test_formula_name_never_reaches_a_cell() -> None:
    with pytest.raises(ValidationError):
        _week(shooters=[_shooter(name='=HYPERLINK("http://x"), y')])


def _stations(n: int) -> dict[str, object]:
    counts = [50 // n + (1 if i < 50 % n else 0) for i in range(n)]
    return {"stations": [str(i + 1) for i in range(n)], "counts": counts}


def test_station_count_bounds() -> None:
    plain = [_shooter()]
    assert len(_week(shooters=plain, **_stations(12)).stations) == 12
    with pytest.raises(ValidationError, match="at most 12"):
        _week(shooters=plain, **_stations(13))
    with pytest.raises(ValidationError, match="at least 1"):
        _week(shooters=plain, stations=[], counts=[])


def test_shooter_count_bounds() -> None:
    def many(n: int) -> list[dict[str, object]]:
        return [
            _shooter(name=f"Testshooter, {chr(65 + i // 26)}{chr(97 + i % 26)}") for i in range(n)
        ]

    assert len(_week(shooters=many(200)).shooters) == 200
    with pytest.raises(ValidationError, match="at most 200"):
        _week(shooters=many(201))


def test_lettered_labels_in_stations_workbook() -> None:
    week = _week(stations=["6", "7", "7A", "8", "9"])
    data = build_stations(week)
    assert data is not None
    parsed = parse_upload(data)
    assert isinstance(parsed, StationsParse)
    assert [e.label for e in parsed.sheets[0].layout] == ["6", "7", "7A", "8", "9"]


_LETTERS = "abcdefghijklmnopqrstuvwxyz\u00e9\u00f6'-"
_PART = st.text(alphabet=_LETTERS, min_size=1, max_size=10).filter(
    lambda t: t[0] not in "'-" and t[-1] not in "'-" and "'-" not in t and "-'" not in t
)
_NAMES = st.builds(lambda a, b: f"{a.capitalize()}, {b.capitalize()}", _PART, _PART)


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
    for i in range(n):  # sometimes a lettered label such as "7A"
        if draw(st.booleans()):
            stations[i] += draw(st.sampled_from("AB"))
    names = draw(st.lists(_NAMES, min_size=1, max_size=10, unique_by=name_key))
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


@given(valid_weeks())
def test_each_violation_is_rejected_by_its_own_rule(data: dict[str, object]) -> None:
    shooters = list(data["shooters"])  # type: ignore[call-overload]
    total = int(str(data["expected_total"]))
    with pytest.raises(ValidationError, match="expected_total"):
        WeekInput.model_validate({**data, "expected_total": total + 1})
    first = shooters[0]
    dup = {**first, "name": str(first["name"]).upper()}
    with pytest.raises(ValidationError, match="duplicate shooter"):
        WeekInput.model_validate({**data, "expected_total": None, "shooters": [*shooters, dup]})
    counts = list(data["counts"])  # type: ignore[call-overload]
    with pytest.raises(ValidationError, match="must sum to 50"):
        WeekInput.model_validate({**data, "counts": [*counts[:-1], counts[-1] - 1]})
    with_hits = [s for s in shooters if "hits" in s]
    if with_hits:
        victim = with_hits[0]
        hits = list(victim["hits"])  # type: ignore[call-overload]
        # move one hit to another station's slot: sum changes only if we bump a slot below cap
        room = [i for i, (h, c) in enumerate(zip(hits, counts, strict=True)) if h < c]
        if room:
            bumped = hits.copy()
            bumped[room[0]] += 1  # in range, but no longer sums to the score
            broken = {**victim, "hits": bumped}
            others = [s for s in shooters if s is not victim]
            with pytest.raises(ValidationError, match="hits sum to"):
                WeekInput.model_validate(
                    {**data, "expected_total": None, "shooters": [broken, *others]}
                )
