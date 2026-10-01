"""Schema tests: the migrations match the ORM models and enforce the C4 constraints."""

import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import (
    URL,
    CheckConstraint,
    Column,
    DefaultClause,
    Engine,
    Table,
    create_engine,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sunday_clays.models import (
    Base,
    EventWeather,
    Import,
    ImportAttendanceRow,
    ImportScoreRow,
    ImportStationHit,
    ImportStationLayout,
    ImportStationSheet,
    Job,
)

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"

# `alembic check` compares neither CHECK constraints nor server defaults, so the migrated catalog
# is compared with Base.metadata directly; FK delete actions are pinned the same way as a second
# guard (alembic check also flags an ondelete change).
CATALOG_CHECKS = text(
    "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) FROM pg_constraint"
    " WHERE contype = 'c' AND connamespace = 'public'::regnamespace"
)
CATALOG_DEFAULTS = text(
    "SELECT table_name, column_name, column_default FROM information_schema.columns"
    " WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
)
CATALOG_FK_DELETE_ACTIONS = text(
    "SELECT conname, confdeltype FROM pg_constraint"
    " WHERE contype = 'f' AND connamespace = 'public'::regnamespace"
)
# 0002: rebuild_live's DELETE FROM rounds runs one FK check per round against station_hits
ROUND_ID_INDEX = text(
    "SELECT indexdef FROM pg_indexes"
    " WHERE schemaname = 'public' AND indexname = 'ix_station_hits_round_id'"
)
ROUND_ID_INDEX_DEF = (
    "CREATE INDEX ix_station_hits_round_id ON public.station_hits USING btree (round_id)"
)
MODEL_CHECK = re.compile(r"(\w+) IN \((.*)\)")
# CHECKs that are not "column IN (...)": name -> (model sqltext, pg_get_constraintdef text).
OTHER_CHECKS = {
    "ck_insights_field_negative_unnamed": (
        "polarity <> 'field_negative' OR cardinality(named_shooter_ids) = 0",
        "CHECK (((polarity <> 'field_negative'::text) OR (cardinality(named_shooter_ids) = 0)))",
    ),
}
CATALOG_CHECK = re.compile(r"CHECK \(\((\w+) = ANY \(ARRAY\[(.*)\]\)\)\)")
QUOTED = re.compile(r"'([^']*)'")
TEXT_CAST = re.compile(r"('[^']*')::text")
FK_DELETE_ACTIONS = {  # pg_constraint.confdeltype -> ForeignKeyConstraint.ondelete
    "a": None,
    "r": "RESTRICT",
    "c": "CASCADE",
    "n": "SET NULL",
    "d": "SET DEFAULT",
}
SERIAL = "<serial>"  # a nextval() default, i.e. the table's autoincrement column

# One value per event_weather measurement column; none of them is exact in float4, so a `real`
# column would read each back changed through avg(), a ::float8 cast or a binary-format cursor.
EVENT_WEATHER_MEASUREMENTS = {
    "temp_f": 55.1,
    "apparent_f": 52.3,
    "precip_in": 0.02,
    "wind_mph": 7.3,
    "gust_mph": 20.1,
    "wind_dir_deg": 212.7,
    "cloud_pct": 75.1,
    "humidity_pct": 81.3,
    "pressure_hpa": 1013.3,
}

C4_TABLES = {
    "imports",
    "import_score_rows",
    "import_attendance_rows",
    "import_station_sheets",
    "import_station_layout",
    "import_station_hits",
    "shooters",
    "shooter_aliases",
    "rules",
    "audit_log",
    "login_attempts",
    "events",
    "rounds",
    "shooter_profiles",
    "station_layouts",
    "station_hits",
    "data_issues",
    "weather_hourly",
    "event_weather",
    "forecast_cache",
    "round_metrics",
    "event_metrics",
    "rating_history",
    "achievements_awarded",
    "jobs",
    "app_state",
    "insights",  # 0003 (Plan 12)
    "insight_picks",  # 0003 (Plan 12)
    "fist_bumps",  # 0006 (Plan 14)
    "bump_attempts",  # 0006 (Plan 14)
}
TABLES_0003 = {"insights", "insight_picks"}
TABLES_0006 = {"fist_bumps", "bump_attempts"}


def _alembic(eng: Engine, action: str, target: str) -> None:
    cfg = Config(str(ALEMBIC_INI))
    with eng.begin() as conn:
        cfg.attributes["connection"] = conn
        getattr(command, action)(cfg, target)


def _tables(eng: Engine) -> set[str]:
    return set(inspect(eng).get_table_names())


def _round_id_index(eng: Engine) -> str | None:
    with eng.connect() as conn:
        return conn.scalar(ROUND_ID_INDEX)


def _in_list(pattern: re.Pattern[str], sql: str) -> tuple[str, tuple[str, ...]]:
    """(column, sorted values) of a ``column IN (...)`` CHECK; any other shape fails loudly."""
    match = pattern.fullmatch(sql)
    assert match is not None, f"unsupported CHECK shape, extend this test: {sql}"
    return match[1], tuple(sorted(QUOTED.findall(match[2])))


def _catalog_default(default: str | None) -> str | None:
    if default is None:
        return None
    return SERIAL if default.startswith("nextval(") else TEXT_CAST.sub(r"\1", default)


def _model_default(table: Table, column: Column[Any]) -> str | None:
    if column.server_default is None:
        return SERIAL if column is table.autoincrement_column else None
    assert isinstance(column.server_default, DefaultClause)
    arg = column.server_default.arg
    if isinstance(arg, str):
        return f"'{arg}'"
    return str(arg.compile(dialect=postgresql.dialect()))


@pytest.fixture
def scratch_engine(engine: Engine) -> Iterator[Engine]:
    """An empty database next to the test database, dropped afterwards."""
    name = f"{engine.url.database}_mig"
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}"')
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    scratch_url: URL = engine.url.set(database=name)
    scratch = create_engine(scratch_url)
    try:
        yield scratch
    finally:
        scratch.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.dispose()


