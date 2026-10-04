import time
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from sunday_clays.db import SOURCE_ALEMBIC_INI, alembic_config, connect_with_retry, make_engine


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db:5432/x",
        "postgres://u:p@db:5432/x",
        "postgresql+psycopg://u:p@db:5432/x",
    ],
)
def test_make_engine_always_uses_psycopg3(url: str) -> None:
    engine = make_engine(url)

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.host == "db"
    assert engine.url.database == "x"


def test_make_engine_connects_with_a_timeout_and_in_utc(closed_port: int) -> None:
    engine = make_engine(f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x")
    connect_params: list[dict[str, Any]] = []

    @event.listens_for(engine, "do_connect")
    def record(dialect: Any, conn_rec: Any, cargs: Any, cparams: dict[str, Any]) -> None:
        connect_params.append(dict(cparams))

    with pytest.raises(OperationalError):
        engine.connect()

    assert len(connect_params) == 1
    assert connect_params[0]["connect_timeout"] == 5
    assert connect_params[0]["options"] == "-c timezone=UTC"


def test_alembic_config_prefers_ini_in_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = elsewhere\n")
    monkeypatch.chdir(tmp_path)

    config = alembic_config()

    assert config.get_main_option("script_location") == "elsewhere"


def test_alembic_config_falls_back_to_source_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    config = alembic_config()

    assert config.config_file_name == str(SOURCE_ALEMBIC_INI)
    script_location = config.get_main_option("script_location")
    assert script_location is not None
    assert Path(script_location) == SOURCE_ALEMBIC_INI.parent / "migrations"


def test_connect_with_retry_gives_up_after_timeout(closed_port: int) -> None:
    engine = make_engine(f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x")
    started = time.monotonic()

    with pytest.raises(OperationalError):
        connect_with_retry(engine, timeout_s=0.3, interval_s=0.1)

    elapsed = time.monotonic() - started
    assert 0.2 <= elapsed < 5.0


def test_make_engine_hides_bound_parameters_from_errors() -> None:
    # Plan 20 D22.1: a failing statement's message never carries its values (an email, say)
    assert make_engine("postgresql://u:p@db:5432/x").hide_parameters is True