def test_migration_matches_models(engine: Engine) -> None:
    cfg = Config(str(ALEMBIC_INI))
    with engine.connect() as conn:
        cfg.attributes["connection"] = conn
        command.check(cfg)  # raises AutogenerateDiffsDetected on any model/migration drift


def test_check_constraints_match_models(engine: Engine) -> None:
    with engine.connect() as conn:
        catalog = {
            name: (table, sql) if name in OTHER_CHECKS else (table, *_in_list(CATALOG_CHECK, sql))
            for table, name, sql in conn.execute(CATALOG_CHECKS)
        }
    models = {
        str(ck.name): (table.name, OTHER_CHECKS[str(ck.name)][1])
        if str(ck.name) in OTHER_CHECKS
        else (table.name, *_in_list(MODEL_CHECK, str(ck.sqltext)))
        for table in Base.metadata.tables.values()
        for ck in table.constraints
        if isinstance(ck, CheckConstraint)
    }
    assert catalog == models
    for table in Base.metadata.tables.values():
        for ck in table.constraints:
            if isinstance(ck, CheckConstraint) and str(ck.name) in OTHER_CHECKS:
                assert str(ck.sqltext) == OTHER_CHECKS[str(ck.name)][0]


def test_server_defaults_match_models(engine: Engine) -> None:
    with engine.connect() as conn:
        catalog = {
            (table, column): _catalog_default(default)
            for table, column, default in conn.execute(CATALOG_DEFAULTS)
        }
    models = {
        (table.name, column.name): _model_default(table, column)
        for table in Base.metadata.tables.values()
        for column in table.columns
    }
    assert catalog == models


def test_fk_delete_actions_match_models(engine: Engine) -> None:
    with engine.connect() as conn:
        catalog = {
            name: FK_DELETE_ACTIONS[code] for name, code in conn.execute(CATALOG_FK_DELETE_ACTIONS)
        }
    models = {
        str(fk.name): fk.ondelete.upper() if fk.ondelete else None
        for table in Base.metadata.tables.values()
        for fk in table.foreign_key_constraints
    }
    assert catalog == models


def test_station_hits_round_id_is_indexed(engine: Engine) -> None:
    assert _round_id_index(engine) == ROUND_ID_INDEX_DEF


def test_upgrade_downgrade_roundtrip(scratch_engine: Engine) -> None:
    _alembic(scratch_engine, "upgrade", "head")
    assert _tables(scratch_engine) == C4_TABLES | {"alembic_version"}
    assert _round_id_index(scratch_engine) == ROUND_ID_INDEX_DEF
    _alembic(scratch_engine, "downgrade", "0005")  # 0006 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0006) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0004")  # 0005 drops the station labels
    _alembic(scratch_engine, "downgrade", "0003")  # 0004 is a data-only no-op
    _alembic(scratch_engine, "downgrade", "0002")  # 0003 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003 - TABLES_0006) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0001")  # 0002 drops only its index
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003 - TABLES_0006) | {"alembic_version"}
    assert _round_id_index(scratch_engine) is None
    _alembic(scratch_engine, "downgrade", "base")
    assert _tables(scratch_engine) == {"alembic_version"}
    _alembic(scratch_engine, "upgrade", "head")
    assert _tables(scratch_engine) == C4_TABLES | {"alembic_version"}
    assert _round_id_index(scratch_engine) == ROUND_ID_INDEX_DEF


def test_0004_folds_unknown_round_type_into_sporting(scratch_engine: Engine) -> None:
    _alembic(scratch_engine, "upgrade", "0003")
    with scratch_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO events (event_date, round_type, round_type_source, n_rounds, "
                "n_shooters, has_scores, has_stations, results_complete) VALUES "
                "('2024-01-07', 'unknown', 'none', 0, 0, false, false, false), "
                "('2024-01-14', 'super_sporting', 'stations', 0, 0, false, true, false)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO rules (rule_type, payload) VALUES "
                "('round_type_override', "
                '\'{"event_date": "2024-01-07", "round_type": "unknown"}\'), '
                "('round_type_override', "
                '\'{"event_date": "2024-01-14", "round_type": "super_sporting"}\')'
            )
        )
    _alembic(scratch_engine, "upgrade", "head")
    with scratch_engine.connect() as conn:
        types = conn.execute(text("SELECT round_type FROM events ORDER BY event_date")).scalars()
        rules = conn.execute(text("SELECT payload ->> 'round_type' FROM rules ORDER BY id"))
        assert list(types) == ["sporting", "super_sporting"]
        assert list(rules.scalars()) == ["sporting", "super_sporting"]
    _alembic(scratch_engine, "downgrade", "0003")  # a no-op: the old value is not recoverable


STATION_TABLES_0005 = (
    "import_station_layout",
    "import_station_hits",
    "station_layouts",
    "station_hits",
)
PRIMARY_KEY_COLUMNS = text(
    "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid"
    " AND a.attnum = ANY (i.indkey) WHERE i.indrelid = CAST(:t AS regclass) AND i.indisprimary"
    " ORDER BY a.attname"
)
UNIQUE_DEF = text(
    "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
    " WHERE conrelid = 'station_hits'::regclass AND contype = 'u'"
)


def _seed_station_rows_0004(conn: Any) -> None:
    """Rows as the previous release wrote them: station_no only, no label column."""
    conn.execute(
        text(
            "INSERT INTO imports (kind, filename, sha256, file_bytes, status, summary) VALUES"
            " ('stations', 'a.xlsx', 'abc', 'x', 'committed', '{}')"
        )
    )
    conn.execute(
        text(
            "INSERT INTO import_station_sheets (import_id, sheet_name, event_date)"
            " SELECT id, '9 13 26', '2026-09-13' FROM imports"
        )
    )
    conn.execute(
        text(
            "INSERT INTO import_station_layout (sheet_id, station_no, target_count)"
            " SELECT id, n, 7 FROM import_station_sheets, generate_series(4, 6) AS n"
        )
    )
    conn.execute(
        text(
            "INSERT INTO import_station_hits (sheet_id, row_number, raw_name, name_key,"
            " station_no, hits) SELECT id, 10, 'A, B', 'a b', n, 5"
            " FROM import_station_sheets, generate_series(4, 6) AS n"
        )
    )
    conn.execute(
        text(
            "INSERT INTO station_layouts (event_date, station_no, target_count, source_import_id)"
            " SELECT '2026-09-13', n, 7, 1 FROM generate_series(4, 6) AS n"
        )
    )
    conn.execute(
        text(
            "INSERT INTO station_hits (event_date, station_no, sheet_id, entry_row, name_key, hits)"
            " SELECT '2026-09-13', n, 1, 10, 'a b', 5 FROM generate_series(4, 6) AS n"
        )
    )


def test_0005_backfills_station_labels_and_moves_the_keys_to_them(scratch_engine: Engine) -> None:
    _alembic(scratch_engine, "upgrade", "0004")
    with scratch_engine.begin() as conn:
        _seed_station_rows_0004(conn)
    _alembic(scratch_engine, "upgrade", "head")
    with scratch_engine.connect() as conn:
        for table in STATION_TABLES_0005:
            rows = conn.execute(
                text(f"SELECT station_no, station_label FROM {table} ORDER BY 1")  # noqa: S608
            ).all()
            assert rows, table
            assert all(label == str(no) for no, label in rows), table
        assert conn.execute(PRIMARY_KEY_COLUMNS, {"t": "station_layouts"}).scalars().all() == [
            "event_date",
            "station_label",
        ]
        assert "(event_date, entry_row, station_label)" in conn.scalar(UNIQUE_DEF)
        nullable = conn.execute(
            text(
                "SELECT table_name, is_nullable FROM information_schema.columns"
                " WHERE column_name = 'station_label' ORDER BY table_name"
            )
        ).all()
        assert sorted(nullable) == sorted((t, "NO") for t in STATION_TABLES_0005)


def test_0005_lets_7_and_7a_share_a_sort_number_and_the_old_release_still_inserts(
    scratch_engine: Engine,
) -> None:
    _alembic(scratch_engine, "upgrade", "head")
    with scratch_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO station_layouts (event_date, station_no, station_label, target_count,"
                " source_import_id) VALUES ('2026-05-10', 7, '7', 8, 1),"
                " ('2026-05-10', 7, '7A', 6, 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id,"
                " entry_row, name_key, hits) VALUES ('2026-05-10', 7, '7', 1, 10, 'a b', 5),"
                " ('2026-05-10', 7, '7A', 1, 10, 'a b', 4)"
            )
        )
        # the previous release knows only station_no: a trigger labels its rows
        conn.execute(
            text(
                "INSERT INTO station_layouts (event_date, station_no, target_count,"
                " source_import_id) VALUES ('2026-05-17', 9, 7, 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO station_hits (event_date, station_no, sheet_id, entry_row, name_key,"
                " hits) VALUES ('2026-05-17', 9, 1, 10, 'a b', 5)"
            )
        )
        assert conn.execute(
            text("SELECT station_label FROM station_layouts WHERE event_date = '2026-05-17'")
        ).scalars().all() == ["9"]
        assert conn.execute(
            text("SELECT station_label FROM station_hits WHERE event_date = '2026-05-17'")
        ).scalars().all() == ["9"]
    for statement in (
        "INSERT INTO station_layouts (event_date, station_no, station_label, target_count,"
        " source_import_id) VALUES ('2026-05-10', 7, '7A', 6, 1)",
        "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id, entry_row,"
        " name_key, hits) VALUES ('2026-05-10', 7, '7A', 1, 10, 'a b', 4)",
    ):
        with pytest.raises(IntegrityError), scratch_engine.begin() as conn:
            conn.execute(text(statement))


def test_0005_downgrade_drops_lettered_rows_and_restores_the_number_keys(
    scratch_engine: Engine,
) -> None:
    _alembic(scratch_engine, "upgrade", "head")
    with scratch_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO station_layouts (event_date, station_no, station_label, target_count,"
                " source_import_id) VALUES ('2026-05-10', 7, '7', 8, 1),"
                " ('2026-05-10', 7, '7A', 6, 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id,"
                " entry_row, name_key, hits) VALUES ('2026-05-10', 7, '7', 1, 10, 'a b', 5),"
                " ('2026-05-10', 7, '7A', 1, 10, 'a b', 4)"
            )
        )
    _alembic(scratch_engine, "downgrade", "0004")
    with scratch_engine.connect() as conn:
        assert conn.execute(text("SELECT station_no FROM station_layouts")).scalars().all() == [7]
        assert conn.execute(text("SELECT hits FROM station_hits")).scalars().all() == [5]
        assert conn.execute(PRIMARY_KEY_COLUMNS, {"t": "station_layouts"}).scalars().all() == [
            "event_date",
            "station_no",
        ]
        assert "(event_date, entry_row, station_no)" in conn.scalar(UNIQUE_DEF)
        columns = conn.execute(
            text("SELECT 1 FROM information_schema.columns WHERE column_name = 'station_label'")
        ).all()
        assert columns == []


def test_queued_dedupe_key_is_unique_but_running_and_finished_jobs_are_not(
    session: Session,
) -> None:
    jobs = [
        Job(kind="rebuild", dedupe_key="rebuild", status=status)
        for status in ("done", "failed", "running")
    ]
    session.add_all(jobs)
    session.flush()
    jobs.append(Job(kind="rebuild", dedupe_key="rebuild", status="queued"))
    session.add(jobs[-1])
    session.flush()  # C4: running and finished jobs never block a new queued request
    stored = session.scalars(
        select(Job.status).where(Job.id.in_([job.id for job in jobs])).order_by(Job.id)
    )
    assert list(stored) == ["done", "failed", "running", "queued"]
    savepoint = session.begin_nested()
    session.add(Job(kind="rebuild", dedupe_key="rebuild", status="queued"))
    with pytest.raises(IntegrityError, match="uq_jobs_dedupe_key_queued"):
        session.flush()
    savepoint.rollback()


def test_deleting_an_import_cascades_to_its_staged_rows(session: Session) -> None:
    sunday = date(2026, 9, 13)
    imp = Import(kind="scores", filename="s.xlsx", sha256="a" * 64, file_bytes=b"x")
    session.add(imp)
    session.flush()
    sheet = ImportStationSheet(import_id=imp.id, sheet_name="9-13-26", event_date=sunday)
    session.add_all(
        [
            ImportScoreRow(
                import_id=imp.id,
                row_number=2,
                raw_name="Hadley, Ike",
                name_key="hadley ike",
                score=34,
                event_date=sunday,
            ),
            ImportAttendanceRow(import_id=imp.id, row_number=2, event_date=sunday, head_count=27),
            sheet,
        ]
    )
    session.flush()
    session.add_all(
        [
            ImportStationLayout(sheet_id=sheet.id, station_no=1, target_count=6),
            ImportStationHit(
                sheet_id=sheet.id,
                row_number=4,
                raw_name="Hadley, Ike",
                name_key="hadley ike",
                station_no=1,
                hits=5,
            ),
        ]
    )
    session.flush()
    staged = [
        (ImportScoreRow, ImportScoreRow.import_id == imp.id),
        (ImportAttendanceRow, ImportAttendanceRow.import_id == imp.id),
        (ImportStationSheet, ImportStationSheet.import_id == imp.id),
        (ImportStationLayout, ImportStationLayout.sheet_id == sheet.id),
        (ImportStationHit, ImportStationHit.sheet_id == sheet.id),
    ]

    def row_counts() -> list[int | None]:
        return [session.scalar(select(func.count()).select_from(m).where(w)) for m, w in staged]

    assert row_counts() == [1, 1, 1, 1, 1]
    session.delete(imp)
    session.flush()  # one DELETE; ON DELETE CASCADE removes both levels of staged rows
    assert row_counts() == [0, 0, 0, 0, 0]


def test_import_kind_check_rejects_unknown_kind(session: Session) -> None:
    savepoint = session.begin_nested()
    session.add(Import(kind="roster", filename="r.xlsx", sha256="b" * 64, file_bytes=b"x"))
    with pytest.raises(IntegrityError, match="ck_imports_kind"):
        session.flush()
    savepoint.rollback()


def test_event_weather_measurements_read_back_exactly(session: Session) -> None:
    """C7's shared rain threshold (precip >= 0.02 in) must hold for a stored 0.02 (Decision 5)."""
    session.add(
        EventWeather(
            event_date=date(2026, 9, 13),
            condition="rain",
            source="archive",
            **EVENT_WEATHER_MEASUREMENTS,
        )
    )
    session.flush()
    rainy = select(func.count()).select_from(EventWeather).where(EventWeather.precip_in >= 0.02)
    assert session.scalar(rainy) == 1
    for name, value in EVENT_WEATHER_MEASUREMENTS.items():
        assert session.scalar(select(func.avg(getattr(EventWeather, name)))) == value, name
